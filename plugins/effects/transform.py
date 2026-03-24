"""
Transform Effect Plugin - 2D transformations (position, scale, rotation)
"""
import math
import cv2
import numpy as np
import logging
from plugins import PluginBase, PluginType, ParameterType
from src.modules.gpu.accelerator import get_gpu_accelerator

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
        """
        Wendet 2D-Transformationen auf Frame an.
        
        Alle 2D-Transforms (Scale + Rotation Z + Translation) werden zu einer einzigen
        Affine-Matrix kombiniert → ein einziger warpAffine-Call auf Original-Größe.
        Kein Resize → np.zeros → Copy-Dance mehr (war 3× so teuer).
        
        3D-Rotation (X/Y) wird davor als Perspektiv-Transform angewandt.
        """
        # FAST PATH: identity — no-op
        if (self.position_x == 0 and self.position_y == 0 and
                self.scale_xy == 100.0 and self.scale_x == 100.0 and self.scale_y == 100.0 and
                self.rotation_x == 0 and self.rotation_y == 0 and self.rotation_z == 0):
            return frame

        h, w = frame.shape[:2]

        # Anchor point in pixels
        ax = w * (self.anchor_x / 100.0)
        ay = h * (self.anchor_y / 100.0)

        # === 3D Rotation (Perspektive) — muss zuerst angewandt werden ===
        if self.rotation_x != 0 or self.rotation_y != 0:
            frame = self._apply_3d_rotation(frame, self.rotation_x, self.rotation_y, ax, ay)

        scale_xy = self.scale_xy / 100.0
        sx = (self.scale_x / 100.0) * scale_xy
        sy = (self.scale_y / 100.0) * scale_xy

        # FAST PATH: scale-only (no rotation_z) → crop-then-resize + canvas placement.
        # warpAffine does per-pixel inverse mapping over the full output buffer which
        # is 3-5× slower than a dedicated resize for the scale case.
        if self.rotation_z == 0:
            new_w = max(1, round(w * sx))
            new_h = max(1, round(h * sy))

            # Top-left corner of scaled frame in canvas coordinates:
            # The anchor point stays fixed → x0 = ax - ax*sx + px, y0 = ay - ay*sy + py
            x0 = int(round(ax * (1.0 - sx) + self.position_x))
            y0 = int(round(ay * (1.0 - sy) + self.position_y))

            # Clip source and destination to canvas bounds
            src_x0 = max(0, -x0)
            src_y0 = max(0, -y0)
            dst_x0 = max(0, x0)
            dst_y0 = max(0, y0)
            copy_w = min(new_w - src_x0, w - dst_x0)
            copy_h = min(new_h - src_y0, h - dst_y0)

            if copy_w <= 0 or copy_h <= 0:
                nc = frame.shape[2] if frame.ndim == 3 else 1
                return np.zeros((h, w, nc), dtype=np.uint8)

            # cv2.resize only READS its input — writeable flag is irrelevant.
            # Only copy when memory layout is non-contiguous (e.g. transposed slice).
            # Memmap views are always read-only but C_CONTIGUOUS, so this is a no-op
            # for the common case, saving the previous 6 MB copy on every frame.
            if not frame.flags['C_CONTIGUOUS']:
                frame = np.ascontiguousarray(frame)

            # Always crop-then-resize: only process the source pixels that map to the
            # visible canvas region. For zoom-in this avoids a large intermediate;
            # for partial off-canvas content it halves or more the resize work.
            orig_x0 = int(src_x0 / sx)
            orig_y0 = int(src_y0 / sy)
            orig_x1 = min(w, math.ceil((src_x0 + copy_w) / sx))
            orig_y1 = min(h, math.ceil((src_y0 + copy_h) / sy))
            result = cv2.resize(frame[orig_y0:orig_y1, orig_x0:orig_x1],
                                (copy_w, copy_h), interpolation=cv2.INTER_LINEAR)

            # Full-canvas fast exit — result already fills the entire output.
            if dst_x0 == 0 and dst_y0 == 0 and copy_w == w and copy_h == h:
                return result

            # Compose into reused canvas (avoids fresh 6 MB alloc every frame).
            nc = frame.shape[2] if frame.ndim == 3 else 1
            target_shape = (h, w, nc)
            if self._canvas is None or self._canvas_shape != target_shape:
                self._canvas = np.empty(target_shape, dtype=np.uint8)
                self._canvas_shape = target_shape
            self._canvas[:] = 0
            self._canvas[dst_y0:dst_y0 + copy_h, dst_x0:dst_x0 + copy_w] = result
            return self._canvas

        # === Slow path: rotation_z present → combined affine matrix ===
        # Kombiniert (α = cos θ, β = sin θ, sx/sy = Scale-Faktoren):
        #   M = [[α·sx,  β·sy,  ax·(1 - α·sx) - ay·β·sy  + px],
        #        [-β·sx, α·sy,  ax·β·sx       + ay·(1 - α·sy) + py]]
        angle_rad = np.radians(self.rotation_z)
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)

        m00 = cos_a * sx
        m01 = sin_a * sy
        m10 = -sin_a * sx
        m11 = cos_a * sy

        M = np.float32([
            [m00, m01, ax * (1.0 - m00) - ay * m01 + self.position_x],
            [m10, m11, ax * (-m10) + ay * (1.0 - m11) + self.position_y],
        ])

        nc = frame.shape[2] if frame.ndim == 3 else 1
        border_val = (0,) * nc
        frame = self.gpu.warpAffine(frame, M, (w, h),
                                    flags=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_CONSTANT,
                                    borderValue=border_val)
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
