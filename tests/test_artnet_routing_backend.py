"""
Test Suite for ArtNet Routing Backend

Tests all rendering pipeline components:
- ColorCorrector: Color adjustments and white channel
- PixelSampler: Video frame sampling
- RGBFormatMapper: Channel order mapping
- OutputManager: Complete rendering pipeline
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
import time
from modules.artnet_routing.color_correction import ColorCorrector
from modules.artnet_routing.pixel_sampler import PixelSampler
from modules.artnet_routing.rgb_format_mapper import RGBFormatMapper
from modules.artnet_routing.output_manager import OutputManager
from modules.artnet_routing.artnet_object import ArtNetObject, ArtNetPoint
from modules.artnet_routing.artnet_output import ArtNetOutput


class TestColorCorrector:
    """Test color correction functionality"""
    
    @staticmethod
    def test_brightness():
        """Test brightness adjustment"""
        print("Testing brightness adjustment...")
        pixels = np.array([[100, 100, 100]], dtype=np.uint8)
        
        # Increase brightness
        result = ColorCorrector.apply(pixels, brightness=50)
        assert result[0, 0] == 150, f"Expected 150, got {result[0, 0]}"
        
        # Decrease brightness
        result = ColorCorrector.apply(pixels, brightness=-50)
        assert result[0, 0] == 50, f"Expected 50, got {result[0, 0]}"
        
        print("✓ Brightness test passed")
    
    @staticmethod
    def test_contrast():
        """Test contrast adjustment"""
        print("Testing contrast adjustment...")
        pixels = np.array([[64, 128, 192]], dtype=np.uint8)
        
        # Increase contrast
        result = ColorCorrector.apply(pixels, contrast=128)
        # Should push values away from midpoint (128)
        assert result[0, 0] < 64, "Dark values should get darker"
        assert result[0, 2] > 192, "Bright values should get brighter"
        
        print("✓ Contrast test passed")
    
    @staticmethod
    def test_rgb_channels():
        """Test per-channel adjustments"""
        print("Testing RGB channel adjustments...")
        pixels = np.array([[100, 100, 100]], dtype=np.uint8)
        
        result = ColorCorrector.apply(pixels, red=50, green=-30, blue=20)
        assert result[0, 0] == 150, f"Red: expected 150, got {result[0, 0]}"
        assert result[0, 1] == 70, f"Green: expected 70, got {result[0, 1]}"
        assert result[0, 2] == 120, f"Blue: expected 120, got {result[0, 2]}"
        
        print("✓ RGB channel test passed")
    
    @staticmethod
    def test_white_channel():
        """Test white channel calculation"""
        print("Testing white channel for RGBW...")
        
        # Pure white should extract white channel
        pixels = np.array([[200, 200, 200]], dtype=np.uint8)
        result = ColorCorrector.apply_white_channel(
            pixels, 
            white_mode='minimum',
            white_threshold=150,
            white_behavior='replace',
            led_type='RGBW'
        )
        
        assert result.shape[1] == 4, f"Expected 4 channels, got {result.shape[1]}"
        assert result[0, 3] == 200, f"White channel: expected 200, got {result[0, 3]}"
        
        print("✓ White channel test passed")
    
    @staticmethod
    def run_all():
        """Run all color corrector tests"""
        print("\n=== ColorCorrector Tests ===")
        TestColorCorrector.test_brightness()
        TestColorCorrector.test_contrast()
        TestColorCorrector.test_rgb_channels()
        TestColorCorrector.test_white_channel()
        print("✓ All ColorCorrector tests passed\n")


class TestPixelSampler:
    """Test pixel sampling functionality"""
    
    @staticmethod
    def test_sample_object():
        """Test sampling from object points"""
        print("Testing object pixel sampling...")
        
        # Create test frame (solid color)
        frame = np.full((100, 100, 3), [255, 128, 64], dtype=np.uint8)
        
        # Create test object with points
        obj = ArtNetObject(
            id='test-obj',
            name='Test Object',
            source_shape_id='shape-1',
            type='line',
            points=[
                ArtNetPoint(1, 50, 50),  # Center
                ArtNetPoint(2, 25, 25),  # Top-left
                ArtNetPoint(3, 75, 75),  # Bottom-right
            ]
        )
        
        sampler = PixelSampler(canvas_width=100, canvas_height=100)
        colors = sampler.sample_object(obj, frame)
        
        assert len(colors) == 3, f"Expected 3 colors, got {len(colors)}"
        assert np.all(colors[0] == [255, 128, 64]), "Color mismatch"
        
        print("✓ Object sampling test passed")
    
    @staticmethod
    def test_coordinate_normalization():
        """Test coordinate scaling from canvas to frame"""
        print("Testing coordinate normalization...")
        
        # Canvas 1920x1080, Frame 100x100
        # Point at (960, 540) should map to (50, 50) in frame
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[50, 50] = [255, 0, 0]  # Red pixel at center
        
        obj = ArtNetObject(
            id='test-obj',
            name='Test Object',
            source_shape_id='shape-1',
            type='line',
            points=[ArtNetPoint(1, 960, 540)]
        )
        
        sampler = PixelSampler(canvas_width=1920, canvas_height=1080)
        colors = sampler.sample_object(obj, frame)
        
        assert np.all(colors[0] == [255, 0, 0]), "Coordinate normalization failed"
        
        print("✓ Coordinate normalization test passed")
    
    @staticmethod
    def run_all():
        """Run all pixel sampler tests"""
        print("\n=== PixelSampler Tests ===")
        TestPixelSampler.test_sample_object()
        TestPixelSampler.test_coordinate_normalization()
        print("✓ All PixelSampler tests passed\n")


class TestRGBFormatMapper:
    """Test RGB format mapping functionality"""
    
    @staticmethod
    def test_rgb_to_grb():
        """Test RGB to GRB conversion (WS2812B)"""
        print("Testing RGB → GRB mapping...")
        
        pixels = np.array([[255, 128, 64]], dtype=np.uint8)
        result = RGBFormatMapper.map_channels(pixels, 'GRB')
        
        assert result[0, 0] == 128, f"Expected G=128, got {result[0, 0]}"
        assert result[0, 1] == 255, f"Expected R=255, got {result[0, 1]}"
        assert result[0, 2] == 64, f"Expected B=64, got {result[0, 2]}"
        
        print("✓ RGB→GRB mapping test passed")
    
    @staticmethod
    def test_rgbw_mapping():
        """Test RGBW channel mapping"""
        print("Testing RGBW channel mapping...")
        
        pixels = np.array([[255, 128, 64, 200]], dtype=np.uint8)
        
        # RGBW → WRGB
        result = RGBFormatMapper.map_channels(pixels, 'WRGB')
        assert result[0, 0] == 200, "White should be first"
        assert result[0, 1] == 255, "Red should be second"
        
        print("✓ RGBW mapping test passed")
    
    @staticmethod
    def test_flatten_to_dmx():
        """Test flattening to DMX bytes"""
        print("Testing DMX flattening...")
        
        pixels = np.array([
            [255, 128, 64],
            [100, 200, 50]
        ], dtype=np.uint8)
        
        dmx_bytes = RGBFormatMapper.flatten_to_dmx(pixels)
        
        assert len(dmx_bytes) == 6, f"Expected 6 bytes, got {len(dmx_bytes)}"
        assert dmx_bytes[0] == 255, "First byte mismatch"
        assert dmx_bytes[1] == 128, "Second byte mismatch"
        assert dmx_bytes[3] == 100, "Fourth byte mismatch"
        
        print("✓ DMX flattening test passed")
    
    @staticmethod
    def run_all():
        """Run all format mapper tests"""
        print("\n=== RGBFormatMapper Tests ===")
        TestRGBFormatMapper.test_rgb_to_grb()
        TestRGBFormatMapper.test_rgbw_mapping()
        TestRGBFormatMapper.test_flatten_to_dmx()
        print("✓ All RGBFormatMapper tests passed\n")


class TestOutputManager:
    """Test complete rendering pipeline"""
    
    @staticmethod
    def test_render_frame():
        """Test complete frame rendering"""
        print("Testing complete frame rendering...")
        
        # Create test video frame (gradient)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        for y in range(100):
            frame[y, :] = [y * 2, y * 2, y * 2]
        
        # Create test object (3 LEDs in vertical line)
        obj = ArtNetObject(
            id='obj-1',
            name='Test LED Strip',
            source_shape_id='shape-1',
            type='line',
            points=[
                ArtNetPoint(1, 50, 25),   # Top (darker)
                ArtNetPoint(2, 50, 50),   # Middle
                ArtNetPoint(3, 50, 75),   # Bottom (brighter)
            ],
            led_type='RGB',
            channel_order='RGB'
        )
        
        # Create test output
        output = ArtNetOutput(
            id='out-1',
            name='Test Output',
            target_ip='127.0.0.1',
            subnet='255.255.255.0',
            start_universe=1,
            fps=30,
            active=True,
            assigned_objects=['obj-1']
        )
        
        # Render frame
        manager = OutputManager(canvas_width=100, canvas_height=100)
        results = manager.render_frame(
            frame=frame,
            objects={'obj-1': obj},
            outputs={'out-1': output}
        )
        
        assert 'out-1' in results, "Output not rendered"
        dmx_data = results['out-1']
        assert len(dmx_data) == 9, f"Expected 9 bytes (3 LEDs × 3 channels), got {len(dmx_data)}"
        
        # Check gradient (bottom should be brighter than top)
        top_brightness = dmx_data[0]
        bottom_brightness = dmx_data[6]
        assert bottom_brightness > top_brightness, "Gradient not sampled correctly"
        
        print("✓ Frame rendering test passed")
    
    @staticmethod
    def test_fps_throttling():
        """Test FPS throttling"""
        print("Testing FPS throttling...")
        
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        obj = ArtNetObject(
            id='obj-1',
            name='Test',
            source_shape_id='shape-1',
            type='line',
            points=[ArtNetPoint(1, 5, 5)]
        )
        output = ArtNetOutput(
            id='out-1',
            name='Test',
            target_ip='127.0.0.1',
            subnet='255.255.255.0',
            start_universe=1,
            fps=10,  # 10 FPS = 100ms per frame
            assigned_objects=['obj-1']
        )
        
        manager = OutputManager()
        
        # First frame should render
        result1 = manager.render_frame(frame, {'obj-1': obj}, {'out-1': output})
        assert 'out-1' in result1, "First frame should render"
        
        # Immediate second frame should be throttled
        result2 = manager.render_frame(frame, {'obj-1': obj}, {'out-1': output})
        assert 'out-1' not in result2, "Second frame should be throttled"
        
        # Wait and try again
        time.sleep(0.11)
        result3 = manager.render_frame(frame, {'obj-1': obj}, {'out-1': output})
        assert 'out-1' in result3, "Frame after delay should render"
        
        print("✓ FPS throttling test passed")
    
    @staticmethod
    def test_last_frame_storage():
        """Test last frame storage for DMX monitor"""
        print("Testing last frame storage...")
        
        frame = np.full((10, 10, 3), [255, 128, 64], dtype=np.uint8)
        obj = ArtNetObject(
            id='obj-1',
            name='Test',
            source_shape_id='shape-1',
            type='line',
            points=[ArtNetPoint(1, 5, 5)]
        )
        output = ArtNetOutput(
            id='out-1',
            name='Test',
            target_ip='127.0.0.1',
            subnet='255.255.255.0',
            start_universe=1,
            assigned_objects=['obj-1']
        )
        
        manager = OutputManager()
        manager.render_frame(frame, {'obj-1': obj}, {'out-1': output})
        
        # Check last frame is accessible
        last_frame = manager.get_last_frame('out-1')
        assert last_frame is not None, "Last frame not stored"
        assert len(last_frame) == 3, "Last frame size mismatch"
        
        print("✓ Last frame storage test passed")
    
    @staticmethod
    def run_all():
        """Run all output manager tests"""
        print("\n=== OutputManager Tests ===")
        TestOutputManager.test_render_frame()
        TestOutputManager.test_fps_throttling()
        TestOutputManager.test_last_frame_storage()
        print("✓ All OutputManager tests passed\n")


def run_all_tests():
    """Run complete test suite"""
    print("\n" + "="*60)
    print("ArtNet Routing Backend Test Suite")
    print("="*60)
    
    try:
        TestColorCorrector.run_all()
        TestPixelSampler.run_all()
        TestRGBFormatMapper.run_all()
        TestOutputManager.run_all()
        
        print("="*60)
        print("✓ ALL TESTS PASSED")
        print("="*60)
        print("\nBackend rendering pipeline is working correctly!")
        print("Ready for integration with player and stupidArtnet.")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
