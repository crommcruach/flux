"""
GLFWDisplay — raw GLFW + wgpu surface, zero-copy GPU display.

Architecture
------------
GPUFrame (rgba8unorm, TEXTURE_BINDING | COPY_SRC)
  → copy_texture_to_texture (GPU blit, no CPU round-trip)
  → _display_tex (internal rgba8unorm buffer, COPY_DST | TEXTURE_BINDING)
  → WGSL fullscreen-quad shader
  → wgpu GPUCanvasContext swapchain
  → present() → screen

Threading
---------
The GLFW event loop runs in a dedicated daemon thread.
push_gpu_frame() is called from the player thread, copies the frame to an
internal buffer via copy_texture_to_texture, then wakes the GLFW thread via
glfw.post_empty_event().  A lock serialises simultaneous GPU submissions.
"""

import threading
import sys

import wgpu

from .context import get_device
from ..core.logger import get_logger

logger = get_logger(__name__)

try:
    import glfw as _glfw_mod
    _GLFW_AVAILABLE: bool = True
except ImportError:
    _GLFW_AVAILABLE = False
    logger.warning("GLFWDisplay: pyglfw not installed — display output disabled")


# ---------------------------------------------------------------------------
# WGSL — fullscreen quad blit (4-vertex TRIANGLE_STRIP)
# Samples _display_tex (rgba8unorm) → swapchain render target.
# ---------------------------------------------------------------------------
_BLIT_WGSL = """
@group(0) @binding(0) var t: texture_2d<f32>;
@group(0) @binding(1) var s: sampler;

struct V {
    @builtin(position) pos: vec4<f32>,
    @location(0) uv:  vec2<f32>,
}

@vertex fn vs(@builtin(vertex_index) i: u32) -> V {
    let x = f32(i & 1u);
    let y = f32((i >> 1u) & 1u);
    var o: V;
    o.pos = vec4<f32>(x * 2.0 - 1.0, 1.0 - y * 2.0, 0.0, 1.0);
    o.uv  = vec2<f32>(x, y);
    return o;
}

@fragment fn fs(v: V) -> @location(0) vec4<f32> {
    return textureSample(t, s, v.uv);
}
"""


class GLFWDisplay:
    """Singleton GPU display window using raw GLFW + wgpu surface.

    All GLFW operations (init, poll, destroy) are confined to the daemon
    event-loop thread.  push_gpu_frame() is safe to call from any thread.
    """

    _instance = None

    def __init__(self):
        self._window = None
        self._canvas_ctx = None       # wgpu GPUCanvasContext (swapchain)
        self._pipeline = None
        self._sampler = None
        self._surface_format = None
        self._display_tex = None      # internal copy buffer (GPUFrame, not pool)
        self._display_lock = threading.Lock()   # serialises GPU submissions
        self._active = False
        self._thread = None
        self._ready_event = threading.Event()
        # Kept for backward-compat with display_output.send_frame() logging.
        self._frame_seq: int = 0

    @classmethod
    def instance(cls) -> 'GLFWDisplay':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------ public

    def start(self, width: int = 1920, height: int = 1080, title: str = "Output",
              monitor_index: int = 0, fullscreen: bool = False) -> bool:
        """Create the display window and start the event loop thread.

        Returns True when the window is ready, False on failure.
        """
        if self._active:
            return True
        if not _GLFW_AVAILABLE:
            logger.error("GLFWDisplay: pyglfw not available — cannot open display window")
            return False

        self._width = width
        self._height = height
        self._title = title
        self._monitor_index = monitor_index
        self._fullscreen = fullscreen

        self._thread = threading.Thread(
            target=self._event_loop, daemon=True, name="GLFWDisplay"
        )
        self._thread.start()
        ok = self._ready_event.wait(timeout=10.0)
        if not ok:
            logger.error("GLFWDisplay: event loop did not become ready in 10 s")
            return False
        return self._active   # False if _init raised

    def stop(self) -> None:
        """Signal the event loop to exit and clean up."""
        self._active = False
        if self._window:
            try:
                _glfw_mod.set_window_should_close(self._window, True)
                _glfw_mod.post_empty_event()
            except Exception:
                pass

    def push_gpu_frame(self, gpu_frame) -> None:
        """Copy *gpu_frame* to the internal display buffer and schedule a redraw.

        Called from the player thread.  gpu_frame is a GPUFrame from the
        texture pool — we copy it immediately so the pool can reuse it.
        """
        if not self._active:
            return
        device = get_device()
        w, h = gpu_frame.width, gpu_frame.height

        with self._display_lock:
            # (Re)create internal display buffer if size changed.
            if self._display_tex is None or (
                self._display_tex.width != w or self._display_tex.height != h
            ):
                from .frame import GPUFrame
                self._display_tex = GPUFrame(device, w, h)

            # GPU copy: pool texture → display buffer (no CPU round-trip).
            encoder = device.create_command_encoder()
            encoder.copy_texture_to_texture(
                {"texture": gpu_frame.texture, "origin": (0, 0, 0), "mip_level": 0},
                {"texture": self._display_tex.texture, "origin": (0, 0, 0), "mip_level": 0},
                (w, h, 1),
            )
            device.queue.submit([encoder.finish()])
            self._frame_seq += 1

        # Wake the GLFW event loop.
        try:
            _glfw_mod.post_empty_event()
        except Exception:
            pass

    def push_frame(self, frame) -> None:
        """Upload a CPU numpy frame to the display buffer.

        Called when CPU post-processing (e.g. active transition) produces a
        blended result that must override the raw composite already pushed by
        push_gpu_frame() earlier in the same render cycle.
        """
        if not self._active or frame is None:
            return
        device = get_device()
        h, w = frame.shape[:2]
        with self._display_lock:
            if self._display_tex is None or (
                self._display_tex.width != w or self._display_tex.height != h
            ):
                from .frame import GPUFrame
                self._display_tex = GPUFrame(device, w, h)
            self._display_tex.upload(frame)
            self._frame_seq += 1
        try:
            _glfw_mod.post_empty_event()
        except Exception:
            pass

    def is_active(self) -> bool:
        return self._active

    def is_gpu_mode(self) -> bool:
        return self._active

    # ------------------------------------------------------------------ private

    def _event_loop(self) -> None:
        """Daemon thread: init GLFW, create wgpu surface, blit loop."""
        try:
            self._init_window_and_pipeline()
        except Exception as exc:
            logger.error("GLFWDisplay: init failed: %s", exc, exc_info=True)
            self._ready_event.set()
            return

        self._active = True
        self._ready_event.set()
        logger.info("GLFWDisplay: window ready (%dx%d)", self._width, self._height)

        try:
            while not _glfw_mod.window_should_close(self._window):
                # wait_events_timeout so push_gpu_frame / post_empty_event wakes us;
                # the 1/30 s timeout is just a safety fallback.
                _glfw_mod.wait_events_timeout(1.0 / 30)
                self._render()
        except Exception as exc:
            if self._active:
                logger.error("GLFWDisplay: event loop error: %s", exc, exc_info=True)
        finally:
            self._shutdown()

    def _init_window_and_pipeline(self) -> None:
        if not _glfw_mod.init():
            raise RuntimeError("glfw.init() failed")

        _glfw_mod.window_hint(_glfw_mod.CLIENT_API, _glfw_mod.NO_API)
        _glfw_mod.window_hint(_glfw_mod.RESIZABLE, False)

        monitor = None
        if self._fullscreen:
            monitors = _glfw_mod.get_monitors()
            idx = min(self._monitor_index, len(monitors) - 1)
            monitor = monitors[idx]

        self._window = _glfw_mod.create_window(
            self._width, self._height, self._title, monitor, None
        )
        if not self._window:
            _glfw_mod.terminate()
            raise RuntimeError("glfw.create_window() returned None")

        # Build wgpu surface from the native Win32 window handle.
        if sys.platform.startswith("win"):
            hwnd = _glfw_mod.get_win32_window(self._window)
            present_info = {
                "method": "screen",
                "platform": "windows",
                "window": int(hwnd),
            }
        elif sys.platform.startswith("linux"):
            # Detect Wayland vs X11 without external dependencies.
            # Try to get the Wayland display handle; falls back to X11.
            wayland_display = None
            try:
                wayland_display = _glfw_mod.get_wayland_display()
            except Exception:
                pass
            if wayland_display:
                present_info = {
                    "method": "screen",
                    "platform": "wayland",
                    "window": int(_glfw_mod.get_wayland_window(self._window)),
                    "display": int(wayland_display),
                }
            else:
                present_info = {
                    "method": "screen",
                    "platform": "x11",
                    "window": int(_glfw_mod.get_x11_window(self._window)),
                    "display": int(_glfw_mod.get_x11_display()),
                }
        elif sys.platform.startswith("darwin"):
            present_info = {
                "method": "screen",
                "platform": "cocoa",
                "window": int(_glfw_mod.get_cocoa_window(self._window)),
            }
        else:
            raise RuntimeError(f"Unsupported platform: {sys.platform}")

        device = get_device()
        self._canvas_ctx = wgpu.gpu.get_canvas_context(present_info)
        self._surface_format = self._canvas_ctx.get_preferred_format(device.adapter)
        self._canvas_ctx.configure(
            device=device,
            format=self._surface_format,
            usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
        )

        # Build a permanent blit render pipeline (cached for the window lifetime).
        shader = device.create_shader_module(code=_BLIT_WGSL)
        self._sampler = device.create_sampler(
            address_mode_u="clamp-to-edge",
            address_mode_v="clamp-to-edge",
            mag_filter="linear",
            min_filter="linear",
        )
        self._pipeline = device.create_render_pipeline(
            layout="auto",
            vertex={"module": shader, "entry_point": "vs"},
            fragment={
                "module": shader,
                "entry_point": "fs",
                "targets": [{"format": self._surface_format}],
            },
            primitive={"topology": "triangle-strip", "strip_index_format": "uint32"},
        )

    def _render(self) -> None:
        """Blit _display_tex → swapchain.  Called from the event loop thread."""
        with self._display_lock:
            frame = self._display_tex
        if frame is None:
            return

        device = get_device()
        try:
            surface_tex = self._canvas_ctx.get_current_texture()
            surface_view = surface_tex.create_view()
            bg = device.create_bind_group(
                layout=self._pipeline.get_bind_group_layout(0),
                entries=[
                    {"binding": 0, "resource": frame.view},
                    {"binding": 1, "resource": self._sampler},
                ],
            )
            encoder = device.create_command_encoder()
            rp = encoder.begin_render_pass(
                color_attachments=[{
                    "view": surface_view,
                    "load_op": "clear",
                    "store_op": "store",
                    "clear_value": (0, 0, 0, 1),
                }]
            )
            rp.set_pipeline(self._pipeline)
            rp.set_bind_group(0, bg)
            rp.draw(4)
            rp.end()
            device.queue.submit([encoder.finish()])
            self._canvas_ctx.present()
        except Exception as exc:
            if self._active:
                logger.warning("GLFWDisplay: render error: %s", exc)

    def _shutdown(self) -> None:
        self._active = False
        self._pipeline = None
        self._sampler = None
        with self._display_lock:
            self._display_tex = None
        if self._canvas_ctx:
            try:
                self._canvas_ctx.unconfigure()
            except Exception:
                pass
            self._canvas_ctx = None
        if self._window:
            try:
                _glfw_mod.destroy_window(self._window)
            except Exception:
                pass
            self._window = None
        try:
            _glfw_mod.terminate()
        except Exception:
            pass
        logger.info("GLFWDisplay: window closed")


def get_glfw_display() -> GLFWDisplay:
    """Return the GLFWDisplay singleton."""
    return GLFWDisplay.instance()
