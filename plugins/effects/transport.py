"""
Transport Effect Plugin
Erweiterte Playback-Kontrolle für Video-Clips:
- Trimming (In/Out Points)
- Speed Control (0.1x - 10x)
- Reverse Playback
- Playback Modes: repeat, play_once, bounce, random
- Echtzeit Position Tracking
"""
from plugins import PluginBase, PluginType, ParameterType
import numpy as np
import logging
import random
from modules.logger import debug_transport, info_log_conditional, DebugCategories

logger = logging.getLogger(__name__)


class TransportEffect(PluginBase):
    """Transport/Playback Control Effect."""
    
    METADATA = {
        'id': 'transport',
        'name': 'Transport',
        'description': 'Erweiterte Playback-Kontrolle: Trimming, Speed, Reverse, Loop-Modi',
        'author': 'Flux Art-Net System',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Playback',
        'system_plugin': True,  # System plugin - not deletable, always first
        'hidden': False  # Visible but with special UI treatment
    }
    
    PARAMETERS = [
        {
            'name': 'transport_position',
            'type': ParameterType.INT,
            'default': 1,
            'min': 0,
            'max': 10000,
            'description': 'Transport: |--S--P--E--| (Start-Position-End)',
            'label': 'Transport Timeline',
            'display_format': 'time',
            'fps': 30
        },
        {
            'name': 'speed',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.1,
            'max': 10.0,
            'step': 0.1,
            'description': 'Playback Speed (1.0 = normal)'
        },
        {
            'name': 'reverse',
            'type': ParameterType.BOOL,
            'default': False,
            'description': 'Rückwärts abspielen'
        },
        {
            'name': 'playback_mode',
            'type': ParameterType.SELECT,
            'default': 'repeat',
            'options': ['repeat', 'play_once', 'bounce', 'random'],
            'description': 'Playback Mode'
        },
        {
            'name': 'loop_count',
            'type': ParameterType.INT,
            'default': 0,
            'min': 0,
            'max': 100,
            'description': 'Loop Count (0 = infinite, 1+ = play N times then advance)'
        }
    ]
    
    def __init__(self, config=None):
        """Initialisiert Transport Effect."""
        # Set minimal default values BEFORE calling super().__init__() 
        self.current_position = 0
        self.in_point = 0
        self.out_point = 0
        self.speed = 1.0
        self.reverse = False
        self.playback_mode = 'repeat'
        self.loop_count = 0
        self._virtual_frame = 0.0
        self._bounce_direction = 1
        self._has_played_once = False
        self.loop_completed = False
        self._current_loop_iteration = 0
        self._random_frames_played = 0
        self._frame_source = None
        self._total_frames = None
        self._fps = 30
        
        # WebSocket update tracking
        self._position_update_counter = 0
        self._last_emitted_position = None
        self.socketio = None  # Will be set by player
        self.player_id = None  # Will be set by player
        self.clip_id = None  # Will be set by player
        
        # Now call parent init
        super().__init__(config)
        
        # Apply config if provided
        if config:
            transport_data = config.get('transport_position', None)
            
            if isinstance(transport_data, dict):
                self.current_position = transport_data.get('_value', self.current_position)
                self.in_point = transport_data.get('_rangeMin', self.in_point)
                self.out_point = transport_data.get('_rangeMax', self.out_point)
            elif transport_data is not None:
                self.current_position = int(transport_data)
            
            self.speed = config.get('speed', self.speed)
            self.reverse = config.get('reverse', self.reverse)
            self.playback_mode = config.get('playback_mode', self.playback_mode)
            self.loop_count = config.get('loop_count', self.loop_count)
            
            # Reset internal state
            self._virtual_frame = float(self.current_position)
        
        info_log_conditional(logger, DebugCategories.TRANSPORT, f"✅ Transport initialized: in={self.in_point}, pos={self.current_position}, out={self.out_point}, speed={self.speed}, mode={self.playback_mode}")
    
    def initialize(self, config):
        """
        Initialisiert Plugin mit Konfiguration.
        
        Args:
            config: Dictionary mit Parameter-Werten
        """
        # Parameters are already set in __init__, but this method is required by PluginBase
        # Re-apply config if provided
        if config:
            # Extract transport_position with range metadata
            transport_data = config.get('transport_position', self.current_position)
            
            if isinstance(transport_data, dict):
                self.current_position = transport_data.get('_value', self.current_position)
                self.in_point = transport_data.get('_rangeMin', self.in_point)
                self.out_point = transport_data.get('_rangeMax', self.out_point)
            else:
                self.current_position = int(transport_data)
            
            self.speed = config.get('speed', self.speed)
            self.reverse = config.get('reverse', self.reverse)
            self.playback_mode = config.get('playback_mode', self.playback_mode)
            self.loop_count = config.get('loop_count', self.loop_count)
            
            # Reset internal state
            self._virtual_frame = float(self.current_position)
            self._bounce_direction = 1
            self._has_played_once = False
            self._current_loop_iteration = 0
            self._random_frames_played = 0
            
            logger.debug(f"Transport Effect re-initialized: S={self.in_point}, P={self.current_position}, E={self.out_point}")
    
    def _get_frame_source(self, kwargs):
        """Extrahiert Frame Source aus kwargs."""
        # WICHTIG: Priorisiere 'source' (Layer-Source) vor player.source
        # Damit jeder Layer seinen eigenen Transport steuert
        if 'source' in kwargs:
            return kwargs['source']
        
        # Fallback: Player's main source (für Clip-Effekte)
        if 'player' in kwargs:
            player = kwargs['player']
            if hasattr(player, 'source'):
                return player.source
        
        return None
    
    def _initialize_state(self, frame_source):
        """Initialisiert State beim ersten Frame."""
        # Get total_frames from source
        if hasattr(frame_source, 'total_frames'):
            self._total_frames = frame_source.total_frames
        else:
            raise ValueError("Transport: frame_source has no 'total_frames' attribute!")
        
        # Get FPS from source
        if hasattr(frame_source, 'fps'):
            self._fps = frame_source.fps
        
        # Validate total_frames
        if not self._total_frames or self._total_frames <= 0:
            raise ValueError(f"Transport: Cannot initialize - invalid total_frames: {self._total_frames}")
        
        # Check if this is first initialization or source changed
        source_changed = (self._frame_source is None or self._frame_source != frame_source)
        
        if source_changed:
            # New clip loaded - BUT preserve user's trim settings if they exist and are valid
            self._frame_source = frame_source
            
            # Check if we have valid, user-defined trim settings
            # Valid means: not (0,0) and in_point < out_point and within bounds
            has_valid_trim = (
                not (self.in_point == 0 and self.out_point == 0) and
                self.in_point < self.out_point and
                self.out_point < self._total_frames
            )
            
            if has_valid_trim:
                # User has set custom trim - preserve it, just clamp to new total_frames if needed
                self.out_point = min(self.out_point, self._total_frames - 1)
                self.in_point = min(self.in_point, self.out_point)
                self.current_position = max(self.in_point, min(self.current_position, self.out_point))
                self._virtual_frame = float(self.current_position)
                info_log_conditional(logger, DebugCategories.TRANSPORT, f"Transport: Preserved custom trim [{self.in_point}, {self.out_point}] for source with {self._total_frames} frames")
            else:
                # No valid trim settings - initialize to full range
                self.in_point = 0
                self.out_point = self._total_frames - 1
                self.current_position = 0
                self._virtual_frame = 0.0
                info_log_conditional(logger, DebugCategories.TRANSPORT, f"Transport: Initialized to full range [0, {self.out_point}] ({self._total_frames} frames)")
            
            # Reset loop counters
            self._current_loop_iteration = 0
            self._random_frames_played = 0
            self.loop_completed = False
            
            # Update transport_position parameter to sync back to frontend
            self.update_parameter('transport_position', {
                '_value': self.current_position,
                '_rangeMin': self.in_point,
                '_rangeMax': self.out_point
            })
            
            if hasattr(frame_source, 'current_frame'):
                frame_source.current_frame = int(self._virtual_frame)
                debug_transport(logger, f"Transport: Set current_frame to {int(self._virtual_frame)}")
            else:
                logger.warning(f"Transport: frame_source has no 'current_frame' attribute!")
            
            # Update config with actual timeline range for persistence
            # This ensures the frontend receives the correct range values
            if hasattr(self, 'config') and self.config:
                transport_data = {
                    '_value': self.current_position,
                    '_rangeMin': self.in_point,
                    '_rangeMax': self.out_point
                }
                self.config['transport_position'] = transport_data
                debug_transport(logger, f"Transport: Updated config with actual range: {transport_data}")
    
    def _calculate_next_frame(self):
        """Berechnet nächsten Frame basierend auf Speed, Direction und Mode."""
        clip_length = self.out_point - self.in_point + 1
        
        if clip_length <= 0:
            return self.in_point
        
        # Random mode: Jump to random positions, signal loop after automatic duration
        if self.playback_mode == 'random':
            self._virtual_frame = float(random.randint(self.in_point, self.out_point))
            frame_num = int(self._virtual_frame)
            self.current_position = frame_num
            
            # Count frames in current random "loop"
            self._random_frames_played += 1
            
            # Calculate automatic random loop duration based on clip length and speed
            clip_length = self.out_point - self.in_point
            random_loop_duration = max(1, int(clip_length / max(0.1, self.speed)))
            
            # Check if we've shown enough random frames to complete one "loop"
            if self._random_frames_played >= random_loop_duration:
                # Reset frame counter and increment loop iteration
                self._random_frames_played = 0
                self._current_loop_iteration += 1
                
                logger.debug(f"🎲 Random loop completed: {self._current_loop_iteration}/{self.loop_count if self.loop_count > 0 else '∞'} ({random_loop_duration} frames shown)")
                
                # Check if we've completed all desired loops
                if self.loop_count > 0 and self._current_loop_iteration >= self.loop_count:
                    self.loop_completed = True
                    info_log_conditional(logger, DebugCategories.TRANSPORT, f"✅ Random mode loop_count reached: {self._current_loop_iteration}/{self.loop_count} - signaling completion")
                elif self.loop_count == 0:
                    # Infinite mode - signal completion after each "loop" of random frames
                    self.loop_completed = True
            
            return frame_num
        
        # Speed anwenden (mit Bounce-Direction)
        direction = -1 if self.reverse else 1
        if self.playback_mode == 'bounce':
            direction *= self._bounce_direction
        
        # DEBUG: Log speed application every 30 frames
        if int(self._virtual_frame) % 30 == 0:
            logger.debug(f"Transport: speed={self.speed}, direction={direction}, virtual_frame={self._virtual_frame:.2f}")
        
        self._virtual_frame += self.speed * direction
        
        # Mode-spezifische Logik
        # Apply loop counting for ALL modes (bounce, random)
        loop_detected = False
        
        if self.playback_mode == 'bounce':
            # Bounce zwischen in_point und out_point
            # One complete loop = start → end → back to start (full cycle)
            if self._virtual_frame > self.out_point:
                self._virtual_frame = self.out_point - (self._virtual_frame - self.out_point)
                self._bounce_direction = -1
                # Reached end, now bouncing back (half cycle)
            elif self._virtual_frame < self.in_point:
                self._virtual_frame = self.in_point + (self.in_point - self._virtual_frame)
                self._bounce_direction = 1
                # Returned to start - complete cycle finished
                loop_detected = True
        
        elif self.playback_mode == 'random':
            # Random Mode: Check if we've played enough frames (based on clip length / speed)
            self._random_frames_played += 1
            
            # Calculate how many frames one "loop" should be in random mode
            # Logic: Play as many random frames as the clip would be long (considering trim and speed)
            clip_length = self.out_point - self.in_point  # Frames in trimmed range
            random_loop_duration = max(1, int(clip_length / max(0.1, self.speed)))  # Adjusted for speed
            
            if self._random_frames_played >= random_loop_duration:
                # One "loop" completed in random mode
                loop_detected = True
                self._random_frames_played = 0  # Reset for next loop
                logger.debug(f"🎲 Random mode loop completed: played {random_loop_duration} frames (clip_length={clip_length}, speed={self.speed})")
        
        # Check if we've reached trim endpoints (for non-bounce modes)
        # This handles forward/reverse playback reaching the trim boundaries
        if self.playback_mode != 'bounce':
            if not self.reverse and self._virtual_frame >= self.out_point:
                # Forward playback reached out_point (trim end)
                self._virtual_frame = self.in_point  # Wrap to start
                loop_detected = True
                logger.debug(f"🔄 Reached trim endpoint (out_point={self.out_point}), wrapping to start")
            elif self.reverse and self._virtual_frame <= self.in_point:
                # Reverse playback reached in_point (trim start)
                self._virtual_frame = self.out_point  # Wrap to end
                loop_detected = True
                logger.debug(f"🔄 Reached trim startpoint (in_point={self.in_point}), wrapping to end")
        
        # Unified loop count logic (applies to all modes)
        if loop_detected:
            self._current_loop_iteration += 1
            logger.debug(f"🔁 Loop detected: iteration {self._current_loop_iteration}/{self.loop_count if self.loop_count > 0 else '∞'}")
            
            # Check if we've completed the desired number of loops
            if self.loop_count > 0 and self._current_loop_iteration >= self.loop_count:
                # Reached loop limit → signal completion (for playlist autoplay)
                self.loop_completed = True
                info_log_conditional(logger, DebugCategories.TRANSPORT, f"✅ Transport loop_count reached: {self._current_loop_iteration}/{self.loop_count} - signaling completion")
            elif self.loop_count == 0:
                # Infinite loop mode → signal completion every loop (legacy behavior)
                self.loop_completed = True
                logger.debug(f"🔁 Infinite loop mode: iteration {self._current_loop_iteration}, signaling completion")
        
        # Clamp to valid range
        frame_num = int(round(self._virtual_frame))
        frame_num = max(self.in_point, min(self.out_point, frame_num))
        
        # Update current_position to actual frame number
        self.current_position = frame_num
        
        # Sync position back to parameters for frontend display
        self.update_parameter('transport_position', {
            '_value': self.current_position,
            '_rangeMin': self.in_point,
            '_rangeMax': self.out_point
        })
        
        # WebSocket position update (rate-limited by config)
        self._emit_position_update()
        
        return frame_num
    
    def process_frame(self, frame, **kwargs):
        """
        Steuert Playback des Video-Clips.
        
        NOTE: Actual transport processing happens in player's pre-processing stage
        BEFORE frame fetch. This method is a no-op now since transport must control
        the frame BEFORE it's fetched, not after.
        """
        # Transport logic is handled in pre-processing stage in player.py
        # This prevents the frame from already being fetched before we can control it
        return frame
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'transport_position':
            # Handle range metadata: {_value: current, _rangeMin: start, _rangeMax: end}
            if isinstance(value, dict):
                # Extract all three values from triple slider
                new_position = value.get('_value', self.current_position)
                new_in = value.get('_rangeMin', self.in_point)
                new_out = value.get('_rangeMax', self.out_point)
                
                debug_transport(logger, f"🎚️ Transport update_parameter received: value={new_position}, min={new_in}, max={new_out}")
                
                # Clamp ranges to valid total_frames (can't trim beyond actual content)
                max_frame = (self._total_frames - 1) if self._total_frames else 10000
                self.in_point = max(0, int(new_in))
                self.out_point = min(max_frame, int(new_out))
                
                debug_transport(logger, f"✅ Transport ranges updated: in_point={self.in_point}, out_point={self.out_point} (clamped to 0-{max_frame})")
                
                # Update position (user can drag position handle to jump)
                new_pos_int = int(new_position)
                if self.in_point <= new_pos_int <= self.out_point:
                    self._virtual_frame = float(new_pos_int)
                    self.current_position = new_pos_int
                    if self._frame_source and hasattr(self._frame_source, 'current_frame'):
                        self._frame_source.current_frame = new_pos_int
                    logger.debug(f"Transport updated: S={self.in_point}, P={self.current_position}, E={self.out_point}")
            else:
                # Simple value update (position only)
                new_pos = int(value)
                if self.in_point <= new_pos <= self.out_point:
                    self._virtual_frame = float(new_pos)
                    self.current_position = new_pos
                    if self._frame_source and hasattr(self._frame_source, 'current_frame'):
                        self._frame_source.current_frame = new_pos
            return True
        
        elif name == 'speed':
            # Extract actual value if it's a range metadata dict
            if isinstance(value, dict) and '_value' in value:
                value = value['_value']
            self.speed = float(value)
            debug_transport(logger, f"🚀 Transport: Speed updated to {self.speed}")
            return True
        
        elif name == 'reverse':
            # Extract actual value if it's a range metadata dict
            if isinstance(value, dict) and '_value' in value:
                value = value['_value']
            old_reverse = self.reverse
            self.reverse = bool(value)
            if old_reverse != self.reverse:
                debug_transport(logger, f"Transport: reverse changed to {self.reverse}")
            return True
        
        elif name == 'playback_mode':
            # Extract actual value if it's a range metadata dict
            if isinstance(value, dict) and '_value' in value:
                value = value['_value']
            old_mode = self.playback_mode
            self.playback_mode = str(value)
            if old_mode != self.playback_mode:
                # Reset state bei Mode-Wechsel
                self._bounce_direction = 1
                self._has_played_once = False
                self._current_loop_iteration = 0
                debug_transport(logger, f"Transport: playback_mode changed to {self.playback_mode}")
            return True
        
        elif name == 'loop_count':
            # Extract actual value if it's a range metadata dict
            if isinstance(value, dict) and '_value' in value:
                value = value['_value']
            old_count = self.loop_count
            self.loop_count = int(value)
            if old_count != self.loop_count:
                # Reset loop counter when count changes
                self._current_loop_iteration = 0
                debug_transport(logger, f"Transport: loop_count changed to {self.loop_count} (0=infinite)")
            return True
        
        return False
    
    def _emit_position_update(self):
        """Emit WebSocket update for transport position (rate-limited by config)."""
        # DEBUG: Check if WebSocket context is available
        if not self.socketio or not self.player_id or not self.clip_id:
            if self._position_update_counter == 0:  # Log only once to avoid spam
                logger.info(f"⚠️ Transport WebSocket context not set: socketio={self.socketio is not None}, player_id={self.player_id}, clip_id={self.clip_id}")
            return
        
        # Increment counter
        self._position_update_counter += 1
        
        # Get update interval from config (default 10 frames)
        try:
            from modules.app_config import get_config
            config = get_config()
            update_interval = config.get('effects', {}).get('transport_position_update_interval', 10)
        except:
            update_interval = 10
        
        # Only emit every N frames or if position changed significantly
        should_emit = (
            self._position_update_counter >= update_interval or
            self._last_emitted_position is None or
            abs(self.current_position - self._last_emitted_position) > 30  # Force update if jumped
        )
        
        if should_emit:
            try:
                self.socketio.emit('transport.position', {
                    'player_id': self.player_id,
                    'clip_id': self.clip_id,
                    'position': self.current_position,
                    'in_point': self.in_point,
                    'out_point': self.out_point,
                    'total_frames': self._total_frames,
                    'fps': self._fps
                }, namespace='/effects')
                
                self._position_update_counter = 0
                self._last_emitted_position = self.current_position
            except Exception as e:
                logger.error(f"❌ Failed to emit transport position: {e}")
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück mit Range Metadata für Transport."""
        # Ensure _totalFrames is valid (use out_point as fallback for short clips)
        total_frames = self._total_frames if self._total_frames is not None else max(self.out_point, 100)
        
        return {
            'transport_position': {
                '_value': self.current_position,
                '_rangeMin': self.in_point,
                '_rangeMax': self.out_point,
                '_fps': self._fps,
                '_totalFrames': total_frames,
                '_displayFormat': 'time'
            },
            'speed': self.speed,
            'reverse': self.reverse,
            'playback_mode': self.playback_mode,
            'loop_count': self.loop_count,
            '_loop_iteration': self._current_loop_iteration,  # Debug info
            '_random_frames_played': self._random_frames_played  # Debug info
        }
    
    def cleanup(self):
        """Cleanup beim Beenden."""
        self._frame_source = None
        logger.debug("Transport effect cleaned up")
