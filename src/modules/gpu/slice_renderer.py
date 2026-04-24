"""GPUSliceRenderer — single-pass WGSL render: viewport crop + rotation + soft-edge + colour + mirror.

Operates entirely on GPU textures; no CPU round-trips.

Usage
-----
    sr = GPUSliceRenderer()
    sliced_frame = sr.slice(composite_gpu_frame, slice_def, canvas_w, canvas_h)
    # sliced_frame is a GPUFrame of (slice_def.width × slice_def.height).
    # The GPUSliceRenderer owns it — caller must NOT release it.
    # It stays valid until the next call to slice() for the same slice_id.

Output frames are cached per slice_id so no new GPU allocation happens after
the first call per slice (as long as the output size doesn't change).
"""

from __future__ import annotations

import math
import os
from typing import TYPE_CHECKING

from ..core.logger import get_logger

if TYPE_CHECKING:
    from .frame import GPUFrame
    from ..player.outputs.slices import SliceDefinition

logger = get_logger(__name__)

_SHADER_PATH = os.path.join(os.path.dirname(__file__), 'shaders', 'slice.wgsl')

_MIRROR_MAP = {'none': 0, 'horizontal': 1, 'vertical': 2, 'both': 3}


class GPUSliceRenderer:
    """Caches WGSL shader source + per-slice output GPUFrames."""

    _shader_src: str | None = None  # class-level cache (one load for all instances)

    @classmethod
    def _load_shader(cls) -> str:
        if cls._shader_src is None:
            with open(_SHADER_PATH, encoding='utf-8') as fh:
                cls._shader_src = fh.read()
        return cls._shader_src

    @classmethod
    def invalidate_shader_cache(cls) -> None:
        """Force re-read of slice.wgsl on next render call."""
        cls._shader_src = None

    def __init__(self) -> None:
        # {slice_id: GPUFrame} — per-output cached render target.
        # Reused each frame to avoid per-frame GPU allocation.
        self._output_frames: dict[str, GPUFrame] = {}
        # {slice_id: (GPUFrame, bytes)} — cached mask texture + last mask fingerprint.
        # The fingerprint is id(mask_array) so we only re-upload when the mask changes.
        self._mask_frames: dict[str, tuple] = {}
        # 1×1 white GPUFrame used as a dummy mask when no mask is present.
        # Keeps the bind group layout consistent (always 2 textures: canvas + mask).
        self._dummy_mask: GPUFrame | None = None

    # ------------------------------------------------------------------
    def slice(
        self,
        composite: GPUFrame,
        slice_def: SliceDefinition,
        canvas_w: int,
        canvas_h: int,
        cache_key: str | None = None,
    ) -> GPUFrame:
        """Render a viewport crop of *composite* into a cached output GPUFrame.

        Parameters
        ----------
        composite   : full-canvas GPUFrame (source texture).
        slice_def   : SliceDefinition with x, y, width, height, rotation, etc.
        canvas_w/h  : canvas dimensions (to compute UV rect).
        cache_key   : unique key for the output frame cache; defaults to
                      ``slice_def.slice_id``.

        Returns
        -------
        GPUFrame : owned by this renderer — do NOT release.
        """
        from .frame import GPUFrame as _GPUFrame
        from .context import get_device
        from .renderer import get_renderer

        key = cache_key or slice_def.slice_id
        w = slice_def.width
        h = slice_def.height

        # (Re-)allocate output frame when dimensions change.
        existing = self._output_frames.get(key)
        if existing is None or getattr(existing, 'width', 0) != w or getattr(existing, 'height', 0) != h:
            if existing is not None:
                try:
                    existing.release()
                except Exception:
                    pass
            existing = _GPUFrame(get_device(), w, h)
            self._output_frames[key] = existing

        # ── Build uniforms ────────────────────────────────────────────────
        rect_x = slice_def.x / canvas_w
        rect_y = slice_def.y / canvas_h
        rect_w = w / canvas_w
        rect_h = h / canvas_h

        rot_rad     = math.radians(slice_def.rotation) if slice_def.rotation else 0.0
        mirror_int  = _MIRROR_MAP.get(slice_def.mirror or 'none', 0)
        brightness  = (slice_def.brightness or 0) / 255.0
        contrast    = (100 + (slice_def.contrast or 0)) / 100.0
        r_shift     = (slice_def.red   or 0) / 255.0
        g_shift     = (slice_def.green or 0) / 255.0
        b_shift     = (slice_def.blue  or 0) / 255.0

        # ── Soft-edge uniforms ────────────────────────────────────────────────
        # Supports both legacy int (symmetric pixel radius) and the frontend
        # dict format {enabled, width:{top,bottom,left,right}, curve, …}.
        soft_frac   = 0.0          # legacy symmetric slot
        soft_edges  = (0.0, 0.0, 0.0, 0.0)  # per-edge (top, right, bottom, left)
        soft_curve  = 1            # default: smooth
        _CURVE_MAP  = {'linear': 0, 'smooth': 1, 'exponential': 2}

        se_raw = slice_def.soft_edge
        if isinstance(se_raw, dict):
            if se_raw.get('enabled'):
                ew = se_raw.get('width', {})
                top_f  = float(ew.get('top',    0)) / h if h else 0.0
                right_f= float(ew.get('right',  0)) / w if w else 0.0
                bot_f  = float(ew.get('bottom', 0)) / h if h else 0.0
                left_f = float(ew.get('left',   0)) / w if w else 0.0
                soft_edges  = (top_f, right_f, bot_f, left_f)
                soft_curve  = _CURVE_MAP.get(se_raw.get('curve', 'smooth'), 1)
        elif isinstance(se_raw, (int, float)) and se_raw and se_raw > 0:
            se_px     = float(se_raw)
            soft_frac = se_px / min(w, h) if min(w, h) > 0 else 0.0

        # ── Perspective transform ─────────────────────────────────────────
        # Compute homography H that maps output UV (0..1) → canvas UV (0..1)
        # entirely on CPU (one matrix inversion, no GPU readback), then pass
        # the 9 coefficients as uniforms so the warp executes in the shader.
        use_persp = 0.0
        h_row0 = (1.0, 0.0, 0.0, 0.0)  # identity rows (no-op when use_persp=0)
        h_row1 = (0.0, 1.0, 0.0, 0.0)
        h_row2 = (0.0, 0.0, 1.0, 0.0)

        corners = getattr(slice_def, 'transformCorners', None)
        if corners and len(corners) == 4:
            defaults = [(0, 0), (w, 0), (w, h), (0, h)]
            is_warped = any(
                abs(corners[i].get('x', 0) - defaults[i][0]) > 1 or
                abs(corners[i].get('y', 0) - defaults[i][1]) > 1
                for i in range(4)
            )
            if is_warped:
                try:
                    import cv2 as _cv2
                    import numpy as _np
                    # Source canvas UV for each output corner (quadrilateral)
                    src_pts = _np.float32([
                        [(slice_def.x + c.get('x', 0)) / canvas_w,
                         (slice_def.y + c.get('y', 0)) / canvas_h]
                        for c in corners
                    ])
                    # Destination: unit square (output UV corners)
                    dst_pts = _np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
                    # H: output UV → canvas UV  (inverse mapping for fragment shader)
                    H = _cv2.getPerspectiveTransform(dst_pts, src_pts)
                    use_persp = 1.0
                    h_row0 = (float(H[0, 0]), float(H[0, 1]), float(H[0, 2]), 0.0)
                    h_row1 = (float(H[1, 0]), float(H[1, 1]), float(H[1, 2]), 0.0)
                    h_row2 = (float(H[2, 0]), float(H[2, 1]), float(H[2, 2]), 0.0)
                except Exception as _exc:
                    logger.warning('GPU perspective transform skipped: %s', _exc)

        uniforms = {
            'rect':       (rect_x, rect_y, rect_w, rect_h),  # slots 0-3
            'rotation':   rot_rad,    # slot 4
            'soft_edge':  soft_frac,  # slot 5
            'mirror':     mirror_int, # slot 6 (stored as bitcast i32)
            'brightness': brightness, # slot 7
            'contrast':   contrast,   # slot 8
            'channels':   (r_shift, g_shift, b_shift),  # slots 9-11
            # perspective fields (slots 12-27)
            'use_persp':  use_persp,  # slot 12
            '_pad':       (0.0, 0.0, 0.0),  # slots 13-15 (align h_rows to 16 bytes)
            'h_row0':     h_row0,     # slots 16-19
            'h_row1':     h_row1,     # slots 20-23
            'h_row2':     h_row2,     # slots 24-27
            # per-edge soft edge (slots 28-32)
            'soft_edges': soft_edges, # slots 28-31  top/right/bottom/left fractions
            'soft_curve': soft_curve, # slot  32     0=linear 1=smooth 2=exponential
            'use_mask':   0.0,        # slot  33     overridden below if mask present
        }

        # ── Mask texture ─────────────────────────────────────────────────────
        # slice_def.mask is a (H, W) uint8 numpy array (255=keep, 0=remove).
        # Upload it as a GPUFrame once and reuse every frame (re-upload only
        # when the mask array identity changes — i.e. after add_slice()).
        # Always pass 2 textures so the bind group layout (tex_count=2) is
        # consistent regardless of whether a mask is present.
        mask_numpy = getattr(slice_def, 'mask', None)
        if mask_numpy is not None:
            fingerprint = id(mask_numpy)
            cached = self._mask_frames.get(key)
            if cached is None or cached[1] != fingerprint:
                # (Re-)allocate mask GPUFrame when content changes.
                if cached is not None:
                    try:
                        cached[0].release()
                    except Exception:
                        pass
                mh, mw = mask_numpy.shape[:2]
                mask_gpu = _GPUFrame(get_device(), mw, mh)
                # Convert grayscale → BGR so upload() → RGBA works correctly.
                import numpy as _np
                import cv2 as _cv2
                mask_bgr = _cv2.cvtColor(mask_numpy, _cv2.COLOR_GRAY2BGR)
                mask_gpu.upload(mask_bgr)
                self._mask_frames[key] = (mask_gpu, fingerprint)
                cached = self._mask_frames[key]
            mask_frame = cached[0]
            uniforms['use_mask'] = 1.0
        else:
            # No mask — use 1×1 white dummy to satisfy the 2-texture bind group layout.
            if self._dummy_mask is None:
                import numpy as _np
                self._dummy_mask = _GPUFrame(get_device(), 1, 1)
                white = _np.full((1, 1, 3), 255, dtype=_np.uint8)
                self._dummy_mask.upload(white)
            mask_frame = self._dummy_mask

        get_renderer().render(
            wgsl_source=self._load_shader(),
            target=existing,
            uniforms=uniforms,
            textures=[composite, mask_frame],
        )
        return existing

    # ------------------------------------------------------------------
    def release(self) -> None:
        """Destroy all cached output frames."""
        for frame in self._output_frames.values():
            try:
                frame.release()
            except Exception:
                pass
        self._output_frames.clear()
        for mask_frame, _ in self._mask_frames.values():
            try:
                mask_frame.release()
            except Exception:
                pass
        self._mask_frames.clear()
        if self._dummy_mask is not None:
            try:
                self._dummy_mask.release()
            except Exception:
                pass
            self._dummy_mask = None
