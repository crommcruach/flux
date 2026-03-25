"""
Renderer — full-screen quad shader runner.

All GPU passes (blend, effects, color grading, …) go through this single renderer.
Programs are cached by fragment shader source string — compiled once, reused every frame.

Usage:
    renderer = get_renderer()
    renderer.render(
        frag_source=blend_src,
        target_fbo=composite.fbo,
        uniforms={'opacity': 0.8, 'mode': 0},
        textures={'base': (0, composite), 'overlay': (1, layer_tex)},
    )
"""
import os
import numpy as np
import moderngl
from .context import get_context
from ..core.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Shared vertex shader (all passes)
# ---------------------------------------------------------------------------

_VERTEX_SHADER = """
#version 330
in vec2 in_position;
in vec2 in_uv;
out vec2 v_uv;
void main() {
    gl_Position = vec4(in_position, 0.0, 1.0);
    v_uv = in_uv;
}
"""

# Full-screen quad: two CCW triangles covering clip-space [-1, 1]²
_QUAD_VERTICES = np.array([
    -1.0, -1.0,   0.0, 0.0,
     1.0, -1.0,   1.0, 0.0,
     1.0,  1.0,   1.0, 1.0,
    -1.0,  1.0,   0.0, 1.0,
], dtype=np.float32)

_QUAD_INDICES = np.array([0, 1, 2, 0, 2, 3], dtype=np.int32)

# Shader directory (same package)
_SHADER_DIR = os.path.join(os.path.dirname(__file__), 'shaders')


def load_shader(filename: str) -> str:
    """Load a GLSL source file from src/modules/gpu/shaders/."""
    path = os.path.join(_SHADER_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


class Renderer:
    """
    Renders a full-screen textured quad using a given fragment shader.
    Programs are cached by fragment source string — compile once per unique shader.
    """

    def __init__(self, ctx: moderngl.Context):
        self.ctx = ctx
        # frag_source → (Program, VertexArray)
        self._programs: dict[str, tuple[moderngl.Program, moderngl.VertexArray]] = {}
        self._vbo = ctx.buffer(_QUAD_VERTICES.tobytes())
        self._ibo = ctx.buffer(_QUAD_INDICES.tobytes())

    def _get_program(self, frag_source: str) -> tuple[moderngl.Program, moderngl.VertexArray]:
        if frag_source not in self._programs:
            prog = self.ctx.program(
                vertex_shader=_VERTEX_SHADER,
                fragment_shader=frag_source,
            )
            vao = self.ctx.vertex_array(
                prog,
                [(self._vbo, '2f 2f', 'in_position', 'in_uv')],
                index_buffer=self._ibo,
            )
            self._programs[frag_source] = (prog, vao)
            logger.debug(f"Renderer: compiled shader ({len(self._programs)} total)")
        return self._programs[frag_source]

    def render(
        self,
        frag_source: str,
        target_fbo: moderngl.Framebuffer,
        uniforms: dict,
        textures: dict,
    ) -> None:
        """
        Run one shader pass.

        uniforms: {name: value}  — int, float, or tuple (for vec2/vec3/…)
        textures: {uniform_name: (texture_unit, GPUFrame)}
        """
        prog, vao = self._get_program(frag_source)

        for name, val in uniforms.items():
            if name in prog:
                prog[name].value = tuple(val) if isinstance(val, (list, tuple)) else val

        for name, (unit, gpu_frame) in textures.items():
            gpu_frame.texture.use(location=unit)
            if name in prog:
                prog[name].value = unit

        target_fbo.use()
        # Set viewport to cover the entire target FBO — the viewport stays at
        # whatever it was when the FBO was last bound, which may be wrong for
        # a freshly created headless context.
        w, h = target_fbo.size
        self.ctx.viewport = (0, 0, w, h)
        # No explicit clear here: the full-screen quad covers every pixel so
        # any previous contents are fully overwritten by the shader output.
        vao.render()

    def release(self) -> None:
        """Release all compiled programs and quad buffers."""
        for prog, vao in self._programs.values():
            vao.release()
            prog.release()
        self._programs.clear()
        self._vbo.release()
        self._ibo.release()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_renderer: Renderer | None = None


def get_renderer() -> Renderer:
    global _renderer
    if _renderer is None:
        _renderer = Renderer(get_context())
    return _renderer


def _reset_renderer() -> None:
    """Discard the cached Renderer so it's recreated in the next calling thread."""
    global _renderer
    _renderer = None
