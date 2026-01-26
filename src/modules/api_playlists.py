"""
Multi-Playlist System API Routes

REST API endpoints for managing multiple playlists.
Separates ACTIVE playlist (controls playback) from VIEWED playlist (shown in GUI).
"""

import os
import uuid
from flask import request, jsonify
from .logger import get_logger

logger = get_logger(__name__)

# Global reference to playlist system (set during initialization)
_playlist_system = None


def set_playlist_system(playlist_system):
    """Set the global playlist system reference"""
    global _playlist_system
    _playlist_system = playlist_system


def get_playlist_system():
    """Get the global playlist system reference"""
    return _playlist_system


def register_playlist_routes(app, player_manager, config, socketio=None):
    """
    Register all playlist-related API routes.
    
    Args:
        app: Flask app instance
        player_manager: PlayerManager instance
        config: Configuration dict with video_dir path
        socketio: SocketIO instance (optional)
    """
    
    video_dir = config['paths']['video_dir']
    
    def format_playlist_for_gui(player_state_dict, video_dir):
        """
        Format player state for GUI in same format as /api/player/status
        This ensures consistent behavior between initial load and playlist switching
        """
        playlist = []
        clips = player_state_dict.get('clips', [])
        clip_ids = player_state_dict.get('clip_ids', [])
        clip_params = player_state_dict.get('clip_params', {})
        
        for idx, path in enumerate(clips):
            if path.startswith('generator:'):
                # Generator item
                generator_id = path.replace('generator:', '')
                playlist_item = {
                    'path': path,
                    'type': 'generator',
                    'generator_id': generator_id
                }
                # Include parameters if stored (keyed by clip_id)
                clip_id = clip_ids[idx] if idx < len(clip_ids) else None
                if clip_id and clip_id in clip_params:
                    playlist_item['parameters'] = clip_params[clip_id]
            else:
                # Regular video - relativize path
                try:
                    rel_path = os.path.relpath(path, video_dir)
                except:
                    rel_path = path
                playlist_item = {
                    'path': rel_path,
                    'type': 'video'
                }
            
            # Add clip ID
            if idx < len(clip_ids):
                playlist_item['id'] = clip_ids[idx]
            
            playlist.append(playlist_item)
        
        return playlist
    
    # ========================================
    # PLAYLIST CRUD
    # ========================================
    
    @app.route('/api/playlists/create', methods=['POST'], endpoint='multi_create_playlist')
    def create_playlist():
        """Create a new playlist"""
        try:
            data = request.get_json()
            name = data.get('name')
            playlist_type = data.get('type', 'standard')
            
            if not name:
                return jsonify({"success": False, "error": "Name is required"}), 400
            
            playlist_system = get_playlist_system()
            if not playlist_system:
                return jsonify({"success": False, "error": "Playlist system not initialized"}), 500
            
            playlist = playlist_system.create_playlist(name, playlist_type)
            
            return jsonify({
                "success": True,
                "playlist": {
                    "id": playlist.id,
                    "name": playlist.name,
                    "type": playlist.type,
                    "created_at": playlist.created_at.isoformat(),
                    "sequencer_mode": playlist.sequencer.get('mode_active', False),
                    "master_player": playlist.master_player
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to create playlist: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/playlists/<playlist_id>', methods=['DELETE'], endpoint='multi_delete_playlist')
    def delete_playlist(playlist_id):
        """Delete a playlist"""
        try:
            playlist_system = get_playlist_system()
            if not playlist_system:
                return jsonify({"success": False, "error": "Playlist system not initialized"}), 500
            
            success = playlist_system.delete_playlist(playlist_id)
            
            if success:
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Failed to delete playlist"}), 400
                
        except Exception as e:
            logger.error(f"Failed to delete playlist: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/playlists/<playlist_id>/rename', methods=['PUT'], endpoint='multi_rename_playlist')
    def rename_playlist(playlist_id):
        """Rename a playlist"""
        try:
            data = request.get_json()
            new_name = data.get('name')
            
            if not new_name:
                return jsonify({"success": False, "error": "Name is required"}), 400
            
            playlist_system = get_playlist_system()
            if not playlist_system:
                return jsonify({"success": False, "error": "Playlist system not initialized"}), 500
            
            success = playlist_system.rename_playlist(playlist_id, new_name)
            
            if success:
                return jsonify({"success": True, "name": new_name})
            else:
                return jsonify({"success": False, "error": "Playlist not found"}), 404
                
        except Exception as e:
            logger.error(f"Failed to rename playlist: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/playlists/list', methods=['GET'], endpoint='multi_list_playlists')
    def list_playlists():
        """Get list of all playlists"""
        try:
            playlist_system = get_playlist_system()
            if not playlist_system:
                return jsonify({"success": False, "error": "Playlist system not initialized"}), 500
            
            playlists = playlist_system.list_playlists()
            
            return jsonify({
                "success": True,
                "playlists": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "type": p.type,
                        "created_at": p.created_at.isoformat(),
                        "sequencer_mode": p.sequencer.get('mode_active', False),
                        "master_player": p.master_player,
                        "is_active": p.id == playlist_system.active_playlist_id,
                        "is_viewed": p.id == playlist_system.viewed_playlist_id
                    }
                    for p in playlists
                ],
                "active_playlist_id": playlist_system.active_playlist_id,
                "viewed_playlist_id": playlist_system.viewed_playlist_id
            })
            
        except Exception as e:
            logger.error(f"Failed to list playlists: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    # ========================================
    # PLAYLIST CONTROL
    # ========================================
    
    @app.route('/api/playlists/activate', methods=['POST'], endpoint='multi_activate_playlist')
    def activate_playlist():
        """
        Activate playlist (change which playlist controls playback).
        This applies the playlist state to ALL players at once.
        Also updates viewed playlist to match active.
        """
        try:
            data = request.get_json()
            playlist_id = data.get('playlist_id')
            
            if not playlist_id:
                return jsonify({"success": False, "error": "playlist_id is required"}), 400
            
            playlist_system = get_playlist_system()
            if not playlist_system:
                return jsonify({"success": False, "error": "Playlist system not initialized"}), 500
            
            success = playlist_system.activate_playlist(playlist_id)
            
            if success:
                active = playlist_system.get_active_playlist()
                
                return jsonify({
                    "success": True,
                    "active_playlist": {
                        "id": active.id,
                        "name": active.name,
                        "type": active.type,
                        "master_player": active.master_player,
                        "sequencer_mode": active.sequencer.get('mode_active', False),
                        "video": active.players['video'].to_dict(),
                        "artnet": active.players['artnet'].to_dict(),
                        "sequencer": active.sequencer
                    }
                })
            else:
                return jsonify({"success": False, "error": "Playlist not found"}), 404
                
        except Exception as e:
            logger.error(f"Failed to activate playlist: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/playlists/view', methods=['POST'], endpoint='multi_view_playlist')
    def view_playlist():
        """
        Set which playlist the GUI is displaying/editing.
        Does NOT affect playback - active playlist continues in background.
        This allows user to edit one playlist while another is playing.
        """
        try:
            data = request.get_json()
            playlist_id = data.get('playlist_id')
            
            if not playlist_id:
                return jsonify({"success": False, "error": "playlist_id is required"}), 400
            
            playlist_system = get_playlist_system()
            if not playlist_system:
                return jsonify({"success": False, "error": "Playlist system not initialized"}), 500
            
            success = playlist_system.set_viewed_playlist(playlist_id)
            
            if success:
                viewed = playlist_system.get_viewed_playlist()
                active_id = playlist_system.active_playlist_id
                is_active = viewed.id == active_id
                
                # DEBUG: Log what we're returning
                logger.info(f"[VIEW DEBUG] Viewing playlist: {viewed.name} (id={viewed.id}, active={is_active})")
                logger.info(f"[VIEW DEBUG] Stored video clips: {viewed.players['video'].clips}")
                logger.info(f"[VIEW DEBUG] Stored video clip_ids: {viewed.players['video'].clip_ids}")
                
                # If viewing the active playlist, get live data from players
                # (active playlist state is in players, not saved to playlist object yet)
                if is_active:
                    # Get live player data (only video and artnet - sequencer is separate)
                    players_data = {}
                    for player_id in ['video', 'artnet']:
                        player = player_manager.get_player(player_id)
                        if player:
                            players_data[player_id] = {
                                "clips": list(player.playlist) if player.playlist else [],
                                "clip_ids": list(player.playlist_ids) if player.playlist_ids else [],
                                "index": player.playlist_index,
                                "autoplay": player.autoplay,
                                "loop": player.loop_playlist,
                                "is_playing": getattr(player, 'is_playing', False)
                            }
                else:
                    # Get stored playlist data for inactive playlists
                    players_data = {
                        player_id: {
                            "clips": state.clips,
                            "clip_ids": state.clip_ids,
                            "index": state.index,
                            "autoplay": state.autoplay,
                            "loop": state.loop,
                            "is_playing": state.is_playing
                        }
                        for player_id, state in viewed.players.items()
                    }
                
                return jsonify({
                    "success": True,
                    "viewed_playlist": {
                        "id": viewed.id,
                        "name": viewed.name,
                        "type": viewed.type,
                        "is_active": is_active,
                        "master_player": viewed.master_player,
                        "sequencer_mode": viewed.sequencer.get('mode_active', False),
                        "video": {
                            "playlist": format_playlist_for_gui(viewed.players['video'].to_dict(), video_dir),
                            "autoplay": viewed.players['video'].autoplay,
                            "loop": viewed.players['video'].loop,
                            "index": viewed.players['video'].index
                        },
                        "artnet": {
                            "playlist": format_playlist_for_gui(viewed.players['artnet'].to_dict(), video_dir),
                            "autoplay": viewed.players['artnet'].autoplay,
                            "loop": viewed.players['artnet'].loop,
                            "index": viewed.players['artnet'].index
                        },
                        "sequencer": viewed.sequencer
                    },
                    "active_playlist_id": active_id
                })
            else:
                return jsonify({"success": False, "error": "Playlist not found"}), 404
                
        except Exception as e:
            logger.error(f"Failed to view playlist: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/playlists/update_player', methods=['POST'], endpoint='multi_update_playlist_player')
    def update_playlist_player():
        """
        Update a specific player's playlist content in a SPECIFIC playlist.
        REQUIRES playlist_id - will fail if not provided.
        If the specified playlist is also active, changes are applied to live player.
        """
        try:
            data = request.get_json()
            playlist_id = data.get('playlist_id')
            player_id = data.get('player_id')
            playlist_data = data.get('playlist', [])
            autoplay = data.get('autoplay', False)
            loop = data.get('loop', False)
            
            # MANDATORY: playlist_id must be provided
            if not playlist_id:
                return jsonify({"success": False, "error": "playlist_id is required"}), 400
            
            if not player_id or player_id not in ['video', 'artnet']:
                return jsonify({"success": False, "error": "Invalid player_id"}), 400
            
            playlist_system = get_playlist_system()
            if not playlist_system:
                return jsonify({"success": False, "error": "Playlist system not initialized"}), 500
            
            # Get the specific playlist by ID
            if playlist_id not in playlist_system.playlists:
                return jsonify({"success": False, "error": f"Playlist {playlist_id} not found"}), 404
            
            target_playlist = playlist_system.playlists[playlist_id]
            
            # Convert playlist items to absolute paths and extract IDs
            clips = []
            clip_ids = []
            clip_params = {}
            
            for item in playlist_data:
                path = item.get('path', '')
                clip_id = item.get('id')
                
                if not path:
                    continue
                
                # Store generator parameters if present
                if path.startswith('generator:') and 'parameters' in item:
                    if clip_id:
                        clip_params[clip_id] = item['parameters']
                    clips.append(path)
                    clip_ids.append(clip_id or str(uuid.uuid4()))
                else:
                    # Convert relative path to absolute
                    try:
                        abs_path = os.path.join(video_dir, path)
                        clips.append(abs_path)
                        clip_ids.append(clip_id or str(uuid.uuid4()))
                    except:
                        logger.warning(f"Failed to convert path: {path}")
                        continue
            
            # Update the target playlist's player state
            player_state = target_playlist.players[player_id]
            
            # DEBUG: Log what we're updating
            logger.info(f"[UPDATE DEBUG] Updating playlist: {target_playlist.name} (id={playlist_id})")
            logger.info(f"[UPDATE DEBUG] Before update - clips: {player_state.clips}")
            logger.info(f"[UPDATE DEBUG] New clips to set: {clips}")
            
            player_state.clips = clips
            player_state.clip_ids = clip_ids
            player_state.clip_params = clip_params
            player_state.autoplay = autoplay
            player_state.loop = loop
            
            # DEBUG: Log after update
            logger.info(f"[UPDATE DEBUG] After update - clips: {player_state.clips}")
            
            # If updating the active playlist, also update the live player
            is_active = target_playlist.id == playlist_system.active_playlist_id
            if is_active:
                player = player_manager.get_player(player_id)
                if player:
                    player.playlist = clips
                    player.playlist_ids = clip_ids
                    if hasattr(player, 'playlist_params'):
                        player.playlist_params = clip_params
                    player.autoplay = autoplay
                    player.loop_playlist = loop
                    logger.info(f"Updated live {player_id} player (active playlist)")
            
            # Save to session state WITHOUT capturing active playlist
            # (we just explicitly updated the playlist state above)
            from .session_state import get_session_state
            from .clip_registry import get_clip_registry
            session_state = get_session_state()
            clip_registry = get_clip_registry()
            session_state.save_without_capture(player_manager, clip_registry)
            
            logger.info(f"Updated {player_id} playlist in '{target_playlist.name}' (id={playlist_id}, active={is_active})")
            
            return jsonify({
                "success": True,
                "playlist_id": target_playlist.id,
                "player_id": player_id,
                "is_active": is_active,
                "clip_count": len(clips)
            })
            
        except Exception as e:
            logger.error(f"Failed to update playlist player: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/playlists/<playlist_id>', methods=['GET'], endpoint='multi_get_playlist')
    def get_playlist(playlist_id):
        """Get detailed information about a specific playlist"""
        try:
            playlist_system = get_playlist_system()
            if not playlist_system:
                return jsonify({"success": False, "error": "Playlist system not initialized"}), 500
            
            playlist = playlist_system.get_playlist(playlist_id)
            
            if not playlist:
                return jsonify({"success": False, "error": "Playlist not found"}), 404
            
            return jsonify({
                "success": True,
                "playlist": {
                    "id": playlist.id,
                    "name": playlist.name,
                    "type": playlist.type,
                    "created_at": playlist.created_at.isoformat(),
                    "sequencer_mode": playlist.sequencer.get('mode_active', False),
                    "master_player": playlist.master_player,
                    "is_active": playlist.id == playlist_system.active_playlist_id,
                    "is_viewed": playlist.id == playlist_system.viewed_playlist_id,
                    "video": playlist.players['video'].to_dict(),
                    "artnet": playlist.players['artnet'].to_dict(),
                    "sequencer": playlist.sequencer
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to get playlist: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    # ========================================
    # STATE MANAGEMENT
    # ========================================
    
    @app.route('/api/playlists/save-state', methods=['POST'], endpoint='multi_save_state')
    def save_state():
        """Manually save current state to viewed playlist"""
        try:
            playlist_system = get_playlist_system()
            if not playlist_system:
                return jsonify({"success": False, "error": "Playlist system not initialized"}), 500
            
            # Capture active playlist state
            if playlist_system.active_playlist_id:
                playlist_system.capture_active_playlist_state()
                playlist_system._auto_save()
            
            return jsonify({"success": True})
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    logger.info("Multi-Playlist API routes registered")
