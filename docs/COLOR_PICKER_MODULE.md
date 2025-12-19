# Color Picker Module - Usage Guide

## Overview
The ColorPicker component is a reusable color picker with HSB, RGB, and Palette modes that can be used in plugin parameters.

## Files
- **JavaScript**: `frontend/js/components/color-picker.js`
- **CSS**: `frontend/css/color-picker.css`
- **Loaded in**: `frontend/player.html`

## Using in Plugins

### 1. Define Color Parameter in Plugin

In your plugin's `get_parameters()` method, add a color parameter:

```python
def get_parameters(self):
    return [
        {
            "name": "color",
            "label": "Color",
            "type": "color",  # Important: type must be "color"
            "default": "#ff0000",
            "description": "Pick a color"
        }
    ]
```

### 2. Automatic Rendering

The color picker will automatically render in the UI when:
- Parameter type is `"color"` (case-insensitive)
- The parameter is shown in Generator Parameters or Effect Parameters sections

### 3. Features

**Three Modes:**
- **HSB Mode**: Hue, Saturation, Brightness sliders
- **RGB Mode**: Red, Green, Blue sliders
- **Palette Mode**: Save and reuse custom colors

**Interactive Controls:**
- Click and drag sliders to adjust values
- Live color preview swatch
- Add colors to palette for quick access
- Switch between modes via tabs

### 4. Value Format

The color value is always returned as a hex string:
```python
# In your plugin's process method:
def process(self, frame, parameters):
    color_hex = parameters.get('color', '#ff0000')  # Returns "#ff0000"
    # Convert to RGB if needed:
    r = int(color_hex[1:3], 16)
    g = int(color_hex[3:5], 16)
    b = int(color_hex[5:7], 16)
```

### 5. Programmatic API

If you need to control the color picker programmatically in JavaScript:

```javascript
// Get reference to picker
const picker = window.colorPickers['gen-color-picker-color'];

// Get current value
const hexColor = picker.getValue();  // Returns "#ff0000"

// Set new value
picker.setValue("#00ff00");

// Set palette colors
picker.setPalette(["#ff0000", "#00ff00", "#0000ff"]);

// Get palette colors
const colors = picker.getPalette();
```

## Example Plugin

```python
class ColorEffectPlugin(EffectBase):
    def get_metadata(self):
        return {
            "id": "color_effect",
            "name": "Color Effect",
            "description": "Apply color overlay",
            "type": "effect",
            "category": "Color"
        }
    
    def get_parameters(self):
        return [
            {
                "name": "overlay_color",
                "label": "Overlay Color",
                "type": "color",
                "default": "#ff0000",
                "description": "Color to overlay"
            },
            {
                "name": "opacity",
                "label": "Opacity",
                "type": "float",
                "min": 0.0,
                "max": 1.0,
                "default": 0.5,
                "step": 0.01
            }
        ]
    
    def process(self, frame, parameters):
        color_hex = parameters.get('overlay_color', '#ff0000')
        opacity = parameters.get('opacity', 0.5)
        
        # Convert hex to RGB
        r = int(color_hex[1:3], 16)
        g = int(color_hex[3:5], 16)
        b = int(color_hex[5:7], 16)
        
        # Create color overlay
        overlay = np.full_like(frame, (b, g, r))
        
        # Blend with original frame
        result = cv2.addWeighted(frame, 1.0 - opacity, overlay, opacity, 0)
        
        return result
```

## Styling

The color picker inherits the dark theme from the main application. If you need custom styling:

```css
/* Target specific picker */
#gen-color-picker-color .color-picker-container {
    max-width: 400px;
}

/* Or all pickers */
.color-picker-container {
    /* Your custom styles */
}
```

## Notes

- Color pickers are automatically cleaned up when parameters are re-rendered
- Palette colors are stored per-instance (not globally saved)
- Hex format is always lowercase: `#ff0000` not `#FF0000`
- Alpha channel is not yet supported (future enhancement)
