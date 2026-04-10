"""
Transition Pipeline Test -- GPU-only path
==========================================
Verifies the pure-GPU transition pipeline introduced after archiving
all CPU transition plugins.

Checks:
  1. start() requires _has_a=True (no CPU buffer fallback)
  2. apply_gpu() calls render_transition_gpu with correct progress
  3. apply_gpu() deactivates when duration expires
  4. Timer reset on frames==0 in apply_gpu
  5. configure() silently ignores legacy plugin= kwarg
  6. CPU-path methods (apply, store_frame, buffer) are removed
  7. push_frame() in glfw_display.py is NOT a no-op
  8. real render_transition_gpu (skipped if GPU unavailable)

Run with:
    python tests/test_transition_pipeline.py
"""

import os, sys, types, time, logging, importlib.util, re
import numpy as np

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)


def _install_stubs():
    import unittest.mock as mock
    if 'wgpu' not in sys.modules:
        wgpu_mod = types.ModuleType('wgpu')
        wgpu_mod.GPUDevice = type('GPUDevice', (), {})
        wgpu_mod.BufferBindingType = mock.MagicMock()
        wgpu_mod.TextureSampleType = mock.MagicMock()
        wgpu_mod.SamplerBindingType = mock.MagicMock()
        wgpu_mod.ShaderStage = mock.MagicMock()
        wgpu_mod.MapMode = mock.MagicMock()
        wgpu_mod.MapMode.READ = 1
        wgpu_mod.gpu = mock.MagicMock()
        sys.modules['wgpu'] = wgpu_mod
        sys.modules['wgpu.utils'] = types.ModuleType('wgpu.utils')
    if 'cv2' not in sys.modules:
        cv2_mod = types.ModuleType('cv2')
        cv2_mod.cvtColor = lambda src, code, dst=None: src.copy()
        cv2_mod.COLOR_BGR2RGBA = 0
        cv2_mod.resize = lambda img, sz: img
        sys.modules['cv2'] = cv2_mod
    _fake_gpu = types.ModuleType('src.modules.gpu.context')
    _fake_gpu.get_device = lambda: None
    sys.modules.setdefault('src.modules.gpu.context', _fake_gpu)
    logging.disable(logging.WARNING)


def _load_transition_manager():
    for pkg in ['src', 'src.modules', 'src.modules.player',
                'src.modules.player.transitions', 'src.modules.core', 'src.modules.gpu']:
        sys.modules.setdefault(pkg, types.ModuleType(pkg))
    def _get_logger(name): return logging.getLogger(name)
    def _debug_playback(lg, msg, *a, **kw): pass
    stub = types.ModuleType('src.modules.core.logger')
    stub.get_logger = _get_logger
    stub.debug_playback = _debug_playback
    sys.modules['src.modules.core.logger'] = stub
    path = os.path.join(WORKSPACE, 'src', 'modules', 'player', 'transitions', 'manager.py')
    spec = importlib.util.spec_from_file_location(
        'src.modules.player.transitions.manager', path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['src.modules.player.transitions.manager'] = mod
    spec.loader.exec_module(mod)
    return mod.TransitionManager


_results = []

def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    msg = f"  [{status}]  {label}"
    if detail:
        msg += "  [" + detail + "]"
    print(msg)
    _results.append((label, condition))
    return condition


# =============================================================================
# Test 1 -- start() requires GPU A-buffer
# =============================================================================

def test_start_requires_gpu_buffer():
    print("\n=== Test 1: start() requires GPU A-buffer ===")
    TM = _load_transition_manager()
    tm = TM()
    tm.configure(enabled=True, effect='fade', duration=1.0, easing='linear')

    # No renderer at all
    check("start() False when _gpu_renderer is None", tm.start("t") is False)
    check("active stays False", tm.active is False)

    class MockR:
        _has_a = False
    tm._gpu_renderer = MockR()
    check("start() False when _has_a=False", tm.start("t") is False)

    tm._gpu_renderer._has_a = True
    check("start() True when _has_a=True", tm.start("t") is True)
    check("active=True after start()", tm.active is True)
    check("frames=0 after start()", tm.frames == 0)


# =============================================================================
# Test 2 -- apply_gpu() calls render_transition_gpu with correct progress
# =============================================================================

def test_apply_gpu_calls_renderer():
    print("\n=== Test 2: apply_gpu() calls render_transition_gpu ===")
    TM = _load_transition_manager()
    sentinel = object()
    render_calls = []
    display_calls = []
    release_calls = []

    class MockR:
        _has_a = True
        def render_transition_gpu(self, wgsl, fb, uniforms):
            render_calls.append(uniforms.copy())
            return sentinel

    class MockPool:
        def release(self, f): release_calls.append(f)

    tm = TM()
    tm.configure(enabled=True, effect='fade', duration=2.0, easing='linear')
    tm._gpu_renderer = MockR()
    tm._gpu_shaders['fade'] = 'fake_wgsl'
    tm.active = True
    tm.frames = 1
    tm.start_time = time.time() - 1.0  # 1s/2s = 50%

    pool_mod = types.ModuleType('src.modules.gpu.texture_pool')
    pool_mod.get_texture_pool = lambda: MockPool()
    sys.modules['src.modules.gpu.texture_pool'] = pool_mod
    result = tm.apply_gpu(object(), lambda f: display_calls.append(f))

    check("apply_gpu() returns True while active", result is True)
    check("render_transition_gpu called once", len(render_calls) == 1)
    prog = render_calls[0].get('progress', -1)
    check("progress ~ 0.5 (linear, 1s of 2s)", abs(prog - 0.5) < 0.05,
          "progress=" + str(round(prog, 3)))
    check("display_fn called with sentinel",
          len(display_calls) == 1 and display_calls[0] is sentinel)
    check("pool.release() called on result",
          len(release_calls) == 1 and release_calls[0] is sentinel)
    check("frames incremented to 2", tm.frames == 2)


# =============================================================================
# Test 3 -- apply_gpu() deactivates when duration expires
# =============================================================================

def test_apply_gpu_deactivates():
    print("\n=== Test 3: apply_gpu() deactivates after duration ===")
    TM = _load_transition_manager()
    tm = TM()
    tm.configure(enabled=True, effect='fade', duration=1.0)
    tm._gpu_renderer = type('R', (), {'_has_a': True})()
    tm._gpu_shaders['fade'] = 'fake'
    tm.active = True
    tm.frames = 5
    tm.start_time = time.time() - 2.0  # elapsed > duration

    result = tm.apply_gpu(object(), lambda f: None)
    check("apply_gpu() returns False after duration", result is False)
    check("active=False after duration", tm.active is False)


# =============================================================================
# Test 4 -- Timer reset on frames==0
# =============================================================================

def test_timer_reset():
    print("\n=== Test 4: apply_gpu() resets timer when frames==0 ===")
    TM = _load_transition_manager()
    display_calls = []

    class MockR:
        _has_a = True
        def render_transition_gpu(self, wgsl, fb, uniforms):
            return object()

    class MockPool:
        def release(self, f): pass

    tm = TM()
    tm.configure(enabled=True, effect='fade', duration=2.0)
    tm._gpu_renderer = MockR()
    tm._gpu_shaders['fade'] = 'fake'
    tm.active = True
    tm.frames = 0
    tm.start_time = time.time() - 5.0  # stale

    pool_mod = types.ModuleType('src.modules.gpu.texture_pool')
    pool_mod.get_texture_pool = lambda: MockPool()
    sys.modules['src.modules.gpu.texture_pool'] = pool_mod
    result = tm.apply_gpu(object(), lambda f: display_calls.append(f))

    check("apply_gpu() returns True after timer reset", result is True)
    delta = abs(time.time() - tm.start_time)
    check("start_time reset to ~now (< 0.1s)", delta < 0.1, "delta=" + str(round(delta, 3)))
    check("display_fn was called", len(display_calls) > 0)


# =============================================================================
# Test 5 -- configure() silently ignores legacy plugin= kwarg
# =============================================================================

def test_configure_ignores_plugin():
    print("\n=== Test 5: configure() ignores legacy plugin= kwarg ===")
    TM = _load_transition_manager()
    tm = TM()
    try:
        tm.configure(enabled=True, effect='fade', duration=1.5,
                     easing='ease_in', plugin=object())
        check("configure(plugin=...) does not raise", True)
    except TypeError as e:
        check("configure(plugin=...) does not raise", False, str(e))
    check("plugin key absent from config", 'plugin' not in tm.config)
    check("effect set correctly", tm.config['effect'] == 'fade')
    check("duration set correctly", tm.config['duration'] == 1.5)


# =============================================================================
# Test 6 -- CPU-path methods removed
# =============================================================================

def test_cpu_methods_removed():
    print("\n=== Test 6: CPU methods / attributes are removed ===")
    TM = _load_transition_manager()
    tm = TM()
    check("apply() method removed", not hasattr(tm, 'apply'))
    check("store_frame() method removed", not hasattr(tm, 'store_frame'))
    check("buffer attribute removed", not hasattr(tm, 'buffer'))
    check("apply_gpu() present", callable(getattr(tm, 'apply_gpu', None)))
    check("store_gpu_frame() present", callable(getattr(tm, 'store_gpu_frame', None)))


# =============================================================================
# Test 7 -- push_frame() in glfw_display.py is NOT a no-op
# =============================================================================

def test_push_frame_functional():
    print("\n=== Test 7: push_frame() is functional (not a no-op) ===")
    display_path = os.path.join(WORKSPACE, 'src', 'modules', 'gpu', 'glfw_display.py')
    with open(display_path, encoding='utf-8') as f:
        src_text = f.read()
    m = re.search(r'def push_frame\(self.*?\n(.*?)(?=\n    def |\Z)', src_text, re.DOTALL)
    body = m.group(1) if m else ''
    non_trivial = [
        l for l in body.splitlines()
        if l.strip() and not l.strip().startswith('#')
        and not l.strip().startswith('"""') and l.strip() != 'pass'
    ]
    check("push_frame() has functional lines (not just pass/comments)",
          len(non_trivial) > 2, str(len(non_trivial)) + " non-trivial lines")
    check("push_frame() references _display_tex", '_display_tex' in body)
    check("push_gpu_frame references copy_texture_to_texture",
          'copy_texture_to_texture' in src_text)


# =============================================================================
# Test 8 -- real render_transition_gpu (skipped without GPU)
# =============================================================================

def test_real_gpu():
    print("\n=== Test 8: real render_transition_gpu (GPU required) ===")
    for key in list(sys.modules.keys()):
        if key.startswith('src.modules.gpu'):
            del sys.modules[key]
    try:
        from src.modules.gpu.context import get_device
        if get_device() is None:
            print("  [SKIP] GPU context unavailable")
            return
    except Exception as e:
        print("  [SKIP] GPU context unavailable: " + str(e))
        return
    try:
        from src.modules.gpu.transition_renderer import GPUTransitionRenderer
        from src.modules.gpu.renderer import load_shader
        W, H = 32, 32
        renderer = GPUTransitionRenderer(W, H)
        check("GPUTransitionRenderer created", renderer is not None)
        frame_a = np.zeros((H, W, 3), dtype=np.uint8)
        frame_a[:, :, 0] = 200
        renderer.store_frame(frame_a)
        check("_has_a=True after store_frame", renderer._has_a is True)
        wgsl = load_shader('fade_transition.wgsl')
        check("fade_transition.wgsl loaded", wgsl is not None and len(wgsl) > 0)
        result = renderer.render_transition_gpu(wgsl, renderer._buf_a, {'progress': 0.5})
        check("render_transition_gpu returns non-None", result is not None)
        if result is not None:
            from src.modules.gpu.texture_pool import get_texture_pool
            get_texture_pool().release(result)
            check("result released to pool without error", True)
    except Exception as e:
        check("real GPU test ran without error", False, str(e))


# =============================================================================
# Entry point
# =============================================================================

if __name__ == '__main__':
    _install_stubs()
    test_start_requires_gpu_buffer()
    test_apply_gpu_calls_renderer()
    test_apply_gpu_deactivates()
    test_timer_reset()
    test_configure_ignores_plugin()
    test_cpu_methods_removed()
    test_push_frame_functional()
    test_real_gpu()
    print()
    passed = sum(1 for _, ok in _results if ok)
    failed = sum(1 for _, ok in _results if not ok)
    print("=" * 50)
    print("  Results: " + str(passed) + " passed, " + str(failed) + " failed out of " + str(len(_results)) + " checks")
    if failed:
        print("\n  Failed checks:")
        for label, ok in _results:
            if not ok:
                print("    x " + label)
        sys.exit(1)
    else:
        print("  All checks passed!")