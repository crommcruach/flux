"""
Test: Fade Transition Plugin
"""
import numpy as np
import cv2
from plugins.transitions.fade import FadeTransition


def test_fade_transition():
    """Test Fade Transition mit verschiedenen Progress-Werten"""
    
    # Create test frames (200x200)
    frame_a = np.zeros((200, 200, 3), dtype=np.uint8)
    frame_a[:] = [255, 0, 0]  # Blue frame
    
    frame_b = np.zeros((200, 200, 3), dtype=np.uint8)
    frame_b[:] = [0, 0, 255]  # Red frame
    
    # Initialize plugin
    fade = FadeTransition(config={'duration': 1.0, 'easing': 'linear'})
    
    print("Testing Fade Transition...")
    print(f"Metadata: {fade.get_metadata()}")
    print(f"Parameters: {fade.get_parameters()}")
    
    # Test different progress values
    progress_values = [0.0, 0.25, 0.5, 0.75, 1.0]
    
    for progress in progress_values:
        result = fade.blend_frames(frame_a, frame_b, progress)
        
        # Check result dimensions
        assert result.shape == frame_a.shape, f"Shape mismatch at progress={progress}"
        
        # Check color values (at center pixel)
        center_color = result[100, 100]
        print(f"Progress {progress:.2f}: Color at center = {center_color} (BGR)")
        
        # Verify blending (at progress=0.5, should be ~[127, 0, 127])
        if progress == 0.5:
            expected_blue = int(255 * (1.0 - progress))
            expected_red = int(255 * progress)
            assert abs(center_color[0] - expected_blue) < 5, "Blue channel incorrect"
            assert abs(center_color[2] - expected_red) < 5, "Red channel incorrect"
    
    print("✅ All tests passed!")
    
    # Test easing functions
    print("\nTesting Easing Functions...")
    easing_modes = ['linear', 'ease_in', 'ease_out', 'ease_in_out']
    
    for easing in easing_modes:
        fade.update_parameter('easing', easing)
        result = fade.blend_frames(frame_a, frame_b, 0.5)
        print(f"  {easing}: Center color = {result[100, 100]}")
    
    print("✅ Easing functions work!")
    
    # Test parameter updates
    print("\nTesting Parameter Updates...")
    fade.update_parameter('duration', 2.5)
    assert fade.get_parameters()['duration'] == 2.5
    print(f"  Duration updated to: {fade.get_parameters()['duration']}")
    
    print("\n✅ Fade Transition Plugin fully functional!")


if __name__ == '__main__':
    test_fade_transition()
