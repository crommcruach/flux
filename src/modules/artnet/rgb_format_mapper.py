"""
RGB Format Mapper Module

Maps RGB pixel data to different LED channel orders.
Supports various LED strip types (WS2812B, SK6812, etc.) with different wiring.
"""

import numpy as np
from typing import Dict, List


class RGBFormatMapper:
    """Map pixel data to different LED channel orders"""
    
    # Channel mapping definitions
    CHANNEL_MAPS: Dict[str, List[int]] = {
        # 3-channel RGB
        'RGB': [0, 1, 2],
        'RBG': [0, 2, 1],
        'GRB': [1, 0, 2],  # WS2812B standard
        'GBR': [1, 2, 0],
        'BRG': [2, 0, 1],
        'BGR': [2, 1, 0],
        
        # 4-channel RGBW
        'RGBW': [0, 1, 2, 3],
        'RBGW': [0, 2, 1, 3],
        'GRBW': [1, 0, 2, 3],  # WS2812B RGBW
        'GBRW': [1, 2, 0, 3],
        'BRGW': [2, 0, 1, 3],
        'BGRW': [2, 1, 0, 3],
        'WRGB': [3, 0, 1, 2],
        'WRBG': [3, 0, 2, 1],
        'WGRB': [3, 1, 0, 2],
        'WGBR': [3, 1, 2, 0],
        'WBRG': [3, 2, 0, 1],
        'WBGR': [3, 2, 1, 0],
        
        # 5-channel RGBAW / RGBWW
        'RGBAW': [0, 1, 2, 3, 4],
        'RGBWA': [0, 1, 2, 4, 3],
        'RGBWW': [0, 1, 2, 3, 4],  # Warm, Cool
        'RGBCW': [0, 1, 2, 4, 3],  # Cool, Warm
        'GRBAW': [1, 0, 2, 3, 4],
        'GRBWA': [1, 0, 2, 4, 3],
        
        # 6-channel RGBCWW
        'RGBCWW': [0, 1, 2, 3, 4, 5],  # RGB, Cool, Warm, White
        'RGBWWC': [0, 1, 2, 4, 5, 3],  # RGB, Warm, White, Cool
    }
    
    @staticmethod
    def map_channels(pixels: np.ndarray, channel_order: str) -> np.ndarray:
        """
        Remap pixel channels to match LED strip wiring.
        
        Args:
            pixels: Input pixel array (N, C) where C is number of channels
            channel_order: Target channel order (e.g., 'GRB', 'RGBW', 'GRBW')
        
        Returns:
            Remapped pixel array (N, C) with channels reordered
        
        Examples:
            RGB → GRB: [255, 128, 64] → [128, 255, 64]
            RGBW → WRGB: [255, 128, 64, 200] → [200, 255, 128, 64]
        """
        if channel_order not in RGBFormatMapper.CHANNEL_MAPS:
            # Unknown format, return unchanged
            return pixels
        
        if len(pixels) == 0:
            return pixels
        
        # Get channel mapping
        channel_map = RGBFormatMapper.CHANNEL_MAPS[channel_order]
        
        # Verify channel count matches
        if pixels.shape[1] != len(channel_map):
            # Channel count mismatch, return unchanged
            return pixels
        
        # Remap channels
        return pixels[:, channel_map]
    
    @staticmethod
    def flatten_to_dmx(pixels: np.ndarray) -> bytes:
        """
        Flatten pixel array to DMX byte stream.
        
        Args:
            pixels: Pixel array (N, C) uint8
        
        Returns:
            Flattened bytes suitable for DMX transmission
        
        Example:
            [[255, 128, 64], [100, 200, 50]] → b'\xff\x80@d\xc82'
        """
        return pixels.flatten().tobytes()
    
    @staticmethod
    def get_supported_formats() -> List[str]:
        """Get list of all supported channel formats"""
        return list(RGBFormatMapper.CHANNEL_MAPS.keys())
    
    @staticmethod
    def get_channel_count(channel_order: str) -> int:
        """
        Get number of channels for a given format.
        
        Args:
            channel_order: Channel format string
        
        Returns:
            Number of channels, or 3 if unknown
        """
        if channel_order in RGBFormatMapper.CHANNEL_MAPS:
            return len(RGBFormatMapper.CHANNEL_MAPS[channel_order])
        return 3  # Default to RGB
    
    @staticmethod
    def is_valid_format(channel_order: str) -> bool:
        """Check if a channel format is supported"""
        return channel_order in RGBFormatMapper.CHANNEL_MAPS
    
    @staticmethod
    def format_description(channel_order: str) -> str:
        """
        Get human-readable description of channel format.
        
        Args:
            channel_order: Channel format string
        
        Returns:
            Description string
        """
        descriptions = {
            'RGB': 'Standard RGB (most common)',
            'GRB': 'WS2812B standard (Green-Red-Blue)',
            'BGR': 'Some Chinese LED strips',
            'RGBW': 'Standard RGBW',
            'GRBW': 'WS2812B RGBW',
            'WRGB': 'White-first RGBW',
            'RGBAW': 'RGB + Amber + White',
            'RGBWW': 'RGB + Warm White + Cool White',
            'RGBCW': 'RGB + Cool White + Warm White',
            'RGBCWW': 'RGB + Cool + Warm + Neutral White',
        }
        return descriptions.get(channel_order, f'{channel_order} format')
