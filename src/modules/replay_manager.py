"""
Replay Manager - Spielt aufgezeichnete DMX-Daten ab
Unabhängig vom Player, direkt über Art-Net
"""
import os
import json
import time
import threading
from .logger import get_logger

logger = get_logger(__name__)


class ReplayManager:
    """Verwaltet Wiedergabe von aufgezeichneten DMX-Sequenzen."""
    
    def __init__(self, artnet_manager, config=None, player=None):
        """
        Initialisiert Replay Manager.
        
        Args:
            artnet_manager: ArtNetManager-Instanz für Ausgabe
            config: Konfigurations-Dict
            player: Player-Instanz (optional, wird beim Start gestoppt)
        """
        self.artnet_manager = artnet_manager
        self.config = config or {}
        self.player = player
        
        # Replay State
        self.is_playing = False
        self.replay_thread = None
        self.current_recording = None
        
        # Steuerung
        self.brightness = 1.0  # 0.0 - 1.0
        self.speed_factor = 1.0
        self.loop_enabled = True
        
        # Records Ordner
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.records_dir = os.path.join(base_path, 'records')
        os.makedirs(self.records_dir, exist_ok=True)
    
    def list_recordings(self):
        """Gibt Liste aller Aufzeichnungen zurück."""
        if not os.path.exists(self.records_dir):
            return []
        
        recordings = []
        for filename in sorted(os.listdir(self.records_dir), reverse=True):
            if filename.endswith('.json'):
                filepath = os.path.join(self.records_dir, filename)
                try:
                    stat = os.stat(filepath)
                    # Lade Metadaten aus Datei
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    
                    recordings.append({
                        'filename': filename,
                        'name': data.get('name', filename),
                        'frame_count': data.get('frame_count', 0),
                        'duration': data.get('total_duration', 0),
                        'size': stat.st_size,
                        'modified': stat.st_mtime
                    })
                except Exception as e:
                    logger.warning(f"Fehler beim Lesen von {filename}: {e}")
        
        return recordings
    
    def load_recording(self, filename):
        """Lädt eine Aufzeichnung."""
        filepath = os.path.join(self.records_dir, filename)
        
        if not os.path.exists(filepath):
            logger.error(f"Aufzeichnung nicht gefunden: {filename}")
            return False
        
        try:
            with open(filepath, 'r') as f:
                self.current_recording = json.load(f)
            
            logger.info(f"✅ Aufzeichnung geladen: {self.current_recording.get('name', filename)} "
                       f"({self.current_recording.get('frame_count', 0)} Frames)")
            return True
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden: {e}")
            return False
    
    def start(self):
        """Startet Replay-Wiedergabe."""
        if not self.current_recording:
            logger.warning("Keine Aufzeichnung geladen!")
            return False
        
        if self.is_playing:
            logger.warning("Replay läuft bereits!")
            return False
        
        # Stoppe Video-Wiedergabe falls aktiv
        if self.player and self.player.is_playing:
            self.player.stop()
            logger.debug("Video gestoppt für Replay")
        
        # Aktiviere Replay-Modus (blockiert Video-Ausgabe)
        # Note: artnet_manager removed - replay needs reimplementation with routing_bridge
        if self.artnet_manager:
            logger.warning("Replay: artnet_manager deprecated, output disabled")
        
        self.is_playing = True
        self.replay_thread = threading.Thread(target=self._replay_loop, daemon=True)
        self.replay_thread.start()
        logger.info(f"▶️ Replay gestartet: {self.current_recording.get('name', 'Unknown')}")
        return True
    
    def stop(self):
        """Stoppt Replay-Wiedergabe."""
        if not self.is_playing:
            return False
        
        self.is_playing = False
        if self.replay_thread:
            self.replay_thread.join(timeout=2)
        
        # Deaktiviere Replay-Modus (erlaubt Video-Ausgabe)
        # Note: artnet_manager removed
        
        logger.info("⏹️ Replay gestoppt")
        return True
    
    def _replay_loop(self):
        """Replay-Loop - spielt Frames mit Timing, Brightness und Speed ab."""
        if not self.current_recording or not self.current_recording.get('frames'):
            logger.error("Keine Replay-Daten vorhanden!")
            self.is_playing = False
            return
        
        frames = self.current_recording['frames']
        logger.debug(f"Replay-Loop: {len(frames)} Frames, Speed: {self.speed_factor}x")
        
        while self.is_playing:
            start_time = time.time()
            
            for i, frame_data in enumerate(frames):
                if not self.is_playing:
                    break
                
                # Berechne Ziel-Zeit mit Speed-Faktor
                target_timestamp = frame_data['timestamp'] / self.speed_factor
                target_time = start_time + target_timestamp
                current_time = time.time()
                
                # Warte bis korrekter Zeitpunkt
                if current_time < target_time:
                    time.sleep(target_time - current_time)
                
                # Hole DMX-Daten und wende Helligkeit an
                dmx_data = frame_data['dmx_data'].copy()
                
                if self.brightness < 1.0:
                    # Wende Helligkeit auf alle Kanäle an
                    dmx_data = [int(val * self.brightness) for val in dmx_data]
                
                # Sende über Art-Net mit Replay-Priorität
                # Note: artnet_manager removed - replay needs reimplementation with routing_bridge
                if self.artnet_manager:
                    logger.warning("Replay: Cannot send frame - artnet_manager deprecated")
            
            # Loop beenden wenn nicht aktiviert
            if not self.loop_enabled:
                break
        
        self.is_playing = False
        logger.debug("Replay-Loop beendet")
    
    def set_brightness(self, value):
        """Setzt Helligkeit (0-100)."""
        try:
            val = float(value)
            if val < 0 or val > 100:
                return
            self.brightness = val / 100.0
            logger.debug(f"Replay Helligkeit: {val}%")
        except ValueError:
            pass
    
    def set_speed(self, value):
        """Setzt Geschwindigkeit."""
        try:
            val = float(value)
            if val <= 0:
                return
            self.speed_factor = val
            logger.debug(f"Replay Geschwindigkeit: {val}x")
        except ValueError:
            pass
    
    def set_loop(self, enabled):
        """Aktiviert/Deaktiviert Loop."""
        self.loop_enabled = enabled
        logger.debug(f"Replay Loop: {'an' if enabled else 'aus'}")
    
    def set_player(self, player):
        """Setzt Player-Referenz (für spätere Initialisierung)."""
        self.player = player
