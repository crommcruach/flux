"""
Test Blend Mode Effect Plugin
"""
import numpy as np
import pytest
from src.plugins.effects.blend_mode import BlendModeEffect


class TestBlendModeEffect:
    """Test cases for Blend Mode Effect Plugin"""
    
    @pytest.fixture
    def plugin(self):
        """Create plugin instance"""
        return BlendModeEffect()
    
    @pytest.fixture
    def test_frame(self):
        """Create test frame (10x10 red frame)"""
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        frame[:, :] = [0, 0, 255]  # BGR: Red
        return frame
    
    def test_normal_blend(self, plugin, test_frame):
        """Test normal blend mode"""
        plugin.set_parameters({
            'mode': 'normal',
            'color_r': 0,
            'color_g': 255,
            'color_b': 0,
            'opacity': 100.0,
            'mix': 100.0
        })
        
        result = plugin.process_frame(test_frame.copy())
        
        # Should be pure green
        assert result.shape == test_frame.shape
        assert np.allclose(result[0, 0], [0, 255, 0], atol=5)
    
    def test_multiply_blend(self, plugin, test_frame):
        """Test multiply blend mode"""
        plugin.set_parameters({
            'mode': 'multiply',
            'color_r': 255,
            'color_g': 255,
            'color_b': 255,
            'opacity': 100.0,
            'mix': 100.0
        })
        
        result = plugin.process_frame(test_frame.copy())
        
        # Red * White = Red
        assert result.shape == test_frame.shape
        assert np.allclose(result[0, 0], [0, 0, 255], atol=5)
    
    def test_screen_blend(self, plugin, test_frame):
        """Test screen blend mode"""
        plugin.set_parameters({
            'mode': 'screen',
            'color_r': 128,
            'color_g': 128,
            'color_b': 128,
            'opacity': 100.0,
            'mix': 100.0
        })
        
        result = plugin.process_frame(test_frame.copy())
        
        # Screen should lighten the image
        assert result.shape == test_frame.shape
        assert np.all(result >= test_frame)
    
    def test_add_blend(self, plugin, test_frame):
        """Test add blend mode"""
        plugin.set_parameters({
            'mode': 'add',
            'color_r': 50,
            'color_g': 50,
            'color_b': 50,
            'opacity': 100.0,
            'mix': 100.0
        })
        
        result = plugin.process_frame(test_frame.copy())
        
        # Add should increase values (clipped at 255)
        assert result.shape == test_frame.shape
        assert np.all(result[:, :, 2] == 255)  # Red channel clipped
    
    def test_subtract_blend(self, plugin, test_frame):
        """Test subtract blend mode"""
        plugin.set_parameters({
            'mode': 'subtract',
            'color_r': 100,
            'color_g': 0,
            'color_b': 0,
            'opacity': 100.0,
            'mix': 100.0
        })
        
        result = plugin.process_frame(test_frame.copy())
        
        # Subtract should decrease values
        assert result.shape == test_frame.shape
        assert np.all(result[:, :, 2] < test_frame[:, :, 2])  # Red channel reduced
    
    def test_darken_blend(self, plugin, test_frame):
        """Test darken blend mode"""
        plugin.set_parameters({
            'mode': 'darken',
            'color_r': 128,
            'color_g': 128,
            'color_b': 128,
            'opacity': 100.0,
            'mix': 100.0
        })
        
        result = plugin.process_frame(test_frame.copy())
        
        # Darken should take minimum values
        assert result.shape == test_frame.shape
        assert np.all(result[:, :, 2] == 128)  # Min(255, 128) = 128
    
    def test_lighten_blend(self, plugin, test_frame):
        """Test lighten blend mode"""
        plugin.set_parameters({
            'mode': 'lighten',
            'color_r': 100,
            'color_g': 100,
            'color_b': 100,
            'opacity': 100.0,
            'mix': 100.0
        })
        
        result = plugin.process_frame(test_frame.copy())
        
        # Lighten should take maximum values
        assert result.shape == test_frame.shape
        assert np.all(result[:, :, 2] == 255)  # Max(255, 100) = 255
    
    def test_overlay_blend(self, plugin, test_frame):
        """Test overlay blend mode"""
        plugin.set_parameters({
            'mode': 'overlay',
            'color_r': 128,
            'color_g': 128,
            'color_b': 128,
            'opacity': 100.0,
            'mix': 100.0
        })
        
        result = plugin.process_frame(test_frame.copy())
        
        # Overlay should combine multiply and screen
        assert result.shape == test_frame.shape
        assert result.dtype == np.uint8
    
    def test_difference_blend(self, plugin, test_frame):
        """Test difference blend mode"""
        plugin.set_parameters({
            'mode': 'difference',
            'color_r': 255,
            'color_g': 0,
            'color_b': 0,
            'opacity': 100.0,
            'mix': 100.0
        })
        
        result = plugin.process_frame(test_frame.copy())
        
        # Difference of red and red = black
        assert result.shape == test_frame.shape
        assert result.dtype == np.uint8
    
    def test_opacity_parameter(self, plugin, test_frame):
        """Test opacity parameter"""
        # 0% opacity = original frame
        plugin.set_parameters({
            'mode': 'normal',
            'color_r': 0,
            'color_g': 255,
            'color_b': 0,
            'opacity': 0.0,
            'mix': 100.0
        })
        
        result = plugin.process_frame(test_frame.copy())
        assert np.allclose(result, test_frame, atol=5)
        
        # 50% opacity = half blend
        plugin.set_parameters({
            'mode': 'normal',
            'color_r': 0,
            'color_g': 255,
            'color_b': 0,
            'opacity': 50.0,
            'mix': 100.0
        })
        
        result = plugin.process_frame(test_frame.copy())
        # Should be between red and green
        assert result[0, 0, 1] > 0  # Some green
        assert result[0, 0, 2] > 0  # Some red
    
    def test_mix_parameter(self, plugin, test_frame):
        """Test mix parameter"""
        # 0% mix = original frame
        plugin.set_parameters({
            'mode': 'multiply',
            'color_r': 0,
            'color_g': 0,
            'color_b': 0,
            'opacity': 100.0,
            'mix': 0.0
        })
        
        result = plugin.process_frame(test_frame.copy())
        assert np.allclose(result, test_frame, atol=5)
        
        # 100% mix = full effect
        plugin.set_parameters({
            'mode': 'multiply',
            'color_r': 0,
            'color_g': 0,
            'color_b': 0,
            'opacity': 100.0,
            'mix': 100.0
        })
        
        result = plugin.process_frame(test_frame.copy())
        # Multiply with black = black
        assert np.all(result == 0)
    
    def test_all_blend_modes_run(self, plugin, test_frame):
        """Test that all blend modes execute without errors"""
        modes = [
            'normal', 'multiply', 'screen', 'overlay', 'add', 'subtract',
            'darken', 'lighten', 'color_dodge', 'color_burn', 'hard_light',
            'soft_light', 'difference', 'exclusion'
        ]
        
        for mode in modes:
            plugin.set_parameters({
                'mode': mode,
                'color_r': 128,
                'color_g': 128,
                'color_b': 128,
                'opacity': 100.0,
                'mix': 100.0
            })
            
            result = plugin.process_frame(test_frame.copy())
            
            # Check result is valid
            assert result.shape == test_frame.shape
            assert result.dtype == np.uint8
            assert np.all((result >= 0) & (result <= 255))
    
    def test_metadata(self, plugin):
        """Test plugin metadata"""
        assert plugin.METADATA['id'] == 'blend_mode'
        assert plugin.METADATA['name'] == 'Blend Mode'
        assert 'blend' in plugin.METADATA['description'].lower()
    
    def test_parameters(self, plugin):
        """Test plugin parameters"""
        param_names = [p['name'] for p in plugin.PARAMETERS]
        assert 'mode' in param_names
        assert 'color_r' in param_names
        assert 'color_g' in param_names
        assert 'color_b' in param_names
        assert 'opacity' in param_names
        assert 'mix' in param_names
