"""
Session State Snapshot API
Handles creating, listing, and restoring snapshots of session state.
"""

import os
import json
import shutil
from datetime import datetime
from flask import Blueprint, jsonify, request
from .logger import get_logger
from .api_playlists import get_playlist_system

logger = get_logger(__name__)

# Create blueprint
session_api = Blueprint('session_api', __name__)


def register_session_routes(app, session_state_manager):
    """Register session snapshot routes."""
    
    SNAPSHOTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'snapshots')
    DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'data')
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    
    @app.route('/api/session/snapshot', methods=['POST'])
    def create_snapshot():
        """Create a snapshot of current session state (includes sequencer)."""
        try:
            data = request.get_json() or {}
            
            # Generate filename with timestamp: YYYYMMDD_HHMMSS_snap.json
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_snap.json"
            
            snapshot_path = os.path.join(SNAPSHOTS_DIR, filename)
            
            # Force save current state to ensure sequencer is included
            if hasattr(app, 'flux_player_manager') and hasattr(app, 'flux_clip_registry'):
                session_state_manager.save(
                    player_manager=app.flux_player_manager,
                    clip_registry=app.flux_clip_registry,
                    force=True
                )
            
            # Copy current session_state.json to snapshots directory
            session_state_path = session_state_manager.get_state_file_path()
            
            if not os.path.exists(session_state_path):
                return jsonify({
                    "success": False,
                    "error": "No session state found to snapshot"
                }), 404
            
            shutil.copy2(session_state_path, snapshot_path)
            
            # Get file info
            file_size = os.path.getsize(snapshot_path)
            created_time = datetime.now().isoformat()
            
            logger.info(f"📸 Snapshot created: {filename}")
            
            return jsonify({
                "success": True,
                "message": f"Snapshot '{filename}' created",
                "filename": filename,
                "path": snapshot_path,
                "size": file_size,
                "created": created_time
            })
            
        except Exception as e:
            logger.error(f"Error creating snapshot: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/session/snapshots', methods=['GET'])
    def list_snapshots():
        """List all available snapshots."""
        try:
            if not os.path.exists(SNAPSHOTS_DIR):
                return jsonify({
                    "success": True,
                    "snapshots": []
                })
            
            snapshots = []
            for filename in os.listdir(SNAPSHOTS_DIR):
                if filename.endswith('.json'):
                    filepath = os.path.join(SNAPSHOTS_DIR, filename)
                    
                    # Get file stats
                    stats = os.stat(filepath)
                    created_time = datetime.fromtimestamp(stats.st_mtime).isoformat()
                    
                    # Try to load snapshot to get metadata
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            video_playlist_count = len(data.get('video_player', {}).get('playlist', []))
                            artnet_playlist_count = len(data.get('artnet_player', {}).get('playlist', []))
                    except:
                        video_playlist_count = 0
                        artnet_playlist_count = 0
                    
                    snapshots.append({
                        "filename": filename,
                        "created": created_time,
                        "size": stats.st_size,
                        "video_count": video_playlist_count,
                        "artnet_count": artnet_playlist_count
                    })
            
            # Sort by creation time (newest first)
            snapshots.sort(key=lambda x: x['created'], reverse=True)
            
            return jsonify({
                "success": True,
                "snapshots": snapshots
            })
            
        except Exception as e:
            logger.error(f"Error listing snapshots: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/session/snapshot/restore', methods=['POST'])
    def restore_snapshot():
        """Restore a snapshot including sequencer state."""
        try:
            data = request.get_json()
            filename = data.get('filename')
            
            if not filename:
                return jsonify({"success": False, "error": "No filename provided"}), 400
            
            snapshot_path = os.path.join(SNAPSHOTS_DIR, filename)
            
            if not os.path.exists(snapshot_path):
                return jsonify({"success": False, "error": f"Snapshot '{filename}' not found"}), 404
            
            # Load the snapshot data
            with open(snapshot_path, 'r', encoding='utf-8') as f:
                snapshot_data = json.load(f)
            
            # Inject restore timestamp for locking mechanism
            from datetime import datetime
            restore_timestamp = datetime.now().isoformat()
            snapshot_data['restore_timestamp'] = restore_timestamp
            
            # Write modified data to session_state.json
            session_state_path = session_state_manager.get_state_file_path()
            with open(session_state_path, 'w', encoding='utf-8') as f:
                json.dump(snapshot_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"🔒 Injected restore_timestamp: {restore_timestamp}")
            
            # Actively restore playlists if available
            playlist_system = get_playlist_system()
            if playlist_system:
                playlists_data = snapshot_data.get('playlists', {})
                logger.info(f"🎵 Playlists data found: {bool(playlists_data)}")
                
                if playlists_data and isinstance(playlists_data, dict):
                    items = playlists_data.get('items', {})
                    logger.info(f"🎵 Playlist items count: {len(items)}")
                    
                    if playlist_system.load_from_dict(playlists_data):
                        playlist_count = len(playlist_system.playlists)
                        logger.info(f"✅ Snapshot restored with {playlist_count} playlists: {filename}")
                        
                        return jsonify({
                            "success": True,
                            "message": f"Snapshot '{filename}' restored successfully with {playlist_count} playlists",
                            "filename": filename,
                            "restore_timestamp": restore_timestamp,
                            "playlists_restored": playlist_count,
                            "requires_reload": True
                        })
                    else:
                        logger.warning("⚠️ load_from_dict returned False")
                else:
                    logger.warning("⚠️ No valid playlists data in snapshot")
            else:
                logger.warning("⚠️ playlist_system not available")
            
            logger.info(f"🔄 Snapshot restored (file only): {filename}")
            
            return jsonify({
                "success": True,
                "message": f"Snapshot '{filename}' restored. Please reload the page to apply changes.",
                "filename": filename,
                "restore_timestamp": restore_timestamp,
                "requires_reload": True
            })
            
        except Exception as e:
            logger.error(f"Error restoring snapshot: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/session/state', methods=['GET'])
    def get_session_state():
        """Get current session state including audio analyzer settings."""
        try:
            session_state_path = session_state_manager.get_state_file_path()
            
            if not os.path.exists(session_state_path):
                return jsonify({
                    "success": True,
                    "state": {"audio_analyzer": {"device": None, "running": False, "config": {}}}
                })
            
            with open(session_state_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            return jsonify({
                "success": True,
                "state": state
            })
            
        except Exception as e:
            logger.error(f"Error getting session state: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/session/editor', methods=['POST'])
    def update_editor_state():
        """Update editor section of session state."""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"success": False, "error": "No data provided"}), 400
            
            # Use SessionStateManager method
            session_state_manager.set_editor_state(data)
            
            return jsonify({
                "success": True,
                "message": "Editor state updated"
            })
            
        except Exception as e:
            logger.error(f"Error updating editor state: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/session/snapshot/delete', methods=['POST'])
    def delete_snapshot():
        """Delete a snapshot."""
        try:
            data = request.get_json()
            filename = data.get('filename')
            
            if not filename:
                return jsonify({"success": False, "error": "No filename provided"}), 400
            
            snapshot_path = os.path.join(SNAPSHOTS_DIR, filename)
            
            if not os.path.exists(snapshot_path):
                return jsonify({"success": False, "error": f"Snapshot '{filename}' not found"}), 404
            
            os.remove(snapshot_path)
            
            logger.info(f"🗑️ Snapshot deleted: {filename}")
            
            return jsonify({
                "success": True,
                "message": f"Snapshot '{filename}' deleted",
                "filename": filename
            })
            
        except Exception as e:
            logger.error(f"Error deleting snapshot: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/session/state', methods=['POST'])
    def update_full_session_state():
        """Update complete session state (replaces session_state.json)."""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"success": False, "error": "No data provided"}), 400
            
            session_state_path = session_state_manager.get_state_file_path()
            
            # Write complete new state
            with open(session_state_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Complete session state updated")
            
            return jsonify({
                "success": True,
                "message": "Session state updated. Please reload the page to apply changes.",
                "requires_reload": True
            })
            
        except Exception as e:
            logger.error(f"Error updating session state: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/session/download', methods=['GET'])
    def download_session_state():
        """Download current session state as JSON file."""
        try:
            from flask import send_file
            
            session_state_path = session_state_manager.get_state_file_path()
            
            if not os.path.exists(session_state_path):
                return jsonify({"success": False, "error": "No session state found"}), 404
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            download_name = f"session_state_{timestamp}.json"
            
            logger.info(f"📥 Session state downloaded: {download_name}")
            
            return send_file(
                session_state_path,
                mimetype='application/json',
                as_attachment=True,
                download_name=download_name
            )
            
        except Exception as e:
            logger.error(f"Error downloading session state: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/session/upload', methods=['POST'])
    def upload_session_state():
        """Upload and restore session state from JSON file."""
        try:
            if 'file' not in request.files:
                return jsonify({"success": False, "error": "No file provided"}), 400
            
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({"success": False, "error": "No file selected"}), 400
            
            if not file.filename.endswith('.json'):
                return jsonify({"success": False, "error": "File must be a JSON file"}), 400
            
            # Parse and validate JSON
            try:
                data = json.load(file)
            except json.JSONDecodeError as e:
                return jsonify({"success": False, "error": f"Invalid JSON: {str(e)}"}), 400
            
            # Write to session_state.json
            session_state_path = session_state_manager.get_state_file_path()
            with open(session_state_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📤 Session state uploaded from: {file.filename}")
            
            return jsonify({
                "success": True,
                "message": f"Session state restored from '{file.filename}'. Please reload the page to apply changes.",
                "filename": file.filename,
                "requires_reload": True
            })
            
        except Exception as e:
            logger.error(f"Error uploading session state: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/session/save', methods=['POST'])
    def save_session_state():
        """Save current session state with custom name to /data directory."""
        try:
            data = request.get_json() or {}
            name = data.get('name', '').strip()
            
            if not name:
                return jsonify({"success": False, "error": "No name provided"}), 400
            
            # Sanitize filename
            import re
            name = re.sub(r'[^\w\s-]', '', name)
            name = re.sub(r'[-\s]+', '_', name)
            
            if not name:
                return jsonify({"success": False, "error": "Invalid name"}), 400
            
            # Add timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{name}_{timestamp}.json"
            
            save_path = os.path.join(DATA_DIR, filename)
            
            # Check if file already exists
            if os.path.exists(save_path):
                return jsonify({"success": False, "error": f"File '{filename}' already exists"}), 400
            
            # Force save current state
            logger.info(f"[API SAVE] Checking app attributes...")
            logger.info(f"[API SAVE]   hasattr(app, 'flux_player_manager') = {hasattr(app, 'flux_player_manager')}")
            logger.info(f"[API SAVE]   hasattr(app, 'flux_clip_registry') = {hasattr(app, 'flux_clip_registry')}")
            
            if hasattr(app, 'flux_player_manager') and hasattr(app, 'flux_clip_registry'):
                logger.info(f"[API SAVE] ✅ Calling session_state_manager.save() NOW...")
                session_state_manager.save(
                    player_manager=app.flux_player_manager,
                    clip_registry=app.flux_clip_registry,
                    force=True
                )
                logger.info(f"[API SAVE] ✅ save() returned")
            else:
                logger.error(f"[API SAVE] ❌ SKIPPING save() - app attributes not found!")
                logger.error(f"[API SAVE] ❌ This means we're copying an OLD session_state.json!")
            
            # Copy current session_state.json to data directory
            session_state_path = session_state_manager.get_state_file_path()
            
            if not os.path.exists(session_state_path):
                return jsonify({
                    "success": False,
                    "error": "No session state found to save"
                }), 404
            
            shutil.copy2(session_state_path, save_path)
            
            # Get file info
            file_size = os.path.getsize(save_path)
            created_time = datetime.now().isoformat()
            
            logger.info(f"💾 Session saved: {filename}")
            
            return jsonify({
                "success": True,
                "message": f"Session '{name}' saved",
                "filename": filename,
                "path": save_path,
                "size": file_size,
                "created": created_time
            })
            
        except Exception as e:
            logger.error(f"Error saving session: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/session/list', methods=['GET'])
    def list_saved_sessions():
        """List all saved sessions from /data directory."""
        try:
            if not os.path.exists(DATA_DIR):
                return jsonify({
                    "success": True,
                    "sessions": []
                })
            
            sessions = []
            for filename in os.listdir(DATA_DIR):
                if filename.endswith('.json') and filename != 'punkte_export.json':
                    filepath = os.path.join(DATA_DIR, filename)
                    
                    # Get file stats
                    stats = os.stat(filepath)
                    created_time = datetime.fromtimestamp(stats.st_mtime).isoformat()
                    
                    # Try to load session to get metadata
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            video_playlist_count = len(data.get('video_player', {}).get('playlist', []))
                            artnet_playlist_count = len(data.get('artnet_player', {}).get('playlist', []))
                    except:
                        video_playlist_count = 0
                        artnet_playlist_count = 0
                    
                    sessions.append({
                        "filename": filename,
                        "created": created_time,
                        "size": stats.st_size,
                        "video_count": video_playlist_count,
                        "artnet_count": artnet_playlist_count,
                        "type": "session"
                    })
            
            # Sort by creation time (newest first)
            sessions.sort(key=lambda x: x['created'], reverse=True)
            
            return jsonify({
                "success": True,
                "sessions": sessions
            })
            
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/session/restore', methods=['POST'])
    def restore_saved_session():
        """Restore a saved session from /data directory."""
        try:
            data = request.get_json()
            filename = data.get('filename')
            
            if not filename:
                return jsonify({"success": False, "error": "No filename provided"}), 400
            
            save_path = os.path.join(DATA_DIR, filename)
            
            if not os.path.exists(save_path):
                return jsonify({"success": False, "error": f"Session '{filename}' not found"}), 404
            
            # Load the saved session data
            with open(save_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            logger.info(f"📂 Loaded session file: {filename}")
            logger.info(f"📊 Session contains keys: {list(session_data.keys())}")
            
            # Inject restore timestamp for locking mechanism
            from datetime import datetime
            restore_timestamp = datetime.now().isoformat()
            session_data['restore_timestamp'] = restore_timestamp
            
            # Write modified data to session_state.json
            session_state_path = session_state_manager.get_state_file_path()
            with open(session_state_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"🔒 Injected restore_timestamp: {restore_timestamp}")
            logger.info(f"💾 Wrote to session_state.json")
            
            # CRITICAL: Restore clip_registry BEFORE playlists!
            # Playlists load will register clips, and we need the saved clip data (effects/layers) to exist first
            from .clip_registry import get_clip_registry
            clip_registry = get_clip_registry()
            clip_registry_data = session_data.get('clip_registry')
            if clip_registry_data:
                try:
                    clip_registry.deserialize(clip_registry_data)
                    logger.info(f"📋 Clip registry restored from session: {len(clip_registry.clips)} clips")
                except Exception as e:
                    logger.error(f"⚠️ Failed to restore clip registry: {e}", exc_info=True)
            else:
                logger.warning("⚠️ No clip_registry data in session file")
            
            # Actively restore playlists if available
            playlist_system = get_playlist_system()
            if playlist_system:
                playlists_data = session_data.get('playlists', {})
                logger.info(f"🎵 Playlists data found: {bool(playlists_data)}")
                
                if playlists_data and isinstance(playlists_data, dict):
                    items = playlists_data.get('items', {})
                    logger.info(f"🎵 Playlist items count: {len(items)}")
                    
                    if playlist_system.load_from_dict(playlists_data):
                        playlist_count = len(playlist_system.playlists)
                        logger.info(f"✅ Session restored with {playlist_count} playlists: {filename}")
                        
                        return jsonify({
                            "success": True,
                            "message": f"Session '{filename}' restored successfully with {playlist_count} playlists",
                            "filename": filename,
                            "restore_timestamp": restore_timestamp,
                            "playlists_restored": playlist_count,
                            "requires_reload": True
                        })
                    else:
                        logger.warning("⚠️ load_from_dict returned False")
                else:
                    logger.warning("⚠️ No valid playlists data in session")
            else:
                logger.warning("⚠️ playlist_system not available")
            
            logger.info(f"🔄 Session restored (file only): {filename}")
            
            return jsonify({
                "success": True,
                "message": f"Session '{filename}' restored. Please reload the page to apply changes.",
                "filename": filename,
                "restore_timestamp": restore_timestamp,
                "requires_reload": True
            })
            
        except Exception as e:
            logger.error(f"Error restoring session: {e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/session/delete', methods=['POST'])
    def delete_saved_session():
        """Delete a saved session from /data directory."""
        try:
            data = request.get_json()
            filename = data.get('filename')
            
            if not filename:
                return jsonify({"success": False, "error": "No filename provided"}), 400
            
            save_path = os.path.join(DATA_DIR, filename)
            
            if not os.path.exists(save_path):
                return jsonify({"success": False, "error": f"Session '{filename}' not found"}), 404
            
            os.remove(save_path)
            
            logger.info(f"🗑️ Session deleted: {filename}")
            
            return jsonify({
                "success": True,
                "message": f"Session '{filename}' deleted",
                "filename": filename
            })
            
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
