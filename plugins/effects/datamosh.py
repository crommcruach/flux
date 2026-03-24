"""
Datamosh Effect Plugin - Video Compression Glitch Art

Simulates the visual artifact that occurs when video I-frames are removed,
leaving only P-frames (delta frames).  Pixels are pushed forward by their
motion vectors each frame instead of being replaced by the current frame.

GPU strategy:
  - Optical flow: DIS ULTRAFAST at 1/4 resolution (CPU â€” no OpenCL equivalent)
                  ~5-8Ã— faster than Farneback at 1/2 res
                  Temporally subsampled: recomputed every 2 frames
  - Warp (remap):  cv2.remap(UMat_accumulator, UMat_mapx, UMat_mapy, INTER_NEAREST) â†’ GPU
  - Blend:         cv2.accumulateWeighted(UMat_frame_uint8, UMat_accumulator) â†’ GPU
  - Accumulator lives permanently on GPU (UMat) â€” no full-buffer upload each frame
  - Warp maps: pre-allocated CPU arrays + np.add(..., out=) â€” 0 allocations per frame
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType
from src.modules.gpu.accelerator import get_gpu_accelerator


class DatamoshEffect(PluginBase):
    """
    Datamosh / P-frame glitch effect.

    Parameters:
        intensity   â€“ How much of the *current* frame bleeds into the
                      accumulator each frame (0 = pure P-frame chaos,
                      0.1 = strong datamosh, 0.5+ = subtle).
        flow_scale  â€“ Multiplier applied to motion vectors before warping.
                      1.0 = realistic motion, 3-5 = exaggerated smear.
        reset       â€“ Set to 1 to flush the accumulator (inject an I-frame).
    """

    METADATA = {
        'id': 'datamosh',
        'name': 'Datamosh',
        'description': 'P-frame glitch: pixels follow motion vectors, I-frames removed',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Glitch & Distortion',
    }

    PARAMETERS = [
        {
            'name': 'intensity',
            'label': 'I-Frame Bleed',
            'type': ParameterType.FLOAT,
            'default': 0.07,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'How much current frame bleeds in (0=pure chaos, 1=bypass)',
        },
        {
            'name': 'flow_scale',
            'label': 'Motion Scale',
            'type': ParameterType.FLOAT,
            'default': 2.0,
            'min': 0.5,
            'max': 8.0,
            'step': 0.25,
            'description': 'Amplify motion vectors (1=realistic, 3-5=exaggerated smear)',
        },
        {
            'name': 'flow_quality',
            'label': 'Flow Resolution',
            'type': ParameterType.INT,
            'default': 4,
            'min': 1,
            'max': 8,
            'step': 1,
            'description': 'Divisor for flow resolution (1=full, 4=quarter, 8=eighth — higher = faster)',
        },
        {
            'name': 'reset',
            'label': 'Reset (I-Frame)',
            'type': ParameterType.INT,
            'default': 0,
            'min': 0,
            'max': 1,
            'step': 1,
            'description': 'Set to 1 to inject a clean I-frame and reset accumulator',
        },
    ]

    # 1/4 resolution for flow (vs 1/2 before) â†’ 4Ã— fewer pixels in Farneback
    _FLOW_DIV  = 4
    # Recompute flow every N frames â€” reuse cached flow on skipped frames
    _FLOW_SKIP = 2

    def initialize(self, config):
        self.intensity    = float(config.get('intensity', 0.07))
        self.flow_scale   = float(config.get('flow_scale', 2.0))
        self.flow_quality = max(1, int(config.get('flow_quality', 4)))
        self.gpu = get_gpu_accelerator(config)

        # DIS optical flow â€” much faster than Farneback (ULTRAFAST preset = 0)
        try:
            self._dis = cv2.DISOpticalFlow_create(0)  # 0 = PRESET_ULTRAFAST
        except AttributeError:
            self._dis = None  # fallback to Farneback if DIS unavailable

        # Float32 pixel accumulator â€” UMat (GPU) or ndarray (CPU), lazy init
        self._mosh = None
        self._prev_gray_small = None
        self._flow_cache = None       # reused on skip frames
        self._flow_tick = 0

        # Identity coordinate grids + pre-allocated warp map output buffers
        self._x_grid = None
        self._y_grid = None
        self._map_x  = None           # pre-allocated â€” written in-place each frame
        self._map_y  = None
        self._grid_h = -1
        self._grid_w = -1

    def _ensure_grid(self, h, w):
        """Rebuild identity grids and pre-allocated map buffers only on size change."""
        if self._grid_h != h or self._grid_w != w:
            self._x_grid, self._y_grid = np.meshgrid(
                np.arange(w, dtype=np.float32),
                np.arange(h, dtype=np.float32),
            )
            # Pre-allocate output arrays: np.add writes into these, no malloc per frame
            self._map_x = np.empty((h, w), dtype=np.float32)
            self._map_y = np.empty((h, w), dtype=np.float32)
            self._grid_h = h
            self._grid_w = w

    def process_frame(self, frame, **kwargs):
        h, w = frame.shape[:2]
        self._ensure_grid(h, w)

        div = self.flow_quality
        sw, sh = max(w // div, 32), max(h // div, 32)

        # Grayscale at 1/4 res for flow (INTER_AREA = correct downsample quality)
        # DIS flow requires CV_8U single-channel — handle all input formats safely
        n_ch = frame.shape[2] if frame.ndim == 3 else 1
        if n_ch == 1:
            gray = frame if frame.ndim == 2 else frame[:, :, 0]
        elif n_ch == 4:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if gray.dtype != np.uint8:
            gray = np.clip(gray, 0, 255).astype(np.uint8)
        gray_small = cv2.resize(gray, (sw, sh), interpolation=cv2.INTER_AREA)

        # First frame: init accumulator
        if self._mosh is None:
            if self.gpu.enabled:
                self._mosh = cv2.UMat(frame.astype(np.float32))
            else:
                self._mosh = frame.astype(np.float32)
            self._prev_gray_small = gray_small
            self._flow_tick = 0
            return frame

        if self._prev_gray_small is None or self._prev_gray_small.shape != gray_small.shape:
            # Resolution changed (flow_quality adjusted) — skip flow this frame
            self._prev_gray_small = gray_small
            self._flow_cache = None
            mosh_out = self._mosh
            return cv2.convertScaleAbs(mosh_out).get() if self.gpu.enabled else cv2.convertScaleAbs(mosh_out)

        # â”€â”€ Temporal flow subsampling â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Only compute optical flow every _FLOW_SKIP frames; reuse cached flow
        # between frames.  At 30fps+skip=2: flow computed 15Ã—/s instead of 30Ã—/s.
        self._flow_tick += 1
        if self._flow_cache is None or self._flow_tick % self._FLOW_SKIP == 0:
            if self._dis is not None:
                self._flow_cache = self._dis.calc(
                    self._prev_gray_small, gray_small, None
                )
            else:
                # Farneback fallback (minimal params for speed)
                self._flow_cache = cv2.calcOpticalFlowFarneback(
                    self._prev_gray_small, gray_small, None,
                    0.5, 1, 7, 1, 5, 1.1, 0
                )
        self._prev_gray_small = gray_small

        # â”€â”€ Upsample flow to full res + scale â†’ write into pre-allocated maps â”€â”€
        flow_full = cv2.resize(self._flow_cache, (w, h))   # (h, w, 2) float32
        scale = self.flow_scale
        # np.add with out= avoids two full-res array allocations per frame
        np.add(self._x_grid, flow_full[:, :, 0] * scale, out=self._map_x)
        np.add(self._y_grid, flow_full[:, :, 1] * scale, out=self._map_y)
        # No np.clip needed â€” BORDER_REPLICATE clamps OOB coords inside remap

        # â”€â”€ GPU path â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if self.gpu.enabled:
            umat_mapx = cv2.UMat(self._map_x)
            umat_mapy = cv2.UMat(self._map_y)
            # INTER_NEAREST: faster AND more authentic datamosh block-pixel look
            warped = cv2.remap(self._mosh, umat_mapx, umat_mapy,
                               cv2.INTER_NEAREST, borderMode=cv2.BORDER_REPLICATE)
            # accumulateWeighted accepts uint8 UMat as src â€” no float conversion
            cv2.accumulateWeighted(cv2.UMat(frame), warped, self.intensity)
            self._mosh = warped
            return cv2.convertScaleAbs(self._mosh).get()

        # â”€â”€ CPU fallback â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        warped = cv2.remap(self._mosh, self._map_x, self._map_y,
                           cv2.INTER_NEAREST, borderMode=cv2.BORDER_REPLICATE)
        cv2.accumulateWeighted(frame, warped, self.intensity)
        self._mosh = warped
        return cv2.convertScaleAbs(self._mosh)

    def update_parameter(self, name, value):
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        if name == 'intensity':
            self.intensity = float(value)
            return True
        if name == 'flow_scale':
            self.flow_scale = float(value)
            return True
        if name == 'flow_quality':
            new_q = max(1, int(value))
            if new_q != self.flow_quality:
                self.flow_quality = new_q
                # Invalidate cached flow — resolution changed, old cache is stale
                self._prev_gray_small = None
                self._flow_cache = None
            return True
        if name == 'reset' and int(value) == 1:
            self._mosh = None
            self._prev_gray_small = None
            self._flow_cache = None
            self._flow_tick = 0
            return True
        return False

    def get_parameters(self):
        return {
            'intensity':    self.intensity,
            'flow_scale':   self.flow_scale,
            'flow_quality': self.flow_quality,
            'reset': 0,
        }

    def cleanup(self):
        self._mosh = None
        self._prev_gray_small = None
        self._flow_cache = None
