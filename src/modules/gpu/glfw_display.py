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
import time
import logging

import wgpu

from .context import get_device
from ..core.logger import get_logger

logger = get_logger(__name__)

# wgpu's internal surface logger emits WARNING-level "Suboptimal present of
# frame N" and "No successful surface texture obtained for N frames" messages
# on Windows D3D12 with vsync=False (immediate present mode).  These are
# normal on the first few frames after surface creation / reconfiguration and
# are fully handled by wgpu internally (it reconfigures and retries).
# Elevate the threshold to ERROR so they don't flood the application log.
logging.getLogger("wgpu").setLevel(logging.ERROR)

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
        self._surface_configured = False  # True after a successful configure() call
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
                # poll_events() + fixed sleep instead of wait_events_timeout().
                # wait_events_timeout() blocks until a window event arrives or the
                # timeout fires.  On Windows, when the window is in the background
                # the compositor stops delivering vblank/WM_PAINT events, so the
                # GLFW thread can stall for hundreds of ms.  present() in FIFO
                # (vsync) mode does the same: it blocks waiting for vblank, and
                # if no vblank comes the GPU command queue fills up, causing
                # device.queue.submit() in push_gpu_frame() to block as well —
                # which freezes the player thread and stops video playback.
                # poll_events() returns immediately; the sleep provides rate-
                # limiting without blocking on compositor events.
                _glfw_mod.poll_events()

                # If Windows iconified the window (e.g. clicking another monitor
                # app, Win+D, taskbar), restore it immediately.  This must be done
                # from the event-loop thread — not from a GLFW callback — to avoid
                # corrupting GLFW's internal window state.
                if _glfw_mod.get_window_attrib(self._window, _glfw_mod.ICONIFIED):
                    _glfw_mod.restore_window(self._window)

                self._render()
                time.sleep(1.0 / 60)  # cap at ~60 fps; player pushes at its own rate
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
        # Keep the output window above all other windows at all times so it
        # is never hidden when another application receives focus.
        _glfw_mod.window_hint(_glfw_mod.FLOATING, True)

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

        # Pump the Win32 message loop so WM_CREATE is fully processed and the
        # HWND is backed by a real drawable surface before we hand it to wgpu.
        _glfw_mod.poll_events()

        # Keep wgpu informed of framebuffer size changes (HiDPI, window resize).
        # Must use get_framebuffer_size (physical pixels) not get_window_size
        # (logical pixels) — they differ on HiDPI/4K displays.
        # Guard against (0, 0): GLFW fires a framebuffer resize event with zero
        # dimensions when the window is minimized on Windows.  Passing (0, 0) to
        # set_physical_size() causes the next get_current_texture() call to raise
        # "Cannot get texture for a canvas with zero pixels" indefinitely.
        def _on_fb_resize(window, w, h):
            if self._canvas_ctx is not None and w > 0 and h > 0:
                self._canvas_ctx.set_physical_size(w, h)
        _glfw_mod.set_framebuffer_size_callback(self._window, _on_fb_resize)

        # Iconify/restore is handled in the event loop (poll-based) rather than
        # via a callback.  Calling restore_window() from inside a GLFW callback
        # can confuse GLFW's internal state on Windows and cause the window to
        # be destroyed.  Polling GLFW_ICONIFIED after poll_events() and restoring
        # there is safe because it runs on the same thread as glfw.init().

        # Build wgpu surface from the native Win32 window handle.
        if sys.platform.startswith("win"):
            hwnd = _glfw_mod.get_win32_window(self._window)
            # Apply Win32 window style fixes for always-on-top and anti-minimize.
            try:
                import ctypes
                import ctypes.wintypes
                _user32 = ctypes.windll.user32

                # ── 1. Remove WS_MINIMIZEBOX so Windows can never minimize the window ──
                GWL_STYLE    = -16
                WS_MINIMIZEBOX = 0x00020000
                style = _user32.GetWindowLongW(int(hwnd), GWL_STYLE)
                _user32.SetWindowLongW(int(hwnd), GWL_STYLE, style & ~WS_MINIMIZEBOX)

                # ── 2. HWND_TOPMOST: keep window above all non-topmost windows ─────────
                # HWND_TOPMOST must be passed as a pointer-sized value (-1), not c_int.
                SWP_NOMOVE      = 0x0002
                SWP_NOSIZE      = 0x0001
                SWP_NOACTIVATE  = 0x0010
                HWND_TOPMOST    = ctypes.c_void_p(-1)
                _user32.SetWindowPos.argtypes = [
                    ctypes.c_void_p, ctypes.c_void_p,
                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                    ctypes.c_uint,
                ]
                ret = _user32.SetWindowPos(
                    int(hwnd), HWND_TOPMOST, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                )
                if ret == 0:
                    err = ctypes.GetLastError()
                    logger.warning("GLFWDisplay: SetWindowPos HWND_TOPMOST failed, error=%d", err)
                else:
                    logger.debug("GLFWDisplay: HWND_TOPMOST set successfully")
            except Exception as _e:
                logger.warning("GLFWDisplay: Win32 window style fixup failed: %s", _e)
            present_info = {
                "method": "screen",
                "platform": "windows",
                "window": int(hwnd),
                # vsync=False → immediate/mailbox present mode.
                # FIFO (vsync) mode blocks present() until the next vblank from
                # the compositor.  When the window is in the background the OS
                # stops delivering vblank signals, so present() stalls the GLFW
                # thread, backs up the GPU queue, and ultimately freezes the
                # player render thread.  Disabling vsync avoids all of this.
                "vsync": False,
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
                    "vsync": False,
                }
            else:
                present_info = {
                    "method": "screen",
                    "platform": "x11",
                    "window": int(_glfw_mod.get_x11_window(self._window)),
                    "display": int(_glfw_mod.get_x11_display()),
                    "vsync": False,
                }
        elif sys.platform.startswith("darwin"):
            present_info = {
                "method": "screen",
                "platform": "cocoa",
                "window": int(_glfw_mod.get_cocoa_window(self._window)),
                "vsync": False,
            }
        else:
            raise RuntimeError(f"Unsupported platform: {sys.platform}")

        device = get_device()
        self._canvas_ctx = wgpu.gpu.get_canvas_context(present_info)
        # The entire pipeline uses rgba8unorm (linear, non-sRGB).
        # get_preferred_format() on Windows D3D12 returns bgra8unorm-srgb, which
        # makes the GPU apply gamma encoding to already-display-ready linear values
        # → double gamma → image appears too bright/washed out.
        # Force bgra8unorm (no automatic gamma) so colours are passed through as-is.
        preferred = self._canvas_ctx.get_preferred_format(device.adapter)
        self._surface_format = preferred.replace("-srgb", "") if preferred.endswith("-srgb") else preferred
        self._do_configure(device)

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

    def _do_configure(self, device=None) -> None:
        """Call wgpuSurfaceConfigure on the underlying surface.

        Required after window creation and after the surface is lost/outdated.
        In wgpu >= 0.19 the GPUCanvasContext._physical_size starts as (0, 0).
        configure() calls _configure_screen_real() which silently skips
        wgpuSurfaceConfigure when width == 0, leaving the surface unconfigured.
        A subsequent get_current_texture() then panics in wgpu-native Rust.
        Fix: always call set_physical_size() before configure() so the C-level
        configure is actually issued.
        """
        if self._canvas_ctx is None or self._surface_format is None:
            return
        if device is None:
            device = get_device()
        # Tell the canvas context the window's physical pixel size.
        # Use get_framebuffer_size (physical pixels) rather than self._width/height
        # (logical pixels) — on HiDPI/4K displays they differ, causing
        # SuccessSuboptimal on every frame if the wrong size is passed.
        if self._window is not None:
            fb_w, fb_h = _glfw_mod.get_framebuffer_size(self._window)
        else:
            fb_w, fb_h = self._width, self._height
        if fb_w <= 0 or fb_h <= 0:
            # Window is minimized — skip configure until it is restored.
            # Do NOT set _surface_configured = True here.
            return
        self._canvas_ctx.set_physical_size(fb_w, fb_h)
        self._canvas_ctx.configure(
            device=device,
            format=self._surface_format,
            usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
            alpha_mode="opaque",
        )
        self._surface_configured = True
        logger.debug("GLFWDisplay: surface configured (format=%s)", self._surface_format)

    def _render(self) -> None:
        """Blit _display_tex → swapchain.  Called from the event loop thread."""
        with self._display_lock:
            frame = self._display_tex
        if frame is None:
            return

        # Guard: if the surface lost configuration (e.g. after a wgpu surface error)
        # reconfigure it now instead of calling get_current_texture() and triggering
        # the "Surface is not configured for presentation" Rust panic.
        if not self._surface_configured:
            try:
                self._do_configure()
            except Exception as exc:
                logger.warning("GLFWDisplay: surface reconfigure failed: %s", exc)
            return  # skip this frame; render on the next event

        device = get_device()
        try:
            surface_tex = self._canvas_ctx.get_current_texture()

            # wgpu-py exposes a .status attribute (enum) on the texture when the
            # surface is lost or outdated.  Reconfigure instead of crashing.
            status = getattr(surface_tex, 'status', None)
            if status is not None:
                status_str = status.name if hasattr(status, 'name') else str(status)
                if status_str.lower() not in ('success', 'optimal'):
                    logger.warning(
                        "GLFWDisplay: surface texture status=%s — reconfiguring",
                        status_str,
                    )
                    self._surface_configured = False
                    return

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
                exc_str = str(exc)
                if "zero pixels" in exc_str:
                    # Window is minimized — framebuffer is (0, 0).  This is
                    # transient: just skip the frame.  Do NOT mark the surface as
                    # needing reconfiguration — that would start an infinite
                    # reconfigure loop that spams the log until the window is
                    # restored.  The resize callback will call set_physical_size
                    # with the real size once the window is unminimized.
                    return
                logger.warning("GLFWDisplay: render error: %s", exc)
                # Mark surface as needing reconfiguration on the next frame.
                self._surface_configured = False

    def _shutdown(self) -> None:
        self._active = False
        self._surface_configured = False
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
