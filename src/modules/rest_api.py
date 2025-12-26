"""
Flask REST API mit WebSocket für Flux Steuerung
"""
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os
import threading
from collections import deque
from .logger import get_logger, debug_api, debug_log, DebugCategories
from .command_executor import CommandExecutor

logger = get_logger(__name__)
from .constants import (
    CONSOLE_LOG_MAX_LENGTH,
    DEFAULT_API_PORT,
    VIDEO_EXTENSIONS
)


class RestAPI:
    """REST API Server mit WebSocket für Video-Player Steuerung."""
    
    def __init__(self, player_manager, dmx_controller, data_dir, video_dir, config=None, replay_manager=None):
        self.player_manager = player_manager
        self.dmx_controller = dmx_controller
        self.data_dir = data_dir
        self.video_dir = video_dir
        self.config = config or {}
        self.replay_manager = replay_manager
        self.logger = logger  # Add logger as instance attribute
        
        # Traffic Counter für Stream-APIs
        import time
        self.stream_traffic = {
            'preview': {'bytes': 0, 'frames': 0, 'start_time': time.time()},
            'fullscreen': {'bytes': 0, 'frames': 0, 'start_time': time.time()}
        }
        
        # Initialize unified command executor
        self.command_executor = CommandExecutor(
            player_provider=lambda: self.player_manager.player,
            dmx_controller=dmx_controller,
            video_dir=video_dir,
            data_dir=data_dir,
            config=config or {}
        )
        
        # Console Log Buffer aus config oder default
        console_maxlen = self.config.get('api', {}).get('console_log_maxlen', CONSOLE_LOG_MAX_LENGTH)
        self.console_log = deque(maxlen=console_maxlen)
        
        # Flask App erstellen - static_folder muss absoluter Pfad sein
        # Pfad: src/modules -> src -> root -> frontend
        static_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'frontend')
        self.app = Flask(__name__, static_folder=static_path, static_url_path='')
        secret_key = self.config.get('api', {}).get('secret_key', 'flux_secret_key_2025')
        self.app.config['SECRET_KEY'] = secret_key
        CORS(self.app)  # CORS für alle Routen aktivieren
        
        # Socket.IO initialisieren mit erweiterten Stabilit\u00e4ts-Einstellungen
        # Force polling first to establish connection, then upgrade to WebSocket
        self.socketio = SocketIO(
            self.app, 
            cors_allowed_origins="*", 
            async_mode='threading',
            logger=False,
            engineio_logger=False,
            ping_timeout=30,           # 30s timeout
            ping_interval=10,          # 10s ping interval  
            max_http_buffer_size=5e6,  # 5MB buffer
            manage_session=False,
            always_connect=True,       # Keep-Alive
            allow_upgrades=True,       # Allow polling -> websocket upgrade
            # Compression settings for binary frames (JPEG)
            http_compression=False,    # No HTTP compression
            websocket_compression=False # No WebSocket compression
        )
        
        # Routen registrieren
        self._register_routes()
        self._register_socketio_events()
        self._setup_websocket_command_handlers()  # NEW: WebSocket command channels
        
        # Error Handler für 500er Fehler (verhindert write() before start_response)
        @self.app.errorhandler(500)
        def handle_internal_error(e):
            """Fängt Server-Fehler ab und verhindert stdout-Probleme."""
            from flask import jsonify
            logger.error(f"Server-Fehler: {e}")
            return jsonify({"error": "Internal Server Error"}), 500
        
        # 404 Handler (ohne lautes Logging)
        @self.app.errorhandler(404)
        def handle_not_found(e):
            """Behandelt 404-Fehler still."""
            from flask import jsonify, request
            # Nur loggen wenn es kein favicon oder bekannte statische Datei ist
            if not request.path.endswith(('.ico', '.map', '.svg')):
                logger.debug(f"404: {request.path}")
            return jsonify({"error": "Not Found"}), 404
        
        self.server_thread = None
        self.status_broadcast_thread = None
        self.is_running = False
    
    @property
    def player(self):
        """Get current player from PlayerManager."""
        return self.player_manager.player
    
    @player.setter
    def set_player(self, new_player):
        """Set player via PlayerManager."""
        self.player_manager.player = new_player
    
    def _register_routes(self):
        """Registriert alle API-Routen."""
        
        # Lade Web-Interface Routen
        from .routes import register_web_routes
        register_web_routes(self.app, self.config, self.player_manager)
        
        # Lade externe API Route-Module
        from .api_routes import (
            register_playback_routes, 
            register_settings_routes,
            register_artnet_routes,
            register_info_routes,
            register_recording_routes,
            register_cache_routes,
            register_script_routes
        )
        from .api_points import register_points_routes
        from .api_console import register_console_routes
        from .api_projects import register_project_routes
        from .api_config import register_config_routes
        from .api_logs import register_log_routes
        from .api_plugins import register_plugins_api
        from .api_benchmark import register_benchmark_routes
        from .api_layers import register_layer_routes
        from .api_clip_layers import register_clip_layer_routes
        from .api_converter import converter_bp
        from .clip_registry import get_clip_registry
        
        # Registriere alle Routen
        register_playback_routes(self.app, self.player_manager)
        register_settings_routes(self.app, self.player_manager)
        register_artnet_routes(self.app, self.player_manager)
        register_info_routes(self.app, self.player_manager, self, self.config)
        register_recording_routes(self.app, self.player_manager, self)
        register_cache_routes(self.app)
        register_script_routes(self.app, self.player_manager, self.config)
        register_points_routes(self.app, self.player_manager, self.data_dir)
        register_console_routes(self.app, self)
        register_project_routes(self.app, self.logger)
        register_config_routes(self.app)
        register_log_routes(self.app)
        register_plugins_api(self.app)
        register_benchmark_routes(self.app, self.player_manager)
        register_layer_routes(self.app, self.player_manager, self.config)
        register_clip_layer_routes(self.app, get_clip_registry(), self.player_manager, self.video_dir)
        
        # Register Converter Blueprint
        self.app.register_blueprint(converter_bp)
        
        # Register Files API
        from .api_files import register_files_api
        register_files_api(self.app, self.video_dir, self.config)
        
        # Register Unified Player API
        from .api_player_unified import register_unified_routes
        register_unified_routes(self.app, self.player_manager, self.config, self.socketio)
        
        # Register Transition API
        from .api_transitions import register_transition_routes
        register_transition_routes(self.app, self.player_manager)
        
        # Register Debug API
        from .api_debug import register_debug_routes
        register_debug_routes(self.app)
        
        # Store config in app for route access
        self.app.flux_config = self.config
        
        # Register Session Snapshot API
        from .api_session import register_session_routes
        from .session_state import get_session_state
        session_state = get_session_state()
        register_session_routes(self.app, session_state)
        
        # Register Sequencer API
        from .api_sequencer import register_sequencer_routes
        register_sequencer_routes(self.app, self.player_manager, self.config, session_state)
        
        # Register Dynamic Parameter Sequences API
        if hasattr(self.player_manager, 'sequence_manager') and hasattr(self.player_manager, 'audio_analyzer'):
            from .api_sequences import register_sequence_routes
            register_sequence_routes(self.app, self.player_manager.sequence_manager, self.player_manager.audio_analyzer, self.player_manager, self.socketio)
            logger.info("Parameter Sequence API routes registered with audio streaming")
    
    def _register_socketio_events(self):
        """Registriert WebSocket Events."""
        
        @self.socketio.on('connect')
        def handle_connect(auth=None):
            """Client verbunden."""
            logger.debug(f"WebSocket Client verbunden")
            # Client sollte 'request_status' Event senden nach erfolgreichem Connect
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Client getrennt."""
            try:
                logger.debug(f"WebSocket Client getrennt")
            except Exception:
                pass  # Ignore disconnect errors (Werkzeug bug)
        
        @self.socketio.on('request_status')
        def handle_status_request():
            """Client fordert Status an."""
            with self.app.app_context():
                emit('status', self._get_status_data())
        
        @self.socketio.on('request_console')
        def handle_console_request(data):
            """Client fordert Console Log an."""
            with self.app.app_context():
                lines = data.get('lines', 100) if data else 100
                log_lines = list(self.console_log)[-lines:]
                emit('console_update', {
                    "log": log_lines,
                    "total": len(self.console_log)
                })
    
    def _setup_websocket_command_handlers(self):
        """Setup WebSocket command handlers for low-latency commands."""
        from flask import request
        
        # ========================================
        # PLAYER NAMESPACE - Transport Controls
        # ========================================
        @self.socketio.on('connect', namespace='/player')
        def handle_player_connect():
            logger.info(f"Client connected to /player namespace: {request.sid}")
            emit('connected', {'status': 'ready'})
        
        @self.socketio.on('disconnect', namespace='/player')
        def handle_player_disconnect():
            logger.info(f"Client disconnected from /player namespace: {request.sid}")
        
        @self.socketio.on('command.play', namespace='/player')
        def handle_play(data):
            """Handle play command via WebSocket."""
            player_id = data.get('player_id', 'video')
            try:
                player = self.player_manager.get_player(player_id)
                if player:
                    player.play()
                    emit('command.response', {
                        'success': True,
                        'command': 'play',
                        'player_id': player_id
                    })
                    # Broadcast status change to all clients
                    self.socketio.emit('player.status', {
                        'player_id': player_id,
                        'is_playing': True,
                        'is_paused': False
                    }, namespace='/player')
            except Exception as e:
                logger.error(f"WebSocket play command error: {e}")
                emit('command.error', {
                    'command': 'play',
                    'error': str(e)
                })
        
        @self.socketio.on('command.pause', namespace='/player')
        def handle_pause(data):
            """Handle pause command via WebSocket."""
            player_id = data.get('player_id', 'video')
            try:
                player = self.player_manager.get_player(player_id)
                if player:
                    player.pause()
                    emit('command.response', {
                        'success': True,
                        'command': 'pause',
                        'player_id': player_id
                    })
                    self.socketio.emit('player.status', {
                        'player_id': player_id,
                        'is_paused': True
                    }, namespace='/player')
            except Exception as e:
                logger.error(f"WebSocket pause command error: {e}")
                emit('command.error', {
                    'command': 'pause',
                    'error': str(e)
                })
        
        @self.socketio.on('command.stop', namespace='/player')
        def handle_stop(data):
            """Handle stop command via WebSocket."""
            player_id = data.get('player_id', 'video')
            try:
                player = self.player_manager.get_player(player_id)
                if player:
                    player.stop()
                    emit('command.response', {
                        'success': True,
                        'command': 'stop',
                        'player_id': player_id
                    })
                    self.socketio.emit('player.status', {
                        'player_id': player_id,
                        'is_playing': False,
                        'is_paused': False
                    }, namespace='/player')
            except Exception as e:
                logger.error(f"WebSocket stop command error: {e}")
                emit('command.error', {
                    'command': 'stop',
                    'error': str(e)
                })
        
        @self.socketio.on('command.next', namespace='/player')
        def handle_next(data):
            """Handle next clip command via WebSocket."""
            player_id = data.get('player_id', 'video')
            try:
                player = self.player_manager.get_player(player_id)
                if player and hasattr(player, 'next_clip'):
                    player.next_clip()
                    emit('command.response', {
                        'success': True,
                        'command': 'next',
                        'player_id': player_id
                    })
                    # Broadcast playlist change
                    self.socketio.emit('playlist.changed', {
                        'player_id': player_id,
                        'current_index': getattr(player, 'playlist_index', 0)
                    }, namespace='/player')
            except Exception as e:
                logger.error(f"WebSocket next command error: {e}")
                emit('command.error', {
                    'command': 'next',
                    'error': str(e)
                })
        
        @self.socketio.on('command.previous', namespace='/player')
        def handle_previous(data):
            """Handle previous clip command via WebSocket."""
            player_id = data.get('player_id', 'video')
            try:
                player = self.player_manager.get_player(player_id)
                if player and hasattr(player, 'previous_clip'):
                    player.previous_clip()
                    emit('command.response', {
                        'success': True,
                        'command': 'previous',
                        'player_id': player_id
                    })
                    self.socketio.emit('playlist.changed', {
                        'player_id': player_id,
                        'current_index': getattr(player, 'playlist_index', 0)
                    }, namespace='/player')
            except Exception as e:
                logger.error(f"WebSocket previous command error: {e}")
                emit('command.error', {
                    'command': 'previous',
                    'error': str(e)
                })
        
        # ========================================
        # EFFECTS NAMESPACE - Effect Parameters
        # ========================================
        @self.socketio.on('connect', namespace='/effects')
        def handle_effects_connect():
            logger.info(f"Client connected to /effects namespace: {request.sid}")
            emit('connected', {'status': 'ready'})
        
        @self.socketio.on('disconnect', namespace='/effects')
        def handle_effects_disconnect():
            logger.info(f"Client disconnected from /effects namespace: {request.sid}")
        
        @self.socketio.on('command.effect.param', namespace='/effects')
        def handle_effect_param_update(data):
            """Handle effect parameter update via WebSocket."""
            player_id = data.get('player_id')
            clip_id = data.get('clip_id')
            effect_index = data.get('effect_index')
            param_name = data.get('param_name')
            value = data.get('value')
            range_min = data.get('rangeMin')
            range_max = data.get('rangeMax')
            uid = data.get('uid')  # Preserve UID for sequence restoration
            
            # CRITICAL: Log every WebSocket call to trace 121.0 source
            logger.warning(f"🌐 WebSocket 'command.effect.param': clip={clip_id[:8]}..., effect[{effect_index}].{param_name} = {value}")
            
            try:
                # Get player and update parameter
                player = self.player_manager.get_player(player_id)
                if not player:
                    raise ValueError(f"Player {player_id} not found")
                
                # Get clip from registry
                from .clip_registry import get_clip_registry
                registry = get_clip_registry()
                clip = registry.get_clip(clip_id)
                
                if not clip:
                    raise ValueError(f"Clip {clip_id} not found")
                
                # Get effects list from clip dict
                effects = clip.get('effects', [])
                
                # Update effect parameter
                if effect_index < len(effects):
                    effect = effects[effect_index]
                    
                    # Effects in registry are dicts with 'parameters' key (not 'params')
                    if isinstance(effect, dict):
                        if 'parameters' not in effect:
                            effect['parameters'] = {}
                        
                        # For triple sliders with range data, store as dict with metadata
                        param_value_to_store = None
                        if range_min is not None and range_max is not None:
                            param_value_to_store = {
                                '_value': value,
                                '_rangeMin': range_min,
                                '_rangeMax': range_max
                            }
                            # Preserve UID if provided
                            if uid:
                                param_value_to_store['_uid'] = uid
                            effect['parameters'][param_name] = param_value_to_store
                            logger.debug(f"✅ WebSocket: Updated {player_id} clip {clip_id} effect[{effect_index}].{param_name} = {value} (range: {range_min}-{range_max})")
                        else:
                            # For simple values, store as dict if UID is present, otherwise plain value
                            if uid:
                                param_value_to_store = {
                                    '_value': value,
                                    '_uid': uid
                                }
                            else:
                                param_value_to_store = value
                            effect['parameters'][param_name] = param_value_to_store
                            logger.debug(f"✅ WebSocket: Updated {player_id} clip {clip_id} effect[{effect_index}].{param_name} = {value}")
                        
                        # Update LIVE effect instance in player layers (critical for transport trim!)
                        if player.layers and len(player.layers) > 0:
                            for layer in player.layers:
                                if layer.clip_id == clip_id and effect_index < len(layer.effects):
                                    live_effect = layer.effects[effect_index]
                                    if live_effect.get('id') == effect.get('plugin_id'):
                                        live_instance = live_effect.get('instance')
                                        if live_instance and hasattr(live_instance, 'update_parameter'):
                                            live_instance.update_parameter(param_name, param_value_to_store)
                                            logger.info(f"🔄 Updated LIVE instance: {effect.get('plugin_id')}.{param_name}")
                                        break
                        
                        # Invalidate cache so changes are picked up
                        registry._invalidate_cache(clip_id)
                        
                        # 🎬 Check if this is a transition effect and update TransitionManager
                        is_transition = effect.get('effect') == 'transition' or effect.get('plugin_id') == 'transition'
                        if is_transition and player.transition_manager:
                            logger.info(f"🎬 Transition effect parameter changed: {param_name}={value}")
                            # Get the full transition config from the effect plugin
                            try:
                                # Use load_plugin() to create a new instance (proper way)
                                transition_effect_plugin = player.plugin_manager.load_plugin('transition')
                                
                                if transition_effect_plugin:
                                    transition_config = transition_effect_plugin.get_transition_config(effect.get('parameters', {}))
                                    
                                    if transition_config:
                                        plugin_name = transition_config.get('plugin')
                                        
                                        # Load the actual transition plugin instance (use load_plugin not get_plugin)
                                        transition_plugin_instance = player.plugin_manager.load_plugin(plugin_name)
                                        
                                        if transition_plugin_instance:
                                            # Save original defaults before applying custom transition
                                            if not hasattr(player.transition_manager, '_original_effect'):
                                                player.transition_manager._original_effect = player.transition_manager.config.get('effect', 'fade')
                                                player.transition_manager._original_plugin = player.transition_manager.config.get('plugin')
                                                player.transition_manager._original_duration = player.transition_manager.config.get('duration', 1.0)
                                                player.transition_manager._original_easing = player.transition_manager.config.get('easing', 'ease_in_out')
                                                logger.debug(f"🎬 Saved playlist defaults: {player.transition_manager._original_effect}")
                                            
                                            # Extract actual values (handle triple-slider metadata)
                                            duration = transition_config.get('duration', 1.0)
                                            if isinstance(duration, dict) and '_value' in duration:
                                                duration = duration['_value']
                                            
                                            easing = transition_config.get('easing', 'ease_in_out')
                                            if isinstance(easing, dict) and '_value' in easing:
                                                easing = easing['_value']
                                            
                                            player.transition_manager.configure(
                                                plugin=transition_plugin_instance,
                                                effect=plugin_name,
                                                duration=duration,
                                                easing=easing
                                            )
                                            logger.info(f"🎬 Applied custom transition: {plugin_name}")
                                        else:
                                            logger.warning(f"🎬 Transition plugin not found: {plugin_name}")
                                    else:
                                        logger.debug(f"🎬 Transition effect disabled")
                            except Exception as e:
                                logger.error(f"🎬 Error applying transition config: {e}")
                        
                        emit('command.response', {
                            'success': True,
                            'command': 'effect.param',
                            'effect_index': effect_index,
                            'param_name': param_name,
                            'value': value
                        })
                        
                        # Broadcast to all clients for multi-user sync
                        self.socketio.emit('effect.param.changed', {
                            'player_id': player_id,
                            'clip_id': clip_id,
                            'effect_index': effect_index,
                            'param_name': param_name,
                            'value': value
                        }, namespace='/effects')
                    else:
                        raise TypeError(f"Effect at index {effect_index} is not a dict")
                else:
                    raise IndexError(f"Effect index {effect_index} out of range")
                    
            except Exception as e:
                logger.error(f"WebSocket effect.param command error: {e}")
                emit('command.error', {
                    'command': 'effect.param',
                    'error': str(e)
                })
        
        # ========================================
        # LAYERS NAMESPACE - Layer Controls
        # ========================================
        @self.socketio.on('connect', namespace='/layers')
        def handle_layers_connect():
            logger.info(f"Client connected to /layers namespace: {request.sid}")
            emit('connected', {'status': 'ready'})
        
        @self.socketio.on('disconnect', namespace='/layers')
        def handle_layers_disconnect():
            logger.info(f"Client disconnected from /layers namespace: {request.sid}")
        
        @self.socketio.on('command.layer.opacity', namespace='/layers')
        def handle_layer_opacity(data):
            """Handle layer opacity update via WebSocket."""
            player_id = data.get('player_id')
            clip_id = data.get('clip_id')
            layer_id = data.get('layer_id')
            opacity = data.get('opacity')
            
            try:
                player = self.player_manager.get_player(player_id)
                if player and player.layers and layer_id < len(player.layers):
                    player.layers[layer_id].opacity = opacity / 100.0
                    
                    logger.debug(f"✅ WebSocket: Updated {player_id} layer[{layer_id}].opacity = {opacity}%")
                    
                    emit('command.response', {
                        'success': True,
                        'command': 'layer.opacity',
                        'layer_id': layer_id,
                        'opacity': opacity
                    })
                    
                    # Broadcast to all clients
                    self.socketio.emit('layer.changed', {
                        'player_id': player_id,
                        'clip_id': clip_id,
                        'layer_id': layer_id,
                        'opacity': opacity
                    }, namespace='/layers')
                else:
                    raise ValueError(f"Layer {layer_id} not found or invalid")
            except Exception as e:
                logger.error(f"WebSocket layer.opacity command error: {e}")
                emit('command.error', {
                    'command': 'layer.opacity',
                    'error': str(e)
                })
        
        @self.socketio.on('command.layer.blend_mode', namespace='/layers')
        def handle_layer_blend_mode(data):
            """Handle layer blend mode update via WebSocket."""
            player_id = data.get('player_id')
            clip_id = data.get('clip_id')
            layer_id = data.get('layer_id')
            blend_mode = data.get('blend_mode')
            
            try:
                player = self.player_manager.get_player(player_id)
                if player and player.layers and layer_id < len(player.layers):
                    player.layers[layer_id].blend_mode = blend_mode
                    
                    logger.debug(f"✅ WebSocket: Updated {player_id} layer[{layer_id}].blend_mode = {blend_mode}")
                    
                    emit('command.response', {
                        'success': True,
                        'command': 'layer.blend_mode',
                        'layer_id': layer_id,
                        'blend_mode': blend_mode
                    })
                    
                    self.socketio.emit('layer.changed', {
                        'player_id': player_id,
                        'clip_id': clip_id,
                        'layer_id': layer_id,
                        'blend_mode': blend_mode
                    }, namespace='/layers')
                else:
                    raise ValueError(f"Layer {layer_id} not found or invalid")
            except Exception as e:
                logger.error(f"WebSocket layer.blend_mode command error: {e}")
                emit('command.error', {
                    'command': 'layer.blend_mode',
                    'error': str(e)
                })
    
    def _get_status_data(self):
        """Erstellt Status-Daten für WebSocket."""
        # Hole Media-Namen und Typ (Video oder Script)
        is_script = False
        media_name = "Unknown"
        
        if hasattr(self.player, 'current_source') and self.player.current_source:
            if hasattr(self.player.current_source, 'script_name'):
                media_name = self.player.current_source.script_name
            elif hasattr(self.player, 'video_path') and self.player.video_path:
                media_name = os.path.basename(self.player.video_path)
        elif hasattr(self.player, 'video_path') and self.player.video_path:
            media_name = os.path.basename(self.player.video_path)
        elif hasattr(self.player, 'script_name') and self.player.script_name:
            media_name = self.player.script_name
            is_script = True
        
        # DMX Preview Daten direkt von Art-Net Manager (= tatsächliche Ausgabe)
        dmx_preview = None
        total_universes = 0
        
        # Prüfe zuerst den artnet_player (falls vorhanden) - der sendet die Daten
        artnet_source = None
        if hasattr(self.player_manager, 'artnet_player') and self.player_manager.artnet_player:
            artnet_source = self.player_manager.artnet_player
        else:
            artnet_source = self.player
        
        # Art-Net Manager ist die zentrale Quelle - zeigt was wirklich gesendet wird
        if hasattr(artnet_source, 'artnet_manager') and artnet_source.artnet_manager:
            artnet_mgr = artnet_source.artnet_manager
            if hasattr(artnet_mgr, 'last_frame') and artnet_mgr.last_frame:
                dmx_preview = artnet_mgr.last_frame
                total_universes = (len(artnet_mgr.last_frame) + 511) // 512
            elif hasattr(artnet_mgr, 'required_universes'):
                total_universes = artnet_mgr.required_universes
        elif hasattr(artnet_source, 'required_universes'):
            total_universes = artnet_source.required_universes
        
        # Replay Status
        is_replaying = False
        if self.replay_manager:
            is_replaying = self.replay_manager.is_playing
        
        # Aktiver Modus (Test/Replay/Video)
        active_mode = "Video"
        if hasattr(self.player, 'artnet_manager') and self.player.artnet_manager:
            active_mode = self.player.artnet_manager.get_active_mode()
        
        return {
            "status": self.player.status(),
            "is_playing": self.player.is_playing,
            "is_paused": self.player.is_paused,
            "current_frame": self.player.current_frame,
            "total_frames": self.player.total_frames,
            "current_loop": self.player.current_loop,
            "brightness": self.player.brightness * 100,
            "speed": self.player.speed_factor,
            "hue_shift": self.player.hue_shift,
            "video": media_name,
            "is_script": is_script,
            "dmx_preview": dmx_preview,
            "total_universes": total_universes,
            "is_replaying": is_replaying,
            "active_mode": active_mode
        }
    
    def _status_broadcast_loop(self):
        """Sendet Status-Updates an alle Clients."""
        import time
        interval = self.config.get('api', {}).get('status_broadcast_interval', 2)
        while self.is_running:
            try:
                time.sleep(interval)
                with self.app.app_context():
                    status_data = self._get_status_data()
                    self.socketio.emit('status', status_data, namespace='/')
            except Exception as e:
                logger.error(f"Fehler beim Status-Broadcast: {e}")
                time.sleep(interval)
    
    def _log_broadcast_loop(self):
        """Sendet Log-Updates an alle Clients."""
        import time
        from pathlib import Path
        
        interval = 5  # Update every 5 seconds
        last_log_data = None
        
        while self.is_running:
            try:
                time.sleep(interval)
                
                # Read current log
                log_dir = Path('logs')
                if log_dir.exists():
                    log_files = sorted(log_dir.glob('flux_*.log'), key=lambda f: f.stat().st_mtime, reverse=True)
                    
                    if log_files:
                        latest_log = log_files[0]
                        
                        try:
                            with open(latest_log, 'r', encoding='utf-8') as f:
                                lines = f.readlines()
                                lines = [line.rstrip('\n') for line in lines]
                                lines = lines[-500:]  # Last 500 lines
                            
                            log_data = {
                                'lines': lines,
                                'file': latest_log.name,
                                'total_lines': len(lines)
                            }
                            
                            # Only emit if data has changed
                            if log_data != last_log_data:
                                with self.app.app_context():
                                    self.socketio.emit('log_update', log_data, namespace='/')
                                last_log_data = log_data
                                
                        except Exception as e:
                            logger.debug(f"Fehler beim Lesen der Log-Datei: {e}")
                
            except Exception as e:
                logger.error(f"Fehler beim Log-Broadcast: {e}")
                time.sleep(interval)
    
    def add_log(self, message):
        """Fügt Nachricht zum Console Log hinzu und sendet an Clients."""
        self.console_log.append(message)
        # Broadcast an alle WebSocket Clients
        if self.is_running:
            try:
                with self.app.app_context():
                    self.socketio.emit('console_update', {
                        "log": [message],
                        "total": len(self.console_log),
                        "append": True
                    }, namespace='/')
            except Exception as e:
                logger.debug(f"Konnte Log nicht broadcasten: {e}")
    
    def clear_console(self):
        """Löscht die Console-Log-Anzeige."""
        self.console_log.clear()
        # Broadcast clear event an alle WebSocket Clients
        if self.is_running:
            try:
                with self.app.app_context():
                    self.socketio.emit('console_update', {
                        "log": [],
                        "total": 0,
                        "clear": True
                    }, namespace='/')
            except Exception as e:
                logger.debug(f"Konnte Console-Clear nicht broadcasten: {e}")
    
    def _execute_command(self, command):
        """Führt CLI-Befehl aus und gibt Ergebnis zurück (via CommandExecutor).
        
        WICHTIG: Verwende NIEMALS print() in API-Funktionen!
        Dies verursacht "write() before start_response" Fehler in Flask/Werkzeug.
        """
        try:
            result = self.command_executor.execute(command)
            return result.message
        except Exception as e:
            logger.error(f"Command execution error: {e}", exc_info=True)
            return f"Fehler: {str(e)}"
    
    def _execute_command_old(self, command):
        """Command execution via CLI handler.
        
        WICHTIG: Verwende NIEMALS print() in API-Funktionen!
        Dies verursacht "write() before start_response" Fehler in Flask/Werkzeug.
        Nutze stattdessen Logger: self.logger.info("message")
        """
        # Prüfe auf video: und script: Prefix
        if ':' in command and command.split(':', 1)[0].lower() in ['video', 'script']:
            prefix, target = command.split(':', 1)
            prefix = prefix.lower()
            
            if prefix == 'video':
                # Lade Video über relativen Pfad
                try:
                    video_path = os.path.join(self.video_dir, target.strip())
                    if os.path.exists(video_path):
                        from .frame_source import VideoSource
                        
                        # Erstelle VideoSource
                        video_source = VideoSource(
                            video_path,
                            self.player.canvas_width,
                            self.player.canvas_height,
                            self.config
                        )
                        
                        # Wechsle Source (unified Player bleibt bestehen)
                        success = self.player.switch_source(video_source)
                        
                        if success:
                            return f"Video geladen: {target}"
                        else:
                            return f"Fehler beim Laden des Videos: {target}"
                    else:
                        return f"Video nicht gefunden: {target}"
                except Exception as e:
                    return f"Fehler beim Laden: {e}"
            
            elif prefix == 'script':
                # Lade Script
                try:
                    from .frame_source import ScriptSource
                    
                    script_name = target.strip()
                    if not script_name.endswith('.py'):
                        script_name += '.py'
                    
                    # Erstelle ScriptSource
                    script_source = ScriptSource(
                        script_name,
                        self.player.canvas_width,
                        self.player.canvas_height,
                        self.config
                    )
                    
                    # Wechsle Source (unified Player bleibt bestehen)
                    success = self.player.switch_source(script_source)
                    
                    if success:
                        return f"Script geladen: {target}"
                    else:
                        return f"Fehler beim Laden des Scripts: {target}"
                except Exception as e:
                    import traceback
                    return f"Fehler beim Laden des Scripts: {e}\n{traceback.format_exc()}"
        
        # Standard-Befehle
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else None
        
        # Playback
        if cmd == "start":
            try:
                self.player.start()
                return "Video gestartet"
            except Exception as e:
                self.logger.error(f"Fehler beim Start: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                return f"Fehler beim Start: {e}"
        elif cmd == "stop":
            self.player.stop()
            return "Video gestoppt"
        elif cmd == "pause":
            self.player.pause()
            return "Video pausiert"
        elif cmd == "resume":
            self.player.resume()
            return "Wiedergabe fortgesetzt"
        elif cmd == "restart":
            self.player.stop()
            self.player.start()
            return "Video neu gestartet"
        
        # Video Management
        elif cmd == "load":
            if args:
                try:
                    self.player.load_video(args)
                    return f"Video geladen: {args}"
                except Exception as e:
                    return f"Fehler beim Laden: {e}"
            return "Verwendung: load <pfad>"
        elif cmd == "list":
            if not os.path.exists(self.video_dir):
                return "Video-Ordner nicht gefunden"
            video_extensions = VIDEO_EXTENSIONS
            videos = []
            for root, dirs, files in os.walk(self.video_dir):
                for f in files:
                    if f.lower().endswith(video_extensions):
                        videos.append(os.path.relpath(os.path.join(root, f), self.video_dir))
            if videos:
                return f"Videos ({len(videos)}):\n" + "\n".join(f"  - {v}" for v in sorted(videos))
            return "Keine Videos gefunden"
        elif cmd == "switch":
            if args:
                try:
                    video_extensions = VIDEO_EXTENSIONS
                    videos = []
                    for root, dirs, files in os.walk(self.video_dir):
                        for f in files:
                            if f.lower().endswith(video_extensions):
                                videos.append(os.path.join(root, f))
                    matching = [v for v in videos if args.lower() in os.path.basename(v).lower()]
                    if matching:
                        self.player.load_video(matching[0])
                        return f"Video gewechselt: {os.path.basename(matching[0])}"
                    return f"Kein Video gefunden mit: {args}"
                except Exception as e:
                    return f"Fehler: {e}"
            return "Verwendung: switch <name>"
        
        # Settings
        elif cmd == "brightness":
            if args:
                self.player.set_brightness(args)
                return f"Helligkeit auf {args} gesetzt"
            return "Verwendung: brightness <0-100>"
        elif cmd == "speed":
            if args:
                self.player.set_speed(args)
                return f"Geschwindigkeit auf {args} gesetzt"
            return "Verwendung: speed <faktor>"
        elif cmd == "fps":
            if args:
                self.player.set_fps(args)
                return f"FPS auf {args} gesetzt"
            return "Verwendung: fps <wert>"
        elif cmd == "loop":
            if args:
                self.player.set_loop_limit(args)
                return f"Loop-Limit auf {args} gesetzt"
            return "Verwendung: loop <anzahl>"
        
        # Art-Net
        elif cmd == "blackout":
            self.player.blackout()
            return "Blackout aktiviert"
        elif cmd == "test":
            color = args if args else 'red'
            self.player.test_pattern(color)
            return f"Testmuster: {color}"
        elif cmd == "ip":
            if args:
                self.player.target_ip = args
                return f"Ziel-IP gesetzt: {args}\nHINWEIS: Starte Video neu f\u00fcr \u00c4nderung"
            return f"Aktuelle IP: {self.player.target_ip}"
        elif cmd == "universe":
            if args:
                try:
                    self.player.start_universe = int(args)
                    return f"Start-Universum gesetzt: {args}\nHINWEIS: Starte Video neu f\u00fcr \u00c4nderung"
                except ValueError:
                    return "Ung\u00fcltiger Wert!"
            return f"Aktuelles Start-Universum: {self.player.start_universe}"
        
        # Info
        elif cmd == "status":
            return f"Status: {self.player.status()}"
        elif cmd == "info":
            info = self.player.get_info()
            return "\n".join([f"{k}: {v}" for k, v in info.items()])
        elif cmd == "stats":
            stats = self.player.get_stats()
            if isinstance(stats, dict):
                return "\n".join([f"{k}: {v}" for k, v in stats.items()])
            return str(stats)
        
        # Cache
        elif cmd == "cache":
            from .cache_commands import execute_cache_command
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cache')
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.json')
            result = execute_cache_command(args, cache_dir, config_path)
            if result:
                return result
            if args == "fill":
                return "⚠ 'cache fill' ist nur über CLI verfügbar (dauert sehr lange)"
            return "Verwendung: cache clear | info | delete <name> | enable | disable | size"
        
        # System
        # reload entfernt
        
        # Help
        elif cmd == "help":
            return "Verfügbare Befehle: start, stop, restart, pause, resume, load, list, switch, video:<pfad>, script:<name>, brightness, speed, fps, loop, ip, universe, blackout, test, status, info, stats, cache, help"
        
        else:
            return f"Unbekannter Befehl: {cmd}. Gib 'help' ein für alle Befehle."
    
    def start(self, host='0.0.0.0', port=5000):
        """Startet REST API & WebSocket Server."""
        if self.is_running:
            logger.warning("REST API läuft bereits!")
            return
        

        
        self.is_running = True
        
        # Flask/SocketIO Logging komplett deaktivieren und von stdout entfernen
        import logging
        import sys
        
        # Entferne alle Handler von werkzeug/socketio/engineio
        werkzeug_logger = logging.getLogger('werkzeug')
        socketio_logger = logging.getLogger('socketio')
        engineio_logger = logging.getLogger('engineio')
        
        for logger_obj in [werkzeug_logger, socketio_logger, engineio_logger]:
            logger_obj.setLevel(logging.CRITICAL)  # Nur kritische Fehler
            logger_obj.handlers = []  # Entferne alle Handler
            logger_obj.propagate = False  # Verhindere Propagierung zu Root-Logger
        
        # Unterdrücke Flask Startup-Nachrichten
        cli = sys.modules.get('flask.cli')
        if cli is not None:
            cli.show_server_banner = lambda *args: None
        
        # Status Broadcast Thread starten
        self.status_broadcast_thread = threading.Thread(target=self._status_broadcast_loop, daemon=True)
        self.status_broadcast_thread.start()
        
        # Log Broadcast Thread starten
        self.log_broadcast_thread = threading.Thread(target=self._log_broadcast_loop, daemon=True)
        self.log_broadcast_thread.start()
        
        # Server Thread starten
        self.server_thread = threading.Thread(
            target=lambda: self.socketio.run(self.app, host=host, port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True),
            daemon=True
        )
        self.server_thread.start()
        logger.info(f"REST API + WebSocket gestartet auf http://{host}:{port}")
        logger.info(f"Web-Interface: http://localhost:{port}")
        logger.info(f"Player Panel: http://localhost:{port}/player")
        logger.info(f"CLI Interface: http://localhost:{port}/cli")
    
    def stop(self):
        """Stoppt REST API Server."""
        self.is_running = False
        logger.info("REST API gestoppt")
