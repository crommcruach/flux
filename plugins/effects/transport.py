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
            'default': 'bounce',
            'options': ['bounce', 'random'],
            'description': 'Playback Mode'
        },
        {
            'name': 'loop_count',
            'type': ParameterType.INT,
            'default': 0,
            'min': 0,
            'max': 100,
            'description': 'Loop Count (0 = infinite, 1+ = play N times then advance)'
        },
        {
            'name': 'random_frame_count',
            'type': ParameterType.INT,
            'default': 30,
            'min': 1,
            'max': 1000,
            'description': 'Random Mode: Number of random frames before signaling loop completion'
        }
    ]
    
    def __init__(self, config=None):
        """Initialisiert Transport Effect."""
        super().__init__(config)
        
        # Extract transport_position with range metadata
        transport_data = self.config.get('transport_position', 1)
        
        # Handle range metadata dict: {_value: current, _rangeMin: start, _rangeMax: end}
        if isinstance(transport_data, dict):
            self.current_position = transport_data.get('_value', 1)
            self.in_point = transport_data.get('_rangeMin', 0)
            self.out_point = transport_data.get('_rangeMax', 100)
        else:
            # Fallback: transport_position ist nur der aktuelle Wert
            self.current_position = int(transport_data)
            self.in_point = 0
            self.out_point = 100
        
        # Other playback parameters
        self.speed = self.config.get('speed', 1.0)
        self.reverse = self.config.get('reverse', False)
        self.playback_mode = self.config.get('playback_mode', 'bounce')
        self.loop_count = self.config.get('loop_count', 0)  # 0 = infinite
        self.random_frame_count = self.config.get('random_frame_count', 30)  # Frames per random "loop"
        
        # Internal state
        self._virtual_frame = float(self.current_position)
        self._bounce_direction = 1  # 1 forward, -1 backward
        self._has_played_once = False
        self.loop_completed = False  # Flag when clip reaches end and loops
        self._current_loop_iteration = 0  # Track how many loops completed
        self._random_frame_counter = 0  # Track random frames in current loop
        
        # Frame source reference (wird bei process_frame gesetzt)
        self._frame_source = None
        self._total_frames = None
        self._fps = 30  # Default FPS, wird vom Source aktualisiert
        
        logger.info(f"✅ Transport Effect initialized: S={self.in_point}, P={self.current_position}, E={self.out_point}, speed={self.speed}, mode={self.playback_mode}, loop_count={self.loop_count}")
    
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
            self.random_frame_count = config.get('random_frame_count', self.random_frame_count)
            
            # Reset internal state
            self._virtual_frame = float(self.current_position)
            self._bounce_direction = 1
            self._has_played_once = False
            self._current_loop_iteration = 0
            self._random_frame_counter = 0
            
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
        # Check if source changed
        source_changed = (self._frame_source is None or self._frame_source != frame_source)
        
        # Check if total_frames changed (generator duration updated)
        total_frames_changed = False
        if hasattr(frame_source, 'total_frames'):
            new_total_frames = frame_source.total_frames
            if self._total_frames is not None and self._total_frames != new_total_frames:
                total_frames_changed = True
                logger.info(f"Transport: Detected total_frames change from {self._total_frames} to {new_total_frames}")
        
        if source_changed or total_frames_changed:
            # New source detected (clip changed) - reset loop counter
            if source_changed:
                logger.info(f"Transport: New source detected, resetting loop counter (was {self._current_loop_iteration})")
                self._current_loop_iteration = 0
                self._random_frame_counter = 0
                self.loop_completed = False
            
            self._frame_source = frame_source
            
            # Debug: Log frame_source attributes
            if source_changed:
                logger.info(f"Transport: Initializing with frame_source type={type(frame_source).__name__}")
                logger.info(f"Transport: frame_source attributes: {dir(frame_source)}")
            
            # Hole total_frames und FPS vom Source (always re-read to catch duration changes)
            if hasattr(frame_source, 'total_frames'):
                self._total_frames = frame_source.total_frames
                logger.info(f"Transport: total_frames={self._total_frames}")
            else:
                logger.warning(f"Transport: frame_source has no 'total_frames' attribute!")
            
            if hasattr(frame_source, 'fps'):
                self._fps = frame_source.fps
                if source_changed:
                    logger.info(f"Transport: fps={self._fps}")
            else:
                logger.warning(f"Transport: frame_source has no 'fps' attribute!")
            
            # Auto-adjust range based on clip/generator length
            if self._total_frames and self._total_frames > 0:
                old_in = self.in_point
                old_out = self.out_point
                
                # Auto-adjust if on default values OR if total_frames changed (generator duration update)
                if (old_in == 0 and old_out == 100) or total_frames_changed:
                    self.in_point = 0
                    self.out_point = self._total_frames - 1
                    
                    if self.current_position > self.out_point:
                        self.current_position = self.in_point
                        self._virtual_frame = float(self.in_point)
                    
                    # Update config so frontend receives correct range
                    if hasattr(self, 'config') and self.config:
                        transport_data = {
                            '_value': self.current_position,
                            '_rangeMin': self.in_point,
                            '_rangeMax': self.out_point
                        }
                        self.config['transport_position'] = transport_data
                    
                    if total_frames_changed:
                        logger.info(f"Transport: Adjusted range to [0,{self.out_point}] due to generator duration change")
                    else:
                        logger.info(f"Transport: Auto-adjusted range to [0,{self.out_point}] ({self._total_frames} frames)")
                else:
                    # User has custom range - validate it's within bounds
                    if old_out >= self._total_frames:
                        self.out_point = self._total_frames - 1
                        logger.info(f"Transport: Clamped out_point to {self.out_point}")
            else:
                # No total_frames available - use defaults
                logger.warning("Transport: No total_frames available, using default range 0-100")
            
            # Setze virtual frame
            self._virtual_frame = float(self.current_position)
            
            if hasattr(frame_source, 'current_frame'):
                frame_source.current_frame = int(self._virtual_frame)
                logger.info(f"Transport: Set current_frame to {int(self._virtual_frame)}")
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
                logger.info(f"Transport: Updated config with actual range: {transport_data}")
    
    def _calculate_next_frame(self):
        """Berechnet nächsten Frame basierend auf Speed, Direction und Mode."""
        clip_length = self.out_point - self.in_point + 1
        
        if clip_length <= 0:
            return self.in_point
        
        # Random mode: Jump to random positions, signal loop after N frames
        if self.playback_mode == 'random':
            self._virtual_frame = float(random.randint(self.in_point, self.out_point))
            frame_num = int(self._virtual_frame)
            self.current_position = frame_num
            
            # Count frames in current random "loop"
            self._random_frame_counter += 1
            
            # Check if we've shown enough random frames to complete one "loop"
            if self._random_frame_counter >= self.random_frame_count:
                # Reset frame counter and increment loop iteration
                self._random_frame_counter = 0
                self._current_loop_iteration += 1
                
                logger.debug(f"🎲 Random loop completed: {self._current_loop_iteration}/{self.loop_count if self.loop_count > 0 else '∞'} ({self.random_frame_count} frames shown)")
                
                # Check if we've completed all desired loops
                if self.loop_count > 0 and self._current_loop_iteration >= self.loop_count:
                    self.loop_completed = True
                    logger.info(f"✅ Random mode loop_count reached: {self._current_loop_iteration}/{self.loop_count} - signaling completion")
                elif self.loop_count == 0:
                    # Infinite mode - signal completion after each "loop" of random frames
                    self.loop_completed = True
            
            return frame_num
        
        # Speed anwenden (mit Bounce-Direction)
        direction = -1 if self.reverse else 1
        if self.playback_mode == 'bounce':
            direction *= self._bounce_direction
        
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
            # Random already handled at start of function
            pass
        
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
                logger.info(f"✅ Transport loop_count reached: {self._current_loop_iteration}/{self.loop_count} - signaling completion")
            elif self.loop_count == 0:
                # Infinite loop mode → signal completion every loop (legacy behavior)
                self.loop_completed = True
                logger.debug(f"🔁 Infinite loop mode: iteration {self._current_loop_iteration}, signaling completion")
        
        # Clamp to valid range
        frame_num = int(round(self._virtual_frame))
        frame_num = max(self.in_point, min(self.out_point, frame_num))
        
        # Update current_position to actual frame number
        self.current_position = frame_num
        
        return frame_num
    
    def process_frame(self, frame, **kwargs):
        """
        Steuert Playback des Video-Clips.
        
        Hinweis: Dieser Effekt manipuliert den Frame Source direkt.
        Er sollte als erster Effekt in der Chain angewendet werden.
        """
        try:
            # Hole Frame Source
            frame_source = self._get_frame_source(kwargs)
            
            if frame_source is None:
                logger.warning("Transport: No frame source found in kwargs")
                return frame
            
            # Initialisiere beim ersten Frame
            self._initialize_state(frame_source)
            
            # Berechne nächsten Frame
            next_frame = self._calculate_next_frame()
            
            # Setze Frame im Source (wenn möglich)
            if hasattr(frame_source, 'current_frame'):
                frame_source.current_frame = next_frame
            
            # Frame selbst wird nicht modifiziert - nur Playback-Position
            return frame
        
        except Exception as e:
            logger.error(f"Error in Transport effect: {e}", exc_info=True)
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
                
                logger.info(f"🎚️ Transport update_parameter received: value={new_position}, min={new_in}, max={new_out}")
                
                # Clamp ranges to valid total_frames (can't trim beyond actual content)
                max_frame = (self._total_frames - 1) if self._total_frames else 10000
                self.in_point = max(0, int(new_in))
                self.out_point = min(max_frame, int(new_out))
                
                logger.info(f"✅ Transport ranges updated: in_point={self.in_point}, out_point={self.out_point} (clamped to 0-{max_frame})")
                
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
            logger.debug(f"Transport: speed set to {self.speed}")
            return True
        
        elif name == 'reverse':
            # Extract actual value if it's a range metadata dict
            if isinstance(value, dict) and '_value' in value:
                value = value['_value']
            old_reverse = self.reverse
            self.reverse = bool(value)
            if old_reverse != self.reverse:
                logger.info(f"Transport: reverse changed to {self.reverse}")
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
                logger.info(f"Transport: playback_mode changed to {self.playback_mode}")
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
                logger.info(f"Transport: loop_count changed to {self.loop_count} (0=infinite)")
            return True
        
        elif name == 'random_frame_count':
            # Extract actual value if it's a range metadata dict
            if isinstance(value, dict) and '_value' in value:
                value = value['_value']
            old_count = self.random_frame_count
            self.random_frame_count = int(value)
            if old_count != self.random_frame_count:
                # Reset frame counter when count changes
                self._random_frame_counter = 0
                logger.info(f"Transport: random_frame_count changed to {self.random_frame_count}")
            return True
        
        return False
    
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
            'random_frame_count': self.random_frame_count,
            '_loop_iteration': self._current_loop_iteration,  # Debug info
            '_random_frame_counter': self._random_frame_counter  # Debug info
        }
    
    def cleanup(self):
        """Cleanup beim Beenden."""
        self._frame_source = None
        logger.debug("Transport effect cleaned up")
