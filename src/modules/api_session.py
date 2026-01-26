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

logger = get_logger(__name__)

# Create blueprint
session_api = Blueprint('session_api', __name__)


def register_session_routes(app, session_state_manager):
    """Register session snapshot routes."""
    
    SNAPSHOTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'snapshots')
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    
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
        """Restore a snapshot including sequencer state (requires page reload)."""
        try:
            data = request.get_json()
            filename = data.get('filename')
            
            if not filename:
                return jsonify({"success": False, "error": "No filename provided"}), 400
            
            snapshot_path = os.path.join(SNAPSHOTS_DIR, filename)
            
            if not os.path.exists(snapshot_path):
                return jsonify({"success": False, "error": f"Snapshot '{filename}' not found"}), 404
            
            # Copy snapshot to session_state.json
            session_state_path = session_state_manager.get_state_file_path()
            
            shutil.copy2(snapshot_path, session_state_path)
            
            logger.info(f"🔄 Snapshot restored: {filename}")
            
            return jsonify({
                "success": True,
                "message": f"Snapshot '{filename}' restored. Please reload the page to apply changes.",
                "filename": filename,
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
