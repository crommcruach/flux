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
    print("  ✓ brightness_contrast process_frame is passthrough")


def test_hue_rotate_process_frame_is_stub():
    fx = HueRotateEffect(config={'hue_shift': 90.0})
    frame = grey(128)
    out = fx.process_frame(frame.copy())
    assert np.array_equal(out, frame), "process_frame must be a passthrough stub"
    print("  ✓ hue_rotate process_frame is passthrough")


def test_colorize_process_frame_is_stub():
    fx = ColorizeEffect(config={'color': '#ff0000', 'invert': False})
    frame = grey(128)
    out = fx.process_frame(frame.copy())
    assert np.array_equal(out, frame), "process_frame must be a passthrough stub"
    print("  ✓ colorize process_frame is passthrough")


def test_transform_process_frame_is_stub():
    fx = TransformEffect(config={'position_x': 50.0, 'rotation_z': 45.0})
    frame = grey(128)
    out = fx.process_frame(frame.copy())
    assert np.array_equal(out, frame), "process_frame must be a passthrough stub"
    print("  ✓ transform process_frame is passthrough")


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
    print("  ✓ all 4 plugins always return a GLSL shader string")


def test_transform_3d_rotation_also_provides_shader():
    """100% GPU: even with rotation_x/Y set, a shader is returned (3D params ignored in GPU pass)."""
    fx = TransformEffect(config={'rotation_x': 45.0, 'rotation_y': 30.0})
    src = fx.get_shader()
    assert isinstance(src, str) and len(src) > 20, \
        "transform must return GPU shader even with rotation_x/Y (3D params ignored in GPU mode)"
    print("  ✓ transform with rotation_x/Y still returns GLSL shader (no CPU fallback)")


# ─── get_uniforms correctness ─────────────────────────────────────────────────

def test_brightness_contrast_uniforms_default():
    fx = BrightnessContrastEffect(config={'brightness': 0.0, 'contrast': 1.0})
    u = fx.get_uniforms()
    assert u['brightness'] == 0.0
    assert u['contrast'] == 1.0
    print("  ✓ brightness_contrast default uniforms correct")


def test_brightness_contrast_uniforms_values():
    fx = BrightnessContrastEffect(config={'brightness': 51.0, 'contrast': 1.5})
    u = fx.get_uniforms()
    assert abs(u['brightness'] - 51.0 / 255.0) < 1e-5
    assert u['contrast'] == 1.5
    print("  ✓ brightness_contrast uniforms normalized correctly")


def test_hue_rotate_uniforms():
    fx = HueRotateEffect(config={'hue_shift': 90.0})
    u = fx.get_uniforms()
    assert u['hue_shift'] == 90.0
    print("  ✓ hue_rotate uniform hue_shift=90")


def test_hue_rotate_uniforms_negative():
    fx = HueRotateEffect(config={'hue_shift': -45.0})
    u = fx.get_uniforms()
    assert u['hue_shift'] == -45.0
    print("  ✓ hue_rotate uniform hue_shift=-45")


def test_colorize_uniforms_red():
    fx = ColorizeEffect(config={'color': '#ff0000', 'invert': False})
    u = fx.get_uniforms()
    # Red: OpenCV H≈0, S=255 → normalized: hue≈0, sat=1
    assert u['saturation'] >= 0.95, f"Red saturation should be ~1.0, got {u['saturation']}"
    assert u['invert'] == 0
    assert u['alpha'] == 1.0   # no alpha byte → fully opaque
    print("  ✓ colorize uniforms for red color correct")


def test_colorize_uniforms_invert():
    fx = ColorizeEffect(config={'color': '#ff0000', 'invert': True})
    u = fx.get_uniforms()
    assert u['invert'] == 1
    print("  ✓ colorize invert=True → uniform 1")


def test_colorize_uniforms_alpha():
    fx = ColorizeEffect(config={'color': '#ff000080', 'invert': False})  # 50% alpha
    u = fx.get_uniforms()
    assert abs(u['alpha'] - 0x80 / 255.0) < 0.01, f"alpha uniform wrong: {u['alpha']}"
    print("  ✓ colorize alpha from hex #rrggbbaa correct")


def test_transform_uniforms_identity():
    fx = TransformEffect(config={})
    u = fx.get_uniforms(frame_w=1920, frame_h=1080)
    assert u['scale'] == (1.0, 1.0)
    assert u['translate'] == (0.0, 0.0)
    assert abs(u['rotation']) < 1e-6
    print("  ✓ transform identity uniforms correct")


def test_transform_uniforms_scale():
    fx = TransformEffect(config={'scale_xy': 50.0})  # 50%
    u = fx.get_uniforms(frame_w=1920, frame_h=1080)
    assert u['scale'] == (0.5, 0.5)
    print("  ✓ transform scale_xy=50 → uniform (0.5, 0.5)")


def test_transform_uniforms_translate():
    fx = TransformEffect(config={'position_x': 192.0, 'position_y': 108.0})
    u = fx.get_uniforms(frame_w=1920, frame_h=1080)
    assert abs(u['translate'][0] - 0.1) < 1e-5
    assert abs(u['translate'][1] - 0.1) < 1e-5
    print("  ✓ transform translate normalized to frame size")


def test_transform_uniforms_rotation_z():
    fx = TransformEffect(config={'rotation_z': 90.0})
    u = fx.get_uniforms(frame_w=1920, frame_h=1080)
    assert abs(u['rotation'] - math.radians(90.0)) < 1e-5
    print("  ✓ transform rotation_z=90° → π/2 radians")


# ─── update_parameter live mutation ──────────────────────────────────────────

def test_brightness_contrast_update_parameter():
    fx = BrightnessContrastEffect(config={'brightness': 0.0, 'contrast': 1.0})
    fx.update_parameter('brightness', 100.0)
    fx.update_parameter('contrast', 2.0)
    u = fx.get_uniforms()
    assert abs(u['brightness'] - 100.0 / 255.0) < 1e-5
    assert u['contrast'] == 2.0
    print("  ✓ brightness_contrast update_parameter works")


def test_hue_rotate_update_parameter():
    fx = HueRotateEffect(config={'hue_shift': 0.0})
    fx.update_parameter('hue_shift', 180.0)
    assert fx.get_uniforms()['hue_shift'] == 180.0
    print("  ✓ hue_rotate update_parameter works")


def test_colorize_update_parameter():
    fx = ColorizeEffect(config={'color': '#ff0000', 'invert': False})
    fx.update_parameter('color', '#0000ff')  # change to blue
    u = fx.get_uniforms()
    # Blue: OpenCV H≈120
    assert abs(u['hue'] - 120.0 / 180.0) < 0.05
    print("  ✓ colorize update_parameter color change works")


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
        print(f"\n{'─'*50}")
        print(f"  {suite_name}")
        print(f"{'─'*50}")
        for t in tests:
            try:
                t()
                passed += 1
            except Exception as e:
                print(f"  ✗ {t.__name__}: {e}")
                failed += 1

    print(f"\n{'═'*50}")
    print(f"  {passed + failed} tests  |  {passed} passed  |  {failed} failed")
    print(f"{'═'*50}")
    sys.exit(1 if failed else 0)

import sys
import os
import numpy as np
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from plugins.effects.brightness_contrast import BrightnessContrastEffect
from plugins.effects.hue_rotate import HueRotateEffect
from plugins.effects.colorize import ColorizeEffect
from plugins.effects.transform import TransformEffect

# ─── helpers ─────────────────────────────────────────────────────────────────

def grey(v):
    """Pure grey frame, BGR."""
    return np.full((64, 64, 3), v, dtype=np.uint8)


def solid(b, g, r):
    """Solid-color BGR frame."""
    f = np.zeros((64, 64, 3), dtype=np.uint8)
    f[:, :] = [b, g, r]
    return f


def quadrants():
    """200×200 frame with 4 colored quadrants."""
    f = np.zeros((200, 200, 3), dtype=np.uint8)
    f[:100, :100] = [0, 0, 255]    # red   top-left    (BGR)
    f[:100, 100:] = [0, 255, 0]    # green top-right
    f[100:, :100] = [255, 0, 0]    # blue  bottom-left
    f[100:, 100:] = [0, 255, 255]  # yellow bottom-right
    return f


# ─── BrightnessContrast ──────────────────────────────────────────────────────

def test_brightness_no_op():
    fx = BrightnessContrastEffect(config={'brightness': 0.0, 'contrast': 1.0})
    frame = grey(100)
    out = fx.process_frame(frame.copy())
    assert np.array_equal(out, frame), "Identity: output must equal input"
    print("  ✓ brightness/contrast identity")


def test_brightness_increase():
    fx = BrightnessContrastEffect(config={'brightness': 50.0, 'contrast': 1.0})
    frame = grey(100)
    out = fx.process_frame(frame.copy())
    assert np.all(out == 150), f"Expected 150, got {out[0,0]}"
    print("  ✓ brightness +50 → 150")


def test_brightness_clamps_at_255():
    fx = BrightnessContrastEffect(config={'brightness': 100.0, 'contrast': 1.0})
    frame = grey(200)
    out = fx.process_frame(frame.copy())
    assert np.all(out == 255), "Should clamp at 255"
    print("  ✓ brightness clamp at 255")


def test_contrast_doubles():
    fx = BrightnessContrastEffect(config={'brightness': 0.0, 'contrast': 2.0})
    frame = grey(50)
    out = fx.process_frame(frame.copy())
    assert np.all(out == 100), f"Expected 100, got {out[0,0]}"
    print("  ✓ contrast ×2 → 100")


def test_brightness_decrease():
    fx = BrightnessContrastEffect(config={'brightness': -50.0, 'contrast': 1.0})
    frame = grey(100)
    out = fx.process_frame(frame.copy())
    assert np.all(out == 50), f"Expected 50, got {out[0,0]}"
    print("  ✓ brightness -50 → 50")


# ─── HueRotate ───────────────────────────────────────────────────────────────

def test_hue_rotate_zero_noop():
    fx = HueRotateEffect(config={'hue_shift': 0.0})
    frame = solid(0, 0, 255)  # pure red in BGR
    out = fx.process_frame(frame.copy())
    assert np.array_equal(out, frame), "0° shift should be identity"
    print("  ✓ hue rotate 0° = no-op")


def test_hue_rotate_changes_color():
    fx = HueRotateEffect(config={'hue_shift': 120.0})
    frame = solid(0, 0, 255)  # red
    out = fx.process_frame(frame.copy())
    # After 120° shift red→green (approx).  Just verify it has changed.
    assert not np.array_equal(out, frame), "120° shift should change color"
    print("  ✓ hue rotate 120° changes pixel values")


def test_hue_rotate_full_circle():
    fx = HueRotateEffect(config={'hue_shift': 360.0})
    frame = solid(0, 128, 255)  # orange-ish
    out = fx.process_frame(frame.copy())
    # 360° = full circle; allow ±2 for rounding
    diff = np.abs(out.astype(int) - frame.astype(int))
    assert diff.max() <= 2, f"360° should return to original, max diff={diff.max()}"
    print("  ✓ hue rotate 360° ≈ original (±2 rounding)")


def test_hue_rotate_preserves_grey():
    fx = HueRotateEffect(config={'hue_shift': 90.0})
    frame = grey(128)   # grey has no hue — shift should be a no-op
    out = fx.process_frame(frame.copy())
    diff = np.abs(out.astype(int) - frame.astype(int))
    assert diff.max() <= 2, f"Grey pixel hue shift should be no-op, max diff={diff.max()}"
    print("  ✓ hue rotate on grey = no-op (±2 rounding)")


# ─── Colorize ────────────────────────────────────────────────────────────────

def test_colorize_changes_color():
    # Red color (#ff0000) applied to grey → should produce a reddish tint
    fx = ColorizeEffect(config={'color': '#ff0000', 'invert': False})
    frame = grey(128)
    out = fx.process_frame(frame.copy())
    assert not np.array_equal(out, frame), "Colorize should change grey frame"
    print("  ✓ colorize changes a grey frame")


def test_colorize_invert():
    fx_normal = ColorizeEffect(config={'color': '#00ff00', 'invert': False})
    fx_invert = ColorizeEffect(config={'color': '#00ff00', 'invert': True})
    frame = grey(128)
    out_n = fx_normal.process_frame(frame.copy())
    out_i = fx_invert.process_frame(frame.copy())
    assert not np.array_equal(out_n, out_i), "Invert flag should change output"
    print("  ✓ colorize invert produces different result")


def test_colorize_zero_saturation_preserves_brightness():
    """Grey color (#808080) has saturation=0 → output should stay grey."""
    fx = ColorizeEffect(config={'color': '#808080', 'invert': False})
    frame = grey(100)
    out = fx.process_frame(frame.copy())
    # Saturation forced to 0 → all channels equal (grey)
    channel_spread = int(out[0, 0].max()) - int(out[0, 0].min())
    assert channel_spread <= 5, f"Saturation 0 should give grey output, spread={channel_spread}"
    print("  ✓ colorize saturation=0 (grey color) → grey output")


# ─── Transform ───────────────────────────────────────────────────────────────

def test_transform_identity():
    fx = TransformEffect(config={})
    frame = quadrants()
    out = fx.process_frame(frame.copy())
    assert np.array_equal(out, frame), "Default transform should be identity"
    print("  ✓ transform identity")


def test_transform_shift_x():
    fx = TransformEffect(config={'position_x': 50.0})
    frame = quadrants()
    out = fx.process_frame(frame.copy())
    # Left 50 pixels should be black (shifted out)
    assert np.all(out[:, :50] == 0), "Left strip should be black after +X shift"
    print("  ✓ transform position_x +50 → left strip black")


def test_transform_shift_y():
    fx = TransformEffect(config={'position_y': 50.0})
    frame = quadrants()
    out = fx.process_frame(frame.copy())
    assert np.all(out[:50, :] == 0), "Top strip should be black after +Y shift"
    print("  ✓ transform position_y +50 → top strip black")


def test_transform_scale_half():
    fx = TransformEffect(config={'scale_xy': 50.0})   # 50% size
    frame = quadrants()
    out = fx.process_frame(frame.copy())
    assert out.shape == frame.shape, "Shape must be preserved"
    # Scaled-down image → outer border should be black
    assert np.all(out[:, -10:] == 0), "Right border should be black at 50% scale"
    print("  ✓ transform scale 50% → outer border black")


def test_transform_rotation_z():
    fx = TransformEffect(config={'rotation_z': 45.0})
    frame = quadrants()
    out = fx.process_frame(frame.copy())
    assert out.shape == frame.shape, "Shape must be preserved"
    # Rotated image differs from original
    assert not np.array_equal(out, frame), "45° rotation should change frame"
    print("  ✓ transform rotation_z 45° changes frame")


def test_transform_output_dtype():
    fx = TransformEffect(config={'position_x': 10.0, 'rotation_z': 15.0})
    frame = quadrants()
    out = fx.process_frame(frame.copy())
    assert out.dtype == np.uint8, f"Output dtype must be uint8, got {out.dtype}"
    print("  ✓ transform output dtype = uint8")


# ─── get_uniforms sanity ─────────────────────────────────────────────────────

def test_get_uniforms_brightness_contrast():
    fx = BrightnessContrastEffect(config={'brightness': 51.0, 'contrast': 1.5})
    u = fx.get_uniforms()
    assert abs(u['brightness'] - 51.0/255.0) < 1e-5
    assert u['contrast'] == 1.5
    print("  ✓ brightness_contrast get_uniforms values correct")


def test_get_uniforms_hue_rotate():
    fx = HueRotateEffect(config={'hue_shift': 90.0})
    u = fx.get_uniforms()
    assert u['hue_shift'] == 90.0
    print("  ✓ hue_rotate get_uniforms values correct")


def test_get_shader_returns_string():
    for cls, cfg in [
        (BrightnessContrastEffect, {'brightness': 0.0, 'contrast': 1.0}),
        (HueRotateEffect, {'hue_shift': 0.0}),
        (ColorizeEffect, {'hue': 0, 'saturation': 0, 'invert': False}),
    ]:
        fx = cls(config=cfg)
        src = fx.get_shader()
        assert isinstance(src, str) and len(src) > 20, f"{cls.__name__}.get_shader() must return shader string"
    print("  ✓ get_shader() returns GLSL string for all 3 plugins")


def test_transform_get_shader_2d_returns_string():
    fx = TransformEffect(config={})
    src = fx.get_shader()
    assert isinstance(src, str) and len(src) > 20
    print("  ✓ transform get_shader() (2D) returns GLSL string")


def test_transform_get_shader_3d_returns_none():
    fx = TransformEffect(config={'rotation_x': 45.0})
    src = fx.get_shader()
    assert src is None, "3D rotation should return None (not GPU-implemented)"
    print("  ✓ transform get_shader() with rotation_x → None (CPU fallback)")


# ─── runner ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    suites = [
        ("BrightnessContrast", [
            test_brightness_no_op,
            test_brightness_increase,
            test_brightness_clamps_at_255,
            test_contrast_doubles,
            test_brightness_decrease,
        ]),
        ("HueRotate", [
            test_hue_rotate_zero_noop,
            test_hue_rotate_changes_color,
            test_hue_rotate_full_circle,
            test_hue_rotate_preserves_grey,
        ]),
        ("Colorize", [
            test_colorize_changes_color,
            test_colorize_invert,
            test_colorize_zero_saturation_preserves_brightness,
        ]),
        ("Transform", [
            test_transform_identity,
            test_transform_shift_x,
            test_transform_shift_y,
            test_transform_scale_half,
            test_transform_rotation_z,
            test_transform_output_dtype,
        ]),
        ("GPU interface", [
            test_get_uniforms_brightness_contrast,
            test_get_uniforms_hue_rotate,
            test_get_shader_returns_string,
            test_transform_get_shader_2d_returns_string,
            test_transform_get_shader_3d_returns_none,
        ]),
    ]

    passed = failed = 0
    for suite_name, tests in suites:
        print(f"\n{'─'*50}")
        print(f"  {suite_name}")
        print(f"{'─'*50}")
        for t in tests:
            try:
                t()
                passed += 1
            except Exception as e:
                print(f"  ✗ {t.__name__}: {e}")
                failed += 1

    print(f"\n{'═'*50}")
    print(f"  {passed + failed} tests  |  {passed} passed  |  {failed} failed")
    print(f"{'═'*50}")
    sys.exit(1 if failed else 0)
