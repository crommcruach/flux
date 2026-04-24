"""GPUCompositionRenderer — multi-slice composition entirely on GPU.

Each output with a ``composition`` config (width, height, slices=[...]) is
rendered into a single cached GPUFrame without any CPU download.

For each slice in the composition:
  1. ``SliceManager.get_slice_gpu()`` crops/processes the named slice from the
     full-canvas composite GPUFrame (rotation, soft-edge, colour, mask — all GPU).
  2. A viewport-constrained blit pass copies the result into the target region
     of the composition output GPUFrame using ``comp_blit.wgsl``.

The first slice blit uses ``LoadOp.clear`` (black background); subsequent
blit passes use ``LoadOp.load`` so previously placed slices are preserved.
Each pass submits its own command encoder — wgpu queue ordering guarantees
that pass N+1 reads the output after pass N has written it.

Usage
-----
    cr = GPUCompositionRenderer()
    output_frame = cr.render(
        output_id, composition_dict, composite_gpu_frame,
        canvas_w, canvas_h, slice_manager,
    )
    # output_frame is owned by this renderer — do NOT release it.
    # It stays valid until the next render() call for the same output_id
    # (or until release() is called).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import wgpu

from ..core.logger import get_logger

if TYPE_CHECKING:
    from .frame import GPUFrame
    from ..player.outputs.slices import SliceManager

logger = get_logger(__name__)

_SHADER_PATH = os.path.join(os.path.dirname(__file__), 'shaders', 'comp_blit.wgsl')


class GPUCompositionRenderer:
    """Renders multi-slice compositions into per-output cached GPUFrames."""

    _shader_src: str | None = None  # class-level — one file load shared across instances

    @classmethod
    def _load_shader(cls) -> str:
        if cls._shader_src is None:
            with open(_SHADER_PATH, encoding='utf-8') as fh:
                cls._shader_src = fh.read()
        return cls._shader_src

    @classmethod
    def invalidate_shader_cache(cls) -> None:
        """Force re-read of comp_blit.wgsl on next render call."""
        cls._shader_src = None

    def __init__(self) -> None:
        # output_id → GPUFrame  (owned here; resized when composition dimensions change)
        self._output_frames: dict[str, GPUFrame] = {}

    # ------------------------------------------------------------------

    def render(
        self,
        output_id: str,
        composition: dict,
        composite: GPUFrame,
        canvas_w: int,
        canvas_h: int,
        slice_manager: SliceManager,
    ) -> GPUFrame | None:
        """Render a multi-slice composition into a cached output GPUFrame.

        Parameters
        ----------
        output_id     : unique key for the per-output frame cache.
        composition   : dict with ``width``, ``height``, and ``slices`` list.
                        Each slice entry: ``{sliceId, x, y, width, height}``.
        composite     : full-canvas GPUFrame (source texture).
        canvas_w/h    : canvas dimensions passed to ``SliceManager.get_slice_gpu()``.
        slice_manager : player SliceManager used to look up/render slice definitions.

        Returns
        -------
        GPUFrame owned by this renderer — do NOT release.
        None if the composition has no valid slices or rendering fails.
        """
        from .frame import GPUFrame as _GPUFrame
        from .context import get_device
        from .renderer import get_renderer

        comp_w = int(composition.get('width', 1920))
        comp_h = int(composition.get('height', 1080))
        comp_slices = composition.get('slices', [])

        if not comp_slices:
            return None

        # (Re-)allocate cached output frame when composition dimensions change.
        existing = self._output_frames.get(output_id)
        if existing is None or existing.width != comp_w or existing.height != comp_h:
            if existing is not None:
                try:
                    existing.release()
                except Exception:
                    pass
            existing = _GPUFrame(get_device(), comp_w, comp_h)
            self._output_frames[output_id] = existing

        renderer = get_renderer()
        shader   = self._load_shader()

        first_pass      = True
        passes_recorded = 0

        for comp_slice in comp_slices:
            slice_id = comp_slice.get('sliceId')
            if not slice_id:
                continue

            out_x = int(comp_slice.get('x', 0))
            out_y = int(comp_slice.get('y', 0))
            out_w = max(1, int(comp_slice.get('width',  100)))
            out_h = max(1, int(comp_slice.get('height', 100)))

            # Skip slices entirely outside the output frame.
            if out_x >= comp_w or out_y >= comp_h or out_x + out_w <= 0 or out_y + out_h <= 0:
                continue

            # Clamp to output frame bounds.
            clamped_x = max(0, out_x)
            clamped_y = max(0, out_y)
            clamped_w = min(out_w, comp_w - clamped_x)
            clamped_h = min(out_h, comp_h - clamped_y)
            if clamped_w <= 0 or clamped_h <= 0:
                continue

            # Get the slice as a GPU-rendered GPUFrame (crop/rotate/colour/mask).
            slice_frame = slice_manager.get_slice_gpu(
                slice_id, composite, canvas_w, canvas_h,
            )
            if slice_frame is None:
                continue

            # First blit: clear output frame to black.  Subsequent blits: load
            # (preserve already-placed slices).
            load_op = wgpu.LoadOp.clear if first_pass else wgpu.LoadOp.load
            first_pass = False

            # Blit slice_frame into (clamped_x, clamped_y, clamped_w, clamped_h)
            # of the output frame.  set_viewport() restricts rasterisation to
            # that rectangle; comp_blit.wgsl remaps UVs accordingly.
            renderer.render(
                wgsl_source=shader,
                target=existing,
                uniforms={
                    'viewport': (
                        float(clamped_x), float(clamped_y),
                        float(clamped_w), float(clamped_h),
                    ),
                },
                textures=[slice_frame],
                load_op=load_op,
                viewport=(
                    float(clamped_x), float(clamped_y),
                    float(clamped_w), float(clamped_h),
                    0.0, 1.0,
                ),
            )
            passes_recorded += 1

        if passes_recorded == 0:
            # No valid slices — clear the output frame to black.
            device = get_device()
            enc = device.create_command_encoder()
            rp  = enc.begin_render_pass(
                color_attachments=[{
                    'view':           existing.view,
                    'resolve_target': None,
                    'load_op':        wgpu.LoadOp.clear,
                    'store_op':       wgpu.StoreOp.store,
                    'clear_value':    (0.0, 0.0, 0.0, 1.0),
                }]
            )
            rp.end()
            device.queue.submit([enc.finish()])

        logger.debug(
            'GPUCompositionRenderer [%s]: %d slice(s) blitted into %dx%d frame',
            output_id, passes_recorded, comp_w, comp_h,
        )
        return existing

    # ------------------------------------------------------------------

    def release(self) -> None:
        """Release all cached output frames."""
        for frame in self._output_frames.values():
            try:
                frame.release()
            except Exception:
                pass
        self._output_frames.clear()
