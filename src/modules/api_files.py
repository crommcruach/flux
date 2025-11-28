"""
API Files - File Browser and Directory Management

Provides endpoints for browsing video directory structure.
"""
from flask import jsonify
import os
from .constants import VIDEO_EXTENSIONS, IMAGE_EXTENSIONS
from .logger import get_logger

logger = get_logger(__name__)


def register_files_api(app, video_dir, config=None):
    """Registriert File Browser API."""
    
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
                        
                        file_info = {
                            "type": file_type,
                            "name": entry,
                            "path": rel_path.replace("\\", "/"),
                            "size": file_size,
                            "size_human": _format_size(file_size)
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
                            
                            files_list.append({
                                "filename": filename,
                                "path": rel_path.replace("\\", "/"),
                                "full_path": filepath,
                                "source": source_name,
                                "source_path": source_path,
                                "folder": folder_name,
                                "size": file_size,
                                "size_human": _format_size(file_size),
                                "type": file_type
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


def _format_size(size_bytes):
    """Formatiert Dateigröße human-readable."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
