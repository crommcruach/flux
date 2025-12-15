"""
ASCII Art Effect Plugin - Converts frames to ASCII art representation
"""
import numpy as np
import cv2
from plugins import PluginBase, PluginType, ParameterType


class AsciiArtEffect(PluginBase):
    """
    ASCII Art Effect - Converts video frames to ASCII art style.
    
    Maps pixel brightness to ASCII characters and renders them back to image.
    Creates a retro terminal/text-based art aesthetic.
    """
    
    METADATA = {
        'id': 'ascii_art',
        'name': 'ASCII Art',
        'description': 'Convert frames to ASCII art representation',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Stylize'
    }
    
    # ASCII character sets (from darkest to brightest)
    CHAR_SETS = {
        'simple': ' .:-=+*#%@',
        'detailed': ' .\'`^",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$',
        'blocks': ' ░▒▓█',
        'numbers': ' 123456789',
        'symbols': ' .oO0@'
    }
    
    PARAMETERS = [
        {
            'name': 'char_set',
            'label': 'Character Set',
            'type': ParameterType.SELECT,
            'default': 'simple',
            'options': list(CHAR_SETS.keys()),
            'description': 'ASCII character set to use'
        },
        {
            'name': 'char_width',
            'label': 'Character Width',
            'type': ParameterType.INT,
            'default': 8,
            'min': 4,
            'max': 32,
            'step': 2,
            'description': 'Width of each character cell in pixels'
        },
        {
            'name': 'char_height',
            'label': 'Character Height',
            'type': ParameterType.INT,
            'default': 16,
            'min': 8,
            'max': 48,
            'step': 2,
            'description': 'Height of each character cell in pixels'
        },
        {
            'name': 'invert',
            'label': 'Invert Colors',
            'type': ParameterType.BOOL,
            'default': False,
            'description': 'Invert brightness mapping (light on dark vs dark on light)'
        },
        {
            'name': 'colored',
            'label': 'Colored ASCII',
            'type': ParameterType.BOOL,
            'default': False,
            'description': 'Use colors from original frame instead of monochrome'
        },
        {
            'name': 'background_color',
            'label': 'Background Color',
            'type': ParameterType.SELECT,
            'default': 'black',
            'options': ['black', 'white', 'original'],
            'description': 'Background color (black, white, or preserve original)'
        }
    ]
    
    def initialize(self, config):
        """Initialize ASCII Art effect with parameters."""
        self.char_set = config.get('char_set', 'simple')
        self.char_width = config.get('char_width', 8)
        self.char_height = config.get('char_height', 16)
        self.invert = config.get('invert', False)
        self.colored = config.get('colored', False)
        self.background_color = config.get('background_color', 'black')
        
        # Get character set
        self.chars = self.CHAR_SETS.get(self.char_set, self.CHAR_SETS['simple'])
        if self.invert:
            self.chars = self.chars[::-1]  # Reverse for inverted brightness
    
    def process_frame(self, frame, **kwargs):
        """
        Convert frame to ASCII art representation.
        
        Args:
            frame: Input frame (RGB)
            
        Returns:
            ASCII art styled frame
        """
        height, width = frame.shape[:2]
        
        # Calculate grid dimensions
        cols = width // self.char_width
        rows = height // self.char_height
        
        # Resize frame to grid dimensions for sampling
        sample_width = cols
        sample_height = rows
        small_frame = cv2.resize(frame, (sample_width, sample_height), interpolation=cv2.INTER_AREA)
        
        # Convert to grayscale for brightness mapping
        if len(small_frame.shape) == 3:
            gray = cv2.cvtColor(small_frame, cv2.COLOR_RGB2GRAY)
        else:
            gray = small_frame
        
        # Create output frame
        if self.background_color == 'black':
            output = np.zeros((height, width, 3), dtype=np.uint8)
        elif self.background_color == 'white':
            output = np.full((height, width, 3), 255, dtype=np.uint8)
        else:  # original
            output = frame.copy()
        
        # Map brightness to ASCII characters and render
        for row in range(rows):
            for col in range(cols):
                # Get brightness value (0-255)
                brightness = gray[row, col]
                
                # Map to character index
                char_idx = int((brightness / 255.0) * (len(self.chars) - 1))
                char = self.chars[char_idx]
                
                # Calculate position
                x = col * self.char_width
                y = row * self.char_height
                
                # Get color for this cell
                if self.colored:
                    color = tuple(int(c) for c in small_frame[row, col])
                else:
                    color = (255, 255, 255) if brightness > 127 else (0, 0, 0)
                    if self.background_color == 'white':
                        color = (0, 0, 0) if brightness > 127 else (255, 255, 255)
                
                # Draw character
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = (self.char_height / 24.0) * 0.8  # Scale font to cell size
                thickness = max(1, int(font_scale * 1.5))
                
                # Center character in cell
                text_size = cv2.getTextSize(char, font, font_scale, thickness)[0]
                text_x = x + (self.char_width - text_size[0]) // 2
                text_y = y + (self.char_height + text_size[1]) // 2
                
                cv2.putText(output, char, (text_x, text_y), font, font_scale, color, thickness, cv2.LINE_AA)
        
        return output
    
    def get_parameters(self):
        """Return current parameter values."""
        return {
            'char_set': self.char_set,
            'char_width': self.char_width,
            'char_height': self.char_height,
            'invert': self.invert,
            'colored': self.colored,
            'background_color': self.background_color
        }
    
    def update_parameter(self, name, value):
        """Update a parameter value."""
        if name == 'char_set':
            self.char_set = value
            self.chars = self.CHAR_SETS.get(value, self.CHAR_SETS['simple'])
            if self.invert:
                self.chars = self.chars[::-1]
        elif name == 'char_width':
            self.char_width = max(4, min(32, int(value)))
        elif name == 'char_height':
            self.char_height = max(8, min(48, int(value)))
        elif name == 'invert':
            self.invert = bool(value)
            self.chars = self.CHAR_SETS.get(self.char_set, self.CHAR_SETS['simple'])
            if self.invert:
                self.chars = self.chars[::-1]
        elif name == 'colored':
            self.colored = bool(value)
        elif name == 'background_color':
            self.background_color = value
    
    def cleanup(self):
        """Cleanup resources."""
        pass
