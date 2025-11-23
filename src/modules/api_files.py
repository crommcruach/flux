"""
API Files - File Browser and Directory Management

Provides endpoints for browsing video directory structure.
"""
from flask import jsonify
import os
from .constants import VIDEO_EXTENSIONS
from .logger import get_logger

logger = get_logger(__name__)


def register_files_api(app, video_dir):
    """Registriert File Browser API."""
    
    @app.route('/api/files/tree', methods=['GET'])
    def get_file_tree():
        """Gibt Ordnerstruktur mit Videos zurück."""
        try:
            if not os.path.exists(video_dir):
                return jsonify({
                    "status": "error",
                    "message": "Video directory not found"
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
                    
                    elif os.path.isfile(full_path) and entry.lower().endswith(VIDEO_EXTENSIONS):
                        file_size = os.path.getsize(full_path)
                        file_info = {
                            "type": "file",
                            "name": entry,
                            "path": rel_path.replace("\\", "/"),
                            "size": file_size,
                            "size_human": _format_size(file_size)
                        }
                        files.append(file_info)
                
                return folders + files
            
            tree = build_tree(video_dir)
            
            return jsonify({
                "status": "success",
                "tree": tree,
                "root": video_dir
            })
            
        except Exception as e:
            logger.error(f"Error building file tree: {e}")
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
    
    @app.route('/api/files/videos', methods=['GET'])
    def get_all_videos():
        """Gibt flache Liste aller Videos zurück (für Drag & Drop)."""
        try:
            videos = []
            
            if os.path.exists(video_dir):
                for root, dirs, files in os.walk(video_dir):
                    for filename in files:
                        if filename.lower().endswith(VIDEO_EXTENSIONS):
                            filepath = os.path.join(root, filename)
                            rel_path = os.path.relpath(filepath, video_dir)
                            file_size = os.path.getsize(filepath)
                            
                            # Extrahiere Ordnername
                            folder_name = os.path.dirname(rel_path) if os.path.dirname(rel_path) else "root"
                            
                            videos.append({
                                "filename": filename,
                                "path": rel_path.replace("\\", "/"),
                                "folder": folder_name,
                                "size": file_size,
                                "size_human": _format_size(file_size)
                            })
            
            return jsonify({
                "status": "success",
                "videos": sorted(videos, key=lambda x: x['path']),
                "total": len(videos)
            })
            
        except Exception as e:
            logger.error(f"Error listing videos: {e}")
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500


def _format_size(size_bytes):
    """Formatiert Dateigröße human-readable."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
