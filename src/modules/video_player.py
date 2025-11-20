"""
Video Player - Spielt Videos ab und sendet RGB-Daten über Art-Net
"""
import cv2
import os
import time
import threading
import json
import numpy as np
from .logger import get_logger
from .artnet_manager import ArtNetManager
from .points_loader import PointsLoader
from .cache_manager import CacheManager
from .constants import (
    DMX_CHANNELS_PER_UNIVERSE,
    DMX_CHANNELS_PER_POINT,
    DEFAULT_CANVAS_WIDTH,
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_SPEED,
    UNLIMITED_LOOPS,
    DEFAULT_FPS
)

logger = get_logger(__name__)

# GLOBALE LOCK: Shared mit ScriptPlayer - importiere Modul für echte Shared State
from . import player_lock


class VideoPlayer:
    """Video-Player mit Art-Net Ausgabe und erweiterten Steuerungsmöglichkeiten."""
    
    def __init__(self, video_path, points_json_path, target_ip='127.0.0.1', start_universe=0, fps_limit=None, config=None):
        self.video_path = video_path
        self.points_json_path = points_json_path
        self.target_ip = target_ip
        self.start_universe = start_universe
        self.fps_limit = fps_limit
        self.config = config or {}
        
        self.is_running = False
        self.is_playing = False
        self.is_paused = False
        self.thread = None
        self.artnet_manager = None
        
        # Erweiterte Steuerung
        self.brightness = 1.0  # 0.0 - 1.0
        self.speed_factor = DEFAULT_SPEED
        self.max_loops = UNLIMITED_LOOPS  # 0 = unendlich
        self.current_loop = 0
        self.current_frame = 0
        self.total_frames = 0
        self.start_time = 0
        self.frames_processed = 0
        self.is_recording = False
        self.recorded_data = []
        self.last_frame = None  # Letztes Frame (LED-Punkte) für Preview
        self.last_video_frame = None  # Letztes Video-Frame (komplettes Bild) für Preview
        
        # RGB Cache Manager
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cache')
        cache_enabled = self.config.get('cache', {}).get('enabled', True)
        self.cache_manager = CacheManager(cache_dir, cache_enabled)
        self.use_cache = cache_enabled
        self.cached_rgb_data = None
        self.cache_loaded = False
        
        # GIF Support
        self.is_gif = self._is_gif_file(video_path)
        self.gif_frame_delays = None
        self.gif_transparency_bg = tuple(self.config.get('video', {}).get('gif_transparency_bg', [0, 0, 0]))
        self.gif_respect_timing = self.config.get('video', {}).get('gif_respect_frame_timing', True)
        
        # Lade Points-Konfiguration mit PointsLoader
        points_data = PointsLoader.load_points(points_json_path, validate_bounds=True)
        
        self.point_coords = points_data['point_coords']
        self.canvas_width = points_data['canvas_width']
        self.canvas_height = points_data['canvas_height']
        self.universe_mapping = points_data['universe_mapping']
        self.total_points = points_data['total_points']
        self.total_channels = points_data['total_channels']
        self.required_universes = points_data['required_universes']
        self.channels_per_universe = points_data['channels_per_universe']
        
        logger.debug(f"Video Player initialisiert:")
        logger.debug(f"  Video: {os.path.basename(video_path)}")
        logger.debug(f"  Canvas-Größe: {self.canvas_width}x{self.canvas_height}")
        logger.debug(f"  Anzahl Punkte: {self.total_points}")
        logger.debug(f"  Benötigte Kanäle: {self.total_channels}")
        logger.debug(f"  Benötigte Universen: {self.required_universes}")
        logger.debug(f"  Art-Net Ziel-IP: {target_ip}")
        logger.debug(f"  Start-Universum: {start_universe}")
        
        # Art-Net Manager erstellen und sofort starten
        self.artnet_manager = ArtNetManager(target_ip, start_universe, self.total_points, self.channels_per_universe)
        artnet_config = self.config.get('artnet', {})
        self.artnet_manager.start(artnet_config)
    
    def load_video(self, video_path):
        """Lädt ein neues Video."""
        if self.is_playing:
            logger.debug("Stoppe aktuelles Video...")
            self.stop()
            shutdown_delay = self.config.get('video', {}).get('shutdown_delay', 0.5)
            time.sleep(shutdown_delay)
        
        if not os.path.exists(video_path):
            logger.debug(f"Fehler: Video nicht gefunden: {video_path}")
            return False
        
        self.video_path = video_path
        logger.debug(f"Video geladen: {os.path.basename(video_path)}")
        return True
    
    def load_points(self, points_json_path):
        """Lädt neue Points-Konfiguration (erfordert Neuinitialisierung)."""
        if not os.path.exists(points_json_path):
            logger.debug(f"Fehler: Points-Datei nicht gefunden: {points_json_path}")
            return False
        
        # Stoppe Art-Net temporär
        if self.artnet_manager:
            self.artnet_manager.stop()
        
        # Lade neue Points und re-initialisiere
        try:
            points_data = PointsLoader.load_points(points_json_path, validate_bounds=True)
            
            # Update Point-Daten
            self.point_coords = points_data['point_coords']
            self.canvas_width = points_data['canvas_width']
            self.canvas_height = points_data['canvas_height']
            self.universe_mapping = points_data['universe_mapping']
            self.total_points = points_data['total_points']
            self.total_channels = points_data['total_channels']
            self.required_universes = points_data['required_universes']
            self.channels_per_universe = points_data['channels_per_universe']
            self.points_json_path = points_json_path
            
            # Re-initialisiere Art-Net mit neuen Points
            self.artnet_manager = ArtNetManager(
                self.target_ip, 
                self.start_universe, 
                self.total_points, 
                self.channels_per_universe
            )
            artnet_config = self.config.get('artnet', {})
            self.artnet_manager.start(artnet_config)
            
            logger.debug(f"Points neu geladen: {os.path.basename(points_json_path)}")
            logger.debug(f"  Punkte: {self.total_points}, Universen: {self.required_universes}")
            return True
            
        except Exception as e:
            logger.debug(f"Fehler beim Laden der Points: {e}")
            # Re-starte altes Art-Net
            if self.artnet_manager:
                artnet_config = self.config.get('artnet', {})
                self.artnet_manager.start(artnet_config)
            return False
    
    def _is_gif_file(self, path):
        """Prüft ob Datei ein GIF ist."""
        return path.lower().endswith('.gif')
    
    def _load_gif_frame_delays(self):
        """Lädt Frame-Delays aus GIF mit Pillow."""
        try:
            from PIL import Image
            img = Image.open(self.video_path)
            delays = []
            try:
                frame_idx = 0
                while True:
                    # Duration in ms, konvertiere zu Sekunden
                    duration = img.info.get('duration', 100)
                    delays.append(duration / 1000.0)
                    frame_idx += 1
                    img.seek(frame_idx)
            except EOFError:
                pass
            
            logger.info(f"GIF Frame-Delays geladen: {len(delays)} Frames")
            return delays
        except ImportError:
            logger.warning("Pillow nicht verfügbar - GIF Frame-Timing wird ignoriert")
            return None
        except Exception as e:
            logger.warning(f"Fehler beim Laden der GIF Frame-Delays: {e}")
            return None
    
    def _process_frame_transparency(self, frame):
        """Verarbeitet Transparenz in Frames (für GIFs mit Alpha-Channel)."""
        if frame.shape[2] == 4:  # RGBA
            # Extrahiere Alpha-Channel
            alpha = frame[:, :, 3:4] / 255.0
            rgb = frame[:, :, :3]
            
            # Background Color aus Config
            bg = np.array(self.gif_transparency_bg, dtype=np.uint8).reshape(1, 1, 3)
            
            # Alpha-Blending: result = foreground * alpha + background * (1 - alpha)
            frame = (rgb * alpha + bg * (1 - alpha)).astype(np.uint8)
        
        return frame[:, :, :3]  # Stelle sicher dass nur RGB zurückgegeben wird
    
    def _load_cache(self):
        """Lädt gecachte RGB-Daten wenn verfügbar."""
        cache_path = self.cache_manager.get_cache_path(
            self.video_path, 
            self.points_json_path, 
            self.canvas_width, 
            self.canvas_height
        )
        
        if not cache_path:
            return False
        
        cache_data = self.cache_manager.load_cache(cache_path)
        if not cache_data:
            return False
        
        # Extrahiere Daten
        self.cached_rgb_data = cache_data['frames']
        self.total_frames = len(self.cached_rgb_data)
        self.video_fps = cache_data.get('video_fps', DEFAULT_FPS)
        self.is_gif = cache_data.get('is_gif', False)
        self.gif_frame_delays = cache_data.get('gif_frame_delays', None)
        self.cache_loaded = True
        
        logger.debug(f"  ✓ Cache geladen: {self.total_frames} Frames, {self.video_fps} FPS")
        if self.is_gif and self.gif_frame_delays:
            logger.debug(f"  ℹ GIF mit {len(self.gif_frame_delays)} Frame-Delays")
        
        return True
    
    def _save_cache(self, rgb_frames):
        """Speichert RGB-Daten als Cache."""
        cache_path = self.cache_manager.get_cache_path(
            self.video_path, 
            self.points_json_path, 
            self.canvas_width, 
            self.canvas_height
        )
        
        if not cache_path:
            return False
        
        video_fps = self.video_fps if hasattr(self, 'video_fps') else DEFAULT_FPS
        
        success = self.cache_manager.save_cache(
            cache_path,
            rgb_frames,
            video_fps,
            self.is_gif,
            self.gif_frame_delays
        )
        
        if success:
            logger.debug(f"  ✓ Cache gespeichert: {len(rgb_frames)} Frames")
        
        return success
    
    def _play_loop(self):
        """Haupt-Wiedergabeschleife (läuft in separatem Thread)."""
        self.is_running = True
        self.is_paused = False
        
        # Deaktiviere Testmuster-Modus (Video hat wieder Vorrang)
        if self.artnet_manager:
            self.artnet_manager.resume_video_mode()
        
        # Versuche Cache zu laden
        cache_loaded = self._load_cache()
        
        if cache_loaded:
            # Cached Playback (viel schneller!)
            self._play_from_cache()
            return
        
        # Fallback: Video laden mit Hardware-Beschleunigung
        cap = cv2.VideoCapture(self.video_path)
        
        if not cap.isOpened():
            logger.debug(f"Fehler: Video konnte nicht geöffnet werden.")
            self.is_running = False
            return
        
        # Versuche Hardware-Beschleunigung zu aktivieren
        try:
            cap.set(cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY)
            hw_accel = cap.get(cv2.CAP_PROP_HW_ACCELERATION)
            
            hw_types = {
                0: "Keine (Software-Decoding)",
                1: "D3D11 (Windows DirectX)",
                2: "VAAPI (Linux)",
                3: "DXVA2 (Windows)",
                4: "VDA (macOS VideoDecodeAcceleration)",
                5: "VideoToolbox (macOS)",
                6: "QSV (Intel Quick Sync Video)",
                7: "MMAL (Raspberry Pi)",
                8: "NVDEC (NVIDIA)"
            }
            
            hw_name = hw_types.get(int(hw_accel), f"Unbekannt ({int(hw_accel)})")
            
            if hw_name:
                logger.debug(f"  ✓ Hardware-Beschleunigung: {hw_name}")
            else:
                logger.debug(f"  ⚠ Hardware-Beschleunigung nicht verfügbar - Software-Decoding aktiv")
        except Exception as e:
            logger.debug(f"  ⚠ Hardware-Beschleunigung konnte nicht aktiviert werden: {e}")
            logger.debug(f"  → Verwende Software-Decoding")
        
        # Video-Informationen
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        self.video_fps = video_fps  # Speichere für Cache
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # GIF Frame-Delays laden falls GIF und noch nicht geladen
        if self.is_gif and not self.gif_frame_delays and self.gif_respect_timing:
            self.gif_frame_delays = self._load_gif_frame_delays()
        
        fps_limit = self.fps_limit if self.fps_limit else video_fps
        
        # Skalierung vorberechnen (statt in jedem Frame zu prüfen)
        needs_scaling = (original_width != self.canvas_width or original_height != self.canvas_height)
        canvas_size = (self.canvas_width, self.canvas_height)
        
        logger.debug(f"Starte Wiedergabe:")
        logger.debug(f"  Original Video-Auflösung: {original_width}x{original_height}")
        logger.debug(f"  Video-FPS: {video_fps}")
        logger.debug(f"  Wiedergabe-FPS: {fps_limit}")
        
        if self.is_gif:
            logger.debug(f"  ℹ GIF-Modus aktiv")
            if self.gif_frame_delays and self.gif_respect_timing:
                logger.debug(f"    └─ Frame-Timing: Variable Delays ({len(self.gif_frame_delays)} Frames)")
            logger.debug(f"    └─ Transparenz-BG: RGB{self.gif_transparency_bg}")
        
        if needs_scaling:
            logger.debug(f"  ➜ Video wird auf Canvas-Größe {self.canvas_width}x{self.canvas_height} skaliert")
        
        self.current_loop = 0
        self.current_frame = 0
        self.start_time = time.time()
        self.frames_processed = 0
        
        # Wenn Cache aktiviert ist, sammle RGB-Daten für ersten Loop
        cache_rgb_frames = [] if self.use_cache and not self.cache_loaded else None
        if cache_rgb_frames is not None:
            logger.debug(f"  ➜ Cache wird beim ersten Durchlauf erstellt...")
        
        try:
            while self.is_running:
                # Pause-Handling
                frame_wait = self.config.get('video', {}).get('frame_wait_delay', 0.1)
                while self.is_paused and self.is_running:
                    time.sleep(frame_wait)
                    continue
                
                if not self.is_running:
                    break
                
                # Frame-Delay mit Speed-Faktor berechnen
                # Bei GIFs: Verwende Frame-spezifisches Delay falls verfügbar
                if self.is_gif and self.gif_frame_delays and self.gif_respect_timing and self.current_frame < len(self.gif_frame_delays):
                    frame_delay = self.gif_frame_delays[self.current_frame] / self.speed_factor
                else:
                    frame_delay = (1.0 / fps_limit) / self.speed_factor if fps_limit > 0 else 0
                
                frame_start = time.time()
                
                ret, frame = cap.read()
                
                # Video-Loop: Bei Ende neu starten
                if not ret:
                    self.current_loop += 1
                    
                    # Loop-Limit prüfen
                    if self.max_loops > 0 and self.current_loop >= self.max_loops:
                        logger.debug(f"Loop-Limit ({self.max_loops}) erreicht, stoppe...")
                        break
                    
                    # Wenn Cache-Sammlung aktiv und erstes Loop beendet, speichere Cache
                    if cache_rgb_frames is not None and self.current_loop == 1:
                        self._save_cache(cache_rgb_frames)
                        cache_rgb_frames = None  # Deaktiviere weitere Sammlung
                    
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.current_frame = 0
                    continue
                
                self.current_frame += 1
                self.frames_processed += 1
                
                # GIF Transparenz-Handling falls nötig
                if self.is_gif and frame.shape[2] == 4:
                    frame = self._process_frame_transparency(frame)
                
                # Video auf Canvas-Größe skalieren (nur falls nötig)
                if needs_scaling:
                    frame = cv2.resize(frame, canvas_size, interpolation=cv2.INTER_LINEAR)
                
                # Speichere komplettes Video-Frame für Preview (BGR Format)
                self.last_video_frame = frame.copy()
                
                # RGB-Werte für alle Punkte sammeln (optimiert mit Numpy)
                if len(self.point_coords) > 0:
                    # Extrahiere alle Pixel auf einmal (viel schneller als Loop)
                    y_coords = self.point_coords[:, 1]
                    x_coords = self.point_coords[:, 0]
                    pixels = frame[y_coords, x_coords]  # BGR Format
                    
                    # Konvertiere BGR zu RGB und flatten zu [r, g, b, r, g, b, ...]
                    rgb_array = pixels[:, [2, 1, 0]]
                    
                    # Brightness anwenden
                    if self.brightness != 1.0:
                        rgb_array = (rgb_array * self.brightness).astype(np.uint8)
                    
                    rgb_values = rgb_array.flatten().tolist()
                else:
                    rgb_values = []
                
                # Cache-Sammlung (nur im ersten Loop)
                if cache_rgb_frames is not None:
                    cache_rgb_frames.append(rgb_values.copy())
                
                # Speichere letztes Frame für Preview
                self.last_frame = rgb_values.copy()
                
                # Recording
                if self.is_recording:
                    self.recorded_data.append({
                        'frame': self.current_frame,
                        'rgb': rgb_values.copy()
                    })
                
                # DMX-Daten auf die Universen verteilen (mit Universe-Mapping)
                # Erstelle DMX-Buffer mit Offsets
                max_channels_8_universes = self.channels_per_universe * 8
                dmx_buffer = [0] * (self.total_channels)
                
                # Fülle Buffer mit RGB-Werten unter Berücksichtigung des Mappings
                for point_idx in range(len(rgb_values) // 3):
                    offset = self.universe_mapping.get(point_idx, 0)
                    base_channel = point_idx * 3 + offset
                    
                    if base_channel + 2 < len(dmx_buffer):
                        dmx_buffer[base_channel] = rgb_values[point_idx * 3]
                        dmx_buffer[base_channel + 1] = rgb_values[point_idx * 3 + 1]
                        dmx_buffer[base_channel + 2] = rgb_values[point_idx * 3 + 2]
                
                # Sende Frame über Art-Net Manager (prüfe ob wir noch aktiver Player sind)
                if self.artnet_manager and self.is_running and player_lock._active_player is self:
                    self.artnet_manager.send_frame(dmx_buffer)
                
                # Beende Loop wenn nicht mehr aktiver Player
                if not self.is_running or player_lock._active_player is not self:
                    break
                
                # Frame-Timing
                frame_elapsed = time.time() - frame_start
                if frame_elapsed < frame_delay:
                    time.sleep(frame_delay - frame_elapsed)
        
        except Exception as e:
            logger.debug(f"Fehler während Wiedergabe: {e}")
        
        finally:
            cap.release()
            self.is_running = False
            self.is_playing = False
            logger.debug("Wiedergabe gestoppt.")
    
    def _play_from_cache(self):
        """Spielt Video aus gecachten RGB-Daten ab (viel schneller als Video-Decoding)."""
        if not self.cached_rgb_data:
            logger.debug("Keine Cache-Daten verfügbar")
            return
        
        # Nutze video_fps aus Cache wenn kein fps_limit gesetzt
        video_fps = self.video_fps if hasattr(self, 'video_fps') else DEFAULT_FPS
        fps_limit = self.fps_limit if self.fps_limit else video_fps
        
        logger.debug(f"Starte Wiedergabe aus Cache:")
        logger.debug(f"  Frames: {len(self.cached_rgb_data)}")
        logger.debug(f"  Video-FPS: {video_fps}")
        logger.debug(f"  Wiedergabe-FPS: {fps_limit}")
        
        if self.is_gif:
            logger.debug(f"  ℹ GIF-Modus aktiv (aus Cache)")
            if self.gif_frame_delays and self.gif_respect_timing:
                logger.debug(f"    └─ Frame-Timing: Variable Delays")
        
        # Öffne Video parallel für Preview (ohne Hardware-Beschleunigung für weniger Overhead)
        cap_preview = None
        try:
            cap_preview = cv2.VideoCapture(self.video_path)
            if cap_preview.isOpened():
                logger.debug(f"  ℹ Video-Preview parallel geöffnet")
        except:
            cap_preview = None
        
        self.current_loop = 0
        self.current_frame = 0
        self.start_time = time.time()
        self.frames_processed = 0
        
        try:
            while self.is_running:
                # Pause-Handling
                frame_wait = self.config.get('video', {}).get('frame_wait_delay', 0.1)
                while self.is_paused and self.is_running:
                    time.sleep(frame_wait)
                    continue
                
                if not self.is_running:
                    break
                
                # Frame-Delay mit Speed-Faktor
                # Bei GIFs: Verwende Frame-spezifisches Delay falls verfügbar
                if self.is_gif and self.gif_frame_delays and self.gif_respect_timing and self.current_frame < len(self.gif_frame_delays):
                    frame_delay = self.gif_frame_delays[self.current_frame] / self.speed_factor
                else:
                    frame_delay = (1.0 / fps_limit) / self.speed_factor if fps_limit > 0 else 0
                
                frame_start = time.time()
                
                # Hole RGB-Daten aus Cache
                if self.current_frame >= len(self.cached_rgb_data):
                    self.current_loop += 1
                    
                    # Loop-Limit prüfen
                    if self.max_loops > 0 and self.current_loop >= self.max_loops:
                        logger.debug(f"Loop-Limit ({self.max_loops}) erreicht, stoppe...")
                        break
                    
                    self.current_frame = 0
                    continue
                
                rgb_values = self.cached_rgb_data[self.current_frame]
                self.current_frame += 1
                self.frames_processed += 1
                
                # Lade entsprechendes Video-Frame für Preview
                if cap_preview and cap_preview.isOpened():
                    ret, preview_frame = cap_preview.read()
                    if ret:
                        # Skaliere auf Canvas-Größe falls nötig
                        if preview_frame.shape[1] != self.canvas_width or preview_frame.shape[0] != self.canvas_height:
                            preview_frame = cv2.resize(preview_frame, (self.canvas_width, self.canvas_height))
                        self.last_video_frame = preview_frame
                    else:
                        # Video neu starten für Preview
                        cap_preview.set(cv2.CAP_PROP_POS_FRAMES, 0)
                
                # Brightness anwenden (falls geändert)
                if self.brightness != 1.0:
                    rgb_array = np.array(rgb_values, dtype=np.float32)
                    rgb_array = (rgb_array * self.brightness).clip(0, 255).astype(np.uint8)
                    rgb_values = rgb_array.tolist()
                
                # Speichere letztes Frame für Preview
                self.last_frame = rgb_values.copy()
                
                # Recording
                if self.is_recording:
                    self.recorded_data.append({
                        'frame': self.current_frame,
                        'rgb': rgb_values.copy()
                    })
                
                # DMX-Daten auf Universen verteilen
                dmx_buffer = [0] * (self.total_channels)
                
                for point_idx in range(len(rgb_values) // 3):
                    offset = self.universe_mapping.get(point_idx, 0)
                    base_channel = point_idx * 3 + offset
                    
                    if base_channel + 2 < len(dmx_buffer):
                        dmx_buffer[base_channel] = rgb_values[point_idx * 3]
                        dmx_buffer[base_channel + 1] = rgb_values[point_idx * 3 + 1]
                        dmx_buffer[base_channel + 2] = rgb_values[point_idx * 3 + 2]
                
                # Sende über Art-Net (prüfe ob wir noch aktiver Player sind)
                if self.artnet_manager and self.is_running and player_lock._active_player is self:
                    self.artnet_manager.send_frame(dmx_buffer)
                
                # Beende Loop wenn nicht mehr aktiver Player
                if not self.is_running or player_lock._active_player is not self:
                    break
                
                # Frame-Timing
                frame_elapsed = time.time() - frame_start
                if frame_elapsed < frame_delay:
                    time.sleep(frame_delay - frame_elapsed)
        
        except Exception as e:
            logger.debug(f"Fehler während Cache-Wiedergabe: {e}")
        
        finally:
            # Schließe Preview-Video
            if cap_preview:
                cap_preview.release()
            self.is_running = False
            self.is_playing = False
            logger.debug("Wiedergabe gestoppt.")
    
    def start(self):
        """Startet die Video-Wiedergabe in Endlosschleife."""
        # Prüfung ob wir schon laufen
        if self.is_playing:
            logger.debug(f"Video läuft bereits!")
            return
        
        # KRITISCH: Registriere als aktiver Player
        # Prüfe ob ALTER Player existiert (mit Lock) - NICHT wir selbst!
        old_player = None
        with player_lock._global_player_lock:
            if player_lock._active_player and player_lock._active_player is not self:
                old_player = player_lock._active_player
                player_lock._active_player = None  # Deregistriere sofort
        
        # Stoppe alten Player OHNE Lock (könnte lange dauern)
        if old_player:
            player_type = type(old_player).__name__
            logger.info(f"Stoppe alten Player vor Start des Videos: {player_type}")
            old_player.stop()
            time.sleep(0.5)  # Längere Wartezeit
            del old_player  # Explizit löschen
            logger.info(f"Alter Player gestoppt und gelöscht")
        
        # Registriere neuen Player (mit Lock)
        with player_lock._global_player_lock:
            player_lock._active_player = self
            logger.info(f"Neuer aktiver Player: VideoPlayer")
        
        # Stoppe eventuelles Testmuster und aktiviere ArtNet
        if self.artnet_manager:
            self.artnet_manager.test_mode = False
            self.artnet_manager._stop_test_thread()
            self.artnet_manager.is_active = True  # WICHTIG: Reaktiviere ArtNet
        
        self.is_playing = True
        self.is_running = True  # WICHTIG: Auch is_running setzen!
        self.thread = threading.Thread(target=self._play_loop, daemon=True)
        self.thread.start()
        logger.info("Video-Thread gestartet")
    
    def stop(self):
        """Stoppt die Video-Wiedergabe."""
        global _active_player
        
        if not self.is_playing:
            logger.debug("Video läuft nicht!")
            return
        
        logger.debug("Stoppe Video...")
        
        # WICHTIG: Reihenfolge ist kritisch!
        # 1. Setze Flags SOFORT - stoppt Loop bei nächster Iteration
        self.is_running = False
        self.is_playing = False
        self.is_paused = False
        
        # 2. Deaktiviere ArtNet temporär - verhindert weitere send_frame() Aufrufe
        if self.artnet_manager:
            self.artnet_manager.is_active = False
        
        # 3. Warte auf Thread-Ende
        if self.thread:
            self.thread.join(timeout=3.0)
            if self.thread.is_alive():
                logger.warning("Video-Thread konnte nicht gestoppt werden!")
        
        # 4. Thread cleanup (ArtNet-Manager NICHT löschen - könnte wiederverwendet werden)
        self.thread = None
        
        # 5. Entferne aus globaler Registrierung
        with player_lock._global_player_lock:
            if player_lock._active_player is self:
                player_lock._active_player = None
    
    def pause(self):
        """Pausiert die Wiedergabe."""
        if not self.is_playing:
            logger.debug("Video läuft nicht!")
            return
        if self.is_paused:
            logger.debug("Video ist bereits pausiert!")
            return
        self.is_paused = True
        logger.debug("Video pausiert")
    
    def resume(self):
        """Setzt die Wiedergabe fort."""
        if not self.is_playing:
            logger.debug("Video läuft nicht!")
            return
        if not self.is_paused:
            logger.debug("Video ist nicht pausiert!")
            return
        
        # Deaktiviere Testmuster KOMPLETT (stoppt auch Test-Thread)
        if self.artnet_manager:
            self.artnet_manager.resume_video_mode()
        
        self.is_paused = False
        logger.debug("Wiedergabe fortgesetzt")
    
    def restart(self):
        """Startet Video von vorne."""
        if self.is_playing:
            was_paused = self.is_paused
            self.stop()
            restart_delay = self.config.get('video', {}).get('recording_stop_delay', 0.3)
            time.sleep(restart_delay)
            self.start()
            if was_paused:
                self.pause()
        logger.debug("Video neu gestartet")
    
    def set_fps(self, fps):
        """Ändert FPS-Limit während der Wiedergabe."""
        try:
            fps_val = float(fps)
            if fps_val <= 0:
                logger.debug("FPS muss größer als 0 sein!")
                return
            self.fps_limit = fps_val
            logger.debug(f"FPS-Limit gesetzt: {fps_val}")
        except ValueError:
            logger.debug("Ungültiger FPS-Wert!")
    
    def set_speed(self, factor):
        """Ändert Wiedergabe-Geschwindigkeit."""
        try:
            speed = float(factor)
            if speed <= 0:
                logger.debug("Speed-Faktor muss größer als 0 sein!")
                return
            self.speed_factor = speed
            logger.debug(f"Geschwindigkeit gesetzt: {speed}x")
        except ValueError:
            logger.debug("Ungültiger Speed-Wert!")
    
    def set_brightness(self, value):
        """Setzt globale Helligkeit (0-100)."""
        try:
            brightness = float(value)
            if brightness < 0 or brightness > 100:
                logger.debug("Helligkeit muss zwischen 0 und 100 sein!")
                return
            self.brightness = brightness / 100.0
            logger.debug(f"Helligkeit gesetzt: {brightness}%")
        except ValueError:
            logger.debug("Ungültiger Helligkeits-Wert!")
    
    def set_loop_limit(self, loops):
        """Setzt Loop-Limit (0 = unendlich)."""
        try:
            loop_val = int(loops)
            if loop_val < 0:
                logger.debug("Loop-Anzahl muss >= 0 sein!")
                return
            self.max_loops = loop_val
            if loop_val == 0:
                logger.debug("Loop-Limit: Unendlich")
            else:
                logger.debug(f"Loop-Limit gesetzt: {loop_val}")
        except ValueError:
            logger.debug("Ungültiger Loop-Wert!")
    
    def blackout(self):
        """Setzt alle DMX-Kanäle auf 0."""
        # Stoppe Video komplett, damit Blackout nicht überschrieben wird
        if self.is_playing:
            self.stop()
        
        if self.artnet_manager:
            self.artnet_manager.blackout()
        else:
            logger.debug("Art-Net nicht aktiv!")
    
    def reload_artnet(self):
        """Lädt Art-Net mit neuer IP neu."""
        try:
            # Prüfe ob erforderliche Attribute existieren
            if not hasattr(self, 'total_points') or not hasattr(self, 'channels_per_universe'):
                logger.debug("⚠️ Art-Net kann nicht neu geladen werden - Player nicht vollständig initialisiert")
                return False
            
            # Stoppe altes Art-Net
            if self.artnet_manager:
                self.artnet_manager.stop()
            
            # Erstelle neues Art-Net mit aktueller IP
            self.artnet_manager = ArtNetManager(
                self.target_ip, 
                self.start_universe, 
                self.total_points, 
                self.channels_per_universe
            )
            
            # Starte mit Config
            artnet_config = self.config.get('artnet', {})
            self.artnet_manager.start(artnet_config)
            
            logger.debug(f"✅ Art-Net neu geladen mit IP: {self.target_ip}")
            return True
        except Exception as e:
            logger.debug(f"❌ Fehler beim Neuladen von Art-Net: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def test_pattern(self, color='red'):
        """Sendet Testmuster (stoppt Video-Wiedergabe)."""
        # Stoppe Video komplett, damit Testmuster nicht überschrieben wird
        if self.is_playing:
            self.stop()
        
        if self.artnet_manager:
            self.artnet_manager.test_pattern(color)
        else:
            logger.debug("Art-Net nicht aktiv!")
    
    def start_recording(self):
        """Startet RGB-Daten-Aufzeichnung."""
        self.recorded_data = []
        self.is_recording = True
        logger.debug("Aufzeichnung gestartet")
    
    def stop_recording(self, filename=None):
        """Stoppt Aufzeichnung und speichert Daten."""
        if not self.is_recording:
            logger.debug("Keine Aufzeichnung aktiv!")
            return
        
        self.is_recording = False
        
        if not filename:
            filename = f"recording_{int(time.time())}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.recorded_data, f)
            logger.debug(f"Aufzeichnung gespeichert: {filename} ({len(self.recorded_data)} Frames)")
        except Exception as e:
            logger.debug(f"Fehler beim Speichern: {e}")
    
    def get_info(self):
        """Gibt detaillierte Informationen zurück."""
        info = {
            'video': os.path.basename(self.video_path),
            'canvas': f"{self.canvas_width}x{self.canvas_height}",
            'points': self.total_points,
            'channels': self.total_channels,
            'universes': self.required_universes,
            'ip': self.target_ip,
            'start_universe': self.start_universe,
            'fps_limit': self.fps_limit,
            'brightness': f"{self.brightness * 100:.0f}%",
            'speed': f"{self.speed_factor}x",
            'loops': self.max_loops if self.max_loops > 0 else "∞"
        }
        return info
    
    def get_stats(self):
        """Gibt Live-Statistiken zurück."""
        if not self.is_playing:
            return "Video läuft nicht"
        
        elapsed = time.time() - self.start_time
        current_fps = self.frames_processed / elapsed if elapsed > 0 else 0
        
        stats = {
            'video': os.path.basename(self.video_path),
            'path': self.video_path,
            'status': 'Pausiert' if self.is_paused else 'Läuft',
            'frame': f"{self.current_frame}/{self.total_frames}",
            'loop': self.current_loop,
            'fps': f"{current_fps:.2f}",
            'runtime': f"{elapsed:.1f}s",
            'recording': 'Ja' if self.is_recording else 'Nein'
        }
        return stats
    
    def status(self):
        """Gibt den aktuellen Status zurück."""
        if self.is_paused:
            return "Pausiert"
        return "Läuft" if self.is_playing else "Gestoppt"
