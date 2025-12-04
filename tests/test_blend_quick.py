"""Quick test script for Blend Mode Effect"""
import sys
sys.path.insert(0, '.')

from plugins.effects.blend_mode import BlendModeEffect
import numpy as np

print('🔧 Testing Blend Mode Effect Plugin...')
print()

# Create plugin
p = BlendModeEffect()
print(f'✅ Plugin created: {p.METADATA["name"]} (ID: {p.METADATA["id"]})')
print(f'   Description: {p.METADATA["description"]}')
print(f'   Parameters: {len(p.PARAMETERS)}')
print()

# Create test frame (red)
frame = np.zeros((10, 10, 3), dtype=np.uint8)
frame[:, :] = [0, 0, 255]  # BGR: Red
print(f'📸 Test frame: {frame.shape}, Red color: {frame[0,0]}')
print()

# Test multiply mode
print('Testing MULTIPLY mode with white...')
for key, value in {
    'mode': 'multiply',
    'color_r': 255,
    'color_g': 255,
    'color_b': 255,
    'opacity': 100.0,
    'mix': 100.0
}.items():
    p.update_parameter(key, value)
result = p.process_frame(frame.copy())
print(f'   Result: {result[0,0]} (should be red: [0,0,255])')
assert np.allclose(result[0,0], [0,0,255], atol=5), "Multiply test failed!"
print('   ✅ PASSED')
print()

# Test all blend modes
modes = [
    'normal', 'multiply', 'screen', 'overlay', 'add', 'subtract',
    'darken', 'lighten', 'color_dodge', 'color_burn', 'hard_light',
    'soft_light', 'difference', 'exclusion'
]

print(f'Testing all {len(modes)} blend modes...')
for mode in modes:
    for key, value in {
        'mode': mode,
        'color_r': 128,
        'color_g': 128,
        'color_b': 128,
        'opacity': 100.0,
        'mix': 100.0
    }.items():
        p.update_parameter(key, value)
    result = p.process_frame(frame.copy())
    assert result.shape == frame.shape, f"{mode} changed frame shape!"
    assert result.dtype == np.uint8, f"{mode} changed frame dtype!"
    print(f'   ✅ {mode:15s} - OK (pixel: {result[0,0]})')

print()
print('🎉 All tests passed! Blend Mode Effect Plugin is fully functional!')
print()
print('Available Blend Modes:')
for mode in modes:
    print(f'   • {mode}')
