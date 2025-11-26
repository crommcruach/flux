"""
Test script for the Opacity effect plugin
"""
import sys
import os
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from plugins.effects.opacity import OpacityEffect


def test_opacity_plugin():
    """Test the opacity plugin functionality"""
    print("Testing Opacity Plugin...")
    
    # Create test frame (100x100 white image)
    test_frame = np.ones((100, 100, 3), dtype=np.uint8) * 255
    
    # Test 1: 100% opacity (no change)
    print("\n1. Testing 100% opacity (should remain white)...")
    plugin = OpacityEffect(config={'opacity': 100.0})
    result = plugin.process_frame(test_frame.copy())
    assert np.array_equal(result, test_frame), "100% opacity should not change the frame"
    print("   ✓ 100% opacity works correctly")
    
    # Test 2: 0% opacity (black)
    print("2. Testing 0% opacity (should be black)...")
    plugin = OpacityEffect(config={'opacity': 0.0})
    result = plugin.process_frame(test_frame.copy())
    expected = np.zeros((100, 100, 3), dtype=np.uint8)
    assert np.array_equal(result, expected), "0% opacity should produce black frame"
    print("   ✓ 0% opacity works correctly")
    
    # Test 3: 50% opacity (half brightness)
    print("3. Testing 50% opacity (should be half brightness)...")
    plugin = OpacityEffect(config={'opacity': 50.0})
    result = plugin.process_frame(test_frame.copy())
    expected = np.ones((100, 100, 3), dtype=np.uint8) * 127  # Half of 255
    # Allow small rounding error
    assert np.allclose(result, expected, atol=1), "50% opacity should produce half brightness"
    print("   ✓ 50% opacity works correctly")
    
    # Test 4: Parameter update
    print("4. Testing parameter update...")
    plugin = OpacityEffect(config={'opacity': 100.0})
    success = plugin.update_parameter('opacity', 25.0)
    assert success, "Parameter update should succeed"
    assert plugin.opacity == 25.0, "Opacity value should be updated"
    result = plugin.process_frame(test_frame.copy())
    expected_value = int(255 * 0.25)
    assert np.allclose(result[0, 0, 0], expected_value, atol=1), "Updated opacity should be applied"
    print("   ✓ Parameter update works correctly")
    
    # Test 5: Get parameters
    print("5. Testing get_parameters...")
    params = plugin.get_parameters()
    assert 'opacity' in params, "Should return opacity parameter"
    assert params['opacity'] == 25.0, "Should return current opacity value"
    print("   ✓ get_parameters works correctly")
    
    # Test 6: Metadata validation
    print("6. Testing metadata...")
    assert OpacityEffect.METADATA['id'] == 'opacity', "Plugin ID should be 'opacity'"
    assert OpacityEffect.METADATA['name'] == 'Opacity', "Plugin name should be 'Opacity'"
    assert len(OpacityEffect.PARAMETERS) == 1, "Should have 1 parameter"
    param = OpacityEffect.PARAMETERS[0]
    assert param['name'] == 'opacity', "Parameter name should be 'opacity'"
    assert param['min'] == 0.0, "Min should be 0"
    assert param['max'] == 100.0, "Max should be 100"
    print("   ✓ Metadata is correct")
    
    print("\n✅ All tests passed!")


if __name__ == '__main__':
    test_opacity_plugin()
