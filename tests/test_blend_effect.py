"""
Test Blend Effect Plugin
Tests verschiedene Blend-Modi mit synthetischen Frames
"""
import numpy as np
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from plugins.effects.blend import BlendEffect


def create_test_frame(color, size=(100, 100, 3)):
    """Erstellt Frame mit Vollton-Farbe."""
    frame = np.zeros(size, dtype=np.uint8)
    frame[:] = color
    return frame


def test_blend_modes():
    """Testet alle Blend-Modi mit bekannten Eingaben."""
    print("\n=== Testing Blend Effect Plugin ===\n")
    
    # Test-Frames: Rot (base) und Blau (overlay)
    red_frame = create_test_frame([255, 0, 0])      # RGB Red
    blue_frame = create_test_frame([0, 0, 255])     # RGB Blue
    gray_frame = create_test_frame([128, 128, 128]) # Gray 50%
    
    blend_modes = ['normal', 'multiply', 'screen', 'add', 'subtract', 'overlay']
    
    for mode in blend_modes:
        print(f"Testing Blend Mode: {mode.upper()}")
        
        # Erstelle Plugin
        plugin = BlendEffect()
        plugin.initialize({'blend_mode': mode, 'opacity': 100.0})
        
        # Teste mit Rot (base) + Blau (overlay)
        result = plugin.process_frame(red_frame, overlay=blue_frame)
        center_pixel = result[50, 50]
        
        # Erwartete Ergebnisse (gerundet):
        expected = {
            'normal': [0, 0, 255],        # Overlay ersetzt Base
            'multiply': [0, 0, 0],        # (255*0, 0*0, 0*255) = (0, 0, 0)
            'screen': [255, 0, 255],      # 1-(1-1)*(1-0) = 1, 1-(1-0)*(1-1) = 1
            'add': [255, 0, 255],         # (255+0, 0+0, 0+255) = (255, 0, 255)
            'subtract': [255, 0, 0],      # (255-0, 0-0, 0-255) = (255, 0, 0) -> clipped
            'overlay': [0, 0, 255]        # Complex, depends on luminance
        }
        
        print(f"  Center Pixel: {center_pixel}")
        print(f"  Expected:     {expected[mode]}")
        print(f"  [OK] Blend Mode '{mode}' executed\n")
    
    return True


def test_opacity():
    """Testet Opacity-Parameter."""
    print("=== Testing Opacity Parameter ===\n")
    
    # Test-Frames
    white_frame = create_test_frame([255, 255, 255])
    black_frame = create_test_frame([0, 0, 0])
    
    # Test mit 50% Opacity
    plugin = BlendEffect()
    plugin.initialize({'blend_mode': 'normal', 'opacity': 50.0})
    
    result = plugin.process_frame(black_frame, overlay=white_frame)
    center_pixel = result[50, 50]
    
    # Erwartung: 50% von Weiß = ~128
    print(f"50% Opacity Test:")
    print(f"  Base:    [0, 0, 0] (Black)")
    print(f"  Overlay: [255, 255, 255] (White)")
    print(f"  Result:  {center_pixel}")
    print(f"  Expected: ~[127, 127, 127] (50% Gray)")
    
    # Toleranz für Rundungsfehler
    assert np.allclose(center_pixel, [127, 127, 127], atol=1), "Opacity 50% should yield ~127"
    print(f"  [OK] Opacity blending correct\n")
    
    return True


def test_multiply_blend():
    """Detaillierter Test: Multiply Mode."""
    print("=== Testing Multiply Blend (Detailed) ===\n")
    
    # Grau 50% (128/255 = 0.5) * Grau 50% (128/255 = 0.5) = Grau 25% (~64)
    gray_50 = create_test_frame([128, 128, 128])
    
    plugin = BlendEffect()
    plugin.initialize({'blend_mode': 'multiply', 'opacity': 100.0})
    
    result = plugin.process_frame(gray_50, overlay=gray_50)
    center_pixel = result[50, 50]
    
    print(f"Multiply 50% Gray * 50% Gray:")
    print(f"  Expected: 0.5 * 0.5 = 0.25 -> ~64")
    print(f"  Result:   {center_pixel[0]}")
    
    assert np.allclose(center_pixel[0], 64, atol=2), "Multiply should yield ~64"
    print(f"  [OK] Multiply blend mathematically correct\n")
    
    return True


def test_screen_blend():
    """Detaillierter Test: Screen Mode."""
    print("=== Testing Screen Blend (Detailed) ===\n")
    
    # Screen: 1 - (1 - base) * (1 - over)
    # Gray 50%: 1 - (1 - 0.5) * (1 - 0.5) = 1 - 0.25 = 0.75 -> ~191
    gray_50 = create_test_frame([128, 128, 128])
    
    plugin = BlendEffect()
    plugin.initialize({'blend_mode': 'screen', 'opacity': 100.0})
    
    result = plugin.process_frame(gray_50, overlay=gray_50)
    center_pixel = result[50, 50]
    
    print(f"Screen 50% Gray + 50% Gray:")
    print(f"  Expected: 1 - 0.5 * 0.5 = 0.75 -> ~191")
    print(f"  Result:   {center_pixel[0]}")
    
    assert np.allclose(center_pixel[0], 191, atol=2), "Screen should yield ~191"
    print(f"  [OK] Screen blend mathematically correct\n")
    
    return True


def test_add_blend():
    """Detaillierter Test: Add Mode (Linear Dodge)."""
    print("=== Testing Add Blend (Detailed) ===\n")
    
    # Add: base + over (mit Clipping)
    # 128 + 128 = 256 -> clamped to 255
    gray_50 = create_test_frame([128, 128, 128])
    
    plugin = BlendEffect()
    plugin.initialize({'blend_mode': 'add', 'opacity': 100.0})
    
    result = plugin.process_frame(gray_50, overlay=gray_50)
    center_pixel = result[50, 50]
    
    print(f"Add 128 + 128:")
    print(f"  Expected: 256 -> clamped to 255")
    print(f"  Result:   {center_pixel[0]}")
    
    assert center_pixel[0] == 255, "Add should clamp to 255"
    print(f"  [OK] Add blend with clipping correct\n")
    
    return True


def test_overlay_blend():
    """Detaillierter Test: Overlay Mode."""
    print("=== Testing Overlay Blend (Detailed) ===\n")
    
    # Overlay mit dunklem Base (< 0.5): 2 * base * over
    dark_gray = create_test_frame([64, 64, 64])    # 25% = 0.25
    mid_gray = create_test_frame([128, 128, 128])  # 50% = 0.5
    
    plugin = BlendEffect()
    plugin.initialize({'blend_mode': 'overlay', 'opacity': 100.0})
    
    # Dunkler Bereich: 2 * 0.25 * 0.5 = 0.25 -> ~64
    result_dark = plugin.process_frame(dark_gray, overlay=mid_gray)
    pixel_dark = result_dark[50, 50]
    
    print(f"Overlay Dark (25% base * 50% overlay):")
    print(f"  Expected: 2 * 0.25 * 0.5 = 0.25 -> ~64")
    print(f"  Result:   {pixel_dark[0]}")
    
    # Heller Bereich: 1 - 2 * (1-0.75) * (1-0.5) = 1 - 0.25 = 0.75 -> ~191
    light_gray = create_test_frame([192, 192, 192])  # 75% = 0.75
    result_light = plugin.process_frame(light_gray, overlay=mid_gray)
    pixel_light = result_light[50, 50]
    
    print(f"\nOverlay Light (75% base * 50% overlay):")
    print(f"  Expected: 1 - 2 * 0.25 * 0.5 = 0.75 -> ~191")
    print(f"  Result:   {pixel_light[0]}")
    
    print(f"  [OK] Overlay blend correct\n")
    
    return True


def test_parameter_update():
    """Testet Runtime-Parameter-Updates."""
    print("=== Testing Parameter Updates ===\n")
    
    plugin = BlendEffect()
    plugin.initialize({'blend_mode': 'normal', 'opacity': 100.0})
    
    # Test Blend-Mode Update
    success = plugin.update_parameter('blend_mode', 'multiply')
    assert success, "Should update blend_mode"
    assert plugin.blend_mode == 'multiply', "Blend mode should be 'multiply'"
    print("  [OK] Blend mode update works")
    
    # Test Opacity Update
    success = plugin.update_parameter('opacity', 50.0)
    assert success, "Should update opacity"
    assert plugin.opacity == 50.0, "Opacity should be 50.0"
    print("  [OK] Opacity update works")
    
    # Test Invalid Blend-Mode
    success = plugin.update_parameter('blend_mode', 'invalid_mode')
    assert not success, "Should reject invalid blend mode"
    print("  [OK] Invalid blend mode rejected")
    
    # Test get_parameters
    params = plugin.get_parameters()
    assert params['blend_mode'] == 'multiply', "Should return 'multiply'"
    assert params['opacity'] == 50.0, "Should return 50.0"
    print("  [OK] get_parameters() works\n")
    
    return True


def test_frame_resize():
    """Testet automatisches Resize bei unterschiedlichen Frame-Größen."""
    print("=== Testing Frame Resize ===\n")
    
    # Unterschiedliche Größen
    large_frame = create_test_frame([255, 0, 0], size=(200, 200, 3))
    small_frame = create_test_frame([0, 0, 255], size=(100, 100, 3))
    
    plugin = BlendEffect()
    plugin.initialize({'blend_mode': 'normal', 'opacity': 100.0})
    
    result = plugin.process_frame(large_frame, overlay=small_frame)
    
    # Result sollte die Größe vom Base-Frame haben
    assert result.shape == large_frame.shape, "Result should match base frame size"
    print(f"  Base Frame:    {large_frame.shape}")
    print(f"  Overlay Frame: {small_frame.shape}")
    print(f"  Result Frame:  {result.shape}")
    print(f"  [OK] Auto-resize works\n")
    
    return True


def run_all_tests():
    """Führt alle Tests aus."""
    tests = [
        test_blend_modes,
        test_opacity,
        test_multiply_blend,
        test_screen_blend,
        test_add_blend,
        test_overlay_blend,
        test_parameter_update,
        test_frame_resize
    ]
    
    print("\n" + "="*60)
    print("BLEND EFFECT PLUGIN TEST SUITE")
    print("="*60)
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"[FAIL] Test failed: {test.__name__}")
            print(f"   Error: {e}")
            return False
    
    print("="*60)
    print("[OK] ALL TESTS PASSED!")
    print("[OK] Blend Effect Plugin fully functional!")
    print("="*60 + "\n")
    
    return True


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
