"""
ModernGL headless context singleton.

One context is shared by all GPU pipeline stages (TexturePool, Renderer, GPUFrame).
No fallback — if ModernGL cannot create a context, the application exits.
"""
import threading
import moderngl
from ..core.logger import get_logger

logger = get_logger(__name__)

_ctx: moderngl.Context | None = None
_ctx_thread_id: int | None = None


def get_context() -> moderngl.Context:
    global _ctx, _ctx_thread_id
    if _ctx is None:
        _ctx = moderngl.create_standalone_context()
        _ctx_thread_id = threading.get_ident()
        logger.info(f"ModernGL context created: {_ctx.info['GL_RENDERER']} "
                    f"(OpenGL {_ctx.info['GL_VERSION']}) "
                    f"in thread {_ctx_thread_id}")
    return _ctx


def is_context_from_current_thread() -> bool:
    """True if _ctx was created by the calling thread (or not yet created)."""
    return _ctx_thread_id is None or _ctx_thread_id == threading.get_ident()


def destroy_context() -> None:
    global _ctx, _ctx_thread_id
    if _ctx is not None:
        _ctx.release()
        _ctx = None
        _ctx_thread_id = None
        logger.info("ModernGL context released")
