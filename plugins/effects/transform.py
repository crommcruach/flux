"""
Transform Effect Plugin - 2D transformations (position, scale, rotation)
"""
import math
import os
import cv2
import numpy as np
import logging
from plugins import PluginBase, PluginType, ParameterType
from src.modules.gpu.accelerator import get_gpu_accelerator

_SHADER_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'modules', 'gpu', 'shaders', 'transform.frag')

logger = logging.getLogger(__name__)


class TransformEffect(PluginBase):
    """
    Transform Effect - 2D Transformationen (Position, Skalierung, Rotation).
    
    Ermöglicht das Verschieben, Skalieren und Rotieren des Videos im 2D-Raum.
    """
    
    METADATA = {
        'id': 'transform',
        'name': 'Transform',
        'description': '2D Transformationen: Position, Skalierung und Rotation',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Transformation'
    }
    
    PARAMETERS = [
        # Position Group
        {
            'name': 'position_x',
            'label': 'X',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -2000.0,
            'max': 2000.0,
            'step': 1.0,
            'group': 'Position',
            'description': 'Horizontale Position (Pixel, negativ = links, positiv = rechts)'
        },
        {
            'name': 'position_y',
            'label': 'Y',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -2000.0,
            'max': 2000.0,
            'step': 1.0,
            'group': 'Position',
            'description': 'Vertikale Position (Pixel, negativ = oben, positiv = unten)'
        },
        # Scale Group
        {
            'name': 'scale_xy',
            'label': 'XY',
            'type': ParameterType.FLOAT,
            'default': 100.0,
            'min': 0.0,
            'max': 500.0,
            'step': 1.0,
            'group': 'Scale',
            'description': 'Symmetrische Skalierung in Prozent (100% = Original)'
        },
        {
            'name': 'scale_x',
            'label': 'X',
            'type': ParameterType.FLOAT,
            'default': 100.0,
            'min': 0.0,
            'max': 500.0,
            'step': 1.0,
            'group': 'Scale',
            'description': 'Horizontale Skalierung in Prozent (100% = Original)'
        },
        {
            'name': 'scale_y',
            'label': 'Y',
            'type': ParameterType.FLOAT,
            'default': 100.0,
            'min': 0.0,
            'max': 500.0,
            'step': 1.0,
            'group': 'Scale',
            'description': 'Vertikale Skalierung in Prozent (100% = Original)'
        },
        # Rotation Group
        {
            'name': 'rotation_x',
            'label': 'X',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': 0.0,
            'max': 360.0,
            'step': 1.0,
            'group': 'Rotation',
            'description': 'Rotation um X-Achse in Grad (3D-Perspektive)'
        },
        {
            'name': 'rotation_y',
            'label': 'Y',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': 0.0,
            'max': 360.0,
            'step': 1.0,
            'group': 'Rotation',
            'description': 'Rotation um Y-Achse in Grad (3D-Perspektive)'
        },
        {
            'name': 'rotation_z',
            'label': 'Z',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': 0.0,
            'max': 360.0,
            'step': 1.0,
            'group': 'Rotation',
            'description': 'Rotation um Z-Achse in Grad (2D-Rotation im Uhrzeigersinn)'
        },
        # Anchor Group
        {
            'name': 'anchor_x',
            'label': 'X',
            'type': ParameterType.FLOAT,
            'default': 50.0,
            'min': 0.0,
            'max': 100.0,
            'step': 1.0,
            'group': 'Anchor',
            'description': 'Ankerpunkt X in Prozent (50% = Mitte, 0% = links, 100% = rechts)'
        },
        {
            'name': 'anchor_y',
            'label': 'Y',
            'type': ParameterType.FLOAT,
            'default': 50.0,
            'min': 0.0,
            'max': 100.0,
            'step': 1.0,
            'group': 'Anchor',
            'description': 'Ankerpunkt Y in Prozent (50% = Mitte, 0% = oben, 100% = unten)'
        },
        {
            'name': 'anchor_z',
            'label': 'Z',
            'type': ParameterType.FLOAT,
            'default': 50.0,
            'min': 0.0,
            'max': 100.0,
            'step': 1.0,
            'group': 'Anchor',
            'description': 'Ankerpunkt Z in Prozent (50% = Mitte, beeinflusst 3D-Perspektive)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Transform-Parametern."""
        # Use _get_param_value() from PluginBase to handle range metadata
        self.position_x = self._get_param_value('position_x', 0.0)
        self.position_y = self._get_param_value('position_y', 0.0)
        self.scale_xy = self._get_param_value('scale_xy', 100.0)
        self.scale_x = self._get_param_value('scale_x', 100.0)
        self.scale_y = self._get_param_value('scale_y', 100.0)
        self.rotation_x = self._get_param_value('rotation_x', 0.0)
        self.rotation_y = self._get_param_value('rotation_y', 0.0)
        self.rotation_z = self._get_param_value('rotation_z', 0.0)
        self.anchor_x = self._get_param_value('anchor_x', 50.0)
        self.anchor_y = self._get_param_value('anchor_y', 50.0)
        self.anchor_z = config.get('anchor_z', 50.0)

        # GPU accelerator for warpAffine / warpPerspective (NOT resize — see below)
        self.gpu = get_gpu_accelerator(config)

        # Pre-allocated output canvas — reused every frame to avoid per-frame 6 MB alloc.
        # Resized lazily when resolution changes.
        self._canvas = None
        self._canvas_shape = None

    def process_frame(self, frame, **kwargs):
        """GPU-native plugin — rendered via GLSL shader. This stub is never called on live frames."""
        return frame

    def _apply_2d_rotation(self, frame, angle, anchor_x, anchor_y):
        """
        Wendet 2D-Rotation (um Z-Achse) an.
        
        Args:
            frame: Input Frame
            angle: Rotation in Grad (im Uhrzeigersinn)
            anchor_x: X-Koordinate des Ankerpunkts
            anchor_y: Y-Koordinate des Ankerpunkts
            
        Returns:
            Rotiertes Frame
        """
        h, w = frame.shape[:2]
        center = (anchor_x, anchor_y)
        
        # Erstelle Rotationsmatrix um Ankerpunkt
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Wende Rotation an
        rotated = self.gpu.warpAffine(frame, M, (w, h),
                                      borderMode=cv2.BORDER_CONSTANT,
                                      borderValue=(0, 0, 0))
        
        return rotated
    
    def _apply_3d_rotation(self, frame, angle_x, angle_y, anchor_x, anchor_y):
        """
        Wendet 3D-Rotation (Perspektiv-Transformation) an.
        
        Args:
            frame: Input Frame
            angle_x: Rotation um X-Achse (horizontal flip) in Grad
            angle_y: Rotation um Y-Achse (vertical flip) in Grad
            anchor_x: X-Koordinate des Ankerpunkts
            anchor_y: Y-Koordinate des Ankerpunkts
            
        Returns:
            Rotiertes Frame
        """
        h, w = frame.shape[:2]
        
        # Konvertiere zu Radians
        angle_x_rad = np.radians(angle_x)
        angle_y_rad = np.radians(angle_y)
        
        # Focal length (bestimmt Stärke der Perspektive)
        # Anchor Z beeinflusst die Tiefe (focal length adjustment)
        focal_length = w * (self.anchor_z / 50.0)  # 50% = normal, <50% = näher, >50% = weiter
        
        # 3D Rotationsmatrix
        # Rotation um X-Achse (pitch)
        cos_x = np.cos(angle_x_rad)
        sin_x = np.sin(angle_x_rad)
        
        # Rotation um Y-Achse (yaw)
        cos_y = np.cos(angle_y_rad)
        sin_y = np.sin(angle_y_rad)
        
        # Perspektiv-Transformationsmatrix
        # Verwende Ankerpunkt statt Mitte
        center_x = anchor_x
        center_y = anchor_y
        
        # Source points (Ecken des Frames)
        src_pts = np.float32([
            [0, 0],
            [w, 0],
            [w, h],
            [0, h]
        ])
        
        # Apply 3D rotation to points
        dst_pts = []
        for x, y in src_pts:
            # Translate to origin
            x_centered = x - center_x
            y_centered = y - center_y
            z = 0
            
            # Rotation um Y-Achse (affects x coordinate)
            x_rot_y = x_centered * cos_y + z * sin_y
            z_rot_y = -x_centered * sin_y + z * cos_y
            
            # Rotation um X-Achse (affects y coordinate)
            y_rot_x = y_centered * cos_x - z_rot_y * sin_x
            z_final = y_centered * sin_x + z_rot_y * cos_x
            
            # Perspektiv-Projektion
            # Je weiter weg (z positiv), desto kleiner erscheint der Punkt
            scale_factor = focal_length / (focal_length + z_final)
            
            x_projected = x_rot_y * scale_factor + center_x
            y_projected = y_rot_x * scale_factor + center_y
            
            dst_pts.append([x_projected, y_projected])
        
        dst_pts = np.float32(dst_pts)
        
        # Berechne Perspektiv-Transformationsmatrix
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        
        # Wende Transformation an
        result = self.gpu.warpPerspective(frame, M, (w, h),
                                          borderMode=cv2.BORDER_CONSTANT,
                                          borderValue=(0, 0, 0))
        
        return result
    
    # ─── GPU shader interface ────────────────────────────────────────────────
    def get_shader(self):
        # NOTE: rotation_x / rotation_y (3D perspective) are not yet implemented
        # in the GLSL shader — those parameters are ignored on the GPU path.
        # This is intentional: 100% GPU pipeline, no CPU fallback.
        with open(_SHADER_PATH) as f:
            return f.read()

    def get_uniforms(self, **kwargs):
        frame_w = kwargs.get('frame_w', 1920)
        frame_h = kwargs.get('frame_h', 1080)
        scale_xy = self.scale_xy / 100.0
        sx = (self.scale_x / 100.0) * scale_xy
        sy = (self.scale_y / 100.0) * scale_xy
        return {
            'anchor':    (self.anchor_x / 100.0, self.anchor_y / 100.0),
            'scale':     (sx, sy),
            'translate': (self.position_x / frame_w, self.position_y / frame_h),
            'rotation':  math.radians(self.rotation_z),
        }

    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'position_x':
            self.position_x = float(value)
            return True
        elif name == 'position_y':
            self.position_y = float(value)
            return True
        elif name == 'scale_xy':
            logger.debug(f"📥 [Transform {id(self)}] BEFORE update: self.scale_xy={self.scale_xy:.1f}, new_value={float(value):.1f}")
            old_value = self.scale_xy
            self.scale_xy = float(value)
            # Only log scale_xy updates with significant change (for debugging instance mismatch)
            if abs(self.scale_xy - old_value) > 1.0:
                import traceback
                caller_info = traceback.extract_stack()[-3]  # Get caller 2 levels up
                logger.debug(f"🔧 [Transform {id(self)}] scale_xy: {old_value:.1f} → {self.scale_xy:.1f} (from {caller_info.filename}:{caller_info.lineno})")
            return True
        elif name == 'scale_x':
            self.scale_x = float(value)
            return True
        elif name == 'scale_y':
            self.scale_y = float(value)
            return True
        elif name == 'rotation_x':
            self.rotation_x = float(value)
            return True
        elif name == 'rotation_y':
            self.rotation_y = float(value)
            return True
        elif name == 'rotation_z':
            self.rotation_z = float(value)
            return True
        elif name == 'anchor_x':
            self.anchor_x = float(value)
            return True
        elif name == 'anchor_y':
            self.anchor_y = float(value)
            return True
        elif name == 'anchor_z':
            self.anchor_z = float(value)
            return True
        return False
    
    def is_noop(self):
        """Check if effect is a no-op (default parameters that don't modify the frame).
        
        Returns:
            bool: True if effect will not modify the frame
        """
        return (self.position_x == 0 and self.position_y == 0 and 
                self.scale_xy == 100.0 and self.scale_x == 100.0 and self.scale_y == 100.0 and
                self.rotation_x == 0 and self.rotation_y == 0 and self.rotation_z == 0)
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'position_x': self.position_x,
            'position_y': self.position_y,
            'scale_xy': self.scale_xy,
            'scale_x': self.scale_x,
            'scale_y': self.scale_y,
            'rotation_x': self.rotation_x,
            'rotation_y': self.rotation_y,
            'rotation_z': self.rotation_z,
            'anchor_x': self.anchor_x,
            'anchor_y': self.anchor_y,
            'anchor_z': self.anchor_z
        }
