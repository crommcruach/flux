"""
Metallic Fold Effect Plugin - Color-space folding for metallic/chrome appearance
"""
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class MetallicFoldEffect(PluginBase):
    """
    Metallic Fold Effect - Folds pixel values at a threshold creating a metallic/chrome look.

    Inspired by the abs() reflection in convertScaleAbs: values that cross 0 bounce
    back upward, creating iridescent highlights and a metal-like sheen.
    """

    METADATA = {
        'id': 'metallic_fold',
        'name': 'Metallic Fold',
        'description': 'Metallischer Glanz durch Farbkanal-Spiegelung (abs-fold)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Artistic'
    }

    PARAMETERS = [
        {
            'name': 'fold_point',
            'label': 'Fold Point',
            'type': ParameterType.FLOAT,
            'default': 60.0,
            'min': 0.0,
            'max': 255.0,
            'step': 1.0,
            'description': 'Schwellwert, um den die Faltung erfolgt (niedriger = intensiver Effekt in dunklen Bereichen)'
        },
        {
            'name': 'scale',
            'label': 'Scale',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.5,
            'max': 2.5,
            'step': 0.05,
            'description': 'Verstärkung vor der Faltung (höher = mehr Reflektionen)'
        },
        {
            'name': 'folds',
            'label': 'Folds',
            'type': ParameterType.INT,
            'default': 1,
            'min': 1,
            'max': 4,
            'step': 1,
            'description': 'Anzahl der Faltungen (mehr = komplexeres Muster)'
        },
        {
            'name': 'channel_shift',
            'label': 'Channel Shift',
            'type': ParameterType.INT,
            'default': 0,
            'min': 0,
            'max': 40,
            'step': 1,
            'description': 'RGB-Kanalversatz für chromatischen Metallglanz'
        }
    ]

    def initialize(self, config):
        self.fold_point = float(config.get('fold_point', 60.0))
        self.scale = float(config.get('scale', 1.0))
        self.folds = int(config.get('folds', 1))
        self.channel_shift = int(config.get('channel_shift', 0))

    def _fold(self, arr, fold_point, scale):
        """Apply abs() fold: scale * x - fold_point, then abs, result in 0-255."""
        folded = np.abs(arr * scale - fold_point)
        # Fold values that exceed 255 back down as well (triangle wave)
        folded = folded % 510
        folded = np.where(folded > 255, 510 - folded, folded)
        return folded

    def process_frame(self, frame, **kwargs):
        f = frame.astype(np.float32)

        # Optional per-channel offset for chromatic sheen
        if self.channel_shift > 0:
            s = self.channel_shift
            b = f[:, :, 0]
            g = f[:, :, 1]
            r = f[:, :, 2]
            # Slightly different fold points per channel
            b = self._apply_folds(b, self.fold_point, self.scale)
            g = self._apply_folds(g, max(0.0, self.fold_point - s), self.scale)
            r = self._apply_folds(r, max(0.0, self.fold_point - s * 2), self.scale)
            result = np.stack([b, g, r], axis=2)
        else:
            result = self._apply_folds(f, self.fold_point, self.scale)

        return np.clip(result, 0, 255).astype(np.uint8)

    def _apply_folds(self, arr, fold_point, scale):
        """Apply the fold N times."""
        result = arr.copy()
        fp = fold_point
        for _ in range(self.folds):
            result = self._fold(result, fp, scale)
            # Each subsequent fold uses a smaller fold_point relative to output range
            fp = fp * 0.5
        return result

    def update_parameter(self, name, value):
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        if name == 'fold_point':
            self.fold_point = float(value)
        elif name == 'scale':
            self.scale = float(value)
        elif name == 'folds':
            self.folds = int(value)
        elif name == 'channel_shift':
            self.channel_shift = int(value)
        return True

    def get_parameters(self):
        return {
            'fold_point': self.fold_point,
            'scale': self.scale,
            'folds': self.folds,
            'channel_shift': self.channel_shift
        }
