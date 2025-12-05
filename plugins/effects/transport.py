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
            'default': 'repeat',
            'options': ['repeat', 'play_once', 'bounce', 'random'],
            'description': 'Playback Mode'
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
        self.playback_mode = self.config.get('playback_mode', 'repeat')
        
        # Internal state
        self._virtual_frame = float(self.current_position)
        self._bounce_direction = 1  # 1 forward, -1 backward
        self._has_played_once = False
        self.loop_completed = False  # Flag when clip reaches end and loops
        
        # Frame source reference (wird bei process_frame gesetzt)
        self._frame_source = None
        self._total_frames = None
        self._fps = 30  # Default FPS, wird vom Source aktualisiert
        
        logger.info(f"✅ Transport Effect initialized: S={self.in_point}, P={self.current_position}, E={self.out_point}, speed={self.speed}, mode={self.playback_mode}")
    
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
            
            # Reset internal state
            self._virtual_frame = float(self.current_position)
            self._bounce_direction = 1
            self._has_played_once = False
            
            logger.debug(f"Transport Effect re-initialized: S={self.in_point}, P={self.current_position}, E={self.out_point}")
    
    def _get_frame_source(self, kwargs):
        """Extrahiert Frame Source aus kwargs."""
        # Versuche frame_source aus verschiedenen Quellen zu holen
        if 'player' in kwargs:
            player = kwargs['player']
            if hasattr(player, 'source'):
                return player.source
        
        if 'source' in kwargs:
            return kwargs['source']
        
        return None
    
    def _initialize_state(self, frame_source):
        """Initialisiert State beim ersten Frame."""
        if self._frame_source is None:
            self._frame_source = frame_source
            
            # Hole total_frames und FPS vom Source
            if hasattr(frame_source, 'total_frames'):
                self._total_frames = frame_source.total_frames
                logger.info(f"Transport: total_frames={self._total_frames}")
            
            if hasattr(frame_source, 'fps'):
                self._fps = frame_source.fps
                logger.info(f"Transport: fps={self._fps}")
            
            # IMMER die Range auf die tatsächliche Clip-Länge setzen beim ersten Load
            # Das überschreibt die gespeicherten Default-Werte aus config.json
            if self._total_frames:
                # User hat noch nichts angepasst - setze auf volle Clip-Länge
                old_in = self.in_point
                old_out = self.out_point
                
                self.in_point = 0
                self.out_point = self._total_frames - 1
                
                # Wenn Position außerhalb des neuen Bereichs, setze auf Start
                if self.current_position > self.out_point:
                    self.current_position = self.in_point
                    self._virtual_frame = float(self.in_point)
                
                logger.info(f"Transport: Auto-adjusted range from [{old_in},{old_out}] to [0,{self.out_point}] based on clip length")
            else:
                # Fallback wenn keine total_frames verfügbar
                if self.out_point == 100:
                    logger.warning("Transport: No total_frames available, using default range 0-100")
            
            # Setze virtual frame
            self._virtual_frame = float(self.current_position)
            
            if hasattr(frame_source, 'current_frame'):
                frame_source.current_frame = int(self._virtual_frame)
                logger.info(f"Transport: Set current_frame to {int(self._virtual_frame)}")
    
    def _calculate_next_frame(self):
        """Berechnet nächsten Frame basierend auf Speed, Direction und Mode."""
        clip_length = self.out_point - self.in_point + 1
        
        if clip_length <= 0:
            return self.in_point
        
        # Random mode: Spring zu komplett zufälliger Position (kein Speed-basiertes Inkrement)
        if self.playback_mode == 'random':
            self._virtual_frame = float(random.randint(self.in_point, self.out_point))
            frame_num = int(self._virtual_frame)
            self.current_position = frame_num
            return frame_num
        
        # Speed anwenden (mit Bounce-Direction)
        direction = -1 if self.reverse else 1
        if self.playback_mode == 'bounce':
            direction *= self._bounce_direction
        
        self._virtual_frame += self.speed * direction
        
        # Mode-spezifische Logik
        if self.playback_mode == 'repeat':
            # Loop zwischen in_point und out_point
            loop_detected = False
            while self._virtual_frame > self.out_point:
                self._virtual_frame -= clip_length
                loop_detected = True
            while self._virtual_frame < self.in_point:
                self._virtual_frame += clip_length
                loop_detected = True
            
            # Signalisiere Loop-Completion an Player (für Playlist-Autoplay)
            if loop_detected:
                self.loop_completed = True
        
        elif self.playback_mode == 'play_once':
            # Spiele einmal und stoppe
            if self.reverse:
                if self._virtual_frame < self.in_point:
                    self._virtual_frame = self.in_point
                    self._has_played_once = True
            else:
                if self._virtual_frame > self.out_point:
                    self._virtual_frame = self.out_point
                    self._has_played_once = True
        
        elif self.playback_mode == 'bounce':
            # Bounce zwischen in_point und out_point
            if self._virtual_frame > self.out_point:
                self._virtual_frame = self.out_point - (self._virtual_frame - self.out_point)
                self._bounce_direction = -1
            elif self._virtual_frame < self.in_point:
                self._virtual_frame = self.in_point + (self.in_point - self._virtual_frame)
                self._bounce_direction = 1
        
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
            
            # FIX: Skip Transport effect für Generator-Clips
            # Generatoren haben keine frame-basierte Navigation
            source_type = getattr(frame_source, 'source_type', None)
            if source_type == 'generator':
                logger.debug("Transport: Skipping for generator clip")
                return frame
            
            # Initialisiere beim ersten Frame
            self._initialize_state(frame_source)
            
            # Berechne nächsten Frame
            next_frame = self._calculate_next_frame()
            
            # Setze Frame im Source (wenn möglich)
            if hasattr(frame_source, 'current_frame'):
                frame_source.current_frame = next_frame
            
            # Für play_once Mode: Halte letzten Frame
            if self.playback_mode == 'play_once' and self._has_played_once:
                # Frame bleibt stehen, keine weitere Bewegung
                pass
            
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
                
                # Update ranges
                self.in_point = int(new_in)
                self.out_point = int(new_out)
                
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
                logger.info(f"Transport: playback_mode changed to {self.playback_mode}")
            return True
        
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück mit Range Metadata für Transport."""
        return {
            'transport_position': {
                '_value': self.current_position,
                '_rangeMin': self.in_point,
                '_rangeMax': self.out_point,
                '_fps': self._fps,
                '_totalFrames': self._total_frames,
                '_displayFormat': 'time'
            },
            'speed': self.speed,
            'reverse': self.reverse,
            'playback_mode': self.playback_mode
        }
    
    def cleanup(self):
        """Cleanup beim Beenden."""
        self._frame_source = None
        logger.debug("Transport effect cleaned up")
