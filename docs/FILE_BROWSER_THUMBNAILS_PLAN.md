# 🔍 File Browser Thumbnails & Multi-Select - Implementierungsplan

## 📋 Übersicht

**Ziel:** Visuelles Datei-Browsing mit Thumbnails, Video-Preview und Mehrfachauswahl für Batch-Operationen

**Geschätzte Zeit:** 10-16 Stunden
- Phase 1: Thumbnail-Generierung Backend (3-4h)
- Phase 2: Thumbnail-Anzeige Frontend (2-3h)
- Phase 3: Video-Preview System (2-3h) ✨ NEU
- Phase 4: Multi-Select System (3-5h)
- Phase 5: Performance & Polish (1-2h)

## ⚙️ Konfiguration

**Alle Einstellungen sind anpassbar über `config.json`:**

```json
{
  "thumbnails": {
    "enabled": true,
    "size": [200, 200],
    "quality": 85,
    "cache_dir": "data/thumbnails",
    "cache_days": 30,
    "video_preview": {
      "enabled": true,
      "duration": 3.0,
      "fps": 10,
      "format": "gif"
    }
  }
}
```

**Parameter:**
- `size`: Thumbnail-Größe [width, height] in Pixel
- `quality`: JPEG-Qualität 0-100
- `cache_dir`: Verzeichnis für Thumbnail-Cache
- `cache_days`: Anzahl Tage bis Cache-Bereinigung
- `video_preview.enabled`: Video-Preview im Modal (Click auf File)
- `video_preview.duration`: Länge des Preview-Clips in Sekunden
- `video_preview.fps`: Frames pro Sekunde für Preview
- `video_preview.format`: "gif" oder "webm"

---

## 🏗️ Architektur-Analyse

### Aktuelle Code-Struktur

**Frontend:**
- `frontend/js/components/files-tab.js` - Wiederverwendbare File-Browser-Komponente
  - Unterstützt bereits `list` und `tree` View-Modes
  - Hat `enableMultiselect` Flag (noch nicht implementiert)
  - Hat `selectedFiles: Set()` (vorbereitet für Multi-Select)
  - Drag & Drop bereits implementiert

**Backend:**
- `src/modules/api_files.py` - File Browser REST API
  - `/api/files/tree` - Hierarchische Ordnerstruktur
  - `/api/files/videos` - Flache Liste aller Videos/Bilder
  - Unterstützt bereits Videos + Bilder
  - Multiple Video-Quellen (config.paths.video_sources)

**Verwendung:**
- `frontend/player.html` - Hauptseite mit File Browser
- `frontend/converter.html` - Video-Converter mit File Browser
- Wird auch in anderen Modulen verwendet

---

## 📦 Phase 1: Thumbnail-Generierung Backend (3-4h)

### 1.1 Thumbnail-System erstellen

**Neue Datei:** `src/modules/thumbnail_generator.py`

```python
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
from .logger import get_logger

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
        self.cache_dir = Path(thumb_config.get('cache_dir', 'data/thumbnails'))
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
```

### 1.2 REST API Endpoints erweitern

**Datei:** `src/modules/api_files.py`

**Neue Endpoints hinzufügen:**

```python
# Nach den bestehenden Imports
from .thumbnail_generator import ThumbnailGenerator

# In register_files_api() nach Funktionsdefinition:
    # Initialisiere Thumbnail-Generator mit Config
    thumbnail_gen = ThumbnailGenerator(config=config)
    thumbnail_gen.start_worker()
    
    @app.route('/api/files/thumbnail/<path:file_path>', methods=['GET'])
    def get_thumbnail(file_path):
        """
        Gibt Thumbnail für Datei zurück
        
        Query Parameters:
            - generate: 'true' um Thumbnail zu generieren falls nicht existiert
        """
        from flask import send_file, request
        
        try:
            # Decode file path
            import urllib.parse
            file_path = urllib.parse.unquote(file_path)
            
            # Finde vollständigen Pfad in Video-Quellen
            full_path = None
            for source_path in get_video_sources():
                potential_path = os.path.join(source_path, file_path)
                if os.path.exists(potential_path):
                    full_path = potential_path
                    break
                    
            if not full_path:
                return jsonify({
                    'success': False,
                    'error': 'File not found'
                }), 404
                
            # Prüfe ob generieren gewünscht
            should_generate = request.args.get('generate', 'false').lower() == 'true'
            
            # Versuche Thumbnail zu laden
            thumbnail_path = thumbnail_gen.get_thumbnail_path(full_path)
            
            if not thumbnail_path and should_generate:
                # Generiere synchron
                thumbnail_path = thumbnail_gen.generate_thumbnail(full_path, async_mode=False)
                
            if thumbnail_path and os.path.exists(thumbnail_path):
                return send_file(
                    thumbnail_path,
                    mimetype='image/jpeg',
                    max_age=86400  # Cache 24h
                )
            else:
                return jsonify({
                    'success': False,
                    'error': 'Thumbnail not available'
                }), 404
                
        except Exception as e:
            logger.error(f"Error serving thumbnail: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
            
    @app.route('/api/files/thumbnails/batch', methods=['POST'])
    def generate_thumbnails_batch():
        """
        Generiert Thumbnails für mehrere Dateien asynchron
        
        Request Body:
            {
                "files": ["path/to/file1.mp4", "path/to/file2.jpg"]
            }
        """
        from flask import request
        
        try:
            data = request.get_json()
            file_paths = data.get('files', [])
            
            if not file_paths:
                return jsonify({
                    'success': False,
                    'error': 'No files provided'
                }), 400
                
            # Finde vollständige Pfade
            full_paths = []
            for file_path in file_paths:
                for source_path in get_video_sources():
                    potential_path = os.path.join(source_path, file_path)
                    if os.path.exists(potential_path):
                        full_paths.append(potential_path)
                        break
                        
            # Queue für asynchrone Generierung
            for full_path in full_paths:
                thumbnail_gen.generate_thumbnail(full_path, async_mode=True)
                
            return jsonify({
                'success': True,
                'queued': len(full_paths),
                'message': f'Queued {len(full_paths)} thumbnails for generation'
            })
            
        except Exception as e:
            logger.error(f"Error queueing thumbnails: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
            
    @app.route('/api/files/thumbnails/stats', methods=['GET'])
    def get_thumbnail_stats():
        """Gibt Cache-Statistiken zurück"""
        try:
            stats = thumbnail_gen.get_cache_stats()
            return jsonify({
                'success': True,
                'stats': stats
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
            
    @app.route('/api/files/thumbnails/cleanup', methods=['POST'])
    def cleanup_thumbnails():
        """Löscht alte Thumbnails"""
        from flask import request
        
        try:
            data = request.get_json() or {}
            days = data.get('days', None)  # None = use config default
            
            deleted = thumbnail_gen.cleanup_old_thumbnails(days)
            
            return jsonify({
                'success': True,
                'deleted': deleted,
                'message': f'Deleted {deleted} thumbnails/previews'
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
            
    @app.route('/api/files/video-preview/<path:file_path>', methods=['GET'])
    def get_video_preview(file_path):
        """
        Gibt animiertes Video-Preview zurück (GIF oder WebM)
        
        Query Parameters:
            - generate: 'true' um Preview zu generieren falls nicht existiert
        """
        from flask import send_file, request
        import urllib.parse
        
        try:
            # Decode file path
            file_path = urllib.parse.unquote(file_path)
            
            # Finde vollständigen Pfad
            full_path = None
            for source_path in get_video_sources():
                potential_path = os.path.join(source_path, file_path)
                if os.path.exists(potential_path):
                    full_path = potential_path
                    break
                    
            if not full_path:
                return jsonify({
                    'success': False,
                    'error': 'File not found'
                }), 404
                
            # Prüfe ob generieren gewünscht
            should_generate = request.args.get('generate', 'false').lower() == 'true'
            
            # Versuche Preview zu laden
            preview_path = None
            if should_generate:
                preview_path = thumbnail_gen.generate_video_preview(full_path)
            else:
                # Check if preview exists
                cache_filename = thumbnail_gen._get_cache_filename(Path(full_path))
                file_ext = '.gif' if thumbnail_gen.video_preview_format == 'gif' else '.webm'
                preview_filename = cache_filename.replace('.jpg', f'_preview{file_ext}')
                potential_preview = thumbnail_gen.cache_dir / preview_filename
                if potential_preview.exists():
                    preview_path = str(potential_preview)
                    
            if preview_path and os.path.exists(preview_path):
                mimetype = 'image/gif' if preview_path.endswith('.gif') else 'video/webm'
                return send_file(
                    preview_path,
                    mimetype=mimetype,
                    max_age=86400  # Cache 24h
                )
            else:
                return jsonify({
                    'success': False,
                    'error': 'Preview not available'
                }), 404
                
        except Exception as e:
            logger.error(f"Error serving video preview: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
```

### 1.3 API in file list/tree integrieren

**Datei:** `src/modules/api_files.py`

In den bestehenden Endpoints `/api/files/videos` und `/api/files/tree` Thumbnail-Verfügbarkeit hinzufügen:

```python
# In get_all_videos() - nach file_type bestimmen:
                            # Prüfe ob Thumbnail existiert
                            has_thumbnail = thumbnail_gen.get_thumbnail_path(filepath) is not None
                            
                            files_list.append({
                                "filename": filename,
                                "path": rel_path.replace("\\", "/"),
                                "full_path": filepath,
                                "source": source_name,
                                "source_path": source_path,
                                "folder": folder_name,
                                "size": file_size,
                                "size_human": _format_size(file_size),
                                "type": file_type,
                                "has_thumbnail": has_thumbnail  # NEU
                            })

# In get_file_tree() - nach file_type bestimmen:
                        has_thumbnail = thumbnail_gen.get_thumbnail_path(full_path) is not None
                        
                        file_info = {
                            "type": file_type,
                            "name": entry,
                            "path": rel_path.replace("\\", "/"),
                            "size": file_size,
                            "size_human": _format_size(file_size),
                            "has_thumbnail": has_thumbnail  # NEU
                        }
```

---

## 🎨 Phase 2: Thumbnail-Anzeige Frontend (2-3h)

### 2.1 CSS für Thumbnails

**Neue Datei:** `frontend/css/thumbnails.css`

```css
/* Thumbnail Display Styles */

.file-list-item.with-thumbnail {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.file-thumbnail {
    width: 50px;
    height: 50px;
    object-fit: cover;
    border-radius: 4px;
    flex-shrink: 0;
    background: #f8f9fa;
    border: 1px solid #dee2e6;
}

.file-thumbnail.loading {
    background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

.file-thumbnail-placeholder {
    width: 50px;
    height: 50px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    font-size: 24px;
    flex-shrink: 0;
}

/* Thumbnail Preview on Hover */
.file-thumbnail-preview {
    position: absolute;
    z-index: 1000;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.2s;
}

.file-thumbnail-preview.show {
    opacity: 1;
}

.file-thumbnail-preview img {
    width: 200px;
    height: 200px;
    object-fit: contain;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    background: #000;
    border: 2px solid #fff;
}

/* Tree View with Thumbnails */
.tree-node.file.with-thumbnail {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.tree-node .file-thumbnail {
    width: 40px;
    height: 40px;
}

/* Thumbnail Toggle Button */
.thumbnail-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.thumbnail-toggle input[type="checkbox"] {
    cursor: pointer;
}

/* Thumbnail Settings Panel */
.thumbnail-settings {
    padding: 0.5rem;
    background: #f8f9fa;
    border-radius: 4px;
    margin-bottom: 0.5rem;
}

.thumbnail-settings .btn-group {
    display: flex;
    gap: 0.5rem;
}
```

### 2.2 FilesTab Component erweitern

**Datei:** `frontend/js/components/files-tab.js`

**Änderungen im Constructor:**

```javascript
constructor(containerId, searchContainerId, viewMode = 'list', enableMultiselect = false, enableThumbnails = false) {
    // ... bestehender Code ...
    
    // NEU: Thumbnail-Unterstützung
    this.enableThumbnails = enableThumbnails;
    this.showThumbnails = enableThumbnails; // User kann toggle
    this.thumbnailCache = new Map(); // Cache für geladene Thumbnails
    this.thumbnailPreview = null; // Hover-Preview Element
}
```

**Neue Methode: setupThumbnails()**

```javascript
/**
 * Setup thumbnail controls
 */
setupThumbnails() {
    if (!this.enableThumbnails) return;
    
    const searchContainer = document.getElementById(this.searchContainerId);
    if (!searchContainer) return;
    
    // Füge Thumbnail-Toggle hinzu
    const controlsDiv = document.createElement('div');
    controlsDiv.className = 'thumbnail-settings';
    controlsDiv.innerHTML = `
        <div class="thumbnail-toggle">
            <input type="checkbox" id="${this.containerId}-thumbnail-toggle" 
                   ${this.showThumbnails ? 'checked' : ''}>
            <label for="${this.containerId}-thumbnail-toggle">
                🖼️ Show Thumbnails
            </label>
        </div>
        <div class="btn-group">
            <button class="btn btn-sm btn-outline-secondary" 
                    id="${this.containerId}-generate-visible"
                    title="Generate thumbnails for visible files">
                ⚡ Generate Visible
            </button>
            <button class="btn btn-sm btn-outline-secondary" 
                    id="${this.containerId}-generate-all"
                    title="Generate thumbnails for all files">
                🔄 Generate All
            </button>
        </div>
    `;
    
    searchContainer.insertBefore(controlsDiv, searchContainer.firstChild);
    
    // Event Listeners
    document.getElementById(`${this.containerId}-thumbnail-toggle`).addEventListener('change', (e) => {
        this.showThumbnails = e.target.checked;
        this.render();
    });
    
    document.getElementById(`${this.containerId}-generate-visible`).addEventListener('click', () => {
        this.generateThumbnailsForVisible();
    });
    
    document.getElementById(`${this.containerId}-generate-all`).addEventListener('click', () => {
        this.generateThumbnailsForAll();
    });
    
    // Erstelle Preview-Container für Hover
    this.createThumbnailPreview();
}

/**
 * Create thumbnail preview element for hover
 */
createThumbnailPreview() {
    this.thumbnailPreview = document.createElement('div');
    this.thumbnailPreview.className = 'file-thumbnail-preview';
    this.thumbnailPreview.innerHTML = '<img src="" alt="Preview">';
    document.body.appendChild(this.thumbnailPreview);
}
```

**Neue Methode: getThumbnailUrl()**

```javascript
/**
 * Get thumbnail URL for file
 */
getThumbnailUrl(filePath, generate = false) {
    const encodedPath = encodeURIComponent(filePath);
    return `/api/files/thumbnail/${encodedPath}${generate ? '?generate=true' : ''}`;
}

/**
 * Load thumbnail for file
 */
async loadThumbnail(filePath, imgElement) {
    // Check cache
    if (this.thumbnailCache.has(filePath)) {
        imgElement.src = this.thumbnailCache.get(filePath);
        imgElement.classList.remove('loading');
        return;
    }
    
    // Set loading state
    imgElement.classList.add('loading');
    
    try {
        // Try to get existing thumbnail
        const url = this.getThumbnailUrl(filePath, false);
        const response = await fetch(url);
        
        if (response.ok) {
            const blob = await response.blob();
            const objectUrl = URL.createObjectURL(blob);
            this.thumbnailCache.set(filePath, objectUrl);
            imgElement.src = objectUrl;
        } else {
            // Generate on-demand
            const generateUrl = this.getThumbnailUrl(filePath, true);
            const generateResponse = await fetch(generateUrl);
            
            if (generateResponse.ok) {
                const blob = await generateResponse.blob();
                const objectUrl = URL.createObjectURL(blob);
                this.thumbnailCache.set(filePath, objectUrl);
                imgElement.src = objectUrl;
            } else {
                // Failed - show placeholder
                imgElement.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error loading thumbnail:', error);
        imgElement.style.display = 'none';
    } finally {
        imgElement.classList.remove('loading');
    }
}
```

**Änderung: renderListItem() mit Thumbnail-Unterstützung**

```javascript
/**
 * Render single list item with optional thumbnail
 */
renderListItem(file) {
    const icon = file.type === 'video' ? '🎬' : '🖼️';
    const isSelected = this.selectedFiles.has(file.path);
    
    let html = `
        <div class="file-list-item ${isSelected ? 'selected' : ''} ${this.showThumbnails ? 'with-thumbnail' : ''}" 
             data-path="${file.path}"
             data-type="${file.type}"
             draggable="true">
    `;
    
    if (this.showThumbnails) {
        if (file.has_thumbnail) {
            html += `
                <img class="file-thumbnail loading" 
                     data-path="${file.path}"
                     alt="${file.filename}">
            `;
        } else {
            html += `<div class="file-thumbnail-placeholder">${icon}</div>`;
        }
    }
    
    html += `
            <div class="file-info flex-grow-1">
                <div class="file-name">${!this.showThumbnails ? icon + ' ' : ''}${file.filename}</div>
                <div class="file-meta">${file.folder} · ${file.size_human}</div>
            </div>
        </div>
    `;
    
    return html;
}
```

**Init-Methode erweitern:**

```javascript
async init() {
    this.setupSearch();
    if (this.viewMode === 'button') {
        this.setupViewToggle();
    }
    if (this.enableThumbnails) {
        this.setupThumbnails();
        this.createThumbnailModal();  // Create preview modal
    }
    await this.loadFiles();
}
```

**Nach dem Render: Thumbnails laden**

```javascript
/**
 * Load thumbnails for rendered items
 */
loadVisibleThumbnails() {
    if (!this.showThumbnails) return;
    
    const container = document.getElementById(this.containerId);
    const thumbnails = container.querySelectorAll('.file-thumbnail.loading');
    
    thumbnails.forEach(img => {
        const filePath = img.dataset.path;
        if (filePath) {
            this.loadThumbnail(filePath, img);
        }
    });
    
    // Setup hover previews
    this.setupThumbnailHoverPreviews();
}

// In render() am Ende aufrufen:
render() {
    // ... bestehender Code ...
    
    // Load thumbnails after render
    if (this.showThumbnails) {
        setTimeout(() => this.loadVisibleThumbnails(), 100);
    }
}

/**
 * Create file preview modal
 */
createThumbnailModal() {
    // Modal implementation - see Phase 3.1
}
```

**Hover-Preview:**

```javascript
/**
 * Setup thumbnail hover previews
 */
setupThumbnailHoverPreviews() {
    const container = document.getElementById(this.containerId);
    const thumbnails = container.querySelectorAll('.file-thumbnail');
    
    thumbnails.forEach(thumb => {
        thumb.addEventListener('mouseenter', (e) => {
            const filePath = thumb.dataset.path;
            if (!filePath || !this.thumbnailCache.has(filePath)) return;
            
            const previewImg = this.thumbnailPreview.querySelector('img');
            previewImg.src = this.thumbnailCache.get(filePath);
            
            // Position near mouse
            const rect = thumb.getBoundingClientRect();
            this.thumbnailPreview.style.left = (rect.right + 10) + 'px';
            this.thumbnailPreview.style.top = rect.top + 'px';
            this.thumbnailPreview.classList.add('show');
        });
        
        thumb.addEventListener('mouseleave', () => {
            this.thumbnailPreview.classList.remove('show');
        });
    });
}
```

**Batch-Generierung:**

```javascript
/**
 * Generate thumbnails for visible files
 */
async generateThumbnailsForVisible() {
    const files = this.filteredFiles
        .filter(f => !f.has_thumbnail)
        .map(f => f.path);
        
    if (files.length === 0) {
        alert('All visible files already have thumbnails');
        return;
    }
    
    try {
        const response = await fetch('/api/files/thumbnails/batch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ files })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`Queued ${data.queued} thumbnails for generation`);
            // Reload after 3 seconds
            setTimeout(() => this.loadFiles(), 3000);
        }
    } catch (error) {
        console.error('Error generating thumbnails:', error);
        alert('Failed to generate thumbnails');
    }
}

/**
 * Generate thumbnails for all files
 */
async generateThumbnailsForAll() {
    if (!confirm('Generate thumbnails for all files? This may take a while.')) {
        return;
    }
    
    const files = this.files
        .filter(f => !f.has_thumbnail)
        .map(f => f.path);
        
    // ... rest similar to generateThumbnailsForVisible
}
```

---

## 🎬 Phase 3: Video-Preview System (2-3h) ✨

### 3.1 Frontend Video-Preview Modal

**Konzept:**
- **Hover:** Zeigt statisches Thumbnail (wie bei Bildern)
- **Click:** Öffnet Modal mit animierter Video-Preview + Datei-Info
- **Modal-Inhalt:** Animierte Preview, Filename, Duration, Size, Resolution

**Datei:** `frontend/js/components/files-tab.js`

**File-Click Handler erweitern:**

```javascript
/**
 * Setup thumbnail hover previews (static only)
 */
setupThumbnailHoverPreviews() {
    const container = document.getElementById(this.containerId);
    const thumbnails = container.querySelectorAll('.file-thumbnail');
    
    thumbnails.forEach(thumb => {
        thumb.addEventListener('mouseenter', (e) => {
            const filePath = thumb.dataset.path;
            
            if (!filePath || !this.thumbnailCache.has(filePath)) return;
            
            // Show static preview for all file types
            this.showStaticPreview(filePath, thumb);
        });
        
        thumb.addEventListener('mouseleave', () => {
            this.thumbnailPreview.classList.remove('show');
        });
    });
}

/**
 * Show static preview (hover)
 */
showStaticPreview(filePath, thumbElement) {
    const previewImg = this.thumbnailPreview.querySelector('img');
    previewImg.src = this.thumbnailCache.get(filePath);
    
    // Position near mouse
    const rect = thumbElement.getBoundingClientRect();
    this.thumbnailPreview.style.left = (rect.right + 10) + 'px';
    this.thumbnailPreview.style.top = rect.top + 'px';
    this.thumbnailPreview.classList.add('show');
}

/**
 * Create file preview modal
 */
createThumbnailModal() {
    const modal = document.createElement('div');
    modal.id = `${this.containerId}-preview-modal`;
    modal.className = 'file-preview-modal';
    modal.innerHTML = `
        <div class="file-preview-modal-backdrop"></div>
        <div class="file-preview-modal-content">
            <button class="file-preview-modal-close">&times;</button>
            <div class="file-preview-modal-body">
                <div class="file-preview-media">
                    <div class="loading-spinner">Loading...</div>
                </div>
                <div class="file-preview-info">
                    <h4 class="file-preview-filename"></h4>
                    <div class="file-preview-meta">
                        <span class="meta-item"><strong>Type:</strong> <span class="meta-type"></span></span>
                        <span class="meta-item"><strong>Size:</strong> <span class="meta-size"></span></span>
                        <span class="meta-item"><strong>Path:</strong> <span class="meta-path"></span></span>
                    </div>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    
    // Close handlers
    modal.querySelector('.file-preview-modal-close').addEventListener('click', () => {
        this.closePreviewModal();
    });
    
    modal.querySelector('.file-preview-modal-backdrop').addEventListener('click', () => {
        this.closePreviewModal();
    });
    
    // ESC key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.classList.contains('show')) {
            this.closePreviewModal();
        }
    });
    
    this.previewModal = modal;
}

/**
 * Show file preview modal (with video preview for videos)
 */
async showFilePreviewModal(filePath, fileInfo) {
    if (!this.previewModal) {
        this.createThumbnailModal();
    }
    
    const modal = this.previewModal;
    const mediaContainer = modal.querySelector('.file-preview-media');
    const filename = modal.querySelector('.file-preview-filename');
    const metaType = modal.querySelector('.meta-type');
    const metaSize = modal.querySelector('.meta-size');
    const metaPath = modal.querySelector('.meta-path');
    
    // Show modal
    modal.classList.add('show');
    
    // Set file info
    filename.textContent = fileInfo.filename || filePath.split('/').pop();
    metaType.textContent = fileInfo.type || 'unknown';
    metaSize.textContent = fileInfo.size_human || '—';
    metaPath.textContent = fileInfo.path || filePath;
    
    // Show loading
    mediaContainer.innerHTML = '<div class="loading-spinner">Loading preview...</div>';
    
    try {
        if (fileInfo.type === 'video') {
            // Try to load video preview
            const encodedPath = encodeURIComponent(filePath);
            const previewUrl = `/api/files/video-preview/${encodedPath}?generate=true`;
            
            const response = await fetch(previewUrl);
            
            if (response.ok) {
                const blob = await response.blob();
                const objectUrl = URL.createObjectURL(blob);
                const contentType = response.headers.get('content-type');
                
                if (contentType.includes('image/gif')) {
                    // Show GIF
                    mediaContainer.innerHTML = `
                        <img src="${objectUrl}" alt="Video preview" class="preview-media">
                    `;
                } else if (contentType.includes('video/webm')) {
                    // Show WebM video
                    mediaContainer.innerHTML = `
                        <video autoplay loop muted playsinline controls class="preview-media">
                            <source src="${objectUrl}" type="video/webm">
                        </video>
                    `;
                }
            } else {
                // Fallback: Show static thumbnail
                await this.showStaticThumbnailInModal(filePath, mediaContainer);
            }
        } else if (fileInfo.type === 'image') {
            // For images: Show full image
            await this.showStaticThumbnailInModal(filePath, mediaContainer);
        } else {
            mediaContainer.innerHTML = '<div class="no-preview">No preview available</div>';
        }
    } catch (error) {
        console.error('Error loading preview:', error);
        mediaContainer.innerHTML = '<div class="error-preview">Failed to load preview</div>';
    }
}

/**
 * Show static thumbnail in modal (fallback)
 */
async showStaticThumbnailInModal(filePath, container) {
    if (this.thumbnailCache.has(filePath)) {
        container.innerHTML = `
            <img src="${this.thumbnailCache.get(filePath)}" alt="Preview" class="preview-media">
        `;
    } else {
        // Try to load thumbnail
        const encodedPath = encodeURIComponent(filePath);
        const thumbUrl = `/api/files/thumbnail/${encodedPath}?generate=true`;
        
        const response = await fetch(thumbUrl);
        if (response.ok) {
            const blob = await response.blob();
            const objectUrl = URL.createObjectURL(blob);
            container.innerHTML = `
                <img src="${objectUrl}" alt="Preview" class="preview-media">
            `;
        } else {
            container.innerHTML = '<div class="no-preview">No preview available</div>';
        }
    }
}

/**
 * Close preview modal
 */
closePreviewModal() {
    if (this.previewModal) {
        this.previewModal.classList.remove('show');
        
        // Clean up media to stop videos
        const mediaContainer = this.previewModal.querySelector('.file-preview-media');
        mediaContainer.innerHTML = '';
    }
}
```

**CSS für Preview-Modal:**

```css
/* File Preview Modal */
.file-preview-modal {
    display: none;
    position: fixed;
    z-index: 10000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
}

.file-preview-modal.show {
    display: flex;
    align-items: center;
    justify-content: center;
}

.file-preview-modal-backdrop {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.8);
}

.file-preview-modal-content {
    position: relative;
    background: #fff;
    border-radius: 12px;
    max-width: 90vw;
    max-height: 90vh;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
    display: flex;
    flex-direction: column;
}

.file-preview-modal-close {
    position: absolute;
    top: 10px;
    right: 10px;
    width: 36px;
    height: 36px;
    border: none;
    background: rgba(0, 0, 0, 0.6);
    color: white;
    font-size: 24px;
    cursor: pointer;
    border-radius: 50%;
    z-index: 10;
    transition: background 0.2s;
}

.file-preview-modal-close:hover {
    background: rgba(0, 0, 0, 0.8);
}

.file-preview-modal-body {
    display: flex;
    flex-direction: column;
    padding: 1rem;
    gap: 1rem;
}

.file-preview-media {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 400px;
    background: #000;
    border-radius: 8px;
}

.file-preview-media .preview-media {
    max-width: 100%;
    max-height: 60vh;
    object-fit: contain;
}

.file-preview-media video.preview-media {
    width: 100%;
    max-width: 800px;
}

.file-preview-info {
    padding: 1rem;
    background: #f8f9fa;
    border-radius: 8px;
}

.file-preview-filename {
    margin: 0 0 0.5rem 0;
    font-size: 1.25rem;
    font-weight: 600;
}

.file-preview-meta {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: #666;
}

.meta-item {
    display: flex;
    gap: 0.5rem;
}

.loading-spinner,
.no-preview,
.error-preview {
    color: #fff;
    font-size: 1.1rem;
}

/* Context menu hint */
.file-list-item:hover::after,
.tree-node.file:hover::after {
    content: 'Right-click for preview';
    position: absolute;
    right: 10px;
    font-size: 11px;
    color: #666;
    opacity: 0.7;
}
```

### 3.2 Video-Preview Batch-Generierung

**Beschreibung:**
Video-Previews werden bei Bedarf generiert (on-demand beim ersten Modal-Öffnen). Optional kann man alle Previews vorab generieren.

**In setupThumbnails() Button hinzufügen:**

```javascript
<button class="btn btn-sm btn-outline-secondary" 
        id="${this.containerId}-generate-video-previews"
        title="Pre-generate animated previews for all videos">
    🎬 Pre-generate Video Previews
</button>
```

**Event Handler:**

```javascript
document.getElementById(`${this.containerId}-generate-video-previews`).addEventListener('click', () => {
    this.generateVideoPreviewsForVideos();
});

/**
 * Generate video previews for all video files
 */
async generateVideoPreviewsForVideos() {
    const videoFiles = this.filteredFiles
        .filter(f => f.type === 'video')
        .map(f => f.path);
        
    if (videoFiles.length === 0) {
        alert('No video files found');
        return;
    }
    
    if (!confirm(`Generate animated previews for ${videoFiles.length} videos? This may take several minutes.`)) {
        return;
    }
    
    try {
        // Generate previews one by one with progress
        let completed = 0;
        
        for (const filePath of videoFiles) {
            const encodedPath = encodeURIComponent(filePath);
            await fetch(`/api/files/video-preview/${encodedPath}?generate=true`);
            
            completed++;
            console.log(`Generated ${completed}/${videoFiles.length} video previews`);
        }
        
        alert(`Generated ${completed} video previews!`);
    } catch (error) {
        console.error('Error generating video previews:', error);
        alert('Failed to generate video previews');
    }
}
```

---

## 🎯 Phase 4: Multi-Select System (3-5h)

### 3.1 Multi-Select UI State

**Datei:** `frontend/js/components/files-tab.js`

**Constructor erweitern:**

```javascript
constructor(containerId, searchContainerId, viewMode = 'list', enableMultiselect = false, enableThumbnails = false) {
    // ... bestehender Code ...
    
    // Multi-Select (bereits vorbereitet)
    this.enableMultiselect = enableMultiselect;
    this.selectedFiles = new Set();
    this.multiSelectMode = false; // Aktuell aktiv?
    this.lastSelectedIndex = -1; // Für Shift-Select
}
```

**Multi-Select Controls:**

```javascript
/**
 * Setup multi-select controls
 */
setupMultiSelectControls() {
    if (!this.enableMultiselect) return;
    
    const container = document.getElementById(this.containerId);
    
    // Toolbar für Multi-Select Actions
    const toolbar = document.createElement('div');
    toolbar.className = 'multiselect-toolbar';
    toolbar.id = `${this.containerId}-multiselect-toolbar`;
    toolbar.style.display = 'none'; // Versteckt bis Auswahl aktiv
    
    toolbar.innerHTML = `
        <div class="multiselect-info">
            <span id="${this.containerId}-selected-count">0</span> files selected
        </div>
        <div class="multiselect-actions">
            <button class="btn btn-sm btn-primary" data-action="add-to-playlist">
                ➕ Add to Playlist
            </button>
            <button class="btn btn-sm btn-primary" data-action="add-as-layers">
                📚 Add as Layers
            </button>
            <button class="btn btn-sm btn-secondary" data-action="generate-thumbnails">
                🖼️ Generate Thumbnails
            </button>
            <button class="btn btn-sm btn-outline-secondary" data-action="select-all">
                ☑️ Select All
            </button>
            <button class="btn btn-sm btn-outline-secondary" data-action="deselect-all">
                ☐ Deselect All
            </button>
            <button class="btn btn-sm btn-outline-secondary" data-action="cancel">
                ✖️ Cancel
            </button>
        </div>
    `;
    
    // Insert before file list
    container.parentElement.insertBefore(toolbar, container);
    
    // Event Listeners für Actions
    toolbar.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', () => {
            const action = btn.dataset.action;
            this.handleMultiSelectAction(action);
        });
    });
}

/**
 * Update multi-select toolbar visibility
 */
updateMultiSelectToolbar() {
    if (!this.enableMultiselect) return;
    
    const toolbar = document.getElementById(`${this.containerId}-multiselect-toolbar`);
    const countSpan = document.getElementById(`${this.containerId}-selected-count`);
    
    if (this.selectedFiles.size > 0) {
        toolbar.style.display = 'flex';
        countSpan.textContent = this.selectedFiles.size;
        this.multiSelectMode = true;
    } else {
        toolbar.style.display = 'none';
        this.multiSelectMode = false;
    }
}
```

### 3.2 Selection Logic

**Click-Handler erweitern:**

```javascript
/**
 * Handle file click with multi-select support and preview modal
 */
handleFileClick(filePath, fileInfo, event) {
    // Preview Modal: Right-Click oder Ctrl+Shift+Click
    if (event.button === 2 || (event.ctrlKey && event.shiftKey)) {
        event.preventDefault();
        this.showFilePreviewModal(filePath, fileInfo);
        return;
    }
    
    if (!this.enableMultiselect) {
        // Normal behavior: trigger file loaded event
        this.onFileSelected(filePath);
        return;
    }
    
    // Multi-Select Logic
    if (event.ctrlKey || event.metaKey) {
        // Ctrl+Click: Toggle selection
        if (this.selectedFiles.has(filePath)) {
            this.selectedFiles.delete(filePath);
        } else {
            this.selectedFiles.add(filePath);
        }
    } else if (event.shiftKey && this.lastSelectedIndex >= 0) {
        // Shift+Click: Range selection
        const currentIndex = this.filteredFiles.findIndex(f => f.path === filePath);
        const start = Math.min(this.lastSelectedIndex, currentIndex);
        const end = Math.max(this.lastSelectedIndex, currentIndex);
        
        for (let i = start; i <= end; i++) {
            this.selectedFiles.add(this.filteredFiles[i].path);
        }
    } else {
        // Normal click
        if (this.multiSelectMode) {
            // In multi-select mode: Toggle
            if (this.selectedFiles.has(filePath)) {
                this.selectedFiles.delete(filePath);
            } else {
                this.selectedFiles.add(filePath);
            }
        } else {
            // Not in multi-select: Single selection
            this.selectedFiles.clear();
            this.selectedFiles.add(filePath);
        }
    }
    
    // Update last selected index
    this.lastSelectedIndex = this.filteredFiles.findIndex(f => f.path === filePath);
    
    // Update UI
    this.updateMultiSelectToolbar();
    this.render(); // Re-render to show selection
}
```

**Event Listeners aktualisieren:**

```javascript
/**
 * Attach event listeners (überschreibt bestehende Methode)
 */
attachListEventListeners() {
    const container = document.getElementById(this.containerId);
    
    // File clicks
    container.querySelectorAll('.file-list-item').forEach(item => {
        // Left click
        item.addEventListener('click', (e) => {
            const filePath = item.dataset.path;
            const fileInfo = this.filteredFiles.find(f => f.path === filePath);
            this.handleFileClick(filePath, fileInfo, e);
        });
        
        // Right click - context menu for preview
        item.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            const filePath = item.dataset.path;
            const fileInfo = this.filteredFiles.find(f => f.path === filePath);
            this.showFilePreviewModal(filePath, fileInfo);
        });
        
        // Drag start
        item.addEventListener('dragstart', (e) => {
            this.handleDragStart(e, item);
        });
    });
}

// Entsprechend für Tree View
attachTreeEventListeners() {
    // ... bestehender Folder-Code ...
    
    // File clicks mit Multi-Select
    container.querySelectorAll('.tree-node.file').forEach(item => {
        item.addEventListener('click', (e) => {
            const filePath = item.dataset.path;
            this.handleFileClick(filePath, e);
        });
        
        // ... Drag code ...
    });
}
```

### 3.3 Batch Actions

**Action Handler:**

```javascript
/**
 * Handle multi-select actions
 */
async handleMultiSelectAction(action) {
    const selectedPaths = Array.from(this.selectedFiles);
    
    switch (action) {
        case 'select-all':
            this.selectedFiles.clear();
            this.filteredFiles.forEach(f => this.selectedFiles.add(f.path));
            this.updateMultiSelectToolbar();
            this.render();
            break;
            
        case 'deselect-all':
            this.selectedFiles.clear();
            this.updateMultiSelectToolbar();
            this.render();
            break;
            
        case 'cancel':
            this.selectedFiles.clear();
            this.updateMultiSelectToolbar();
            this.render();
            break;
            
        case 'add-to-playlist':
            await this.addSelectedToPlaylist(selectedPaths);
            break;
            
        case 'add-as-layers':
            await this.addSelectedAsLayers(selectedPaths);
            break;
            
        case 'generate-thumbnails':
            await this.generateThumbnailsForSelected(selectedPaths);
            break;
            
        default:
            console.warn('Unknown action:', action);
    }
}

/**
 * Add selected files to playlist
 */
async addSelectedToPlaylist(filePaths) {
    if (filePaths.length === 0) return;
    
    // Emit custom event für Player Integration
    const event = new CustomEvent('filesAddedToPlaylist', {
        detail: { files: filePaths }
    });
    document.dispatchEvent(event);
    
    // Clear selection
    this.selectedFiles.clear();
    this.updateMultiSelectToolbar();
    this.render();
    
    alert(`Added ${filePaths.length} files to playlist`);
}

/**
 * Add selected files as layers to current clip
 */
async addSelectedAsLayers(filePaths) {
    if (filePaths.length === 0) return;
    
    // Emit custom event
    const event = new CustomEvent('filesAddedAsLayers', {
        detail: { files: filePaths }
    });
    document.dispatchEvent(event);
    
    // Clear selection
    this.selectedFiles.clear();
    this.updateMultiSelectToolbar();
    this.render();
    
    alert(`Added ${filePaths.length} files as layers`);
}

/**
 * Generate thumbnails for selected files
 */
async generateThumbnailsForSelected(filePaths) {
    if (filePaths.length === 0) return;
    
    try {
        const response = await fetch('/api/files/thumbnails/batch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ files: filePaths })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`Queued ${data.queued} thumbnails for generation`);
            
            // Reload files after delay
            setTimeout(() => {
                this.loadFiles();
                this.selectedFiles.clear();
                this.updateMultiSelectToolbar();
            }, 2000);
        }
    } catch (error) {
        console.error('Error generating thumbnails:', error);
        alert('Failed to generate thumbnails');
    }
}
```

### 3.4 Keyboard Shortcuts

```javascript
/**
 * Setup keyboard shortcuts
 */
setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Nur wenn Container fokussiert oder Multi-Select aktiv
        if (!this.multiSelectMode && !document.getElementById(this.containerId).contains(document.activeElement)) {
            return;
        }
        
        // Ctrl+A: Select All
        if ((e.ctrlKey || e.metaKey) && e.key === 'a' && this.enableMultiselect) {
            e.preventDefault();
            this.handleMultiSelectAction('select-all');
        }
        
        // Escape: Cancel selection
        if (e.key === 'Escape' && this.multiSelectMode) {
            e.preventDefault();
            this.handleMultiSelectAction('cancel');
        }
    });
}

// Im Constructor oder init() aufrufen:
this.setupKeyboardShortcuts();
```

### 3.5 Drag & Drop für Multiple Files

**Bestehenden Drag-Handler erweitern:**

```javascript
/**
 * Handle drag start with multi-select support
 */
handleDragStart(event, element) {
    const filePath = element.dataset.path;
    
    if (this.enableMultiselect && this.selectedFiles.size > 1 && this.selectedFiles.has(filePath)) {
        // Multi-file drag
        const selectedPaths = Array.from(this.selectedFiles);
        event.dataTransfer.setData('application/json', JSON.stringify({
            type: 'multiple-files',
            files: selectedPaths
        }));
        event.dataTransfer.effectAllowed = 'copy';
        
        // Visual feedback
        element.classList.add('dragging-multiple');
        const badge = document.createElement('span');
        badge.className = 'drag-count-badge';
        badge.textContent = selectedPaths.length;
        element.appendChild(badge);
    } else {
        // Single file drag (bestehender Code)
        event.dataTransfer.setData('text/plain', filePath);
        event.dataTransfer.setData('application/json', JSON.stringify({
            type: 'file',
            path: filePath
        }));
        event.dataTransfer.effectAllowed = 'copy';
    }
}
```

---

## 🚀 Phase 5: Integration & Polish (1-2h)

### 5.1 Player.js Integration

**Datei:** `frontend/js/player.js`

**FilesTab mit neuen Features initialisieren:**

```javascript
// In initializeTabComponents() oder wo FilesTab initialisiert wird:
window.filesTab = new FilesTab(
    'files-container',
    'files-search',
    'button',  // viewMode
    true,      // enableMultiselect - NEU!
    true       // enableThumbnails - NEU!
);
await window.filesTab.init();

// Event Listeners für Multi-Select Actions
document.addEventListener('filesAddedToPlaylist', async (e) => {
    const files = e.detail.files;
    
    // Füge alle Dateien zum Playlist hinzu
    for (const filePath of files) {
        try {
            await fetch(`/api/player/${currentPlayerId}/clips/add`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    video_path: filePath,
                    auto_play: false
                })
            });
        } catch (error) {
            console.error('Error adding file to playlist:', error);
        }
    }
    
    // Reload playlist
    await loadPlaylist();
    showNotification(`✅ Added ${files.length} files to playlist`);
});

document.addEventListener('filesAddedAsLayers', async (e) => {
    const files = e.detail.files;
    
    // Get current clip
    const currentClipId = window.currentClipId;
    if (!currentClipId) {
        alert('No clip selected. Please select a clip first.');
        return;
    }
    
    // Füge alle als Layer hinzu
    for (const filePath of files) {
        try {
            await fetch(`/api/player/${currentPlayerId}/clips/${currentClipId}/layers/add`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    video_path: filePath,
                    opacity: 1.0,
                    blend_mode: 'normal'
                })
            });
        } catch (error) {
            console.error('Error adding layer:', error);
        }
    }
    
    // Reload layers
    await loadLayers(currentClipId);
    showNotification(`✅ Added ${files.length} layers`);
});
```

### 5.2 CSS für Multi-Select

**Datei:** `frontend/css/thumbnails.css` (ergänzen)

```css
/* Multi-Select Toolbar */
.multiselect-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem;
    background: #e3f2fd;
    border: 1px solid #90caf9;
    border-radius: 4px;
    margin-bottom: 0.5rem;
}

.multiselect-info {
    font-weight: 600;
    color: #1976d2;
}

.multiselect-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}

/* Selection State */
.file-list-item.selected,
.tree-node.file.selected {
    background: #e3f2fd !important;
    border-left: 3px solid #1976d2 !important;
}

/* Drag Multiple Badge */
.drag-count-badge {
    position: absolute;
    top: -8px;
    right: -8px;
    background: #1976d2;
    color: white;
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: bold;
}

.dragging-multiple {
    position: relative;
    opacity: 0.8;
}

/* Keyboard Hints */
.file-list-item:hover::after,
.tree-node.file:hover::after {
    content: 'Ctrl+Click for multi-select';
    position: absolute;
    right: 10px;
    font-size: 11px;
    color: #666;
    opacity: 0.7;
}
```

### 5.3 HTML Anpassungen

**Datei:** `frontend/player.html`

**CSS einbinden:**

```html
<head>
    <!-- ... andere CSS ... -->
    <link rel="stylesheet" href="css/thumbnails.css">
</head>
```

### 5.4 Performance-Optimierung

**Lazy Loading für Thumbnails:**

```javascript
/**
 * Intersection Observer für lazy loading
 */
setupThumbnailLazyLoading() {
    if (!('IntersectionObserver' in window)) {
        // Fallback: Load all immediately
        this.loadVisibleThumbnails();
        return;
    }
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                const filePath = img.dataset.path;
                
                if (filePath && img.classList.contains('loading')) {
                    this.loadThumbnail(filePath, img);
                    observer.unobserve(img);
                }
            }
        });
    }, {
        root: document.getElementById(this.containerId),
        rootMargin: '50px'
    });
    
    // Observe all thumbnail images
    const container = document.getElementById(this.containerId);
    container.querySelectorAll('.file-thumbnail.loading').forEach(img => {
        observer.observe(img);
    });
}

// In render() verwenden:
render() {
    // ... rendering code ...
    
    if (this.showThumbnails) {
        setTimeout(() => this.setupThumbnailLazyLoading(), 100);
    }
}
```

---

## 📊 Testing & Validation

### Test-Cases

1. **Thumbnail-Generierung:**
   - [ ] Video-Thumbnail wird korrekt extrahiert
   - [ ] Bild-Thumbnail wird korrekt resized
   - [ ] Cache funktioniert (zweiter Aufruf schneller)
   - [ ] Fehlerhafte Dateien werden behandelt

2. **Thumbnail-Anzeige:**
   - [ ] Thumbnails werden in List View angezeigt
   - [ ] Thumbnails werden in Tree View angezeigt
   - [ ] Lazy Loading funktioniert
   - [ ] Hover-Preview funktioniert

3. **Multi-Select:**
   - [ ] Ctrl+Click togglet Selektion
   - [ ] Shift+Click selektiert Range
   - [ ] "Select All" funktioniert
   - [ ] Toolbar erscheint bei Selektion
   - [ ] Selected Count ist korrekt

4. **Batch-Operationen:**
   - [ ] "Add to Playlist" fügt alle Dateien hinzu
   - [ ] "Add as Layers" fügt alle als Layer hinzu
   - [ ] "Generate Thumbnails" startet Batch-Generierung
   - [ ] Drag & Drop mit mehreren Dateien funktioniert

5. **Performance:**
   - [ ] Lazy Loading reduziert Initial Load
   - [ ] Große Dateilisten (1000+ Dateien) performant
   - [ ] Thumbnail-Cache spart Netzwerk-Requests

---

## 🔧 Dependencies

**Backend:**
```bash
pip install Pillow opencv-python
```

**Frontend:**
- Keine neuen Dependencies (nutzt natives JavaScript)

---

## 📁 Dateien-Struktur

```
src/modules/
├── thumbnail_generator.py        # NEU - Thumbnail-Generierung
└── api_files.py                  # ERWEITERT - Thumbnail-Endpoints

frontend/
├── css/
│   └── thumbnails.css            # NEU - Thumbnail & Multi-Select Styles
└── js/
    └── components/
        └── files-tab.js          # ERWEITERT - Thumbnail & Multi-Select

data/
└── thumbnails/                   # NEU - Cache-Verzeichnis
    └── (auto-generated)
```

---

## 🎯 Erweiterungsmöglichkeiten (Optional)

1. **Thumbnail-Größen:**
   - UI-Slider für dynamische Größenanpassung
   - User-Präferenz im LocalStorage speichern
   - Mehrere vordefinierte Größen (klein/mittel/groß)

2. **Preview-Verbesserungen:**
   - ✅ Video-Preview (GIF/WebM) - IMPLEMENTED
   - Scrubbing: Mit Maus über Thumbnail = Zeit-Preview
   - Audio-Waveform für Videos mit Audio

3. **Erweiterte Batch-Ops (Zukunft):**
   - Batch-Delete (mit Confirmation)
   - Batch-Move/Copy
   - Metadata-Editing (Resolution, Duration, etc.)

4. **Filter-Erweiterungen:**
   - Nach Dateigröße
   - Nach Datum
   - Nach Resolution

5. **Grid View:**
   - Pinterest-style Grid
   - Thumbnail-only View

---

## ⏱️ Zeitplan

| Phase | Aufgabe | Geschätzt | Priorität |
|-------|---------|-----------|-----------|
| 1 | Backend Thumbnail-Generator | 2h | 🔥 High |
| 1 | REST API Endpoints | 1h | 🔥 High |
| 1 | API Integration in Files | 0.5h | 🔥 High |
| 2 | CSS Styles | 0.5h | 🔥 High |
| 2 | FilesTab Thumbnail-Support | 1.5h | 🔥 High |
| 2 | Lazy Loading | 0.5h | ⚡ Medium |
| 3 | Multi-Select UI | 1h | 🔥 High |
| 3 | Selection Logic | 1h | 🔥 High |
| 3 | Batch Actions | 1.5h | 🔥 High |
| 3 | Keyboard Shortcuts | 0.5h | ⚡ Medium |
| 3 | Drag & Drop Multi | 0.5h | ⚡ Medium |
| 4 | Player Integration | 0.5h | 🔥 High |
| 4 | Testing & Polish | 1h | ⚡ Medium |
| **GESAMT** | | **12h** | |

**Minimum Viable Product (MVP):** Phase 1 + Phase 2 = ~5 Stunden (nur Thumbnails)
**With Video Preview:** Phase 1-3 = ~8 Stunden (Thumbnails + Video-Preview)
**Full Feature Set:** Alle Phasen = ~15 Stunden (inkl. Multi-Select)

---

## 🚦 Next Steps

1. **Review dieses Plans** - Feedback und Anpassungen
2. **Phase 1 starten** - Backend Thumbnail-Generator
3. **Schrittweise implementieren** - Eine Phase nach der anderen
4. **Testing nach jeder Phase** - Sicherstellen dass alles funktioniert

---

**Bereit zum Start?** 🚀
