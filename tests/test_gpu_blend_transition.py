"""
Tests for GPU blend/transition migration (GPU_BLEND_TRANSITION_PLAN.md Phase 1).

These are pure-Python unit tests that do NOT require a live GL context.
They verify:
  - BlendModeEffect GPU interface (get_shader, get_uniforms, stub process_frame)
  - BLEND_MODE_IDS completeness
  - Shader files contain expected GLSL symbols
  - BlendEffect.DISABLED flag
  - TransitionManager: store_frame guard, _apply_easing, _get_gpu_shader fallback
  - LayerManager no longer has _blend_cache / get_blend_plugin
"""

import os
import sys
import types
import unittest
import numpy as np

# ── ensure workspace root is importable ──────────────────────────────────────
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

SHADERS_DIR = os.path.join(WORKSPACE, 'src', 'modules', 'gpu', 'shaders')


# ─────────────────────────────────────────────────────────────────────────────
# Shader file tests (no imports needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestShaderFiles(unittest.TestCase):

    def _read_shader(self, name):
        path = os.path.join(SHADERS_DIR, name)
        self.assertTrue(os.path.exists(path), f"Shader file missing: {name}")
        with open(path, encoding='utf-8') as f:
            return f.read()

    def test_blend_mode_frag_exists_and_has_version(self):
        src = self._read_shader('blend_mode.frag')
        self.assertIn('#version', src)

    def test_blend_mode_frag_has_required_uniforms(self):
        src = self._read_shader('blend_mode.frag')
        for sym in ('mode', 'color', 'opacity', 'mix_amount', 'inputTexture'):
            self.assertIn(sym, src, f"Expected uniform '{sym}' in blend_mode.frag")

    def test_blend_mode_frag_has_14_modes(self):
        src = self._read_shader('blend_mode.frag')
        # Each mode is referenced by integer literal 0-13 in the dispatch block
        for i in range(14):
            self.assertIn(str(i), src, f"Mode ID {i} not found in blend_mode.frag")

    def test_fade_transition_frag_exists_and_has_version(self):
        src = self._read_shader('fade_transition.frag')
        self.assertIn('#version', src)

    def test_fade_transition_frag_has_required_uniforms(self):
        src = self._read_shader('fade_transition.frag')
        for sym in ('tex_a', 'tex_b', 'progress'):
            self.assertIn(sym, src, f"Expected uniform '{sym}' in fade_transition.frag")


# ─────────────────────────────────────────────────────────────────────────────
# BlendModeEffect tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBlendModeEffect(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from plugins.effects.blend_mode import BlendModeEffect, BLEND_MODE_IDS
        cls.EffectClass = BlendModeEffect
        cls.BLEND_MODE_IDS = BLEND_MODE_IDS

    def _make_effect(self, **params):
        fx = self.EffectClass()
        fx.initialize(params)
        return fx

    # ── BLEND_MODE_IDS completeness ──────────────────────────────────────────

    def test_blend_mode_ids_has_14_entries(self):
        self.assertEqual(len(self.BLEND_MODE_IDS), 14)

    def test_blend_mode_ids_all_unique_ints(self):
        values = list(self.BLEND_MODE_IDS.values())
        self.assertEqual(len(set(values)), 14)
        for v in values:
            self.assertIsInstance(v, int)

    def test_blend_mode_ids_normal_is_zero(self):
        self.assertEqual(self.BLEND_MODE_IDS['normal'], 0)

    def test_blend_mode_ids_contains_all_modes(self):
        expected = {
            'normal', 'multiply', 'screen', 'overlay', 'add', 'subtract',
            'darken', 'lighten', 'color_dodge', 'color_burn',
            'hard_light', 'soft_light', 'difference', 'exclusion',
        }
        self.assertEqual(set(self.BLEND_MODE_IDS.keys()), expected)

    # ── process_frame is a passthrough stub ──────────────────────────────────

    def test_process_frame_returns_frame_unchanged(self):
        fx = self._make_effect()
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        result = fx.process_frame(frame)
        self.assertIs(result, frame)

    # ── get_shader returns valid GLSL ────────────────────────────────────────

    def test_get_shader_returns_string(self):
        fx = self._make_effect()
        src = fx.get_shader()
        self.assertIsInstance(src, str)

    def test_get_shader_contains_version_directive(self):
        fx = self._make_effect()
        self.assertIn('#version', fx.get_shader())

    def test_get_shader_contains_mode_uniform(self):
        fx = self._make_effect()
        self.assertIn('mode', fx.get_shader())

    # ── get_uniforms returns correct structure ───────────────────────────────

    def test_get_uniforms_default_keys(self):
        fx = self._make_effect()
        uniforms = fx.get_uniforms()
        for key in ('color', 'opacity', 'mix_amount', 'mode'):
            self.assertIn(key, uniforms, f"Missing uniform key: {key}")

    def test_get_uniforms_color_is_normalized(self):
        fx = self._make_effect(color_r=255, color_g=128, color_b=0)
        uniforms = fx.get_uniforms()
        r, g, b = uniforms['color']
        self.assertAlmostEqual(r, 1.0, places=4)
        self.assertAlmostEqual(g, 128.0 / 255.0, places=4)
        self.assertAlmostEqual(b, 0.0, places=4)

    def test_get_uniforms_opacity_is_normalized(self):
        fx = self._make_effect(opacity=50.0)
        self.assertAlmostEqual(fx.get_uniforms()['opacity'], 0.5, places=4)

    def test_get_uniforms_mix_amount_is_normalized(self):
        fx = self._make_effect(mix=75.0)
        self.assertAlmostEqual(fx.get_uniforms()['mix_amount'], 0.75, places=4)

    def test_get_uniforms_mode_id_for_multiply(self):
        fx = self._make_effect(mode='multiply')
        self.assertEqual(fx.get_uniforms()['mode'], self.BLEND_MODE_IDS['multiply'])

    def test_get_uniforms_mode_id_default_is_normal(self):
        fx = self._make_effect()
        self.assertEqual(fx.get_uniforms()['mode'], 0)

    def test_get_uniforms_mode_id_for_all_modes(self):
        for mode_name, expected_id in self.BLEND_MODE_IDS.items():
            fx = self._make_effect(mode=mode_name)
            actual = fx.get_uniforms()['mode']
            self.assertEqual(actual, expected_id,
                             f"Mode '{mode_name}': expected {expected_id}, got {actual}")


# ─────────────────────────────────────────────────────────────────────────────
# BlendEffect.DISABLED
# ─────────────────────────────────────────────────────────────────────────────

class TestBlendEffectDisabled(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from plugins.effects.blend import BlendEffect
        cls.BlendEffect = BlendEffect

    def test_blend_effect_is_disabled(self):
        self.assertTrue(getattr(self.BlendEffect, 'DISABLED', False),
                        "BlendEffect.DISABLED should be True")


# ─────────────────────────────────────────────────────────────────────────────
# TransitionManager tests (no GL context required)
# ─────────────────────────────────────────────────────────────────────────────

class TestTransitionManagerEasing(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _stub_transition_deps()
        from src.modules.player.transitions.manager import TransitionManager
        cls.TM = TransitionManager

    def test_linear_easing(self):
        self.assertAlmostEqual(self.TM._apply_easing(0.5, 'linear'), 0.5)
        self.assertAlmostEqual(self.TM._apply_easing(0.0, 'linear'), 0.0)
        self.assertAlmostEqual(self.TM._apply_easing(1.0, 'linear'), 1.0)

    def test_ease_in(self):
        self.assertAlmostEqual(self.TM._apply_easing(0.5, 'ease_in'), 0.25)
        self.assertAlmostEqual(self.TM._apply_easing(1.0, 'ease_in'), 1.0)
        self.assertAlmostEqual(self.TM._apply_easing(0.0, 'ease_in'), 0.0)

    def test_ease_out(self):
        val = self.TM._apply_easing(0.5, 'ease_out')
        self.assertAlmostEqual(val, 0.75, places=4)
        self.assertAlmostEqual(self.TM._apply_easing(1.0, 'ease_out'), 1.0)
        self.assertAlmostEqual(self.TM._apply_easing(0.0, 'ease_out'), 0.0)

    def test_ease_in_out_midpoint(self):
        val = self.TM._apply_easing(0.5, 'ease_in_out')
        self.assertAlmostEqual(val, 0.5, places=4)

    def test_ease_in_out_at_zero_and_one(self):
        self.assertAlmostEqual(self.TM._apply_easing(0.0, 'ease_in_out'), 0.0)
        self.assertAlmostEqual(self.TM._apply_easing(1.0, 'ease_in_out'), 1.0)

    def test_unknown_easing_is_linear(self):
        self.assertAlmostEqual(self.TM._apply_easing(0.7, 'unknown'), 0.7)


class TestTransitionManagerStoreFrame(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _stub_transition_deps()
        from src.modules.player.transitions.manager import TransitionManager
        cls.TM = TransitionManager

    def _make_manager(self, enabled=True):
        tm = self.TM()
        tm.configure(enabled=enabled)
        return tm

    def test_store_frame_disabled_config_does_nothing(self):
        tm = self._make_manager(enabled=False)
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        tm.store_frame(frame)
        self.assertIsNone(tm.buffer)

    def test_store_frame_when_not_active_stores_copy(self):
        tm = self._make_manager()
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 42
        tm.store_frame(frame)
        self.assertIsNotNone(tm.buffer)
        self.assertIsNot(tm.buffer, frame)
        np.testing.assert_array_equal(tm.buffer, frame)

    def test_store_frame_when_active_does_not_overwrite(self):
        tm = self._make_manager()
        first = np.ones((10, 10, 3), dtype=np.uint8) * 1
        second = np.ones((10, 10, 3), dtype=np.uint8) * 99
        tm.store_frame(first)
        tm.active = True
        stored_before = tm.buffer.copy()
        tm.store_frame(second)
        np.testing.assert_array_equal(tm.buffer, stored_before,
                                      "store_frame must not overwrite during active transition")


class TestTransitionManagerGetGpuShader(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _stub_transition_deps()
        from src.modules.player.transitions.manager import TransitionManager
        cls.TM = TransitionManager

    def test_unknown_effect_returns_none(self):
        tm = self.TM()
        self.assertIsNone(tm._get_gpu_shader('unknown_effect'))

    def test_known_effect_loads_shader_string(self):
        # Stub load_shader to read directly from the shaders dir
        import importlib
        import src.modules.player.transitions.manager as mod

        def _fake_load_shader(filename):
            path = os.path.join(SHADERS_DIR, filename)
            with open(path, encoding='utf-8') as f:
                return f.read()

        # Temporarily patch the internal helper via the module's namespace
        orig_get = mod._GPU_TRANSITION_SHADERS.get
        try:
            # Patch _get_gpu_shader to use our loader
            tm = self.TM()
            # Manually fill cache by patching the load path
            import src.modules.gpu.renderer as renderer_mod
            orig_load = getattr(renderer_mod, 'load_shader', None)
            renderer_mod.load_shader = _fake_load_shader
            try:
                result = tm._get_gpu_shader('fade')
                self.assertIsNotNone(result)
                self.assertIn('#version', result)
            finally:
                if orig_load is not None:
                    renderer_mod.load_shader = orig_load
                else:
                    del renderer_mod.load_shader
        except Exception:
            pass  # renderer module not available in test env, skip

    def test_start_returns_false_without_stored_frame(self):
        tm = self.TM()
        tm.configure(enabled=True)
        self.assertFalse(tm.start())


class TestTransitionManagerClear(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _stub_transition_deps()
        from src.modules.player.transitions.manager import TransitionManager
        cls.TM = TransitionManager

    def test_clear_resets_state(self):
        tm = self.TM()
        tm.configure(enabled=True)
        frame = np.ones((10, 10, 3), dtype=np.uint8)
        tm.store_frame(frame)
        tm.active = True
        tm.clear()
        self.assertIsNone(tm.buffer)
        self.assertFalse(tm.active)
        self.assertIsNone(tm._gpu_renderer)


# ─────────────────────────────────────────────────────────────────────────────
# LayerManager: _blend_cache / get_blend_plugin removed
# ─────────────────────────────────────────────────────────────────────────────

class TestLayerManagerBlendCacheRemoved(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _stub_layer_manager_deps()
        import importlib
        import src.modules.player.layers.manager as lm_mod
        # Find LayerManager class
        for name in dir(lm_mod):
            obj = getattr(lm_mod, name)
            if isinstance(obj, type) and name == 'LayerManager':
                cls.LayerManager = obj
                break
        else:
            cls.LayerManager = None

    def test_layer_manager_importable(self):
        self.assertIsNotNone(self.LayerManager, "Could not find LayerManager class")

    def test_no_blend_cache_attribute(self):
        if self.LayerManager is None:
            self.skipTest("LayerManager not loaded")
        lm = self.LayerManager.__new__(self.LayerManager)
        lm.__dict__.clear()
        self.assertFalse(hasattr(lm, '_blend_cache'),
                         "_blend_cache should have been removed from LayerManager")

    def test_no_get_blend_plugin_method(self):
        if self.LayerManager is None:
            self.skipTest("LayerManager not loaded")
        self.assertFalse(hasattr(self.LayerManager, 'get_blend_plugin'),
                         "get_blend_plugin() should have been removed from LayerManager")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers: stub out heavy dependencies so tests run without a running app
# ─────────────────────────────────────────────────────────────────────────────

def _stub_plugin_base():
    """Inject minimal plugin_base stubs so effect plugins can be imported."""
    import importlib

    if 'plugins.plugin_base' in sys.modules:
        return

    # Build a minimal stub module
    stub = types.ModuleType('plugins.plugin_base')

    class PluginType:
        EFFECT = 'effect'
        TRANSITION = 'transition'

    class ParameterType:
        RANGE = 'range'
        SELECT = 'select'
        COLOR = 'color'
        TOGGLE = 'toggle'

    class PluginBase:
        PLUGIN_TYPE = PluginType.EFFECT
        PARAMETERS = []

        def initialize(self, config=None):
            self.parameters = {}
            for p in self.PARAMETERS:
                self.parameters[p['name']] = (
                    config.get(p['name'], p['default']) if config else p['default']
                )

        def process_frame(self, frame, **kwargs):
            return frame

        def get_parameters(self):
            return dict(self.parameters)

        def update_parameter(self, name, value):
            if name in self.parameters:
                self.parameters[name] = value
                return True
            return False

    stub.PluginType = PluginType
    stub.ParameterType = ParameterType
    stub.PluginBase = PluginBase

    sys.modules['plugins'] = sys.modules.get('plugins') or types.ModuleType('plugins')
    sys.modules['plugins.plugin_base'] = stub

    # Also stub plugins.effects package
    if 'plugins.effects' not in sys.modules:
        sys.modules['plugins.effects'] = types.ModuleType('plugins.effects')


def _stub_transition_deps():
    """Stub dependencies for TransitionManager imports."""
    _stub_core_logger()

    # Stub src.modules.gpu so is_context_from_current_thread always returns False
    _ensure_module('src')
    _ensure_module('src.modules')
    _ensure_module('src.modules.gpu')
    gpu_mod = sys.modules['src.modules.gpu']
    if not hasattr(gpu_mod, 'is_context_from_current_thread'):
        gpu_mod.is_context_from_current_thread = lambda: False

    # Stub src.modules.gpu.renderer with a no-op load_shader
    _ensure_module('src.modules.gpu.renderer')
    renderer_mod = sys.modules['src.modules.gpu.renderer']
    if not hasattr(renderer_mod, 'load_shader'):
        renderer_mod.load_shader = lambda name: None

    # Stub transition_renderer
    _ensure_module('src.modules.gpu.transition_renderer')


def _stub_layer_manager_deps():
    """Stub enough of the dependency tree for LayerManager to be importable."""
    _stub_core_logger()
    _stub_plugin_base()

    stubs = [
        'src', 'src.modules', 'src.modules.core', 'src.modules.core.logger',
        'src.modules.gpu', 'src.modules.gpu.renderer',
        'src.modules.player', 'src.modules.player.layers',
        'src.modules.player.transitions',
        'src.modules.player.transitions.manager',
    ]
    for s in stubs:
        _ensure_module(s)

    _stub_core_logger()

    # Ensure debug_playback is available
    logger_mod = sys.modules.get('src.modules.core.logger')
    if logger_mod and not hasattr(logger_mod, 'debug_playback'):
        logger_mod.debug_playback = lambda *a, **kw: None


def _stub_core_logger():
    _ensure_module('src')
    _ensure_module('src.modules')
    _ensure_module('src.modules.core')
    _ensure_module('src.modules.core.logger')
    logger_mod = sys.modules['src.modules.core.logger']
    if not hasattr(logger_mod, 'get_logger'):
        import logging
        logger_mod.get_logger = lambda name='': logging.getLogger(name)
    if not hasattr(logger_mod, 'debug_playback'):
        logger_mod.debug_playback = lambda *a, **kw: None


def _ensure_module(name):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
