"""
ModernGL headless context singleton.

One context is shared by all GPU pipeline stages (TexturePool, Renderer, GPUFrame).
No fallback — if ModernGL cannot create a context, the application exits.
"""
import moderngl
from ..core.logger import get_logger

logger = get_logger(__name__)

_ctx: moderngl.Context | None = None


def get_context() -> moderngl.Context:
    global _ctx
    if _ctx is None:
        _ctx = moderngl.create_standalone_context()
        logger.info(f"ModernGL context created: {_ctx.info['GL_RENDERER']} "
                    f"(OpenGL {_ctx.info['GL_VERSION']})")
    return _ctx


def destroy_context() -> None:
    global _ctx
    if _ctx is not None:
        _ctx.release()
        _ctx = None
        logger.info("ModernGL context released")
