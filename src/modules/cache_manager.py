"""
Cache Manager - Verwaltet RGB-Cache für Videos
"""
import os
import hashlib
from .logger import get_logger
from .constants import (
    CACHE_CHUNK_SIZE,
    CACHE_HASH_LENGTH,
    DEFAULT_FPS
)

logger = get_logger(__name__)

try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False
    logger.warning("msgpack nicht installiert - Cache-Funktion deaktiviert")


class CacheManager:
    """Verwaltet RGB-Cache für Videos."""
    
    def __init__(self, cache_dir, enabled=True):
        """
        Initialisiert Cache Manager.
        
        Args:
            cache_dir: Verzeichnis für Cache-Dateien
            enabled: Ob Cache aktiviert sein soll
        """
        self.cache_dir = cache_dir
        self.enabled = enabled and MSGPACK_AVAILABLE
        
        if self.enabled and not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            logger.info(f"Cache-Verzeichnis erstellt: {cache_dir}")
    
    def get_cache_path(self, video_path, points_json_path, canvas_width, canvas_height):
        """
        Generiert Cache-Dateinamen basierend auf Video-Inhalt und Points Hash.
        
        Args:
            video_path: Pfad zur Video-Datei
            points_json_path: Pfad zur Points-JSON
            canvas_width: Canvas-Breite
            canvas_height: Canvas-Höhe
            
        Returns:
            str: Pfad zur Cache-Datei oder None bei Fehler
        """
        if not self.enabled:
            return None
        
        try:
            video_hash = self._get_video_hash(video_path)
            points_hash = hashlib.md5(open(points_json_path, 'rb').read()).hexdigest()[:8]
            canvas_hash = hashlib.md5(f"{canvas_width}x{canvas_height}".encode()).hexdigest()[:8]
            
            file_hash = f"{video_hash}_{points_hash}_{canvas_hash}"
            return os.path.join(self.cache_dir, f"{file_hash}.msgpack")
        except Exception as e:
            logger.error(f"Fehler beim Berechnen des Cache-Hash: {e}")
            return None
    
    def _get_video_hash(self, video_path):
        """
        Berechnet eindeutigen Hash für Video-Datei (schnelle Methode).
        
        Args:
            video_path: Pfad zur Video-Datei
            
        Returns:
            str: Hash-String
        """
        chunk_size = CACHE_CHUNK_SIZE
        file_size = os.path.getsize(video_path)
        
        hash_md5 = hashlib.md5()
        hash_md5.update(str(file_size).encode())
        
        with open(video_path, 'rb') as f:
            # Lese ersten Chunk
            chunk = f.read(chunk_size)
            hash_md5.update(chunk)
            
            # Wenn Datei größer, lese auch letzten Chunk
            if file_size > chunk_size:
                f.seek(-min(chunk_size, file_size - chunk_size), 2)
                chunk = f.read(chunk_size)
                hash_md5.update(chunk)
        
        return hash_md5.hexdigest()[:CACHE_HASH_LENGTH]
    
    def load_cache(self, cache_path):
        """
        Lädt gecachte RGB-Daten.
        
        Args:
            cache_path: Pfad zur Cache-Datei
            
        Returns:
            dict: Cache-Daten oder None bei Fehler
            {
                'frames': list,  # Liste von RGB-Daten pro Frame
                'video_fps': float,
                'is_gif': bool,
                'gif_frame_delays': list or None
            }
        """
        if not self.enabled or not cache_path or not os.path.exists(cache_path):
            return None
        
        try:
            logger.info(f"Lade RGB-Cache: {os.path.basename(cache_path)}")
            with open(cache_path, 'rb') as f:
                cache_data = msgpack.unpackb(f.read(), raw=False)
            
            # Validiere Cache-Format
            if not isinstance(cache_data, dict) or 'frames' not in cache_data:
                logger.warning("Ungültiges Cache-Format")
                return None
            
            file_size_mb = os.path.getsize(cache_path) / (1024*1024)
            frame_count = len(cache_data['frames'])
            fps = cache_data.get('video_fps', DEFAULT_FPS)
            
            logger.info(f"Cache geladen: {frame_count} Frames, {file_size_mb:.2f} MB, {fps} FPS")
            
            return cache_data
            
        except Exception as e:
            logger.error(f"Fehler beim Laden des Cache: {e}", exc_info=True)
            return None
    
    def save_cache(self, cache_path, rgb_frames, video_fps, is_gif=False, gif_frame_delays=None):
        """
        Speichert RGB-Daten als Cache.
        
        Args:
            cache_path: Pfad zur Cache-Datei
            rgb_frames: Liste von RGB-Daten pro Frame
            video_fps: FPS des Videos
            is_gif: Ob es ein GIF ist
            gif_frame_delays: Frame-Delays für GIFs
            
        Returns:
            bool: True bei Erfolg, False bei Fehler
        """
        if not self.enabled or not cache_path:
            return False
        
        try:
            logger.info(f"Speichere RGB-Cache: {os.path.basename(cache_path)}")
            
            cache_data = {
                'frames': rgb_frames,
                'video_fps': video_fps,
                'is_gif': is_gif,
                'gif_frame_delays': gif_frame_delays
            }
            
            with open(cache_path, 'wb') as f:
                f.write(msgpack.packb(cache_data, use_bin_type=True))
            
            file_size_mb = os.path.getsize(cache_path) / (1024*1024)
            logger.info(f"Cache gespeichert: {len(rgb_frames)} Frames, {file_size_mb:.2f} MB")
            
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Cache: {e}", exc_info=True)
            return False
    
    def clear_cache(self):
        """Löscht alle Cache-Dateien."""
        if not self.enabled or not os.path.exists(self.cache_dir):
            return 0
        
        deleted = 0
        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.msgpack'):
                try:
                    os.remove(os.path.join(self.cache_dir, filename))
                    deleted += 1
                except Exception as e:
                    logger.error(f"Fehler beim Löschen von {filename}: {e}")
        
        logger.info(f"Cache geleert: {deleted} Dateien gelöscht")
        return deleted
    
    def get_cache_stats(self):
        """
        Gibt Cache-Statistiken zurück.
        
        Returns:
            dict: {'total_files': int, 'total_size_mb': float}
        """
        if not self.enabled or not os.path.exists(self.cache_dir):
            return {'total_files': 0, 'total_size_mb': 0.0}
        
        total_files = 0
        total_size = 0
        
        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.msgpack'):
                total_files += 1
                total_size += os.path.getsize(os.path.join(self.cache_dir, filename))
        
        return {
            'total_files': total_files,
            'total_size_mb': total_size / (1024*1024)
        }
