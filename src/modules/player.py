"""
Unified Player - Universeller Media-Player mit austauschbaren Frame-Quellen
Unterstützt Videos, Scripts und zukünftige Quellen über FrameSource-Interface
"""
import time
import threading
import numpy as np
import cv2
import os
from .logger import get_logger
from .artnet_manager import ArtNetManager
from .points_loader import PointsLoader
from .frame_source import VideoSource, ScriptSource
from .constants import (
    DEFAULT_SPEED,
    UNLIMITED_LOOPS,
    DEFAULT_FPS
)

logger = get_logger(__name__)

# GLOBALE LOCK: Shared Lock für Player-Synchronisation
from . import player_lock


class Player:
    """
    Universeller Media-Player mit austauschbaren Frame-Quellen.
    Unterstützt Videos, Scripts und zukünftige Medien-Typen.
    """
    
    def __init__(self, frame_source, points_json_path, target_ip='127.0.0.1', start_universe=0, fps_limit=None, config=None):
        """
        Initialisiert Player mit Frame-Quelle.
        
        Args:
            frame_source: FrameSource-Instanz (VideoSource, ScriptSource, etc.)
            points_json_path: Pfad zur Points-JSON-Datei
            target_ip: Art-Net Ziel-IP
            start_universe: Start-Universum für Art-Net
            fps_limit: FPS-Limit (None = Source-FPS)
            config: Konfigurations-Dict
        """
        self.source = frame_source
        self.points_json_path = points_json_path
        self.target_ip = target_ip
        self.start_universe = start_universe
        self.fps_limit = fps_limit
        self.config = config or {}
        
        # Playback State
        self.is_running = False
        self.is_playing = False
        self.is_paused = False
        self.thread = None
        self.artnet_manager = None
        
        # Erweiterte Steuerung
        self.brightness = 1.0  # 0.0 - 1.0
        self.speed_factor = DEFAULT_SPEED
        self.hue_shift = 0  # 0-360 Grad Hue Rotation
        self.max_loops = UNLIMITED_LOOPS  # 0 = unendlich
        self.current_loop = 0
        self.start_time = 0
        self.frames_processed = 0
        
        # Recording
        self.is_recording = False
        self.recorded_data = []
        self.recording_name = None
        
        # Preview Frames
        self.last_frame = None  # Letztes Frame (LED-Punkte RGB) für Preview
        self.last_video_frame = None  # Letztes komplettes Frame für Preview
        
        # Lade Points-Konfiguration
        # validate_bounds nur für Videos, nicht für Scripts
        validate_bounds = isinstance(frame_source, VideoSource)
        points_data = PointsLoader.load_points(points_json_path, validate_bounds=validate_bounds)
        
        self.point_coords = points_data['point_coords']
        self.canvas_width = points_data['canvas_width']
        self.canvas_height = points_data['canvas_height']
        self.universe_mapping = points_data['universe_mapping']
        self.total_points = points_data['total_points']
        self.total_channels = points_data['total_channels']
        self.required_universes = points_data['required_universes']
        self.channels_per_universe = points_data['channels_per_universe']
        
        # Initialisiere Frame-Source
        if not self.source.initialize():
            raise ValueError(f"Frame-Source konnte nicht initialisiert werden: {self.source.get_source_name()}")
        
        logger.debug(f"Player initialisiert:")
        logger.debug(f"  Source: {self.source.get_source_name()} ({type(self.source).__name__})")
        logger.debug(f"  Canvas: {self.canvas_width}x{self.canvas_height}")
        logger.debug(f"  Punkte: {self.total_points}, Kanäle: {self.total_channels}")
        logger.debug(f"  Universen: {self.required_universes}")
        logger.debug(f"  Art-Net: {target_ip}, Start-Universe: {start_universe}")
        
        # Art-Net Manager wird extern gesetzt
        self.artnet_manager = None
    
    # Properties that delegate to source for backward compatibility
    @property
    def current_frame(self):
        """Aktueller Frame der Quelle."""
        return self.source.current_frame if self.source else 0
    
    @property
    def total_frames(self):
        """Gesamtzahl Frames der Quelle."""
        return self.source.total_frames if self.source else 0
    
    @property
    def video_path(self):
        """Video-Pfad (falls VideoSource)."""
        return getattr(self.source, 'video_path', None)
    
    @property
    def script_name(self):
        """Script-Name (falls ScriptSource)."""
        return getattr(self.source, 'script_name', None)
    
    def switch_source(self, new_source):
        """
        Wechselt zu einer neuen Frame-Quelle ohne Player zu zerstören.
        
        Args:
            new_source: Neue FrameSource-Instanz
        
        Returns:
            bool: True bei Erfolg
        """
        was_playing = self.is_playing
        was_paused = self.is_paused
        
        # Stoppe aktuelle Wiedergabe
        if was_playing:
            self.stop()
            time.sleep(0.3)
        
        # Cleanup alte Source
        if self.source:
            self.source.cleanup()
        
        # Setze neue Source
        self.source = new_source
        
        # Initialisiere neue Source
        if not self.source.initialize():
            logger.error(f"Neue Source konnte nicht initialisiert werden: {self.source.get_source_name()}")
            return False
        
        logger.info(f"Source gewechselt: {self.source.get_source_name()} ({type(self.source).__name__})")
        
        # Starte Wiedergabe wieder falls vorher aktiv
        if was_playing:
            self.start()
            if was_paused:
                self.pause()
        
        return True
    
    def start(self):
        """Startet die Wiedergabe."""
        if self.is_playing:
            logger.debug("Wiedergabe läuft bereits!")
            return
        
        # Registriere als aktiver Player (unified Player ersetzt player_lock Mechanismus)
        with player_lock._global_player_lock:
            player_lock._active_player = self
            logger.info(f"Aktiver Player: {self.source.get_source_name()}")
        
        # Re-initialisiere Source falls nötig (nach stop)
        if not self.source.initialize():
            logger.error(f"Fehler beim Re-Initialisieren der Source: {self.source.get_source_name()}")
            return
        
        # Deaktiviere Testmuster
        if self.artnet_manager:
            self.artnet_manager.resume_video_mode()
        
        self.is_playing = True
        self.is_running = True
        self.source.reset()
        self.thread = threading.Thread(target=self._play_loop, daemon=True)
        self.thread.start()
        logger.info(f"Wiedergabe gestartet: {self.source.get_source_name()}")
    
    def stop(self):
        """Stoppt die Wiedergabe."""
        if not self.is_playing:
            logger.debug("Wiedergabe läuft nicht!")
            return
        
        logger.debug("Stoppe Wiedergabe...")
        
        # Flags SOFORT setzen
        self.is_running = False
        self.is_playing = False
        self.is_paused = False
        
        # ArtNet deaktivieren
        if self.artnet_manager:
            self.artnet_manager.is_active = False
        
        # Warte auf Thread-Ende
        if self.thread:
            self.thread.join(timeout=3.0)
            if self.thread.is_alive():
                logger.warning("Thread konnte nicht gestoppt werden!")
        
        self.thread = None
        
        # HINWEIS: Source und ArtNet Manager NICHT cleanup/zerstören
        # Sie werden beim nächsten start() wiederverwendet
        # Nur bei switch_source() oder Shutdown cleanup nötig
        
        # Deregistriere Player
        with player_lock._global_player_lock:
            if player_lock._active_player is self:
                player_lock._active_player = None
        
        logger.info("Wiedergabe gestoppt")
    
    def pause(self):
        """Pausiert die Wiedergabe."""
        if not self.is_playing or self.is_paused:
            logger.debug("Wiedergabe läuft nicht oder ist bereits pausiert!")
            return
        
        self.is_paused = True
        logger.debug("Wiedergabe pausiert")
    
    def resume(self):
        """Setzt Wiedergabe fort."""
        if not self.is_playing or not self.is_paused:
            logger.debug("Wiedergabe läuft nicht oder ist nicht pausiert!")
            return
        
        self.is_paused = False
        logger.debug("Wiedergabe fortgesetzt")
        
        if self.artnet_manager:
            self.artnet_manager.resume_video_mode()
    
    def restart(self):
        """Startet Wiedergabe neu."""
        was_paused = self.is_paused
        was_playing = self.is_playing
        
        if was_playing:
            self.stop()
            time.sleep(0.3)
        
        # Reset Source
        self.source.reset()
        
        # Starte neu
        self.start()
        
        if was_paused:
            self.pause()
        
        logger.debug("Wiedergabe neu gestartet")
    
    def _play_loop(self):
        """Haupt-Wiedergabeschleife (läuft in separatem Thread)."""
        self.is_running = True
        self.is_paused = False
        self.start_time = time.time()
        self.frames_processed = 0
        self.current_loop = 0
        
        # Deaktiviere Testmuster
        if self.artnet_manager:
            self.artnet_manager.resume_video_mode()
        
        # FPS für Timing
        fps = self.fps_limit if self.fps_limit else self.source.fps
        frame_time = 1.0 / fps if fps > 0 else 0
        next_frame_time = time.time()
        
        frame_wait_delay = self.config.get('video', {}).get('frame_wait_delay', 0.1)
        
        logger.debug(f"Play-Loop gestartet: FPS={fps}, Source={self.source.get_source_name()}")
        
        while self.is_running and self.is_playing:
            # Pause-Handling
            if self.is_paused:
                time.sleep(frame_wait_delay)
                next_frame_time = time.time()  # Reset timing
                continue
            
            loop_start = time.time()
            
            # Hole nächstes Frame von Source
            frame, source_delay = self.source.get_next_frame()
            
            if frame is None:
                # Ende der Source (Video-Loop oder Fehler)
                self.current_loop += 1
                
                # Loop-Limit prüfen (nur für nicht-infinite Sources)
                if not self.source.is_infinite and self.max_loops > 0 and self.current_loop >= self.max_loops:
                    logger.debug(f"Loop-Limit ({self.max_loops}) erreicht, stoppe...")
                    break
                
                # Reset Source für nächsten Loop
                self.source.reset()
                continue
            
            # Helligkeit und Hue Shift auf komplettes Frame anwenden für Preview
            frame_with_brightness = frame.astype(np.float32)
            frame_with_brightness *= self.brightness
            frame_with_brightness = np.clip(frame_with_brightness, 0, 255).astype(np.uint8)
            
            # Hue Shift anwenden wenn aktiviert
            if self.hue_shift != 0:
                frame_hsv = cv2.cvtColor(frame_with_brightness, cv2.COLOR_RGB2HSV)
                frame_hsv[:, :, 0] = (frame_hsv[:, :, 0].astype(np.int16) + self.hue_shift // 2) % 180
                frame_with_brightness = cv2.cvtColor(frame_hsv, cv2.COLOR_HSV2RGB)
            
            # Speichere komplettes Frame für Preview (konvertiere zu BGR für OpenCV)
            self.last_video_frame = cv2.cvtColor(frame_with_brightness, cv2.COLOR_RGB2BGR)
            
            # NumPy-optimierte Pixel-Extraktion
            valid_mask = (
                (self.point_coords[:, 1] >= 0) & 
                (self.point_coords[:, 1] < self.canvas_height) &
                (self.point_coords[:, 0] >= 0) & 
                (self.point_coords[:, 0] < self.canvas_width)
            )
            
            # Extrahiere RGB-Werte für alle Punkte (mit Helligkeit bereits angewendet)
            y_coords = self.point_coords[valid_mask, 1]
            x_coords = self.point_coords[valid_mask, 0]
            rgb_values = frame_with_brightness[y_coords, x_coords]
            
            # DMX-Buffer erstellen
            dmx_buffer = np.zeros((len(self.point_coords), 3), dtype=np.uint8)
            dmx_buffer[valid_mask] = rgb_values
            dmx_buffer = dmx_buffer.flatten().tolist()
            
            # Speichere für Preview
            self.last_frame = dmx_buffer.copy()
            
            # Recording
            if self.is_recording:
                self.recorded_data.append({
                    'frame': self.source.current_frame,
                    'timestamp': time.time() - self.start_time,
                    'dmx_data': dmx_buffer.copy()
                })
            
            # Sende über Art-Net (prüfe ob wir aktiver Player sind)
            if self.artnet_manager and self.is_running and player_lock._active_player is self:
                self.artnet_manager.send_frame(dmx_buffer, source='video')
            
            # Beende wenn gestoppt oder nicht mehr aktiv
            if not self.is_running or player_lock._active_player is not self:
                break
            
            self.frames_processed += 1
            
            # Frame-Timing mit Drift-Kompensation
            # Verwende source_delay wenn verfügbar, sonst calculated frame_time
            delay = source_delay if source_delay > 0 else frame_time
            delay /= self.speed_factor  # Speed-Faktor anwenden
            
            next_frame_time += delay
            current_time = time.time()
            sleep_time = next_frame_time - current_time
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            elif sleep_time < -0.1:  # Zu langsam, Reset
                next_frame_time = current_time + delay
        
        logger.debug("Play-Loop beendet")
    
    def status(self):
        """Gibt Status-String zurück."""
        if self.is_playing:
            if self.is_paused:
                return "pausiert"
            return "läuft"
        return "gestoppt"
    
    def get_info(self):
        """Gibt Informationen zurück."""
        import os
        
        info = {
            'source_type': type(self.source).__name__,
            'total_points': self.total_points,
            'total_universes': self.required_universes,
            'points_list': os.path.basename(self.points_json_path) if self.points_json_path else 'N/A',
            'fps_limit': self.fps_limit or self.source.fps
        }
        
        # Erweitere mit Source-spezifischen Infos
        source_info = self.source.get_info()
        info.update(source_info)
        
        return info
    
    def get_stats(self):
        """Gibt Live-Statistiken zurück."""
        runtime = time.time() - self.start_time if self.start_time > 0 else 0
        fps = self.frames_processed / runtime if runtime > 0 else 0
        
        return {
            'fps': round(fps, 1),
            'frames': self.frames_processed,
            'current_frame': self.source.current_frame,
            'total_frames': self.source.total_frames if not self.source.is_infinite else -1,
            'runtime': f"{int(runtime // 60):02d}:{int(runtime % 60):02d}"
        }
    
    # Art-Net Methoden
    def blackout(self):
        """Blackout (alle LEDs aus)."""
        if self.is_playing and not self.is_paused:
            self.pause()
        
        if self.artnet_manager:
            self.artnet_manager.blackout()
    
    def test_pattern(self, color='red'):
        """Testmuster senden."""
        if self.is_playing and not self.is_paused:
            self.pause()
        
        if self.artnet_manager:
            self.artnet_manager.test_pattern(color)
    
    def set_artnet_manager(self, artnet_manager):
        """Setzt den Art-Net Manager von außen."""
        self.artnet_manager = artnet_manager
    
    def reload_artnet(self):
        """Lädt Art-Net Manager neu (falls bereits gesetzt)."""
        if not self.artnet_manager:
            logger.warning("Kein Art-Net Manager gesetzt")
            return False
        
        try:
            self.artnet_manager.stop()
            artnet_config = self.config.get('artnet', {})
            self.artnet_manager.start(artnet_config)
            logger.debug(f"✅ Art-Net neu geladen mit IP: {self.target_ip}")
            return True
        except Exception as e:
            logger.error(f"❌ Fehler beim Neuladen von Art-Net: {e}")
            return False
    
    # Einstellungen
    def set_brightness(self, value):
        """Setzt Helligkeit (0-100)."""
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
    
    def set_hue_shift(self, value):
        """Setzt Hue Rotation (0-360 Grad)."""
        try:
            val = int(value)
            if val < 0 or val > 360:
                logger.debug("Hue Shift muss zwischen 0 und 360 liegen!")
                return
            self.hue_shift = val
            logger.debug(f"Hue Shift auf {val}° gesetzt")
        except ValueError:
            logger.debug("Ungültiger Hue Shift-Wert!")
    
    # Recording
    def start_recording(self, name=None):
        """Startet Aufzeichnung."""
        if not self.is_playing:
            logger.debug("Aufzeichnung nur während Wiedergabe möglich!")
            return False
        
        self.is_recording = True
        self.recorded_data = []
        self.recording_name = name or "Unnamed"
        logger.debug(f"Aufzeichnung gestartet: {self.recording_name}")
        return True
    
    def stop_recording(self):
        """Stoppt Aufzeichnung und speichert sie."""
        if not self.is_recording:
            logger.debug("Keine Aufzeichnung aktiv!")
            return None
        
        self.is_recording = False
        frame_count = len(self.recorded_data)
        
        if frame_count == 0:
            logger.debug("Keine Frames aufgezeichnet")
            return None
        
        # Speichere Aufzeichnung
        import json
        from datetime import datetime
        
        # Erstelle records Ordner falls nicht vorhanden (Root-Level)
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        records_dir = os.path.join(base_path, 'records')
        os.makedirs(records_dir, exist_ok=True)
        
        # Dateiname mit Timestamp und Name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in (self.recording_name or "recording") if c.isalnum() or c in (' ', '_', '-')).strip()
        filename = f"{safe_name}_{timestamp}.json"
        filepath = os.path.join(records_dir, filename)
        
        # Speichere als JSON
        recording_data = {
            'name': self.recording_name or "Unnamed Recording",
            'timestamp': timestamp,
            'frame_count': frame_count,
            'total_duration': self.recorded_data[-1]['timestamp'] if self.recorded_data else 0,
            'canvas_width': self.canvas_width,
            'canvas_height': self.canvas_height,
            'total_points': self.total_points,
            'frames': self.recorded_data
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(recording_data, f)
            logger.info(f"✅ Aufzeichnung gespeichert: {filename} ({frame_count} Frames)")
            return filename
        except Exception as e:
            logger.error(f"❌ Fehler beim Speichern der Aufzeichnung: {e}")
            return None
    
    def load_points(self, points_json_path):
        """
        Lädt neue Points-Konfiguration und passt Player entsprechend an.
        
        WICHTIG: Stoppt/Startet Source neu, da Canvas-Größe sich ändern kann!
        
        Args:
            points_json_path: Pfad zur neuen Points-JSON-Datei
        """
        logger.info(f"Lade neue Points-Konfiguration: {os.path.basename(points_json_path)}")
        
        # Lade neue Points-Daten
        validate_bounds = isinstance(self.source, VideoSource)
        points_data = PointsLoader.load_points(points_json_path, validate_bounds=validate_bounds)
        
        # Prüfe ob Canvas-Größe sich ändert
        canvas_changed = (
            points_data['canvas_width'] != self.canvas_width or 
            points_data['canvas_height'] != self.canvas_height
        )
        
        # Update Points-Daten
        old_points = self.total_points
        old_universes = self.required_universes
        
        self.points_json_path = points_json_path
        self.point_coords = points_data['point_coords']
        self.canvas_width = points_data['canvas_width']
        self.canvas_height = points_data['canvas_height']
        self.universe_mapping = points_data['universe_mapping']
        self.total_points = points_data['total_points']
        self.total_channels = points_data['total_channels']
        self.required_universes = points_data['required_universes']
        self.channels_per_universe = points_data['channels_per_universe']
        
        # Wenn Canvas-Größe sich ändert, muss Source neu initialisiert werden
        if canvas_changed:
            logger.info(f"Canvas-Größe geändert: {self.canvas_width}x{self.canvas_height}")
            
            # Stoppe Source
            self.source.cleanup()
            
            # Erstelle neue Source-Instanz mit neuer Canvas-Größe
            source_path = self.source.source_path if hasattr(self.source, 'source_path') else None
            is_video_source = isinstance(self.source, VideoSource)
            
            if is_video_source:
                self.source = VideoSource(source_path, self.canvas_width, self.canvas_height, self.config)
            else:
                # ScriptSource oder andere - passe Canvas-Größe an
                self.source.canvas_width = self.canvas_width
                self.source.canvas_height = self.canvas_height
            
            # Neu initialisieren
            if not self.source.initialize():
                raise ValueError(f"Source konnte nicht neu initialisiert werden")
        
        # Art-Net Manager aktualisieren
        if self.artnet_manager:
            # Stoppe alten Manager
            self.artnet_manager.stop()
            
            # Erstelle neuen Manager mit neuen Dimensionen
            from .artnet_manager import ArtNetManager
            artnet_config = self.config.get('artnet', {})
            self.artnet_manager = ArtNetManager(
                self.target_ip,
                self.start_universe,
                self.total_points,
                self.channels_per_universe
            )
            self.artnet_manager.start(artnet_config)
            
            logger.info(f"Art-Net Manager aktualisiert: {self.required_universes} Universen")
        
        logger.info(f"✅ Points gewechselt:")
        logger.info(f"   Punkte: {old_points} → {self.total_points}")
        logger.info(f"   Universen: {old_universes} → {self.required_universes}")
        logger.info(f"   Canvas: {self.canvas_width}x{self.canvas_height}")
    
