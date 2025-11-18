"""
Script Player - Führt Python-Scripts als prozedurale Video-Quellen aus
Kompatibel mit VideoPlayer Schnittstelle
"""
import time
import threading
import numpy as np
from .logger import get_logger
from .script_generator import ScriptGenerator
from .artnet_manager import ArtNetManager
from .constants import (
    DMX_CHANNELS_PER_UNIVERSE,
    DMX_CHANNELS_PER_POINT,
    DEFAULT_SPEED,
    UNLIMITED_LOOPS,
    DEFAULT_FPS
)

logger = get_logger(__name__)


class ScriptPlayer:
    """Player für prozedural generierte Grafiken via Python-Scripts."""
    
    def __init__(self, script_name, points_json_path, target_ip='127.0.0.1', start_universe=0, fps_limit=None, config=None):
        self.script_name = script_name
        self.points_json_path = points_json_path
        self.target_ip = target_ip
        self.start_universe = start_universe
        self.fps_limit = fps_limit or DEFAULT_FPS
        self.config = config or {}
        
        self.is_running = False
        self.is_playing = False
        self.is_paused = False
        self.thread = None
        self.artnet_manager = None
        
        # Script Generator
        self.script_gen = ScriptGenerator(self.config.get('paths', {}).get('scripts_dir', 'scripts'))
        
        # Erweiterte Steuerung
        self.brightness = 1.0
        self.speed_factor = DEFAULT_SPEED
        self.max_loops = UNLIMITED_LOOPS
        self.current_loop = 0
        self.current_frame = 0
        self.total_frames = 0  # Unendlich für Scripts
        self.start_time = 0
        self.frames_processed = 0
        
        # Lade Points-Konfiguration
        import json
        with open(points_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        canvas = data.get('canvas', {})
        self.canvas_width = canvas.get('width', 1920)
        self.canvas_height = canvas.get('height', 1080)
        
        objects = data.get('objects', [])
        
        # Sammle Punkte (gleiche Logik wie VideoPlayer)
        point_list = []
        self.universe_mapping = {}
        current_channel = 0
        universe_offset = 0
        channels_per_universe = DMX_CHANNELS_PER_UNIVERSE
        channels_per_point = DMX_CHANNELS_PER_POINT
        max_channels_8_universes = channels_per_universe * 8
        
        for obj_idx, obj in enumerate(objects):
            obj_id = obj.get('id', f'object-{obj_idx}')
            points = obj.get('points', [])
            obj_channels = len(points) * channels_per_point
            
            if current_channel + obj_channels > max_channels_8_universes:
                universe_offset += channels_per_universe
                current_channel = 0
            
            for point in points:
                x, y = point['x'], point['y']
                point_list.append([x, y])
                
                point_idx = len(point_list) - 1
                self.universe_mapping[point_idx] = universe_offset
            
            current_channel += obj_channels
        
        self.point_coords = np.array(point_list, dtype=np.int32) if point_list else np.array([])
        total_points = len(point_list)
        total_channels = total_points * channels_per_point + universe_offset
        self.required_universes = (total_channels + channels_per_universe - 1) // channels_per_universe
        self.channels_per_universe = channels_per_universe
        self.total_points = total_points
        self.total_channels = total_channels
        
        print(f"Script Player initialisiert:")
        print(f"  Script: {script_name}")
        print(f"  Canvas-Größe: {self.canvas_width}x{self.canvas_height}")
        print(f"  Anzahl Punkte: {total_points}")
        print(f"  Benötigte Kanäle: {total_channels}")
        print(f"  Benötigte Universen: {self.required_universes}")
        print(f"  Art-Net Ziel-IP: {target_ip}")
        
        # Lade Script
        if not self.script_gen.load_script(script_name):
            raise ValueError(f"Script konnte nicht geladen werden: {script_name}")
        
        # Art-Net Manager
        self.artnet_manager = ArtNetManager(target_ip, start_universe, total_points, channels_per_universe)
        artnet_config = self.config.get('artnet', {})
        self.artnet_manager.start(artnet_config)
    
    def start(self):
        """Startet die Script-Wiedergabe."""
        if self.is_playing:
            print("Script läuft bereits!")
            return
        
        self.is_playing = True
        self.script_gen.reset()
        self.thread = threading.Thread(target=self._play_loop, daemon=True)
        self.thread.start()
        print("Script gestartet (Endlosschleife)")
    
    def stop(self):
        """Stoppt die Wiedergabe."""
        if not self.is_playing:
            print("Script läuft nicht!")
            return
        
        print("Stoppe Script...")
        self.is_running = False
        self.is_playing = False
        self.is_paused = False
        
        if self.thread:
            self.thread.join(timeout=2.0)
    
    def pause(self):
        """Pausiert die Wiedergabe."""
        if not self.is_playing or self.is_paused:
            print("Script läuft nicht oder ist bereits pausiert!")
            return
        
        self.is_paused = True
        print("Script pausiert")
    
    def resume(self):
        """Setzt Wiedergabe fort."""
        if not self.is_playing or not self.is_paused:
            print("Script läuft nicht oder ist nicht pausiert!")
            return
        
        self.is_paused = False
        print("Script fortgesetzt")
        
        if self.artnet_manager:
            self.artnet_manager.resume_video_mode()
    
    def restart(self):
        """Startet Script neu."""
        if self.is_playing:
            was_paused = self.is_paused
            self.stop()
            time.sleep(0.3)
            self.start()
            if was_paused:
                self.pause()
        print("Script neu gestartet")
    
    def _play_loop(self):
        """Haupt-Loop für Script-Generierung."""
        self.is_running = True
        self.start_time = time.time()
        self.frames_processed = 0
        self.current_frame = 0
        
        frame_time = 1.0 / self.fps_limit
        next_frame_time = time.time()
        
        while self.is_running and self.is_playing:
            loop_start = time.time()
            
            # Warte wenn pausiert
            if self.is_paused:
                time.sleep(0.1)
                next_frame_time = time.time()  # Reset timing nach Pause
                continue
            
            # Berechne aktuelle Zeit seit Start (für Script)
            current_time = time.time() - self.start_time
            
            # Generiere Frame mit korrekter Zeit
            frame = self.script_gen.generate_frame(
                width=self.canvas_width,
                height=self.canvas_height,
                fps=self.fps_limit,
                frame_number=self.current_frame,
                time=current_time
            )
            
            if frame is None:
                print("Fehler beim Generieren des Frames")
                time.sleep(frame_time)
                continue
            
            # NumPy-optimierte Pixel-Extraktion
            # Erstelle boolean Maske für gültige Koordinaten
            valid_mask = (
                (self.point_coords[:, 1] >= 0) & 
                (self.point_coords[:, 1] < self.canvas_height) &
                (self.point_coords[:, 0] >= 0) & 
                (self.point_coords[:, 0] < self.canvas_width)
            )
            
            # Extrahiere alle RGB-Werte auf einmal
            y_coords = self.point_coords[valid_mask, 1]
            x_coords = self.point_coords[valid_mask, 0]
            
            # Hole RGB-Werte für alle gültigen Punkte
            rgb_values = frame[y_coords, x_coords].astype(np.float32)
            
            # Wende Helligkeit an (NumPy-Operation)
            rgb_values *= self.brightness
            rgb_values = np.clip(rgb_values, 0, 255).astype(np.uint8)
            
            # Erstelle DMX-Buffer
            dmx_buffer = np.zeros((len(self.point_coords), 3), dtype=np.uint8)
            dmx_buffer[valid_mask] = rgb_values
            dmx_buffer = dmx_buffer.flatten().tolist()
            
            # Sende über Art-Net
            if self.artnet_manager:
                self.artnet_manager.send_frame(dmx_buffer)
            
            self.current_frame += 1
            self.frames_processed += 1
            
            # Präzises Frame-Timing mit Drift-Kompensation
            next_frame_time += (frame_time / self.speed_factor)
            current_time_now = time.time()
            sleep_time = next_frame_time - current_time_now
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            elif sleep_time < -0.1:  # Zu langsam, Reset
                next_frame_time = current_time_now + frame_time
        
        print("Script-Wiedergabe beendet")
    
    def status(self):
        """Gibt Status-String zurück."""
        if self.is_playing:
            if self.is_paused:
                return "pausiert"
            return "läuft"
        return "gestoppt"
    
    def get_info(self):
        """Gibt Informationen zurück."""
        script_info = self.script_gen.get_info()
        return {
            **script_info,
            'canvas_width': self.canvas_width,
            'canvas_height': self.canvas_height,
            'total_points': self.total_points,
            'total_universes': self.required_universes,
            'brightness': int(self.brightness * 100),
            'speed': self.speed_factor,
            'fps_limit': self.fps_limit
        }
    
    def get_stats(self):
        """Gibt Live-Statistiken zurück."""
        runtime = time.time() - self.start_time if self.start_time > 0 else 0
        fps = self.frames_processed / runtime if runtime > 0 else 0
        
        return {
            'fps': round(fps, 1),
            'frames': self.frames_processed,
            'runtime': f"{int(runtime // 60):02d}:{int(runtime % 60):02d}"
        }
    
    # Delegiere andere Methoden
    def blackout(self):
        """Blackout."""
        if self.artnet_manager:
            self.artnet_manager.blackout()
    
    def test_pattern(self, color='red'):
        """Testmuster."""
        if self.artnet_manager:
            self.artnet_manager.test_pattern(color)
    
    def set_brightness(self, value):
        """Setzt Helligkeit."""
        try:
            val = float(value)
            if val < 0 or val > 100:
                print("Helligkeit muss zwischen 0 und 100 liegen!")
                return
            self.brightness = val / 100.0
            print(f"Helligkeit auf {val}% gesetzt")
        except ValueError:
            print("Ungültiger Helligkeits-Wert!")
    
    def set_speed(self, value):
        """Setzt Geschwindigkeit."""
        try:
            val = float(value)
            if val <= 0:
                print("Geschwindigkeit muss größer als 0 sein!")
                return
            self.speed_factor = val
            print(f"Geschwindigkeit auf {val}x gesetzt")
        except ValueError:
            print("Ungültiger Geschwindigkeits-Wert!")
    
    def reload_artnet(self):
        """Lädt Art-Net neu."""
        try:
            if not hasattr(self, 'total_points') or not hasattr(self, 'channels_per_universe'):
                print("⚠️ Art-Net kann nicht neu geladen werden - Player nicht vollständig initialisiert")
                return False
            
            if self.artnet_manager:
                self.artnet_manager.stop()
            
            self.artnet_manager = ArtNetManager(
                self.target_ip, 
                self.start_universe, 
                self.total_points, 
                self.channels_per_universe
            )
            
            artnet_config = self.config.get('artnet', {})
            self.artnet_manager.start(artnet_config)
            
            print(f"✅ Art-Net neu geladen mit IP: {self.target_ip}")
            return True
        except Exception as e:
            print(f"❌ Fehler beim Neuladen von Art-Net: {e}")
            import traceback
            traceback.print_exc()
            return False
