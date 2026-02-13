"""
API Files - File Browser and Directory Management

Provides endpoints for browsing video directory structure.
"""
from flask import jsonify, send_file, request
import os
import urllib.parse
import cv2
from ...core.constants import VIDEO_EXTENSIONS, IMAGE_EXTENSIONS
from ...core.logger import get_logger
from .thumbnail_generator import ThumbnailGenerator

logger = get_logger(__name__)


def register_files_api(app, video_dir, config=None):
    """Registriert File Browser API."""
    
    # Initialisiere Thumbnail-Generator mit Config
    thumbnail_gen = ThumbnailGenerator(config=config)
    thumbnail_gen.start_worker()
    
    def get_video_sources():
        """Gibt alle konfigurierten Video-Quellen zurück."""
        sources = [video_dir]  # Haupt video_dir ist immer dabei
        
        if config and 'paths' in config and 'video_sources' in config['paths']:
            additional_sources = config['paths']['video_sources']
            if isinstance(additional_sources, list):
                sources.extend([s for s in additional_sources if s and os.path.exists(s)])
        
        return sources
    
    @app.route('/api/files/tree', methods=['GET'])
    def get_file_tree():
        """Gibt Ordnerstruktur mit Videos und Bildern zurück."""
        try:
            sources = get_video_sources()
            
            if not sources:
                return jsonify({
                    "success": False,
                    "error": "No video directories found"
                }), 404
            
            def build_tree(path, relative_path=""):
                """Rekursiv Ordnerstruktur erstellen."""
                items = []
                
                try:
                    entries = sorted(os.listdir(path))
                except PermissionError:
                    return items
                
                # Zuerst Ordner
                folders = []
                files = []
                
                for entry in entries:
                    full_path = os.path.join(path, entry)
                    rel_path = os.path.join(relative_path, entry) if relative_path else entry
                    
                    if os.path.isdir(full_path):
                        folder_info = {
                            "type": "folder",
                            "name": entry,
                            "path": rel_path.replace("\\", "/"),
                            "children": build_tree(full_path, rel_path)
                        }
                        folders.append(folder_info)
                    
                    elif os.path.isfile(full_path):
                        file_lower = entry.lower()
                        file_size = os.path.getsize(full_path)
                        
                        # Bestimme Dateityp
                        if file_lower.endswith(VIDEO_EXTENSIONS):
                            file_type = "video"
                        elif file_lower.endswith(IMAGE_EXTENSIONS):
                            file_type = "image"
                        else:
                            continue  # Überspringe andere Dateitypen
                        
                        # Alle Videos und Bilder können Thumbnails haben (on-demand generiert)
                        has_thumbnail = True
                        
                        # Extrahiere Video-Metadaten
                        metadata = {}
                        if file_type == "video":
                            video_meta = _get_video_metadata(full_path)
                            if video_meta:
                                metadata = video_meta
                        
                        file_info = {
                            "type": file_type,
                            "name": entry,
                            "path": rel_path.replace("\\", "/"),
                            "size": file_size,
                            "size_human": _format_size(file_size),
                            "has_thumbnail": has_thumbnail,
                            **metadata  # Füge fps, duration, frame_count hinzu
                        }
                        files.append(file_info)
                
                return folders + files
            
            # Build tree for all sources
            all_items = []
            
            for source_path in sources:
                if os.path.exists(source_path):
                    source_name = os.path.basename(source_path) or source_path
                    source_tree = build_tree(source_path)
                    
                    # Wrap each source in a folder node
                    all_items.append({
                        "type": "folder",
                        "name": source_name,
                        "path": source_path,
                        "source": source_path,
                        "children": source_tree
                    })
            
            return jsonify({
                "success": True,
                "tree": all_items,
                "sources": sources
            })
            
        except Exception as e:
            logger.error(f"Error building file tree: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route('/api/files/videos', methods=['GET'])
    def get_all_videos():
        """Gibt flache Liste aller Videos und Bilder zurück (für Drag & Drop)."""
        try:
            files_list = []
            sources = get_video_sources()
            
            for source_path in sources:
                if os.path.exists(source_path):
                    source_name = os.path.basename(source_path) or source_path
                    
                    for root, dirs, files in os.walk(source_path):
                        for filename in files:
                            file_lower = filename.lower()
                            
                            # Bestimme Dateityp
                            if file_lower.endswith(VIDEO_EXTENSIONS):
                                file_type = "video"
                            elif file_lower.endswith(IMAGE_EXTENSIONS):
                                file_type = "image"
                            else:
                                continue  # Überspringe andere Dateitypen
                            
                            filepath = os.path.join(root, filename)
                            rel_path = os.path.relpath(filepath, source_path)
                            file_size = os.path.getsize(filepath)
                            
                            # Extrahiere Ordnername
                            folder_name = os.path.dirname(rel_path) if os.path.dirname(rel_path) else "root"
                            
                            # Alle Videos und Bilder können Thumbnails haben (on-demand generiert)
                            has_thumbnail = True
                            
                            # Extrahiere Video-Metadaten
                            metadata = {}
                            if file_type == "video":
                                video_meta = _get_video_metadata(filepath)
                                if video_meta:
                                    metadata = video_meta
                            
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
                                "has_thumbnail": has_thumbnail,
                                **metadata  # Füge fps, duration, frame_count hinzu
                            })
            
            return jsonify({
                "success": True,
                "files": sorted(files_list, key=lambda x: x['path']),
                "total": len(files_list)
            })
            
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    # ==================== THUMBNAIL ENDPOINTS ====================
    
    @app.route('/api/files/thumbnail/<path:file_path>', methods=['GET'])
    def get_thumbnail(file_path):
        """
        Gibt Thumbnail für Datei zurück
        
        Query Parameters:
            - generate: 'true' um Thumbnail zu generieren falls nicht existiert
        """
        try:
            # Decode file path
            file_path = urllib.parse.unquote(file_path)
            
            # Handle generator sources
            if file_path.startswith('generator:'):
                generator_id = file_path.replace('generator:', '')
                try:
                    from .frame_source import GeneratorSource
                    import cv2
                    import io
                    
                    # Create generator and get first frame
                    gen_source = GeneratorSource(generator_id, {}, canvas_width=200, canvas_height=200)
                    if gen_source.initialize():
                        frame, _ = gen_source.get_next_frame()
                        if frame is not None:
                            # Encode as JPEG
                            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                            if ret:
                                return send_file(
                                    io.BytesIO(buffer.tobytes()),
                                    mimetype='image/jpeg',
                                    max_age=86400
                                )
                except Exception as e:
                    logger.error(f"Error generating thumbnail for generator {generator_id}: {e}")
                
                return jsonify({
                    'success': False,
                    'error': 'Could not generate thumbnail for generator'
                }), 404
            
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
    
    @app.route('/api/files/video-preview/<path:file_path>', methods=['GET'])
    def get_video_preview(file_path):
        """
        Gibt animiertes Video-Preview zurück (GIF oder WebM)
        
        Query Parameters:
            - generate: 'true' um Preview zu generieren falls nicht existiert
        """
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
                from pathlib import Path
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
            
    @app.route('/api/files/thumbnails/batch', methods=['POST'])
    def generate_thumbnails_batch():
        """
        Generiert Thumbnails für mehrere Dateien asynchron
        
        Request Body:
            {
                "files": ["path/to/file1.mp4", "path/to/file2.jpg"]
            }
        """
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
    
    @app.route('/api/files/delete', methods=['DELETE'])
    def delete_file():
        """Delete a file from the video directory"""
        try:
            data = request.get_json()
            file_path = data.get('path')
            
            if not file_path:
                return jsonify({
                    'success': False,
                    'error': 'No file path provided'
                }), 400
            
            # Find full path in video sources
            full_path = None
            for source_path in get_video_sources():
                candidate_path = os.path.join(source_path, file_path)
                if os.path.exists(candidate_path):
                    full_path = candidate_path
                    break
            
            if not full_path or not os.path.exists(full_path):
                return jsonify({
                    'success': False,
                    'error': 'File not found'
                }), 404
            
            # Security check: ensure file is within allowed directories
            real_path = os.path.realpath(full_path)
            allowed = False
            for source_path in get_video_sources():
                real_source = os.path.realpath(source_path)
                if real_path.startswith(real_source):
                    allowed = True
                    break
            
            if not allowed:
                logger.warning(f"Attempted to delete file outside allowed directories: {full_path}")
                return jsonify({
                    'success': False,
                    'error': 'Access denied'
                }), 403
            
            # Delete the file
            os.remove(full_path)
            logger.info(f"File deleted: {full_path}")
            
            # Also delete thumbnail if exists
            if thumbnail_gen:
                try:
                    thumbnail_gen.delete_thumbnail(full_path)
                except Exception as e:
                    logger.warning(f"Failed to delete thumbnail: {e}")
            
            return jsonify({
                'success': True,
                'message': 'File deleted successfully'
            })
            
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


def _format_size(size_bytes):
    """Formatiert Dateigröße human-readable."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def _get_video_metadata(video_path):
    """Extract video metadata (duration, fps) using OpenCV."""
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Skip corrupted videos (invalid metadata)
        if fps <= 0 or frame_count <= 0:
            cap.release()
            return None
        
        duration = frame_count / fps if fps > 0 else 0
        
        cap.release()
        
        return {
            'fps': round(fps, 2),
            'duration': round(duration, 2),
            'frame_count': frame_count
        }
    except Exception as e:
        # Silently skip corrupted files (don't spam logs)
        return None

