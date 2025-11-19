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
from .points_loader import PointsLoader
from .constants import (
    DEFAULT_SPEED,
    UNLIMITED_LOOPS,
    DEFAULT_FPS
)

logger = get_logger(__name__)

# GLOBALE LOCK: Shared mit VideoPlayer - importiere Modul für echte Shared State
from . import player_lock


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
        self.script_gen = ScriptGenerator(self.config['paths']['scripts_dir'])
        
        # Erweiterte Steuerung
        self.brightness = 1.0
        self.speed_factor = DEFAULT_SPEED
        self.max_loops = UNLIMITED_LOOPS
        self.current_loop = 0
        self.current_frame = 0
        self.total_frames = 0  # Unendlich für Scripts
        self.start_time = 0
        self.frames_processed = 0
        
        # Lade Points-Konfiguration mit PointsLoader (ohne Bounds-Validierung für Scripts)
        points_data = PointsLoader.load_points(points_json_path, validate_bounds=False)
        
        self.point_coords = points_data['point_coords']
        self.canvas_width = points_data['canvas_width']
        self.canvas_height = points_data['canvas_height']
        self.universe_mapping = points_data['universe_mapping']
        self.total_points = points_data['total_points']
        self.total_channels = points_data['total_channels']
        self.required_universes = points_data['required_universes']
        self.channels_per_universe = points_data['channels_per_universe']
        
        logger.debug(f"Script Player initialisiert:")
        logger.debug(f"  Script: {script_name}")
        logger.debug(f"  Canvas-Größe: {self.canvas_width}x{self.canvas_height}")
        logger.debug(f"  Anzahl Punkte: {self.total_points}")
        logger.debug(f"  Benötigte Kanäle: {self.total_channels}")
        logger.debug(f"  Benötigte Universen: {self.required_universes}")
        logger.debug(f"  Art-Net Ziel-IP: {target_ip}")
        
        # Lade Script
        if not self.script_gen.load_script(script_name):
            raise ValueError(f"Script konnte nicht geladen werden: {script_name}")
        
        # Art-Net Manager
        self.artnet_manager = ArtNetManager(target_ip, start_universe, self.total_points, self.channels_per_universe)
        artnet_config = self.config.get('artnet', {})
        self.artnet_manager.start(artnet_config)
    
    def start(self):
        """Startet die Script-Wiedergabe."""
        if self.is_playing:
            logger.debug("Script läuft bereits!")
            return
        
        # KRITISCH: Registriere als aktiver Player
        # Prüfe ob alter Player existiert (mit Lock)
        old_player = None
        with player_lock._global_player_lock:
            if player_lock._active_player and player_lock._active_player is not self:
                old_player = player_lock._active_player
                player_lock._active_player = None  # Deregistriere sofort
        
        # Stoppe alten Player OHNE Lock (könnte lange dauern)
        if old_player:
            player_type = type(old_player).__name__
            player_name = getattr(old_player, 'script_name', getattr(old_player, 'video_path', 'Unknown'))
            logger.info(f"Stoppe alten Player: {player_type} - {player_name}")
            old_player.stop()
            time.sleep(0.5)  # Längere Wartezeit
            del old_player  # Explizit löschen
            logger.info(f"Alter Player gestoppt und gelöscht")
        
        # Registriere neuen Player (mit Lock)
        with player_lock._global_player_lock:
            player_lock._active_player = self
            logger.info(f"Neuer aktiver Player: {self.script_name}")
        
        # Deaktiviere Testmuster, damit Script sendet
        if self.artnet_manager:
            self.artnet_manager.resume_video_mode()
        
        self.is_playing = True
        self.is_running = True  # WICHTIG: Auch is_running setzen!
        self.script_gen.reset()
        self.thread = threading.Thread(target=self._play_loop, daemon=True)
        self.thread.start()
        logger.info(f"Script-Thread gestartet: {self.script_name}")
    
    def stop(self):
        """Stoppt die Wiedergabe."""
        if not self.is_playing:
            logger.debug("Script läuft nicht!")
            return
        
        logger.debug("Stoppe Script...")
        
        # WICHTIG: Reihenfolge ist kritisch!
        # 1. Setze Flags SOFORT - stoppt Loop bei nächster Iteration
        self.is_running = False
        self.is_playing = False
        self.is_paused = False
        
        # 2. Deaktiviere ArtNet SOFORT - verhindert weitere send_frame() Aufrufe
        if self.artnet_manager:
            self.artnet_manager.is_active = False
        
        # 3. Warte auf Thread-Ende
        if self.thread:
            self.thread.join(timeout=3.0)
            if self.thread.is_alive():
                logger.warning("Script-Thread konnte nicht gestoppt werden!")
        
        # 4. Cleanup: Stoppe und entferne ArtNet-Manager komplett
        if self.artnet_manager:
            self.artnet_manager.stop()
            self.artnet_manager = None
        
        self.thread = None
        
        # 5. Entferne aus globaler Registrierung
        with player_lock._global_player_lock:
            if player_lock._active_player is self:
                player_lock._active_player = None
    
    def pause(self):
        """Pausiert die Wiedergabe."""
        if not self.is_playing or self.is_paused:
            logger.debug("Script läuft nicht oder ist bereits pausiert!")
            return
        
        self.is_paused = True
        logger.debug("Script pausiert")
    
    def resume(self):
        """Setzt Wiedergabe fort."""
        if not self.is_playing or not self.is_paused:
            logger.debug("Script läuft nicht oder ist nicht pausiert!")
            return
        
        self.is_paused = False
        logger.debug("Script fortgesetzt")
        
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
        logger.debug("Script neu gestartet")
    
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
                logger.debug("Fehler beim Generieren des Frames")
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
            
            # Sende über Art-Net (prüfe ob Manager noch existiert UND wir der aktive Player sind)
            if self.artnet_manager and self.is_running and player_lock._active_player is self:
                self.artnet_manager.send_frame(dmx_buffer)
            
            # Beende Loop wenn gestoppt ODER nicht mehr aktiver Player
            if not self.is_running or player_lock._active_player is not self:
                break
            
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
        
        logger.debug("Script-Wiedergabe beendet")
    
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
        # Pausiere Script, damit Blackout nicht überschrieben wird
        if self.is_playing and not self.is_paused:
            self.pause()
        
        if self.artnet_manager:
            self.artnet_manager.blackout()
    
    def test_pattern(self, color='red'):
        """Testmuster."""
        # Pausiere Script, damit Testmuster nicht überschrieben wird
        if self.is_playing and not self.is_paused:
            self.pause()
        
        if self.artnet_manager:
            self.artnet_manager.test_pattern(color)
    
    def set_brightness(self, value):
        """Setzt Helligkeit."""
        try:
            val = float(value)
            if val < 0 or val > 100:
                logger.debug("Helligkeit muss zwischen 0 und 100 liegen!")
                return
            self.brightness = val / 100.0
            logger.debug(f"Helligkeit auf {val}% gesetzt")
        except ValueError:
            logger.debug("Ungültiger Helligkeits-Wert!")
    
    def set_speed(self, value):
        """Setzt Geschwindigkeit."""
        try:
            val = float(value)
            if val <= 0:
                logger.debug("Geschwindigkeit muss größer als 0 sein!")
                return
            self.speed_factor = val
            logger.debug(f"Geschwindigkeit auf {val}x gesetzt")
        except ValueError:
            logger.debug("Ungültiger Geschwindigkeits-Wert!")
    
    def reload_artnet(self):
        """Lädt Art-Net neu."""
        try:
            if not hasattr(self, 'total_points') or not hasattr(self, 'channels_per_universe'):
                logger.debug("⚠️ Art-Net kann nicht neu geladen werden - Player nicht vollständig initialisiert")
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
            
            logger.debug(f"✅ Art-Net neu geladen mit IP: {self.target_ip}")
            return True
        except Exception as e:
            logger.debug(f"❌ Fehler beim Neuladen von Art-Net: {e}")
            import traceback
            traceback.print_exc()
            return False
