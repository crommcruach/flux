"""
GeneratorSource — GPU-shader-based procedural frame generator.

Each generator plugin implements:
    get_shader()    -> WGSL source string
    get_uniforms()  -> dict of uniform values

get_next_frame() renders the shader directly to a GPUFrame (no CPU compute).
Plugins that have not yet been converted return a black numpy frame with a
one-time warning.
"""
import time
import numpy as np
from ...core.logger import get_logger
from ...core.constants import DEFAULT_FPS
from .base import FrameSource

logger = get_logger(__name__)


class GeneratorSource(FrameSource):
    """Plugin-basierter Generator als Frame-Quelle (prozedural generiert)."""

    def __init__(self, generator_id, parameters, canvas_width, canvas_height, config=None):
        super().__init__(canvas_width, canvas_height, config)
        self.generator_id = generator_id
        self.parameters = parameters or {}
        self.source_path = f"generator:{generator_id}"
        self.source_type = 'generator'
        self.plugin_instance = None
        self.start_time = 0

        # Duration: configurable per generator, max 60 s
        duration_value = parameters.get('duration', 10) if parameters else 10
        if isinstance(duration_value, str):
            try:
                duration_value = float(duration_value)
            except (ValueError, TypeError):
                duration_value = 10
        self.duration = min(60, max(1, duration_value))
        self.is_infinite = False
        self.total_frames = int(self.duration * self.fps)

        logger.debug(
            f"GeneratorSource: duration={self.duration}s, "
            f"total_frames={self.total_frames} (frames 0-{self.total_frames - 1})"
        )

        self.start_time = 0

    def initialize(self):
        """Initialisiert Generator-Plugin."""
        from ...plugins.manager import get_plugin_manager

        pm = get_plugin_manager()
        logger.debug(
            f"🔧 GeneratorSource initializing: {self.generator_id} "
            f"with parameters: {self.parameters}"
        )
        self.plugin_instance = pm.load_plugin(self.generator_id, config=self.parameters)
        if not self.plugin_instance:
            logger.error(f"❌ Generator konnte nicht geladen werden: {self.generator_id}")
            return False

        self.start_time = time.time()

        logger.debug(f"✅ GeneratorSource initialisiert:")
        logger.debug(f"  Generator: {self.generator_id}")
        logger.debug(f"  Canvas: {self.canvas_width}x{self.canvas_height}")
        logger.debug(f"  Parameters: {self.parameters}")
        logger.debug(f"  Plugin instance: {type(self.plugin_instance).__name__}")
        logger.debug(f"  Has update_parameter: {hasattr(self.plugin_instance, 'update_parameter')}")

        # Apply parameters that were set before initialization
        if self.parameters and hasattr(self.plugin_instance, 'update_parameter'):
            logger.debug(f"📝 Applying pre-initialization parameters to plugin...")
            for param_name, param_value in self.parameters.items():
                if param_name != 'duration':
                    success = self.plugin_instance.update_parameter(param_name, param_value)
                    if success:
                        logger.debug(f"  ✓ {param_name} = {param_value}")
                    else:
                        logger.debug(f"  ✗ {param_name} = {param_value} (not accepted)")

        return True

    def get_next_frame(self):
        """
        Renders the next frame via WGSL shader on the GPU.
        Returns (GPUFrame, delay) when a shader is available, or a black numpy
        frame with a one-time warning for unconverted plugins.
        """
        if not self.plugin_instance:
            return None, 0

        if hasattr(self, 'current_frame') and self.current_frame >= 0:
            virtual_frame = self.current_frame
            current_time = virtual_frame / self.fps
        else:
            current_time = time.time() - self.start_time
            virtual_frame = int(current_time * self.fps)
            if self.total_frames > 0:
                virtual_frame = virtual_frame % self.total_frames
                current_time = virtual_frame / self.fps

        # ── GPU shader path ──────────────────────────────────────────────────
        shader_src = self.plugin_instance.get_shader()
        if shader_src is not None:
            uniforms = self.plugin_instance.get_uniforms(
                time=current_time,
                frame_number=virtual_frame,
                width=self.canvas_width,
                height=self.canvas_height,
            )
            try:
                from ...gpu.renderer import get_renderer
                from ...gpu.texture_pool import get_texture_pool
                dst = get_texture_pool().acquire(self.canvas_width, self.canvas_height)
                get_renderer().render(
                    wgsl_source=shader_src,
                    target=dst,
                    uniforms=uniforms,
                    textures=[],
                )
                delay = 1.0 / self.fps
                self.current_frame += 1
                return dst, delay
            except Exception as e:
                logger.error(
                    f"[GeneratorSource] GPU render failed for '{self.generator_id}': {e}"
                )
                # fall through to black frame

        # ── No GPU shader ────────────────────────────────────────────────────
        if not hasattr(self, '_warned_no_shader'):
            logger.warning(
                f"⚠️ [GeneratorSource] '{self.generator_id}' has no GPU shader "
                f"(get_shader() returned None). Implement get_shader() + get_uniforms() "
                f"for the GPU pipeline. Returning black frame."
            )
            self._warned_no_shader = True

        delay = 1.0 / self.fps
        self.current_frame += 1
        return np.zeros((self.canvas_height, self.canvas_width, 3), dtype=np.uint8), delay

    def update_parameter(self, param_name, value):
        """Aktualisiert Generator-Parameter zur Laufzeit."""
        if not self.plugin_instance:
            logger.debug(f"📝 Parameter '{param_name}' stored for initialization (plugin not ready yet)")
            self.parameters[param_name] = value
            return True

        try:
            value = float(value) if isinstance(value, (str, int, float)) else value
        except (ValueError, TypeError):
            pass

        self.parameters[param_name] = value

        if param_name == 'duration':
            self.duration = min(60, max(1, float(value)))
            self.total_frames = int(self.duration * self.fps)
            logger.debug(
                f"Generator duration updated to {self.duration}s "
                f"(total_frames={self.total_frames}, max 60s)"
            )
            return True

        if self.plugin_instance and hasattr(self.plugin_instance, 'update_parameter'):
            success = self.plugin_instance.update_parameter(param_name, value)
            if success:
                logger.debug(f"Generator parameter updated: {param_name} = {value}")
                return True
            else:
                logger.debug(f"Plugin's update_parameter returned False for: {param_name}")

        if self.plugin_instance and hasattr(self.plugin_instance, param_name):
            setattr(self.plugin_instance, param_name, value)
            logger.debug(f"Generator parameter updated (direct): {param_name} = {value}")
            return True

        logger.warning(
            f"Unknown generator parameter: {param_name} "
            f"(plugin: {self.generator_id}, has update_parameter: "
            f"{hasattr(self.plugin_instance, 'update_parameter') if self.plugin_instance else 'No instance'})"
        )
        return False

    def reset(self):
        """Setzt Generator zurück."""
        self.current_frame = 0
        self.start_time = time.time()

    def cleanup(self):
        """Cleanup für Generator."""
        if self.plugin_instance:
            if hasattr(self.plugin_instance, 'cleanup'):
                self.plugin_instance.cleanup()
            self.plugin_instance = None

    def get_source_name(self):
        if self.plugin_instance and hasattr(self.plugin_instance, 'METADATA'):
            return self.plugin_instance.METADATA.get('name', self.generator_id)
        return self.generator_id

    def get_info(self):
        info = super().get_info()
        info['type'] = 'generator'
        info['generator_id'] = self.generator_id
        info['parameters'] = self.parameters

        if self.plugin_instance and hasattr(self.plugin_instance, 'METADATA'):
            metadata = self.plugin_instance.METADATA
            info['generator_name'] = metadata.get('name', self.generator_id)
            info['description'] = metadata.get('description', '')
            info['version'] = metadata.get('version', '1.0.0')

        return info

    def is_duration_defined(self):
        """Returns True if the generator has a finite duration."""
        return self.duration > 0
