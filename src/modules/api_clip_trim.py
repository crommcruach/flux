"""
API Endpoints for Clip Trimming & Playback Control
Provides trim in/out points and reverse playback control.

DEPRECATED: This API is deprecated in favor of the Transport Effect Plugin.
Use the "Transport" effect from the effects panel for:
- Trimming (in/out points)
- Speed control (0.1x - 10x)
- Reverse playback
- Playback modes (repeat, play_once, bounce, random)
- Real-time position tracking

This API is kept for backwards compatibility but will be removed in a future version.
"""
from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)


def register_clip_trim_api(app, clip_registry, player_manager):
    """
    Registriert API-Endpoints für Clip Trimming & Playback Control.
    
    Args:
        app: Flask app instance
        clip_registry: ClipRegistry instance
        player_manager: PlayerManager instance for accessing active player
    """
    
    @app.route('/api/clips/<clip_id>/trim', methods=['POST'])
    def set_clip_trim(clip_id):
        """
        Setzt In/Out Points für Clip-Trimming.
        
        POST /api/clips/<clip_id>/trim
        Body: {
            "in_point": <frame_number or null>,
            "out_point": <frame_number or null>
        }
        """
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"success": False, "error": "No data provided"}), 400
            
            in_point = data.get('in_point')
            out_point = data.get('out_point')
            
            # Validate frame numbers
            if in_point is not None and not isinstance(in_point, int):
                return jsonify({"success": False, "error": "in_point must be integer or null"}), 400
            
            if out_point is not None and not isinstance(out_point, int):
                return jsonify({"success": False, "error": "out_point must be integer or null"}), 400
            
            if in_point is not None and out_point is not None and in_point >= out_point:
                return jsonify({"success": False, "error": "in_point must be less than out_point"}), 400
            
            # Set trim points
            success = clip_registry.set_clip_trim(clip_id, in_point, out_point)
            
            if not success:
                return jsonify({"success": False, "error": f"Clip {clip_id} not found"}), 404
            
            return jsonify({
                "success": True,
                "clip_id": clip_id,
                "in_point": in_point,
                "out_point": out_point
            })
            
        except Exception as e:
            logger.error(f"Error setting clip trim: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/clips/<clip_id>/reverse', methods=['POST'])
    def set_clip_reverse(clip_id):
        """
        Aktiviert/deaktiviert Rückwärts-Wiedergabe.
        
        POST /api/clips/<clip_id>/reverse
        Body: {
            "enabled": <boolean>
        }
        """
        try:
            data = request.get_json()
            
            if not data or 'enabled' not in data:
                return jsonify({"success": False, "error": "No 'enabled' field provided"}), 400
            
            enabled = bool(data['enabled'])
            
            # Set reverse mode
            success = clip_registry.set_clip_reverse(clip_id, enabled)
            
            if not success:
                return jsonify({"success": False, "error": f"Clip {clip_id} not found"}), 404
            
            return jsonify({
                "success": True,
                "clip_id": clip_id,
                "reverse": enabled
            })
            
        except Exception as e:
            logger.error(f"Error setting clip reverse: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/clips/<clip_id>/playback', methods=['GET'])
    def get_clip_playback(clip_id):
        """
        Holt Playback-Informationen für Clip.
        
        GET /api/clips/<clip_id>/playback
        Returns: {
            "in_point": <frame_number or null>,
            "out_point": <frame_number or null>,
            "reverse": <boolean>,
            "filename": <string>,
            "relative_path": <string>
        }
        """
        try:
            playback_info = clip_registry.get_clip_playback_info(clip_id)
            
            if not playback_info:
                return jsonify({"success": False, "error": f"Clip {clip_id} not found"}), 404
            
            return jsonify({
                "success": True,
                "clip_id": clip_id,
                **playback_info
            })
            
        except Exception as e:
            logger.error(f"Error getting clip playback info: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/clips/<clip_id>/reset-trim', methods=['POST'])
    def reset_clip_trim(clip_id):
        """
        Setzt Trimming zurück (voller Clip).
        
        POST /api/clips/<clip_id>/reset-trim
        """
        try:
            # Reset to full clip (None = start/end)
            success = clip_registry.set_clip_trim(clip_id, None, None)
            
            if not success:
                return jsonify({"success": False, "error": f"Clip {clip_id} not found"}), 404
            
            return jsonify({
                "success": True,
                "clip_id": clip_id,
                "message": "Trim reset to full clip"
            })
            
        except Exception as e:
            logger.error(f"Error resetting clip trim: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/clips/<clip_id>/reload', methods=['POST'])
    def reload_clip_settings(clip_id):
        """Lädt Trim-Einstellungen für aktiven Clip neu - oder lädt Clip wenn Settings geändert wurden."""
        try:
            logger.info(f"Reload trim settings for clip {clip_id}")
            
            # Strategy: 
            # 1. Check if clip is currently loaded in any player -> reload trim settings
            # 2. If not loaded, just save settings (will be applied on next load)
            
            from .frame_source import VideoSource
            reloaded = False
            
            for player_id in ['video', 'artnet']:
                player = player_manager.get_player(player_id)
                
                if player:
                    current_id = getattr(player, 'current_clip_id', None)
                    logger.info(f"  [{player_id}] player.current_clip_id = {current_id} (looking for {clip_id})")
                else:
                    logger.info(f"  [{player_id}] player not found")
                
                if player and hasattr(player, 'current_clip_id') and player.current_clip_id == clip_id:
                    # Clip is currently loaded - reload trim settings
                    logger.info(f"  ✅ MATCH FOUND! Reloading trim for {player_id} player")
                    
                    # Get actual VideoSource - could be in layers or direct source
                    source = None
                    if hasattr(player, 'layers') and player.layers:
                        source = player.layers[0].source  # Layer 0 is the master/base layer
                        logger.info(f"  Using layer[0] source: {type(source).__name__}")
                    else:
                        source = player.source
                        logger.info(f"  Using direct source: {type(source).__name__}")
                    
                    logger.info(f"  Source has reload_trim_settings: {hasattr(source, 'reload_trim_settings')}")
                    
                    if isinstance(source, VideoSource) and hasattr(source, 'reload_trim_settings'):
                        reload_result = source.reload_trim_settings()
                        logger.info(f"  reload_trim_settings() returned: {reload_result}")
                        if reload_result:
                            reloaded = True
                            logger.info(f"✅ Reloaded trim settings for clip in {player_id} player")
                    else:
                        logger.warning(f"  Source in {player_id} is not VideoSource: {type(source).__name__}")
            
            if reloaded:
                return jsonify({
                    'success': True,
                    'message': 'Trim settings applied to active playback',
                    'reloaded': True
                })
            else:
                # Clip not currently playing - settings will apply on next load
                logger.info(f"Clip {clip_id} not currently playing - settings saved for next load")
                return jsonify({
                    'success': True,
                    'message': 'Settings saved (will apply when clip is loaded)',
                    'reloaded': False
                })
        
        except Exception as e:
            logger.error(f"Error reloading clip settings: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    logger.info("✅ Clip Trim API registered")
