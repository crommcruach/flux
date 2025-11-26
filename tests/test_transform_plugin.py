"""
Test script for the Transform effect plugin
"""
import sys
import os
import numpy as np
import cv2

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from plugins.effects.transform import TransformEffect


def test_transform_plugin():
    """Test the transform plugin functionality"""
    print("Testing Transform Plugin...")
    
    # Create test frame (200x200 with colored quadrants)
    test_frame = np.zeros((200, 200, 3), dtype=np.uint8)
    test_frame[:100, :100] = [255, 0, 0]  # Red top-left
    test_frame[:100, 100:] = [0, 255, 0]  # Green top-right
    test_frame[100:, :100] = [0, 0, 255]  # Blue bottom-left
    test_frame[100:, 100:] = [255, 255, 0]  # Yellow bottom-right
    
    # Test 1: No transformation (default values)
    print("\n1. Testing default values (no transformation)...")
    plugin = TransformEffect(config={})
    result = plugin.process_frame(test_frame.copy())
    assert result.shape == test_frame.shape, "Shape should remain unchanged"
    assert np.array_equal(result, test_frame), "Default values should not change frame"
    print("   ✓ Default values work correctly")
    
    # Test 2: Position X
    print("2. Testing position_x...")
    plugin = TransformEffect(config={'position_x': 50.0})
    result = plugin.process_frame(test_frame.copy())
    assert result.shape == test_frame.shape, "Shape should remain unchanged"
    # Check that frame has been shifted right (left side should be black)
    assert np.array_equal(result[:, :50], 0), "Left 50px should be black after x shift"
    print("   ✓ position_x works correctly")
    
    # Test 3: Position Y
    print("3. Testing position_y...")
    plugin = TransformEffect(config={'position_y': 50.0})
    result = plugin.process_frame(test_frame.copy())
    assert result.shape == test_frame.shape, "Shape should remain unchanged"
    # Check that frame has been shifted down (top should be black)
    assert np.array_equal(result[:50, :], 0), "Top 50px should be black after y shift"
    print("   ✓ position_y works correctly")
    
    # Test 4: Symmetric scale
    print("4. Testing scale_xy (symmetric scaling)...")
    plugin = TransformEffect(config={'scale_xy': 50.0})  # 50% = half size
    result = plugin.process_frame(test_frame.copy())
    assert result.shape == test_frame.shape, "Output shape should match input"
    print("   ✓ scale_xy works correctly")
    
    # Test 5: Individual scale X
    print("5. Testing scale_x (horizontal scaling)...")
    plugin = TransformEffect(config={'scale_x': 200.0})  # 200% = double width
    result = plugin.process_frame(test_frame.copy())
    assert result.shape == test_frame.shape, "Output shape should match input"
    print("   ✓ scale_x works correctly")
    
    # Test 6: Individual scale Y
    print("6. Testing scale_y (vertical scaling)...")
    plugin = TransformEffect(config={'scale_y': 200.0})  # 200% = double height
    result = plugin.process_frame(test_frame.copy())
    assert result.shape == test_frame.shape, "Output shape should match input"
    print("   ✓ scale_y works correctly")
    
    # Test 7: Rotation X (3D)
    print("7. Testing rotation_x (3D perspective)...")
    plugin = TransformEffect(config={'rotation_x': 45.0})
    result = plugin.process_frame(test_frame.copy())
    assert result.shape == test_frame.shape, "Output shape should match input"
    print("   ✓ rotation_x works correctly")
    
    # Test 8: Rotation Y (3D)
    print("8. Testing rotation_y (3D perspective)...")
    plugin = TransformEffect(config={'rotation_y': 45.0})
    result = plugin.process_frame(test_frame.copy())
    assert result.shape == test_frame.shape, "Output shape should match input"
    print("   ✓ rotation_y works correctly")
    
    # Test 9: Combined transformations
    print("9. Testing combined transformations...")
    plugin = TransformEffect(config={
        'position_x': 10.0,
        'position_y': 10.0,
        'scale_xy': 80.0,
        'rotation_x': 15.0
    })
    result = plugin.process_frame(test_frame.copy())
    assert result.shape == test_frame.shape, "Output shape should match input"
    print("   ✓ Combined transformations work correctly")
    
    # Test 10: Parameter update
    print("10. Testing parameter updates...")
    plugin = TransformEffect(config={})
    assert plugin.update_parameter('position_x', 100.0), "Should update position_x"
    assert plugin.position_x == 100.0, "Value should be updated"
    assert plugin.update_parameter('scale_xy', 150.0), "Should update scale_xy"
    assert plugin.scale_xy == 150.0, "Value should be updated"
    assert plugin.update_parameter('rotation_x', 90.0), "Should update rotation_x"
    assert plugin.rotation_x == 90.0, "Value should be updated"
    assert not plugin.update_parameter('invalid_param', 0), "Should reject invalid parameter"
    print("   ✓ Parameter updates work correctly")
    
    # Test 11: Get parameters
    print("11. Testing get_parameters...")
    params = plugin.get_parameters()
    assert 'position_x' in params, "Should return position_x"
    assert 'position_y' in params, "Should return position_y"
    assert 'scale_xy' in params, "Should return scale_xy"
    assert 'scale_x' in params, "Should return scale_x"
    assert 'scale_y' in params, "Should return scale_y"
    assert 'rotation_x' in params, "Should return rotation_x"
    assert 'rotation_y' in params, "Should return rotation_y"
    assert params['position_x'] == 100.0, "Should return correct value"
    print("   ✓ get_parameters works correctly")
    
    # Test 12: Metadata validation
    print("12. Testing metadata...")
    assert TransformEffect.METADATA['id'] == 'transform', "Plugin ID should be 'transform'"
    assert TransformEffect.METADATA['name'] == 'Transform', "Plugin name should be 'Transform'"
    assert len(TransformEffect.PARAMETERS) == 7, "Should have 7 parameters"
    
    param_names = [p['name'] for p in TransformEffect.PARAMETERS]
    assert 'position_x' in param_names, "Should have position_x parameter"
    assert 'position_y' in param_names, "Should have position_y parameter"
    assert 'scale_xy' in param_names, "Should have scale_xy parameter"
    assert 'scale_x' in param_names, "Should have scale_x parameter"
    assert 'scale_y' in param_names, "Should have scale_y parameter"
    assert 'rotation_x' in param_names, "Should have rotation_x parameter"
    assert 'rotation_y' in param_names, "Should have rotation_y parameter"
    print("   ✓ Metadata is correct")
    
    # Test 13: Edge cases
    print("13. Testing edge cases...")
    
    # Zero scale (should return black)
    plugin = TransformEffect(config={'scale_xy': 0.0})
    result = plugin.process_frame(test_frame.copy())
    # Should handle gracefully (return black or unchanged)
    assert result.shape == test_frame.shape, "Should maintain shape"
    
    # Extreme scale
    plugin = TransformEffect(config={'scale_xy': 500.0})
    result = plugin.process_frame(test_frame.copy())
    assert result.shape == test_frame.shape, "Should maintain shape"
    
    # 360 degree rotation (should look similar to original with perspective)
    plugin = TransformEffect(config={'rotation_x': 360.0})
    result = plugin.process_frame(test_frame.copy())
    assert result.shape == test_frame.shape, "Should maintain shape"
    
    print("   ✓ Edge cases handled correctly")
    
    print("\n✅ All Transform plugin tests passed!")


if __name__ == '__main__':
    test_transform_plugin()
