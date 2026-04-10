"""
Trails Effect Plugin - Ghost-Trails with frame blending

GPU path:  cv2.accumulateWeighted on UMat (OpenCL) — accumulator lives on GPU,
           only one .get() download per frame needed for the uint8 output.
CPU path:  same cv2.accumulateWeighted call on plain numpy arrays — still a
           single optimised C++ op, no Python loop.

Formula:  trail = decay * trail + (1-decay) * frame
          cv2.accumulateWeighted(src, dst, alpha=1-decay)  ← identical
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType
from src.modules.gpu.accelerator import get_gpu_accelerator


class TrailsEffect(PluginBase):
    """
    Trails Effect - Erstellt Ghost-Trails durch Frame-Blending.

    Single cv2.accumulateWeighted() call per frame.
    When OpenCL is available the float32 accumulator is kept as a UMat on the
    GPU — no round-trip upload every frame, only one .get() download per frame.
    """

    METADATA = {
        'id': 'trails',
        'name': 'Trails',
        'description': 'Ghost-Trails Effekt durch Frame-Blending',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Time & Motion'
    }

    PARAMETERS = [
        {
            'name': 'decay',
            'label': 'Decay',
            'type': ParameterType.FLOAT,
            'default': 0.7,
            'min': 0.1,
            'max': 0.99,
            'step': 0.05,
            'description': 'Decay-Faktor (höher = längerer / persistenterer Trail)'
        }
    ]

    def initialize(self, config):
        """Initialisiert Plugin."""
        self.decay = float(config.get('decay', 0.7))
        self.gpu = get_gpu_accelerator(config)
        # float32 accumulator — None until first frame (lazy init for correct shape)
        self._trail = None   # cv2.UMat when GPU enabled, else np.ndarray

    def process_frame(self, frame, **kwargs):
        """
        GPU:  cv2.accumulateWeighted(UMat(frame), UMat_trail, alpha)
              accumulator stays on GPU; one .get() download per frame.
        CPU:  cv2.accumulateWeighted(frame, np_trail, alpha) — single C++ call.

        alpha = 1 - decay  (weight of the incoming frame)
        """
        alpha = 1.0 - self.decay  # weight given to the new frame

        if self._trail is None:
            self._trail = frame.astype(np.float32)
            return frame
        cv2.accumulateWeighted(frame, self._trail, alpha)
        return cv2.convertScaleAbs(self._trail)

    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        if name == 'decay':
            self.decay = float(value)
            return True
        if name == 'length':
            # Legacy parameter — silently accepted
            return True
        return False

    def get_parameters(self):
        return {'decay': self.decay}

    def cleanup(self):
        self._trail = None
