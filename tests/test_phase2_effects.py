"""
Phase 2 effect plugin tests — GPU-native plugins.

All 4 plugins (brightness_contrast, hue_rotate, colorize, transform) are
GPU-native: they always provide a GLSL shader via get_shader() and correct
uniform values via get_uniforms(). process_frame() is a passthrough stub.

Tests verify:
  - get_shader() always returns a valid GLSL string
  - get_uniforms() returns correct values for min/max/default params
  - process_frame() is a passthrough (frame returned unchanged)
  - update_parameter() correctly mutates state
"""
import sys
import os
import math
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from plugins.effects.brightness_contrast import BrightnessContrastEffect
from plugins.effects.hue_rotate import HueRotateEffect
from plugins.effects.colorize import ColorizeEffect
from plugins.effects.transform import TransformEffect

# ─── helpers ─────────────────────────────────────────────────────────────────

def grey(v):
    return np.full((64, 64, 3), v, dtype=np.uint8)


# ─── process_frame passthrough (all 4 plugins) ───────────────────────────────

def test_brightness_contrast_process_frame_is_stub():
    fx = BrightnessContrastEffect(config={'brightness': 50.0, 'contrast': 2.0})
    frame = grey(100)
    out = fx.process_frame(frame.copy())
    assert np.array_equal(out, frame), "process_frame must be a passthrough stub"
    print("  \u2713 brightness_contrast process_frame is passthrough")


def test_hue_rotate_process_frame_is_stub():
    fx = HueRotateEffect(config={'hue_shift': 90.0})
    frame = grey(128)
    out = fx.process_frame(frame.copy())
    assert np.array_equal(out, frame), "process_frame must be a passthrough stub"
    print("  \u2713 hue_rotate process_frame is passthrough")


def test_colorize_process_frame_is_stub():
    fx = ColorizeEffect(config={'color': '#ff0000', 'invert': False})
    frame = grey(128)
    out = fx.process_frame(frame.copy())
    assert np.array_equal(out, frame), "process_frame must be a passthrough stub"
    print("  \u2713 colorize process_frame is passthrough")


def test_transform_process_frame_is_stub():
    fx = TransformEffect(config={'position_x': 50.0, 'rotation_z': 45.0})
    frame = grey(128)
    out = fx.process_frame(frame.copy())
    assert np.array_equal(out, frame), "process_frame must be a passthrough stub"
    print("  \u2713 transform process_frame is passthrough")


# ─── get_shader always returns a GLSL string ─────────────────────────────────

def test_all_plugins_always_provide_shader():
    cases = [
        BrightnessContrastEffect(config={'brightness': 0.0, 'contrast': 1.0}),
        HueRotateEffect(config={'hue_shift': 0.0}),
        ColorizeEffect(config={'color': '#00ff00', 'invert': False}),
        TransformEffect(config={}),
    ]
    for fx in cases:
        src = fx.get_shader()
        assert isinstance(src, str) and len(src) > 20, \
            f"{fx.__class__.__name__}.get_shader() must always return a GLSL string"
    print("  \u2713 all 4 plugins always return a GLSL shader string")


def test_transform_3d_rotation_also_provides_shader():
    """100% GPU: even with rotation_x/Y set, a shader is returned (3D params ignored in GPU pass)."""
    fx = TransformEffect(config={'rotation_x': 45.0, 'rotation_y': 30.0})
    src = fx.get_shader()
    assert isinstance(src, str) and len(src) > 20, \
        "transform must return GPU shader even with rotation_x/Y (3D params ignored in GPU mode)"
    print("  \u2713 transform with rotation_x/Y still returns GLSL shader (no CPU fallback)")


# ─── get_uniforms correctness ─────────────────────────────────────────────────

def test_brightness_contrast_uniforms_default():
    fx = BrightnessContrastEffect(config={'brightness': 0.0, 'contrast': 1.0})
    u = fx.get_uniforms()
    assert u['brightness'] == 0.0
    assert u['contrast'] == 1.0
    print("  \u2713 brightness_contrast default uniforms correct")


def test_brightness_contrast_uniforms_values():
    fx = BrightnessContrastEffect(config={'brightness': 51.0, 'contrast': 1.5})
    u = fx.get_uniforms()
    assert abs(u['brightness'] - 51.0 / 255.0) < 1e-5
    assert u['contrast'] == 1.5
    print("  \u2713 brightness_contrast uniforms normalized correctly")


def test_hue_rotate_uniforms():
    fx = HueRotateEffect(config={'hue_shift': 90.0})
    u = fx.get_uniforms()
    assert u['hue_shift'] == 90.0
    print("  \u2713 hue_rotate uniform hue_shift=90")


def test_hue_rotate_uniforms_negative():
    fx = HueRotateEffect(config={'hue_shift': -45.0})
    u = fx.get_uniforms()
    assert u['hue_shift'] == -45.0
    print("  \u2713 hue_rotate uniform hue_shift=-45")


def test_colorize_uniforms_red():
    fx = ColorizeEffect(config={'color': '#ff0000', 'invert': False})
    u = fx.get_uniforms()
    # Red: OpenCV H~=0, S=255 -> normalized: hue~=0, sat=1
    assert u['saturation'] >= 0.95, f"Red saturation should be ~1.0, got {u['saturation']}"
    assert u['invert'] == 0
    assert u['alpha'] == 1.0   # no alpha byte -> fully opaque
    print("  \u2713 colorize uniforms for red color correct")


def test_colorize_uniforms_invert():
    fx = ColorizeEffect(config={'color': '#ff0000', 'invert': True})
    u = fx.get_uniforms()
    assert u['invert'] == 1
    print("  \u2713 colorize invert=True -> uniform 1")


def test_colorize_uniforms_alpha():
    fx = ColorizeEffect(config={'color': '#ff000080', 'invert': False})  # 50% alpha
    u = fx.get_uniforms()
    assert abs(u['alpha'] - 0x80 / 255.0) < 0.01, f"alpha uniform wrong: {u['alpha']}"
    print("  \u2713 colorize alpha from hex #rrggbbaa correct")


def test_transform_uniforms_identity():
    fx = TransformEffect(config={})
    u = fx.get_uniforms(frame_w=1920, frame_h=1080)
    assert u['scale'] == (1.0, 1.0)
    assert u['translate'] == (0.0, 0.0)
    assert abs(u['rotation']) < 1e-6
    print("  \u2713 transform identity uniforms correct")


def test_transform_uniforms_scale():
    fx = TransformEffect(config={'scale_xy': 50.0})  # 50%
    u = fx.get_uniforms(frame_w=1920, frame_h=1080)
    assert u['scale'] == (0.5, 0.5)
    print("  \u2713 transform scale_xy=50 -> uniform (0.5, 0.5)")


def test_transform_uniforms_translate():
    fx = TransformEffect(config={'position_x': 192.0, 'position_y': 108.0})
    u = fx.get_uniforms(frame_w=1920, frame_h=1080)
    assert abs(u['translate'][0] - 0.1) < 1e-5
    assert abs(u['translate'][1] - 0.1) < 1e-5
    print("  \u2713 transform translate normalized to frame size")


def test_transform_uniforms_rotation_z():
    fx = TransformEffect(config={'rotation_z': 90.0})
    u = fx.get_uniforms(frame_w=1920, frame_h=1080)
    assert abs(u['rotation'] - math.radians(90.0)) < 1e-5
    print("  \u2713 transform rotation_z=90 -> pi/2 radians")


# ─── update_parameter live mutation ──────────────────────────────────────────

def test_brightness_contrast_update_parameter():
    fx = BrightnessContrastEffect(config={'brightness': 0.0, 'contrast': 1.0})
    fx.update_parameter('brightness', 100.0)
    fx.update_parameter('contrast', 2.0)
    u = fx.get_uniforms()
    assert abs(u['brightness'] - 100.0 / 255.0) < 1e-5
    assert u['contrast'] == 2.0
    print("  \u2713 brightness_contrast update_parameter works")


def test_hue_rotate_update_parameter():
    fx = HueRotateEffect(config={'hue_shift': 0.0})
    fx.update_parameter('hue_shift', 180.0)
    assert fx.get_uniforms()['hue_shift'] == 180.0
    print("  \u2713 hue_rotate update_parameter works")


def test_colorize_update_parameter():
    fx = ColorizeEffect(config={'color': '#ff0000', 'invert': False})
    fx.update_parameter('color', '#0000ff')  # change to blue
    u = fx.get_uniforms()
    # Blue: OpenCV H~=120
    assert abs(u['hue'] - 120.0 / 180.0) < 0.05
    print("  \u2713 colorize update_parameter color change works")


# ─── runner ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    suites = [
        ("Passthrough stubs", [
            test_brightness_contrast_process_frame_is_stub,
            test_hue_rotate_process_frame_is_stub,
            test_colorize_process_frame_is_stub,
            test_transform_process_frame_is_stub,
        ]),
        ("Always-GPU shader", [
            test_all_plugins_always_provide_shader,
            test_transform_3d_rotation_also_provides_shader,
        ]),
        ("Uniforms correctness", [
            test_brightness_contrast_uniforms_default,
            test_brightness_contrast_uniforms_values,
            test_hue_rotate_uniforms,
            test_hue_rotate_uniforms_negative,
            test_colorize_uniforms_red,
            test_colorize_uniforms_invert,
            test_colorize_uniforms_alpha,
            test_transform_uniforms_identity,
            test_transform_uniforms_scale,
            test_transform_uniforms_translate,
            test_transform_uniforms_rotation_z,
        ]),
        ("Live parameter updates", [
            test_brightness_contrast_update_parameter,
            test_hue_rotate_update_parameter,
            test_colorize_update_parameter,
        ]),
    ]

    passed = failed = 0
    for suite_name, tests in suites:
        print(f"\n{'---' * 17}")
        print(f"  {suite_name}")
        print(f"{'---' * 17}")
        for t in tests:
            try:
                t()
                passed += 1
            except Exception as e:
                print(f"  x {t.__name__}: {e}")
                failed += 1

    print(f"\n{'===' * 17}")
    print(f"  {passed + failed} tests  |  {passed} passed  |  {failed} failed")
    print(f"{'===' * 17}")
    sys.exit(1 if failed else 0)
