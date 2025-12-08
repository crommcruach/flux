"""
WebRTC Signaling API Endpoints
Handles WebRTC offer/answer exchange and peer connection management
"""

import asyncio
import logging
import uuid
from typing import Dict
from flask import jsonify, request
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaBlackhole

from .webrtc_track import PlayerVideoTrack

logger = logging.getLogger(__name__)


# Global state for peer connections
peer_connections: Dict[str, RTCPeerConnection] = {}
video_tracks: Dict[str, PlayerVideoTrack] = {}

# Connection limits (can be overridden by config)
MAX_CONNECTIONS = 5
active_connections = 0

# Config cache
_webrtc_config = None


def cleanup_stale_connections():
    """
    Clean up connections that are in failed/closed state.
    This is a synchronous cleanup of already-closed connections.
    """
    global active_connections
    
    stale_ids = []
    for conn_id, pc in list(peer_connections.items()):
        if pc.connectionState in ["failed", "closed"]:
            stale_ids.append(conn_id)
    
    for conn_id in stale_ids:
        try:
            # Stop video track
            if conn_id in video_tracks:
                video_track = video_tracks[conn_id]
                video_track.stop()
                del video_tracks[conn_id]
            
            # Remove peer connection
            if conn_id in peer_connections:
                del peer_connections[conn_id]
            
            # Decrement connection count
            if active_connections > 0:
                active_connections -= 1
            
            logger.info(f"Cleaned up stale connection: {conn_id}, active_connections={active_connections}")
        except Exception as e:
            logger.error(f"Error cleaning stale connection {conn_id}: {e}")


def register_webrtc_routes(app, player_manager):
    """
    Register WebRTC signaling API routes.
    
    Args:
        app: Flask application instance
        player_manager: PlayerManager instance for video frames
    """
    global MAX_CONNECTIONS, _webrtc_config
    
    # Load WebRTC config from app.flux_config
    if hasattr(app, 'flux_config') and 'webrtc' in app.flux_config:
        _webrtc_config = app.flux_config.get('webrtc', {})
        MAX_CONNECTIONS = _webrtc_config.get('max_connections', 5)
        logger.info(f"WebRTC config loaded: max_connections={MAX_CONNECTIONS}, "
                   f"default_quality={_webrtc_config.get('default_quality', 'medium')}")
    else:
        logger.warning("WebRTC config not found, using defaults")
        _webrtc_config = {
            'enabled': True,
            'default_quality': 'medium',
            'max_connections': 5,
            'fallback_to_mjpeg': True
        }
    
    @app.route('/api/webrtc/offer', methods=['POST'])
    async def webrtc_offer():
        """
        Handle WebRTC offer from client.
        Creates peer connection and returns answer.
        
        Request JSON:
        {
            "sdp": "...",
            "type": "offer",
            "quality": "medium",  // optional: low, medium, high
            "player_id": "video"  // optional: video, artnet
        }
        
        Response JSON:
        {
            "sdp": "...",
            "type": "answer",
            "connection_id": "uuid",
            "success": true
        }
        """
        print("=== WEBRTC OFFER ENDPOINT CALLED ===")
        logger.info("WebRTC offer endpoint called")
        global active_connections
        
        try:
            print(f"DEBUG: active_connections={active_connections}, MAX_CONNECTIONS={MAX_CONNECTIONS}")
            
            # Clean up any stale connections first
            cleanup_stale_connections()
            
            print(f"DEBUG: After cleanup, active_connections={active_connections}")
            
            # Check connection limit
            if active_connections >= MAX_CONNECTIONS:
                print(f"DEBUG: Connection limit reached!")
                return jsonify({
                    'success': False,
                    'error': f'Connection limit reached ({MAX_CONNECTIONS} max)',
                    'max_connections': MAX_CONNECTIONS,
                    'active_connections': active_connections
                }), 429
            else:
                print(f"DEBUG: Connection limit OK, proceeding...")
            
            data = request.json
            print(f"DEBUG: Got request data, keys={list(data.keys())}")
            
            try:
                offer_sdp = data.get('sdp')
                offer_type = data.get('type')
                quality = data.get('quality', _webrtc_config.get('default_quality', 'medium'))
                player_id = data.get('player_id', 'video')
                
                print(f"DEBUG: offer_type={offer_type}, quality={quality}, player_id={player_id}")
                
                if not offer_sdp or offer_type != 'offer':
                    print(f"DEBUG: Invalid offer data")
                    return jsonify({
                        'success': False,
                        'error': 'Invalid offer: missing sdp or type != offer'
                    }), 400
            
                # Validate quality
                print(f"DEBUG: Validating quality preset...")
                if quality not in PlayerVideoTrack.QUALITY_PRESETS:
                    quality = _webrtc_config.get('default_quality', 'medium')
                    logger.warning(f"Invalid quality preset, using '{quality}': {data.get('quality')}")
                
                # Generate connection ID
                connection_id = str(uuid.uuid4())
                print(f"DEBUG: Generated connection_id={connection_id}")
                
                logger.info(f"WebRTC offer received: connection_id={connection_id}, quality={quality}, player={player_id}")
                
                # Get STUN servers from config (empty for LAN-only)
                stun_servers = _webrtc_config.get('stun_servers', [])
                lan_only = _webrtc_config.get('lan_only', True)
                print(f"DEBUG: LAN-only={lan_only}, STUN servers={stun_servers}")
                
                # Create RTCPeerConnection optimized for LAN
                ice_servers = [RTCIceServer(urls=[url]) for url in stun_servers] if stun_servers else []
                configuration = RTCConfiguration(iceServers=ice_servers)
                
                print(f"DEBUG: Creating RTCPeerConnection...")
                # For LAN-only, aiortc will use host candidates only (no STUN/TURN)
                pc = RTCPeerConnection(configuration=configuration)
                print(f"DEBUG: RTCPeerConnection created successfully")
                
                logger.info(f"Created RTCPeerConnection for {connection_id} (LAN-only={lan_only}, ICE servers={len(ice_servers)})")
                peer_connections[connection_id] = pc
            
                # Handle connection state changes
                @pc.on("connectionstatechange")
                async def on_connectionstatechange():
                    print(f"DEBUG: Connection state changed: {pc.connectionState} (id={connection_id})")
                    logger.info(f"WebRTC connection state: {pc.connectionState} (id={connection_id})")
                    if pc.connectionState in ["failed", "closed"]:
                        print(f"DEBUG: Connection failed/closed, cleaning up {connection_id}")
                        await cleanup_connection(connection_id)
                
                @pc.on("iceconnectionstatechange")
                async def on_iceconnectionstatechange():
                    print(f"DEBUG: ICE state changed: {pc.iceConnectionState} (id={connection_id})")
                    logger.info(f"ICE connection state: {pc.iceConnectionState} (id={connection_id})")
                
                @pc.on("icegatheringstatechange")
                async def on_icegatheringstatechange():
                    print(f"DEBUG: ICE gathering state: {pc.iceGatheringState} (id={connection_id})")
                
                @pc.on("track")
                def on_track(track):
                    print(f"DEBUG: Track event received: {track.kind} (id={connection_id})")
                    logger.info(f"Track received: {track.kind} (id={connection_id})")
                
                print(f"DEBUG: Setting remote description...")
                print(f"DEBUG: Offer SDP (first 500 chars): {offer_sdp[:500]}")
                # Set remote description (offer) first
                offer = RTCSessionDescription(sdp=offer_sdp, type=offer_type)
                await pc.setRemoteDescription(offer)
                print(f"DEBUG: Remote description set successfully")
                
                print(f"DEBUG: Creating video track...")
                # Create video track with config
                video_track = PlayerVideoTrack(
                    player_manager, 
                    quality=quality, 
                    player_id=player_id,
                    config=_webrtc_config
                )
                video_tracks[connection_id] = video_track
                print(f"DEBUG: Video track created: {video_track.width}x{video_track.height} @ {video_track.fps}fps")
            
                print(f"DEBUG: Finding video transceiver...")
                # Find existing video transceiver from the offer and add our track
                video_transceiver = None
                for transceiver in pc.getTransceivers():
                    if transceiver.kind == "video":
                        video_transceiver = transceiver
                        logger.info(f"Found video transceiver: mid={transceiver.mid}, direction={transceiver.direction}")
                        break
                
                if video_transceiver:
                    print(f"DEBUG: Replacing track in existing transceiver (current direction={video_transceiver.direction})...")
                    # Replace the track in existing transceiver (not async in aiortc)
                    video_transceiver.sender.replaceTrack(video_track)
                    # Set direction to sendonly (server sends video to client)
                    video_transceiver.direction = "sendonly"
                    print(f"DEBUG: Track replaced, direction set to: {video_transceiver.direction}")
                    logger.info(f"Replaced track in transceiver mid={video_transceiver.mid}, direction={video_transceiver.direction}")
                else:
                    print(f"DEBUG: No transceiver found, adding track...")
                    # No video transceiver in offer, add our own
                    pc.addTrack(video_track)
                    logger.warning("No video transceiver in offer, added new track")
                
                logger.debug(f"Video track added to connection {connection_id}, transceivers: {len(pc.getTransceivers())}")
                
                print(f"DEBUG: Creating answer...")
                # Create answer
                answer = await pc.createAnswer()
                print(f"DEBUG: Setting local description...")
                await pc.setLocalDescription(answer)
                print(f"DEBUG: Local description set")
            
                print(f"DEBUG: Waiting for ICE gathering (state={pc.iceGatheringState})...")
                # Wait for ICE gathering to complete (with timeout)
                logger.info(f"Waiting for ICE gathering... (state={pc.iceGatheringState})")
                
                # Give ICE a moment to gather candidates (aiortc gathers them automatically)
                # For LAN, this should be very fast
                await asyncio.sleep(0.1)
                
                print(f"DEBUG: ICE gathering done (state={pc.iceGatheringState})")
                print(f"DEBUG: Answer SDP (first 500 chars): {pc.localDescription.sdp[:500]}")
                logger.info(f"ICE gathering done (state={pc.iceGatheringState})")
                
                # Increment connection count
                active_connections += 1
                
                print(f"DEBUG: Sending answer back to client...")
                logger.info(f"WebRTC answer created: connection_id={connection_id}, active_connections={active_connections}")
                
                response = {
                    'success': True,
                    'sdp': pc.localDescription.sdp,
                    'type': pc.localDescription.type,
                    'connection_id': connection_id,
                    'quality': quality,
                    'resolution': f'{video_track.width}x{video_track.height}',
                    'fps': video_track.fps,
                    'active_connections': active_connections,
                    'max_connections': MAX_CONNECTIONS
                }
                print(f"DEBUG: Answer ready, returning response")
                return jsonify(response)
            
            except Exception as e:
                print(f"DEBUG: Exception caught: {type(e).__name__}: {e}")
                logger.error(f"WebRTC offer error: {e}", exc_info=True)
                import traceback
                traceback.print_exc()
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        except Exception as e:
            print(f"DEBUG: Outer exception caught: {type(e).__name__}: {e}")
            logger.error(f"WebRTC offer error (outer): {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/webrtc/close', methods=['POST'])
    async def webrtc_close():
        """
        Close WebRTC connection.
        
        Request JSON:
        {
            "connection_id": "uuid"
        }
        """
        try:
            data = request.json
            connection_id = data.get('connection_id')
            
            if not connection_id:
                return jsonify({
                    'success': False,
                    'error': 'Missing connection_id'
                }), 400
            
            await cleanup_connection(connection_id)
            
            return jsonify({
                'success': True,
                'message': f'Connection {connection_id} closed'
            })
        
        except Exception as e:
            logger.error(f"WebRTC close error: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/webrtc/stats', methods=['GET'])
    def webrtc_stats():
        """
        Get WebRTC connection statistics.
        
        Response JSON:
        {
            "active_connections": 2,
            "max_connections": 5,
            "connections": [
                {
                    "connection_id": "uuid",
                    "state": "connected",
                    "quality": "medium",
                    "stats": {...}
                }
            ]
        }
        """
        try:
            connections_info = []
            
            for conn_id, pc in peer_connections.items():
                video_track = video_tracks.get(conn_id)
                track_stats = video_track.get_stats() if video_track else {}
                
                connections_info.append({
                    'connection_id': conn_id,
                    'state': pc.connectionState,
                    'ice_state': pc.iceConnectionState,
                    'quality': track_stats.get('quality', 'unknown'),
                    'resolution': track_stats.get('resolution', 'unknown'),
                    'target_fps': track_stats.get('target_fps', 0),
                    'stats': track_stats
                })
            
            return jsonify({
                'success': True,
                'active_connections': active_connections,
                'max_connections': MAX_CONNECTIONS,
                'connections': connections_info
            })
        
        except Exception as e:
            logger.error(f"WebRTC stats error: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/webrtc/quality', methods=['POST'])
    async def webrtc_quality():
        """
        Change quality of existing connection.
        Requires recreating the connection with new track.
        
        Request JSON:
        {
            "connection_id": "uuid",
            "quality": "high"
        }
        """
        try:
            data = request.json
            connection_id = data.get('connection_id')
            quality = data.get('quality', 'medium')
            
            if not connection_id or connection_id not in peer_connections:
                return jsonify({
                    'success': False,
                    'error': 'Invalid or missing connection_id'
                }), 400
            
            if quality not in PlayerVideoTrack.QUALITY_PRESETS:
                return jsonify({
                    'success': False,
                    'error': f'Invalid quality: {quality}',
                    'valid_qualities': list(PlayerVideoTrack.QUALITY_PRESETS.keys())
                }), 400
            
            # Get existing track info
            old_track = video_tracks.get(connection_id)
            player_id = old_track.player_id if old_track else 'video'
            
            logger.info(f"WebRTC quality change requested: connection_id={connection_id}, "
                       f"old_quality={old_track.quality if old_track else 'unknown'}, new_quality={quality}")
            
            return jsonify({
                'success': False,
                'error': 'Quality change requires reconnection',
                'message': 'Close current connection and create new one with desired quality',
                'current_quality': old_track.quality if old_track else 'unknown',
                'requested_quality': quality
            }), 400
        
        except Exception as e:
            logger.error(f"WebRTC quality change error: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


async def cleanup_connection(connection_id: str):
    """
    Cleanup peer connection and associated resources.
    
    Args:
        connection_id: Connection UUID to cleanup
    """
    global active_connections
    
    try:
        # Stop video track
        if connection_id in video_tracks:
            video_track = video_tracks[connection_id]
            try:
                video_track.stop()
            except Exception as e:
                logger.warning(f"Error stopping video track {connection_id}: {e}")
            del video_tracks[connection_id]
            logger.info(f"Video track stopped: {connection_id}")
        
        # Close peer connection
        if connection_id in peer_connections:
            pc = peer_connections[connection_id]
            try:
                await pc.close()
            except RuntimeError as e:
                # Event loop might be closed, just remove the connection
                if "Event loop is closed" in str(e):
                    logger.debug(f"Event loop closed during cleanup of {connection_id}, removing from registry")
                else:
                    raise
            except Exception as e:
                logger.warning(f"Error closing peer connection {connection_id}: {e}")
            
            del peer_connections[connection_id]
            logger.info(f"Peer connection closed: {connection_id}")
        
        # Decrement connection count
        if active_connections > 0:
            active_connections -= 1
        
        logger.info(f"Connection cleaned up: {connection_id}, active_connections={active_connections}")
    
    except Exception as e:
        logger.error(f"Cleanup error for {connection_id}: {e}", exc_info=True)
        # Still decrement counter and remove from dicts to avoid leaks
        if connection_id in video_tracks:
            del video_tracks[connection_id]
        if connection_id in peer_connections:
            del peer_connections[connection_id]
        if active_connections > 0:
            active_connections -= 1


# Cleanup all connections on shutdown
async def cleanup_all_connections():
    """Cleanup all active connections."""
    logger.info(f"Cleaning up all WebRTC connections ({len(peer_connections)} active)")
    
    connection_ids = list(peer_connections.keys())
    for connection_id in connection_ids:
        await cleanup_connection(connection_id)
    
    logger.info("All WebRTC connections cleaned up")
