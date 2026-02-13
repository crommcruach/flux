"""
Thumbnail Generator
Erstellt und cached Thumbnails für Videos und Bilder
"""
import os
import hashlib
from pathlib import Path
from PIL import Image
import cv2
import threading
from queue import Queue
from ..core.logger import get_logger

logger = get_logger(__name__)


class ThumbnailGenerator:
    """
    Generiert Thumbnails mit Caching und asynchroner Verarbeitung
    """
    
    def __init__(self, config=None):
        """
        Args:
            config: Dictionary mit Thumbnail-Konfiguration oder None für Defaults
        """
        # Load config with defaults
        if config is None:
            config = {}
        
        thumb_config = config.get('thumbnails', {})
        
        # Thumbnail settings
        cache_dir_config = thumb_config.get('cache_dir', 'thumbnails')
        self.cache_dir = Path(cache_dir_config)
        
        # Mache den Pfad absolut wenn er relativ ist
        if not self.cache_dir.is_absolute():
            # Gehe von src/modules aus zum Projektroot
            project_root = Path(__file__).parent.parent.parent
            self.cache_dir = project_root / self.cache_dir
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        size_config = thumb_config.get('size', [200, 200])
        self.size = tuple(size_config) if isinstance(size_config, list) else (200, 200)
        self.quality = thumb_config.get('quality', 85)
        self.cache_days = thumb_config.get('cache_days', 30)
        
        # Video preview settings
        preview_config = thumb_config.get('video_preview', {})
        self.video_preview_enabled = preview_config.get('enabled', True)
        self.video_preview_duration = preview_config.get('duration', 3.0)
        self.video_preview_fps = preview_config.get('fps', 10)
        self.video_preview_format = preview_config.get('format', 'gif')
        
        # Queue für asynchrone Generierung
        self.generation_queue = Queue()
        self.worker_thread = None
        self.running = False
        
        logger.info(f"🖼️ ThumbnailGenerator initialized: size={self.size}, quality={self.quality}, cache={self.cache_dir}")
        
    def start_worker(self):
        """Startet Worker-Thread für asynchrone Generierung"""
        if self.worker_thread and self.worker_thread.is_alive():
            return
            
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("🖼️ Thumbnail worker thread started")
        
    def stop_worker(self):
        """Stoppt Worker-Thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
            
    def _worker_loop(self):
        """Worker-Thread für Thumbnail-Generierung"""
        while self.running:
            try:
                task = self.generation_queue.get(timeout=1)
                if task:
                    file_path, callback = task
                    thumbnail_path = self._generate_thumbnail(file_path)
                    if callback:
                        callback(thumbnail_path)
            except:
                continue
                
    def get_thumbnail_path(self, file_path):
        """
        Gibt Pfad zum Thumbnail zurück (ohne Generierung)
        
        Returns:
            str: Pfad zum Thumbnail oder None wenn nicht existiert
        """
        cache_filename = self._get_cache_filename(file_path)
        thumbnail_path = self.cache_dir / cache_filename
        
        if thumbnail_path.exists():
            return str(thumbnail_path)
        return None
    
    def delete_thumbnail(self, file_path):
        """
        Löscht Thumbnail und Preview-Dateien für eine Datei
        
        Args:
            file_path: Pfad zur Original-Datei
            
        Returns:
            bool: True wenn Dateien gelöscht wurden, False wenn keine gefunden
        """
        try:
            deleted_any = False
            cache_filename = self._get_cache_filename(file_path)
            
            # Delete main thumbnail
            thumbnail_path = self.cache_dir / cache_filename
            if thumbnail_path.exists():
                thumbnail_path.unlink()
                logger.debug(f"Deleted thumbnail: {thumbnail_path}")
                deleted_any = True
            
            # Delete video preview files (GIF and WebM)
            for ext in ['.gif', '.webm']:
                preview_filename = cache_filename.replace('.jpg', f'_preview{ext}')
                preview_path = self.cache_dir / preview_filename
                if preview_path.exists():
                    preview_path.unlink()
                    logger.debug(f"Deleted video preview: {preview_path}")
                    deleted_any = True
            
            return deleted_any
            
        except Exception as e:
            logger.error(f"Error deleting thumbnail for {file_path}: {e}")
            return False
        
    def generate_thumbnail(self, file_path, async_mode=False, callback=None):
        """
        Generiert Thumbnail für Datei
        
        Args:
            file_path: Pfad zur Originaldatei
            async_mode: Wenn True, wird asynchron generiert
            callback: Optional callback für async_mode (wird mit Pfad aufgerufen)
            
        Returns:
            str: Pfad zum Thumbnail oder None bei Fehler
        """
        # Prüfe ob bereits cached
        existing = self.get_thumbnail_path(file_path)
        if existing:
            if callback:
                callback(existing)
            return existing
            
        if async_mode:
            # Async: In Queue einreihen
            self.generation_queue.put((file_path, callback))
            return None
        else:
            # Sync: Sofort generieren
            return self._generate_thumbnail(file_path)
            
    def _generate_thumbnail(self, file_path):
        """
        Interne Methode: Generiert Thumbnail
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                return None
                
            # Bestimme Cache-Dateiname
            cache_filename = self._get_cache_filename(file_path)
            thumbnail_path = self.cache_dir / cache_filename
            
            # Prüfe ob bereits existiert (Double-Check für Race Conditions)
            if thumbnail_path.exists():
                return str(thumbnail_path)
                
            # Generiere basierend auf Dateityp
            file_ext = file_path.suffix.lower()
            
            if file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']:
                # Video: Erstes Frame extrahieren
                success = self._generate_video_thumbnail(file_path, thumbnail_path)
            elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                # Bild: Resizen
                success = self._generate_image_thumbnail(file_path, thumbnail_path)
            else:
                logger.warning(f"Unsupported file type: {file_ext}")
                return None
                
            if success:
                logger.debug(f"✅ Generated thumbnail: {cache_filename}")
                return str(thumbnail_path)
            else:
                logger.warning(f"❌ Failed to generate thumbnail for: {file_path.name}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating thumbnail for {file_path}: {e}")
            return None
            
    def _generate_video_thumbnail(self, video_path, output_path):
        """Extrahiert erstes Frame aus Video"""
        try:
            cap = cv2.VideoCapture(str(video_path))
            
            # Lese erstes Frame
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                return False
                
            # Konvertiere BGR -> RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Erstelle PIL Image und resize
            img = Image.fromarray(frame_rgb)
            img.thumbnail(self.size, Image.Resampling.LANCZOS)
            
            # Speichere als JPEG
            img.save(output_path, 'JPEG', quality=self.quality, optimize=True)
            return True
            
        except Exception as e:
            logger.error(f"Error extracting video frame: {e}")
            return False
            
    def _generate_image_thumbnail(self, image_path, output_path):
        """Erstellt Thumbnail von Bild"""
        try:
            img = Image.open(image_path)
            
            # Konvertiere zu RGB falls nötig
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')
                
            # Resize
            img.thumbnail(self.size, Image.Resampling.LANCZOS)
            
            # Speichere als JPEG
            img.save(output_path, 'JPEG', quality=self.quality, optimize=True)
            return True
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return False
            
    def _get_cache_filename(self, file_path):
        """
        Generiert eindeutigen Cache-Dateinamen basierend auf Pfad + Timestamp
        """
        file_path = Path(file_path)
        
        # Hash aus Pfad + Modification Time (für Cache Invalidation)
        try:
            mtime = file_path.stat().st_mtime
        except:
            mtime = 0
            
        hash_input = f"{file_path.absolute()}_{mtime}".encode('utf-8')
        file_hash = hashlib.md5(hash_input).hexdigest()
        
        # Format: hash_originalname.jpg
        original_name = file_path.stem[:50]  # Max 50 Zeichen vom Original
        return f"{file_hash}_{original_name}.jpg"
        
    def generate_video_preview(self, video_path):
        """
        Generiert animiertes Preview (GIF oder WebM) für Video
        
        Args:
            video_path: Pfad zur Video-Datei
            
        Returns:
            str: Pfad zum Preview oder None bei Fehler
        """
        if not self.video_preview_enabled:
            return None
            
        try:
            video_path = Path(video_path)
            
            if not video_path.exists():
                return None
                
            # Bestimme Cache-Dateiname
            file_ext = '.gif' if self.video_preview_format == 'gif' else '.webm'
            cache_filename = self._get_cache_filename(video_path).replace('.jpg', f'_preview{file_ext}')
            preview_path = self.cache_dir / cache_filename
            
            # Prüfe ob bereits existiert
            if preview_path.exists():
                return str(preview_path)
                
            # Generiere Preview
            if self.video_preview_format == 'gif':
                success = self._generate_gif_preview(video_path, preview_path)
            else:
                success = self._generate_webm_preview(video_path, preview_path)
                
            if success:
                logger.debug(f"✅ Generated video preview: {cache_filename}")
                return str(preview_path)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error generating video preview: {e}")
            return None
            
    def _generate_gif_preview(self, video_path, output_path):
        """
        Generiert animiertes GIF aus Video
        """
        try:
            cap = cv2.VideoCapture(str(video_path))
            
            # Video-Eigenschaften
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            
            if total_frames == 0 or video_fps == 0:
                cap.release()
                return False
                
            # Berechne Frame-Intervall
            target_frames = int(self.video_preview_duration * self.video_preview_fps)
            frame_interval = max(1, int(video_fps / self.video_preview_fps))
            
            # Extrahiere Frames
            frames = []
            frame_count = 0
            
            while len(frames) < target_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                    
                if frame_count % frame_interval == 0:
                    # Konvertiere BGR -> RGB und resize
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    img.thumbnail(self.size, Image.Resampling.LANCZOS)
                    frames.append(img)
                    
                frame_count += 1
                
            cap.release()
            
            if len(frames) < 2:
                return False
                
            # Speichere als GIF
            frames[0].save(
                output_path,
                save_all=True,
                append_images=frames[1:],
                duration=int(1000 / self.video_preview_fps),  # ms per frame
                loop=0,
                optimize=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error generating GIF preview: {e}")
            return False
            
    def _generate_webm_preview(self, video_path, output_path):
        """
        Generiert WebM-Preview mit FFmpeg
        """
        try:
            import subprocess
            
            # FFmpeg command für kurzen Preview-Clip
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-t', str(self.video_preview_duration),
                '-vf', f'scale={self.size[0]}:{self.size[1]}:force_original_aspect_ratio=decrease',
                '-r', str(self.video_preview_fps),
                '-c:v', 'libvpx-vp9',
                '-b:v', '200k',
                '-an',  # No audio
                '-y',
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error generating WebM preview: {e}")
            return False
    
    def cleanup_old_thumbnails(self, days=None):
        """
        Löscht Thumbnails älter als X Tage
        
        Args:
            days: Anzahl Tage (None = nutzt self.cache_days)
            
        Returns:
            int: Anzahl gelöschter Dateien
        """
        import time
        
        if days is None:
            days = self.cache_days
        
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        deleted_count = 0
        
        try:
            for thumbnail in self.cache_dir.glob('*'):
                if thumbnail.is_file() and thumbnail.stat().st_mtime < cutoff_time:
                    thumbnail.unlink()
                    deleted_count += 1
                    
            logger.info(f"🗑️ Cleaned up {deleted_count} old thumbnails/previews")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning thumbnails: {e}")
            return deleted_count
            
    def get_cache_stats(self):
        """
        Gibt Cache-Statistiken zurück
        
        Returns:
            dict: Stats (count, total_size_mb)
        """
        try:
            # Count all files (thumbnails + previews)
            all_files = list(self.cache_dir.glob('*'))
            total_size = sum(f.stat().st_size for f in all_files if f.is_file())
            
            return {
                'count': len(all_files),
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'cache_dir': str(self.cache_dir)
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {'count': 0, 'total_size_mb': 0, 'error': str(e)}
