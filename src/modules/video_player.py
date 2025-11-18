"""
Video Player - Spielt Videos ab und sendet RGB-Daten über Art-Net
"""
import cv2
import os
import json
import time
import threading
import hashlib
import numpy as np
from .logger import get_logger

logger = get_logger(__name__)
try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False
    print("⚠ msgpack nicht installiert - Cache-Funktion deaktiviert")
from .artnet_manager import ArtNetManager
from .constants import (
    DMX_CHANNELS_PER_UNIVERSE,
    DMX_CHANNELS_PER_POINT,
    DMX_MAX_CHANNELS_8_UNIVERSES,
    CACHE_CHUNK_SIZE,
    CACHE_HASH_LENGTH,
    DEFAULT_CANVAS_WIDTH,
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_SPEED,
    UNLIMITED_LOOPS,
    DEFAULT_FPS
)


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
        
        # RGB Cache
        self.use_cache = MSGPACK_AVAILABLE and self.config.get('cache', {}).get('enabled', True)
        self.cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cache')
        self.cached_rgb_data = None
        self.cache_loaded = False
        
        # GIF Support
        self.is_gif = self._is_gif_file(video_path)
        self.gif_frame_delays = None
        self.gif_transparency_bg = tuple(self.config.get('video', {}).get('gif_transparency_bg', [0, 0, 0]))
        self.gif_respect_timing = self.config.get('video', {}).get('gif_respect_frame_timing', True)
        
        # JSON-Datei einlesen
        with open(points_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Canvas-Größe auslesen
        canvas = data.get('canvas', {})
        self.canvas_width = canvas.get('width', DEFAULT_CANVAS_WIDTH)
        self.canvas_height = canvas.get('height', DEFAULT_CANVAS_HEIGHT)
        
        objects = data.get('objects', [])
        
        # Universen-Logik: Objekte die über 8 Universen hinausgehen, ab Universum 9 fortführen
        channels_per_universe = DMX_CHANNELS_PER_UNIVERSE
        channels_per_point = DMX_CHANNELS_PER_POINT  # RGB
        max_channels_8_universes = DMX_MAX_CHANNELS_8_UNIVERSES  # 4080 Kanäle
        
        # Sammle Punkte mit Objekt-Zuordnung und berechne Universe-Mapping
        point_list = []
        self.universe_mapping = {}  # Mapping: Punkt-Index -> Universum-Offset
        current_channel = 0
        universe_offset = 0
        
        for obj_idx, obj in enumerate(objects):
            obj_id = obj.get('id', f'object-{obj_idx}')
            points = obj.get('points', [])
            
            # Validiere Punkte
            valid_points = []
            for point in points:
                x, y = point.get('x'), point.get('y')
                if 0 <= x < self.canvas_width and 0 <= y < self.canvas_height:
                    valid_points.append((x, y))
            
            if not valid_points:
                continue
            
            obj_channels = len(valid_points) * channels_per_point
            obj_start_channel = current_channel + universe_offset
            obj_end_channel = obj_start_channel + obj_channels
            
            # Prüfe ob Objekt über 8-Universen-Grenze geht
            if obj_start_channel < max_channels_8_universes and obj_end_channel > max_channels_8_universes:
                # Objekt würde Grenze überschreiten -> verschiebe komplett zu Universum 9
                universe_offset = max_channels_8_universes - current_channel
                obj_start_channel = current_channel + universe_offset
                obj_end_channel = obj_start_channel + obj_channels
                print(f"  ⚠️  Objekt '{obj_id}' verschoben zu Universum 9+ (würde Grenze überschreiten)")
            
            # Füge Punkte hinzu und speichere Universe-Mapping
            start_idx = len(point_list)
            for point in valid_points:
                point_list.append(point)
                point_idx = len(point_list) - 1
                self.universe_mapping[point_idx] = universe_offset
            
            current_channel += obj_channels
        
        # Als Numpy-Array für schnelleren Zugriff speichern
        self.point_coords = np.array(point_list, dtype=np.int32) if point_list else np.array([])
        total_points = len(point_list)
        total_channels = total_points * channels_per_point + universe_offset
        
        # Berechne benötigte Universen
        self.required_universes = (total_channels + channels_per_universe - 1) // channels_per_universe
        self.channels_per_universe = channels_per_universe
        
        self.total_points = total_points
        self.total_channels = total_channels
        
        print(f"Video Player initialisiert:")
        print(f"  Video: {os.path.basename(video_path)}")
        print(f"  Canvas-Größe: {self.canvas_width}x{self.canvas_height}")
        print(f"  Anzahl Punkte: {total_points}")
        print(f"  Benötigte Kanäle: {total_channels}")
        print(f"  Benötigte Universen: {self.required_universes}")
        print(f"  Art-Net Ziel-IP: {target_ip}")
        print(f"  Start-Universum: {start_universe}")
        
        # Art-Net Manager erstellen und sofort starten
        self.artnet_manager = ArtNetManager(target_ip, start_universe, total_points, channels_per_universe)
        artnet_config = self.config.get('artnet', {})
        self.artnet_manager.start(artnet_config)
    
    def load_video(self, video_path):
        """Lädt ein neues Video."""
        if self.is_playing:
            print("Stoppe aktuelles Video...")
            self.stop()
            shutdown_delay = self.config.get('video', {}).get('shutdown_delay', 0.5)
            time.sleep(shutdown_delay)
        
        if not os.path.exists(video_path):
            print(f"Fehler: Video nicht gefunden: {video_path}")
            return False
        
        self.video_path = video_path
        print(f"Video geladen: {os.path.basename(video_path)}")
        return True
    
    def load_points(self, points_json_path):
        """Lädt neue Points-Konfiguration (erfordert Neuinitialisierung)."""
        if not os.path.exists(points_json_path):
            print(f"Fehler: Points-Datei nicht gefunden: {points_json_path}")
            return False
        
        # Stoppe Art-Net temporär
        if self.artnet_manager:
            self.artnet_manager.stop()
        
        # Lade neue Points und re-initialisiere
        try:
            with open(points_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Update Canvas-Größe
            canvas = data.get('canvas', {})
            self.canvas_width = canvas.get('width', DEFAULT_CANVAS_WIDTH)
            self.canvas_height = canvas.get('height', DEFAULT_CANVAS_HEIGHT)
            
            # Re-calculate points (gleiche Logik wie __init__)
            objects = data.get('objects', [])
            channels_per_universe = DMX_CHANNELS_PER_UNIVERSE
            channels_per_point = DMX_CHANNELS_PER_POINT
            max_channels_8_universes = DMX_MAX_CHANNELS_8_UNIVERSES
            
            point_list = []
            self.universe_mapping = {}
            current_channel = 0
            universe_offset = 0
            
            for obj_idx, obj in enumerate(objects):
                obj_id = obj.get('id', f'object-{obj_idx}')
                points = obj.get('points', [])
                
                valid_points = []
                for point in points:
                    x, y = point.get('x'), point.get('y')
                    if 0 <= x < self.canvas_width and 0 <= y < self.canvas_height:
                        valid_points.append((x, y))
                
                if not valid_points:
                    continue
                
                obj_channels = len(valid_points) * channels_per_point
                obj_start_channel = current_channel + universe_offset
                obj_end_channel = obj_start_channel + obj_channels
                
                if obj_start_channel < max_channels_8_universes and obj_end_channel > max_channels_8_universes:
                    universe_offset = max_channels_8_universes - current_channel
                    obj_start_channel = current_channel + universe_offset
                    obj_end_channel = obj_start_channel + obj_channels
                
                for point in valid_points:
                    point_list.append(point)
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
            self.points_json_path = points_json_path
            
            # Re-initialisiere Art-Net mit neuen Points
            self.artnet_manager = ArtNetManager(
                self.target_ip, 
                self.start_universe, 
                total_points, 
                channels_per_universe
            )
            artnet_config = self.config.get('artnet', {})
            self.artnet_manager.start(artnet_config)
            
            print(f"Points neu geladen: {os.path.basename(points_json_path)}")
            print(f"  Punkte: {total_points}, Universen: {self.required_universes}")
            return True
            
        except Exception as e:
            print(f"Fehler beim Laden der Points: {e}")
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
    
    def _get_cache_path(self):
        """Generiert Cache-Dateinamen basierend auf Video-Inhalt und Points Hash."""
        if not self.use_cache:
            return None
        
        # Berechne Hash vom Video-Inhalt (erste 5MB + Dateigröße)
        # Dies verhindert Duplikate bei gleichen Videos mit unterschiedlichen Namen
        try:
            video_hash = self._get_video_hash()
            points_hash = hashlib.md5(open(self.points_json_path, 'rb').read()).hexdigest()[:8]
            canvas_hash = hashlib.md5(f"{self.canvas_width}x{self.canvas_height}".encode()).hexdigest()[:8]
            
            # Cache-Dateiname: <video_hash>_<points_hash>_<canvas_hash>.msgpack
            file_hash = f"{video_hash}_{points_hash}_{canvas_hash}"
            return os.path.join(self.cache_dir, f"{file_hash}.msgpack")
        except Exception as e:
            print(f"  ⚠ Fehler beim Berechnen des Cache-Hash: {e}")
            return None
    
    def _get_video_hash(self):
        """Berechnet eindeutigen Hash für Video-Datei (schnelle Methode)."""
        # Lese erste 5MB + Dateigröße für schnellen aber eindeutigen Hash
        chunk_size = CACHE_CHUNK_SIZE
        file_size = os.path.getsize(self.video_path)
        
        hash_md5 = hashlib.md5()
        hash_md5.update(str(file_size).encode())  # Dateigröße einbeziehen
        
        with open(self.video_path, 'rb') as f:
            # Lese ersten Chunk
            chunk = f.read(chunk_size)
            hash_md5.update(chunk)
            
            # Wenn Datei größer als chunk_size, lese auch letzten Chunk
            if file_size > chunk_size:
                f.seek(-min(chunk_size, file_size - chunk_size), 2)
                chunk = f.read(chunk_size)
                hash_md5.update(chunk)
        
        return hash_md5.hexdigest()[:CACHE_HASH_LENGTH]  # Erste Zeichen für Hash
    
    def _load_cache(self):
        """Lädt gecachte RGB-Daten wenn verfügbar."""
        if not self.use_cache or not MSGPACK_AVAILABLE:
            return False
        
        cache_path = self._get_cache_path()
        if not cache_path or not os.path.exists(cache_path):
            return False
        
        try:
            logger.info(f"Lade RGB-Cache: {os.path.basename(cache_path)}")
            print(f"Lade RGB-Cache: {os.path.basename(cache_path)}")
            with open(cache_path, 'rb') as f:
                cache_data = msgpack.unpackb(f.read(), raw=False)
            
            # Validiere Cache-Format
            if not isinstance(cache_data, dict) or 'frames' not in cache_data:
                logger.warning("Ungültiges Cache-Format")
                print("  ⚠ Ungültiges Cache-Format")
                return False
            
            self.cached_rgb_data = cache_data['frames']
            self.total_frames = len(self.cached_rgb_data)
            self.video_fps = cache_data.get('video_fps', DEFAULT_FPS)  # FPS aus Cache laden
            
            # GIF-Metadaten aus Cache laden
            self.is_gif = cache_data.get('is_gif', False)
            self.gif_frame_delays = cache_data.get('gif_frame_delays', None)
            
            file_size_mb = os.path.getsize(cache_path) / (1024*1024)
            
            logger.info(f"Cache geladen: {self.total_frames} Frames, {file_size_mb:.2f} MB, {self.video_fps} FPS")
            print(f"  ✓ Cache geladen: {self.total_frames} Frames, {file_size_mb:.2f} MB, {self.video_fps} FPS")
            if self.is_gif:
                print(f"  ℹ GIF mit {len(self.gif_frame_delays) if self.gif_frame_delays else 0} Frame-Delays")
            self.cache_loaded = True
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Laden des Cache: {e}", exc_info=True)
            print(f"  ⚠ Fehler beim Laden des Cache: {e}")
            self.cached_rgb_data = None
            self.cache_loaded = False
            return False
    
    def _save_cache(self, rgb_frames):
        """Speichert RGB-Daten als Cache."""
        if not self.use_cache or not MSGPACK_AVAILABLE:
            return False
        
        cache_path = self._get_cache_path()
        if not cache_path:
            return False
        
        try:
            # Erstelle cache-Ordner falls nicht vorhanden
            os.makedirs(self.cache_dir, exist_ok=True)
            
            print(f"Speichere RGB-Cache: {os.path.basename(cache_path)}")
            
            # Packe Daten mit msgpack
            cache_data = {
                'video': os.path.basename(self.video_path),
                'points': os.path.basename(self.points_json_path),
                'canvas_size': [self.canvas_width, self.canvas_height],
                'total_points': self.total_points,
                'is_gif': self.is_gif,
                'gif_frame_delays': self.gif_frame_delays,
                'video_fps': self.video_fps if hasattr(self, 'video_fps') else DEFAULT_FPS,
                'frames': rgb_frames
            }
            
            packed_data = msgpack.packb(cache_data, use_bin_type=True)
            
            with open(cache_path, 'wb') as f:
                f.write(packed_data)
            
            file_size_mb = len(packed_data) / (1024*1024)
            logger.info(f"Cache gespeichert: {self.total_frames} Frames, {file_size_mb:.2f} MB")
            print(f"  ✓ Cache gespeichert: {self.total_frames} Frames, {file_size_mb:.2f} MB")
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Cache: {e}", exc_info=True)
            print(f"  ⚠ Fehler beim Speichern des Cache: {e}")
            return False
    
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
            print(f"Fehler: Video konnte nicht geöffnet werden.")
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
            
            if hw_accel > 0:
                print(f"  ✓ Hardware-Beschleunigung: {hw_name}")
            else:
                print(f"  ⚠ Hardware-Beschleunigung nicht verfügbar - Software-Decoding aktiv")
        except Exception as e:
            print(f"  ⚠ Hardware-Beschleunigung konnte nicht aktiviert werden: {e}")
            print(f"  → Verwende Software-Decoding")
        
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
        
        print(f"Starte Wiedergabe:")
        print(f"  Original Video-Auflösung: {original_width}x{original_height}")
        print(f"  Video-FPS: {video_fps}")
        print(f"  Wiedergabe-FPS: {fps_limit}")
        
        if self.is_gif:
            print(f"  ℹ GIF-Modus aktiv")
            if self.gif_frame_delays and self.gif_respect_timing:
                print(f"    └─ Frame-Timing: Variable Delays ({len(self.gif_frame_delays)} Frames)")
            print(f"    └─ Transparenz-BG: RGB{self.gif_transparency_bg}")
        
        if needs_scaling:
            print(f"  ➜ Video wird auf Canvas-Größe {self.canvas_width}x{self.canvas_height} skaliert")
        
        self.current_loop = 0
        self.current_frame = 0
        self.start_time = time.time()
        self.frames_processed = 0
        
        # Wenn Cache aktiviert ist, sammle RGB-Daten für ersten Loop
        cache_rgb_frames = [] if self.use_cache and not self.cache_loaded else None
        if cache_rgb_frames is not None:
            print(f"  ➜ Cache wird beim ersten Durchlauf erstellt...")
        
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
                        print(f"Loop-Limit ({self.max_loops}) erreicht, stoppe...")
                        break
                    
                    print(f"Loop {self.current_loop} beendet, starte neu...")
                    
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
                
                # Sende Frame über Art-Net Manager
                if self.artnet_manager:
                    self.artnet_manager.send_frame(dmx_buffer)
                
                # Frame-Timing
                frame_elapsed = time.time() - frame_start
                if frame_elapsed < frame_delay:
                    time.sleep(frame_delay - frame_elapsed)
        
        except Exception as e:
            print(f"Fehler während Wiedergabe: {e}")
        
        finally:
            cap.release()
            self.is_running = False
            self.is_playing = False
            print("Wiedergabe gestoppt.")
    
    def _play_from_cache(self):
        """Spielt Video aus gecachten RGB-Daten ab (viel schneller als Video-Decoding)."""
        if not self.cached_rgb_data:
            print("Keine Cache-Daten verfügbar")
            return
        
        # Nutze video_fps aus Cache wenn kein fps_limit gesetzt
        video_fps = self.video_fps if hasattr(self, 'video_fps') else DEFAULT_FPS
        fps_limit = self.fps_limit if self.fps_limit else video_fps
        
        print(f"Starte Wiedergabe aus Cache:")
        print(f"  Frames: {len(self.cached_rgb_data)}")
        print(f"  Video-FPS: {video_fps}")
        print(f"  Wiedergabe-FPS: {fps_limit}")
        
        if self.is_gif:
            print(f"  ℹ GIF-Modus aktiv (aus Cache)")
            if self.gif_frame_delays and self.gif_respect_timing:
                print(f"    └─ Frame-Timing: Variable Delays")
        
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
                        print(f"Loop-Limit ({self.max_loops}) erreicht, stoppe...")
                        break
                    
                    print(f"Loop {self.current_loop} beendet, starte neu...")
                    self.current_frame = 0
                    continue
                
                rgb_values = self.cached_rgb_data[self.current_frame]
                self.current_frame += 1
                self.frames_processed += 1
                
                # Brightness anwenden (falls geändert)
                if self.brightness != 1.0:
                    rgb_array = np.array(rgb_values, dtype=np.float32)
                    rgb_array = (rgb_array * self.brightness).clip(0, 255).astype(np.uint8)
                    rgb_values = rgb_array.tolist()
                
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
                
                # Sende über Art-Net
                if self.artnet_manager:
                    self.artnet_manager.send_frame(dmx_buffer)
                
                # Frame-Timing
                frame_elapsed = time.time() - frame_start
                if frame_elapsed < frame_delay:
                    time.sleep(frame_delay - frame_elapsed)
        
        except Exception as e:
            print(f"Fehler während Cache-Wiedergabe: {e}")
        
        finally:
            self.is_running = False
            self.is_playing = False
            print("Wiedergabe gestoppt.")
    
    def start(self):
        """Startet die Video-Wiedergabe in Endlosschleife."""
        if self.is_playing:
            print("Video läuft bereits!")
            return
        
        self.is_playing = True
        self.thread = threading.Thread(target=self._play_loop, daemon=True)
        self.thread.start()
        print("Video gestartet (Endlosschleife)")
    
    def stop(self):
        """Stoppt die Video-Wiedergabe."""
        if not self.is_playing:
            print("Video läuft nicht!")
            return
        
        print("Stoppe Video...")
        self.is_running = False
        self.is_playing = False
        self.is_paused = False
        
        if self.thread:
            self.thread.join(timeout=2.0)
    
    def pause(self):
        """Pausiert die Wiedergabe."""
        if not self.is_playing:
            print("Video läuft nicht!")
            return
        if self.is_paused:
            print("Video ist bereits pausiert!")
            return
        self.is_paused = True
        print("Video pausiert")
    
    def resume(self):
        """Setzt die Wiedergabe fort."""
        if not self.is_playing:
            print("Video läuft nicht!")
            return
        if not self.is_paused:
            print("Video ist nicht pausiert!")
            return
        self.is_paused = False
        print("Wiedergabe fortgesetzt")
    
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
        print("Video neu gestartet")
    
    def set_fps(self, fps):
        """Ändert FPS-Limit während der Wiedergabe."""
        try:
            fps_val = float(fps)
            if fps_val <= 0:
                print("FPS muss größer als 0 sein!")
                return
            self.fps_limit = fps_val
            print(f"FPS-Limit gesetzt: {fps_val}")
        except ValueError:
            print("Ungültiger FPS-Wert!")
    
    def set_speed(self, factor):
        """Ändert Wiedergabe-Geschwindigkeit."""
        try:
            speed = float(factor)
            if speed <= 0:
                print("Speed-Faktor muss größer als 0 sein!")
                return
            self.speed_factor = speed
            print(f"Geschwindigkeit gesetzt: {speed}x")
        except ValueError:
            print("Ungültiger Speed-Wert!")
    
    def set_brightness(self, value):
        """Setzt globale Helligkeit (0-100)."""
        try:
            brightness = float(value)
            if brightness < 0 or brightness > 100:
                print("Helligkeit muss zwischen 0 und 100 sein!")
                return
            self.brightness = brightness / 100.0
            print(f"Helligkeit gesetzt: {brightness}%")
        except ValueError:
            print("Ungültiger Helligkeits-Wert!")
    
    def set_loop_limit(self, loops):
        """Setzt Loop-Limit (0 = unendlich)."""
        try:
            loop_val = int(loops)
            if loop_val < 0:
                print("Loop-Anzahl muss >= 0 sein!")
                return
            self.max_loops = loop_val
            if loop_val == 0:
                print("Loop-Limit: Unendlich")
            else:
                print(f"Loop-Limit gesetzt: {loop_val}")
        except ValueError:
            print("Ungültiger Loop-Wert!")
    
    def blackout(self):
        """Setzt alle DMX-Kanäle auf 0."""
        if self.artnet_manager:
            self.artnet_manager.blackout()
        else:
            print("Art-Net nicht aktiv!")
    
    def reload_artnet(self):
        """Lädt Art-Net mit neuer IP neu."""
        try:
            # Prüfe ob erforderliche Attribute existieren
            if not hasattr(self, 'total_points') or not hasattr(self, 'channels_per_universe'):
                print("⚠️ Art-Net kann nicht neu geladen werden - Player nicht vollständig initialisiert")
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
            
            print(f"✅ Art-Net neu geladen mit IP: {self.target_ip}")
            return True
        except Exception as e:
            print(f"❌ Fehler beim Neuladen von Art-Net: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_pattern(self, color='red'):
        """Sendet Testmuster (stoppt Video-Wiedergabe)."""
        if self.artnet_manager:
            self.artnet_manager.test_pattern(color)
        else:
            print("Art-Net nicht aktiv!")
    
    def start_recording(self):
        """Startet RGB-Daten-Aufzeichnung."""
        self.recorded_data = []
        self.is_recording = True
        print("Aufzeichnung gestartet")
    
    def stop_recording(self, filename=None):
        """Stoppt Aufzeichnung und speichert Daten."""
        if not self.is_recording:
            print("Keine Aufzeichnung aktiv!")
            return
        
        self.is_recording = False
        
        if not filename:
            filename = f"recording_{int(time.time())}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.recorded_data, f)
            print(f"Aufzeichnung gespeichert: {filename} ({len(self.recorded_data)} Frames)")
        except Exception as e:
            print(f"Fehler beim Speichern: {e}")
    
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
