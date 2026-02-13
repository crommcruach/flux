"""
Color Correction Module

Applies brightness, contrast, and RGB adjustments to pixel arrays.
Used for both per-object and per-output color correction.
"""

import numpy as np
from typing import List, Tuple, Union


class ColorCorrector:
    """Apply color correction to pixel arrays"""
    
    @staticmethod
    def apply(
        pixels: Union[np.ndarray, List[Tuple[int, int, int]]],
        brightness: int = 0,
        contrast: int = 0,
        red: int = 0,
        green: int = 0,
        blue: int = 0
    ) -> np.ndarray:
        """
        Apply color correction to pixel array.
        
        Args:
            pixels: RGB pixel array (Nx3) or list of (R, G, B) tuples
            brightness: -255 to 255 (additive adjustment)
            contrast: -255 to 255 (multiplicative around 128)
            red: -255 to 255 (additive to red channel)
            green: -255 to 255 (additive to green channel)
            blue: -255 to 255 (additive to blue channel)
        
        Returns:
            Corrected pixel array as uint8 numpy array (Nx3)
        """
        # Convert to numpy array if needed
        if isinstance(pixels, list):
            arr = np.array(pixels, dtype=np.float32)
        else:
            arr = pixels.astype(np.float32)
        
        # Skip processing if no corrections needed
        if brightness == 0 and contrast == 0 and red == 0 and green == 0 and blue == 0:
            return arr.astype(np.uint8)
        
        # Apply contrast (multiplicative around midpoint 128)
        if contrast != 0:
            # Normalize contrast: -255 to 255 → 0.0 to 2.0 multiplier
            contrast_factor = 1.0 + (contrast / 255.0)
            arr = (arr - 128) * contrast_factor + 128
        
        # Apply brightness (additive)
        if brightness != 0:
            arr += brightness
        
        # Apply per-channel adjustments
        if red != 0:
            arr[:, 0] += red
        if green != 0:
            arr[:, 1] += green
        if blue != 0:
            arr[:, 2] += blue
        
        # Clamp to valid range and convert to uint8
        arr = np.clip(arr, 0, 255)
        return arr.astype(np.uint8)
    
    @staticmethod
    def apply_white_channel(
        rgb_pixels: np.ndarray,
        white_mode: str = 'luminance',
        white_threshold: int = 200,
        white_behavior: str = 'hybrid',
        color_temp: int = 4500,
        led_type: str = 'RGBW'
    ) -> np.ndarray:
        """
        Calculate white channel values for RGBW+ LEDs.
        
        Args:
            rgb_pixels: RGB pixel array (Nx3 uint8)
            white_mode: 'luminance', 'average', or 'minimum'
            white_threshold: Minimum RGB value to trigger white (0-255)
            white_behavior: 'replace', 'additive', or 'hybrid'
            color_temp: Color temperature in Kelvin (2700-6500) for multi-white
            led_type: LED type (RGBW, RGBAW, RGBWW, RGBCW, RGBCWW)
        
        Returns:
            Extended pixel array with white channel(s) based on LED type:
            - RGBW: Nx4 (RGB + W)
            - RGBAW: Nx5 (RGB + A + W)
            - RGBWW/RGBCW: Nx5 (RGB + WW + CW)
            - RGBCWW: Nx6 (RGB + C + W + W)
        """
        rgb_float = rgb_pixels.astype(np.float32)
        
        # Calculate white value based on mode
        if white_mode == 'minimum':
            white = np.min(rgb_float, axis=1)
        elif white_mode == 'average':
            white = np.mean(rgb_float, axis=1)
        elif white_mode == 'luminance':
            # ITU-R BT.709 luminance weights
            white = (0.2126 * rgb_float[:, 0] + 
                    0.7152 * rgb_float[:, 1] + 
                    0.0722 * rgb_float[:, 2])
        else:
            white = np.min(rgb_float, axis=1)
        
        # Apply threshold
        white = np.where(white >= white_threshold, white, 0)
        
        # Adjust RGB based on behavior
        if white_behavior == 'replace':
            # Fully replace RGB with white
            new_rgb = rgb_float - white[:, np.newaxis]
            new_rgb = np.maximum(new_rgb, 0)  # Prevent negative
        elif white_behavior == 'hybrid':
            # 50% replace, 50% keep
            reduce = white[:, np.newaxis] * 0.5
            new_rgb = rgb_float - reduce
            new_rgb = np.maximum(new_rgb, 0)
        else:  # additive
            # Keep RGB unchanged
            new_rgb = rgb_float
        
        # Build output based on LED type
        if led_type == 'RGBW':
            # Simple RGBW: RGB + W
            output = np.column_stack([new_rgb, white])
        
        elif led_type == 'RGBAW':
            # RGB + Amber + White
            # Amber channel: emphasize warm colors (yellow/orange)
            amber = np.minimum(rgb_float[:, 0], rgb_float[:, 1]) * 0.8
            amber = np.where(amber >= white_threshold * 0.7, amber, 0)
            output = np.column_stack([new_rgb, amber, white])
        
        elif led_type in ['RGBWW', 'RGBCW']:
            # RGB + Warm White + Cool White
            # Split white based on color temperature
            temp_normalized = (color_temp - 2700) / (6500 - 2700)
            temp_normalized = np.clip(temp_normalized, 0, 1)
            
            warm_white = white * (1 - temp_normalized)
            cool_white = white * temp_normalized
            
            if led_type == 'RGBWW':
                output = np.column_stack([new_rgb, warm_white, cool_white])
            else:  # RGBCW
                output = np.column_stack([new_rgb, cool_white, warm_white])
        
        elif led_type == 'RGBCWW':
            # RGB + Cool White + Warm White + White
            temp_normalized = (color_temp - 2700) / (6500 - 2700)
            temp_normalized = np.clip(temp_normalized, 0, 1)
            
            warm_white = white * (1 - temp_normalized) * 0.5
            cool_white = white * temp_normalized * 0.5
            neutral_white = white * 0.5
            
            output = np.column_stack([new_rgb, cool_white, warm_white, neutral_white])
        
        else:
            # Unknown type, return RGB only
            output = new_rgb
        
        # Clamp and convert
        output = np.clip(output, 0, 255)
        return output.astype(np.uint8)
