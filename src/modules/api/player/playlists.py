"""
Multi-Playlist System API Routes

REST API endpoints for managing multiple playlists.
Separates ACTIVE playlist (controls playback) from VIEWED playlist (shown in GUI).
"""

import os
import uuid
import time
from flask import request, jsonify
from ...core.logger import get_logger

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
                            "index": viewed.players['video'].index,
                            "transition_config": viewed.players['video'].transition_config,
                            "global_effects": viewed.players['video'].global_effects
                        },
                        "artnet": {
                            "playlist": format_playlist_for_gui(viewed.players['artnet'].to_dict(), video_dir),
                            "autoplay": viewed.players['artnet'].autoplay,
                            "loop": viewed.players['artnet'].loop,
                            "index": viewed.players['artnet'].index,
                            "transition_config": viewed.players['artnet'].transition_config,
                            "global_effects": viewed.players['artnet'].global_effects
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
            from ...player.clips.registry import get_clip_registry
            clip_registry = get_clip_registry()
            
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
                item_type = item.get('type', 'video')
                generator_id = item.get('generator_id')
                parameters = item.get('parameters', {})
                
                if not path:
                    continue
                
                # Store generator parameters if present
                if path.startswith('generator:') and 'parameters' in item:
                    if clip_id:
                        clip_params[clip_id] = {'parameters': item['parameters']}
                    clips.append(path)
                    clip_ids.append(clip_id or str(uuid.uuid4()))
                else:
                    # Convert relative path to absolute
                    try:
                        abs_path = os.path.join(video_dir, path)
                        clips.append(abs_path)
                        
                        # Generate or use provided clip_id
                        final_clip_id = clip_id or str(uuid.uuid4())
                        clip_ids.append(final_clip_id)
                        
                        # Register clip in clip_registry if not already registered
                        # This ensures default effects (transport, transform) are applied
                        if final_clip_id not in clip_registry.clips:
                            relative_path = os.path.relpath(abs_path, video_dir) if not abs_path.startswith('generator:') else abs_path
                            metadata = {'type': item_type, 'generator_id': generator_id, 'parameters': parameters} if item_type == 'generator' else {}
                            
                            # Register the clip (this applies default effects automatically)
                            registered_id = clip_registry.register_clip(
                                player_id,
                                abs_path,
                                relative_path,
                                metadata
                            )
                            
                            # If registered_id differs from final_clip_id, update the registry
                            if registered_id != final_clip_id:
                                clip_registry.clips[final_clip_id] = clip_registry.clips[registered_id]
                                clip_registry.clips[final_clip_id]['clip_id'] = final_clip_id
                                del clip_registry.clips[registered_id]
                                logger.debug(f"📌 Registered clip {final_clip_id} with default effects")
                        
                        # ALWAYS extract clip effects from registry to clip_params (for both new and existing clips)
                        if final_clip_id in clip_registry.clips:
                            clip_data = clip_registry.clips[final_clip_id]
                            if 'effects' in clip_data and clip_data['effects']:
                                # Merge effects with existing clip_params (e.g., generator parameters)
                                if final_clip_id not in clip_params:
                                    clip_params[final_clip_id] = {}
                                clip_params[final_clip_id]['effects'] = clip_data['effects']
                                logger.info(f"📌 Extracted {len(clip_data['effects'])} effects for clip {final_clip_id[:8]}...")
                        
                    except:
                        logger.warning(f"Failed to convert path: {path}")
                        continue
            
            # Update the target playlist's player state
            player_state = target_playlist.players[player_id]
            
            # DEBUG: Log what we're updating
            logger.info(f"[UPDATE DEBUG] Updating playlist: {target_playlist.name} (id={playlist_id})")
            logger.info(f"[UPDATE DEBUG] Processing {len(clips)} clips")
            logger.info(f"[UPDATE DEBUG] clip_params populated for {len(clip_params)} clips")
            
            # Log per-clip effects summary
            for cid, params in clip_params.items():
                if 'effects' in params:
                    logger.info(f"[UPDATE DEBUG]   Clip {cid[:8]}... has {len(params['effects'])} effects")
            
            player_state.clips = clips
            player_state.clip_ids = clip_ids
            player_state.clip_params = clip_params
            player_state.autoplay = autoplay
            player_state.loop = loop
            
            # If updating the active playlist, also update the live player
            is_active = target_playlist.id == playlist_system.active_playlist_id
            if is_active:
                player = player_manager.get_player(player_id)
                if player:
                    player.playlist = clips
                    player.playlist_ids = clip_ids
                    if hasattr(player, 'playlist_params'):
                        player.playlist_params = clip_params
                        logger.info(f"[UPDATE DEBUG] Set player.playlist_params with {len(clip_params)} clip entries")
                    player.autoplay = autoplay
                    player.loop_playlist = loop
                    logger.info(f"[UPDATE DEBUG] Updated live {player_id} player (active playlist)")
            
            # Save to session state WITHOUT capturing active playlist
            # (we just explicitly updated the playlist state above)
            from ...session.state import get_session_state
            session_state = get_session_state()
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
    
    # ========================================
    # CLIP PREVIEW (for non-active playlists)
    # ========================================
    
    @app.route('/api/playlists/<playlist_id>/preview-clip', methods=['POST'], endpoint='multi_preview_clip')
    def preview_clip(playlist_id):
        """
        Load and preview a clip from any playlist (active or inactive).
        Creates a temporary preview stream for non-active playlist clips.
        
        Request body:
            {
                "player_id": "video" or "artnet",
                "clip_index": 0,  // Index in playlist
                "clip_id": "optional-clip-id"  // Alternative to index
            }
        """
        try:
            data = request.get_json()
            player_id = data.get('player_id', 'video')
            clip_index = data.get('clip_index')
            clip_id = data.get('clip_id')
            
            if clip_index is None and not clip_id:
                return jsonify({
                    "success": False,
                    "error": "Either clip_index or clip_id is required"
                }), 400
            
            playlist_system = get_playlist_system()
            if not playlist_system:
                return jsonify({"success": False, "error": "Playlist system not initialized"}), 500
            
            # Get the playlist
            playlist = playlist_system.get_playlist(playlist_id)
            if not playlist:
                return jsonify({"success": False, "error": f"Playlist {playlist_id} not found"}), 404
            
            # Get player state
            if player_id not in playlist.players:
                return jsonify({"success": False, "error": f"Player {player_id} not found"}), 404
            
            player_state = playlist.players[player_id]
            
            # Find clip by index or ID
            if clip_id:
                try:
                    clip_index = player_state.clip_ids.index(clip_id)
                except ValueError:
                    return jsonify({"success": False, "error": f"Clip ID {clip_id} not found"}), 404
            
            if clip_index < 0 or clip_index >= len(player_state.clips):
                return jsonify({"success": False, "error": "Invalid clip index"}), 404
            
            clip_path = player_state.clips[clip_index]
            actual_clip_id = player_state.clip_ids[clip_index] if clip_index < len(player_state.clip_ids) else None
            
            is_active = playlist.id == playlist_system.active_playlist_id
            
            if is_active:
                # For active playlist, load directly into the player
                player = player_manager.get_player(player_id)
                if not player:
                    return jsonify({"success": False, "error": f"Player {player_id} not available"}), 500
                
                # Load the clip by index
                success = player.load_clip_by_index(clip_index, notify_manager=True)
                
                return jsonify({
                    "success": success,
                    "mode": "active_player",
                    "message": "Clip loaded into active player" if success else "Failed to load clip"
                })
            else:
                # For non-active playlist: LIVE PREVIEW MODE
                # Use preview players to show actual playback without affecting output
                
                # Create preview players if not exists
                if not player_manager.create_preview_players():
                    return jsonify({
                        "success": False,
                        "error": "Failed to create preview players"
                    }), 500
                
                # Get the preview player
                preview_player_id = f"{player_id}_preview"
                preview_player = player_manager.get_player(preview_player_id)
                
                if not preview_player:
                    return jsonify({
                        "success": False,
                        "error": f"Preview player {preview_player_id} not available"
                    }), 500
                
                # Load the viewed playlist into preview player
                preview_player.playlist = player_state.clips.copy()
                preview_player.playlist_ids = player_state.clip_ids.copy()
                preview_player.autoplay = player_state.autoplay
                preview_player.loop_playlist = player_state.loop
                
                # Load the specific clip
                success = preview_player.load_clip_by_index(clip_index, notify_manager=False)
                
                if not success:
                    return jsonify({
                        "success": False,
                        "error": "Failed to load clip into preview player"
                    }), 500
                
                # Start preview player if not running
                if not preview_player.is_running:
                    preview_player.play()
                
                return jsonify({
                    "success": True,
                    "mode": "preview_live",
                    "message": f"Live preview: {clip_path}",
                    "clip": {
                        "path": clip_path,
                        "id": actual_clip_id,
                        "index": clip_index,
                        "type": "generator" if clip_path.startswith('generator:') else "video"
                    },
                    "preview_settings": {
                        "autoplay": player_state.autoplay,
                        "loop": player_state.loop
                    },
                    "note": "Live preview mode: Preview players running independently, active playlist continues outputting"
                })
        
        except Exception as e:
            logger.error(f"Failed to preview clip: {e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/playlists/<playlist_id>/takeover-preview/start', methods=['POST'])
    def start_takeover_preview(playlist_id):
        """
        Start takeover preview mode: Pause active playlist and play preview playlist on output.
        
        Request body (optional):
            {
                "player_id": "video" or "artnet" or null (both players),
                "clip_index": 0  // Optional: Start at specific clip index
            }
        """
        try:
            data = request.get_json() or {}
            player_id = data.get('player_id')  # None = takeover both players
            clip_index = data.get('clip_index', 0)  # Default to first clip
            
            result = player_manager.start_takeover_preview(playlist_id, player_id)
            
            if result['success']:
                # Load the preview playlist into the output players
                playlist_system = get_playlist_system()
                preview_playlist = playlist_system.get_playlist(playlist_id)
                
                if preview_playlist:
                    players_to_load = [player_id] if player_id else ['video', 'artnet']
                    
                    for pid in players_to_load:
                        player = player_manager.get_player(pid)
                        if not player:
                            continue
                        
                        player_state = preview_playlist.get_player_state(pid)
                        if not player_state:
                            continue
                        
                        # Load preview playlist
                        player.playlist = player_state.clips.copy()
                        player.playlist_ids = player_state.clip_ids.copy()
                        player.autoplay = player_state.autoplay
                        player.loop_playlist = player_state.loop
                        
                        # Load clip at specified index
                        if len(player.playlist) > 0:
                            # Clamp clip_index to valid range
                            safe_index = max(0, min(clip_index, len(player.playlist) - 1))
                            player.load_clip_by_index(safe_index, notify_manager=False)
                            player.play()
                            logger.info(f"🎬 Loaded preview playlist into {pid} player at clip {safe_index}")
                
                return jsonify(result)
            else:
                return jsonify(result), 400
        
        except Exception as e:
            logger.error(f"Failed to start takeover preview: {e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/playlists/takeover-preview/stop', methods=['POST'])
    def stop_takeover_preview():
        """
        Stop takeover preview mode and restore active playlist.
        """
        try:
            result = player_manager.stop_takeover_preview()
            
            if result['success']:
                return jsonify(result)
            else:
                return jsonify(result), 400
        
        except Exception as e:
            logger.error(f"Failed to stop takeover preview: {e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/playlists/takeover-preview/status', methods=['GET'])
    def get_takeover_preview_status():
        """
        Get current takeover preview status.
        """
        try:
            state = player_manager.get_takeover_preview_state()
            
            if state:
                return jsonify({
                    "success": True,
                    "takeover_active": True,
                    "state": state
                })
            else:
                return jsonify({
                    "success": True,
                    "takeover_active": False,
                    "state": None
                })
        
        except Exception as e:
            logger.error(f"Failed to get takeover preview status: {e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500
