# Effects UI - Dynamic Parameter Panel

## Overview
The Effects UI provides a user-friendly interface for managing the plugin system's effect chain with dynamic parameter controls that automatically adapt to each plugin's parameter types.

## Features

### 🎨 Dynamic Control Generation
- **Automatic UI Generation**: Controls are generated based on plugin metadata
- **Type-Specific Controls**: Each parameter type maps to an appropriate UI element
- **Real-time Updates**: Parameter changes are applied immediately to the video stream
- **Live Refresh**: Effect chain updates automatically every 2 seconds

### 📊 Parameter Type Mapping

| Parameter Type | UI Control | Description |
|---------------|------------|-------------|
| `FLOAT` | Range Slider | Floating-point values with configurable min/max/step |
| `INT` | Range Slider | Integer values with step=1 |
| `BOOL` | Toggle Switch | True/False values |
| `SELECT` | Dropdown Menu | Multiple choice from predefined options |
| `COLOR` | Color Picker | Hex color values with visual preview |
| `STRING` | Text Input | Free-form text entry |
| `RANGE` | Dual Input | Min/Max pair for range values |

## Architecture

### Frontend Components

**effects.html** (HTML Template)
```
- Two-column layout (Bootstrap 5 grid)
- Left column: Active effect chain with parameter controls
- Right column: Available effects library
- Empty states for no effects
- Responsive design
```

**effects.js** (JavaScript Module)
```javascript
// Core Functions
init()                          // Initialize panel and start auto-refresh
loadAvailableEffects()          // Fetch plugin list from /api/plugins/list
renderAvailableEffects()        // Display effect cards
addEffect(pluginId)             // Add effect to chain
refreshEffectChain()            // Fetch current chain from /api/player/effects
renderEffectChain()             // Display active effects with controls
renderEffectItem()              // Generate HTML for single effect
renderParameterControl(param)   // Generate control based on parameter type
updateParameter()               // Send parameter update to API
removeEffect(index)             // Remove effect from chain
clearAllEffects()               // Clear entire chain
```

### REST API Integration

The UI communicates with these endpoints:

```
GET  /api/plugins/list                              → Load available effects
POST /api/player/effects/add                        → Add effect to chain
GET  /api/player/effects                            → Get current chain
POST /api/player/effects/{index}/parameters/{name}  → Update parameter
DELETE /api/player/effects/{index}                  → Remove effect
POST /api/player/effects/clear                      → Clear all effects
```

## Usage

### Access the Panel
Navigate to `http://localhost:5000/effects` or click the ✨ icon in the menu bar.

### Add an Effect
1. Browse available effects in the right panel
2. Click an effect card to add it to the chain
3. The effect appears in the left panel with its parameter controls

### Adjust Parameters
Each parameter type has a specific control:

**Slider (FLOAT/INT)**
```
Blur Strength: [=========|-------] 5.0
- Drag slider or click to adjust
- Current value displayed in real-time
- Updates sent automatically
```

**Toggle Switch (BOOL)**
```
[✓] Enable Effect
- Click to toggle on/off
- Instant update
```

**Dropdown (SELECT)**
```
Blend Mode: [Normal ▼]
- Click to open options
- Select from predefined list
```

**Color Picker (COLOR)**
```
[🎨] #FF5733 [#FF5733]
- Click color swatch to open picker
- Hex value displayed alongside
```

### Remove Effects
- Click **🗑️ Remove** on individual effect to remove it
- Click **🗑️ Clear All** to remove all effects

### Effect Ordering
Effects are processed sequentially from top to bottom. The order determines the visual result.

## Example Workflows

### Workflow 1: Apply Blur Effect
```
1. Open effects panel (/effects)
2. Click "Blur" in available effects
3. Adjust "strength" slider (0.0 - 20.0)
4. See blur applied to video in real-time
```

### Workflow 2: Multiple Effects
```
1. Add "Blur" effect (strength: 3.0)
2. Add "Brightness" effect (factor: 1.2)
3. Add "Hue Shift" effect (degrees: 30)
4. Effects process in sequence: blur → brightness → hue
```

### Workflow 3: Parameter Tuning
```
1. Add effect with default parameters
2. Drag slider to adjust value
3. Value display updates immediately
4. Video reflects changes in real-time
5. No need to save - updates are instant
```

## Code Examples

### Example 1: Parameter Definition in Plugin

```python
class MyEffect(PluginBase):
    METADATA = {
        "id": "my_effect",
        "name": "My Effect",
        "type": PluginType.EFFECT,
        "version": "1.0.0",
        "author": "Developer",
        "description": "Example effect with various parameter types"
    }
    
    PARAMETERS = [
        {
            "name": "intensity",
            "type": ParameterType.FLOAT,
            "default": 5.0,
            "min": 0.0,
            "max": 10.0,
            "description": "Effect intensity"
        },
        {
            "name": "enabled",
            "type": ParameterType.BOOL,
            "default": True,
            "description": "Enable or disable effect"
        },
        {
            "name": "mode",
            "type": ParameterType.SELECT,
            "default": "normal",
            "options": ["normal", "multiply", "screen"],
            "description": "Blending mode"
        },
        {
            "name": "color",
            "type": ParameterType.COLOR,
            "default": "#FF0000",
            "description": "Tint color"
        }
    ]
```

**Generated UI:**
```html
<!-- FLOAT → Slider -->
<input type="range" min="0.0" max="10.0" step="0.1" value="5.0" />

<!-- BOOL → Toggle Switch -->
<input type="checkbox" checked />

<!-- SELECT → Dropdown -->
<select>
  <option>normal</option>
  <option>multiply</option>
  <option>screen</option>
</select>

<!-- COLOR → Color Picker -->
<input type="color" value="#FF0000" />
```

### Example 2: Custom Parameter Validation

The UI respects min/max constraints defined in plugin metadata:

```python
PARAMETERS = [
    {
        "name": "blur_radius",
        "type": ParameterType.INT,
        "default": 5,
        "min": 1,        # Slider minimum
        "max": 50,       # Slider maximum
        "description": "Blur kernel size (must be odd)"
    }
]
```

```javascript
// Generated HTML respects constraints
<input type="range" 
       min="1" 
       max="50" 
       step="1" 
       value="5" />
```

### Example 3: API Communication

```javascript
// Add Effect
fetch('/api/player/effects/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plugin_id: 'blur' })
});

// Update Parameter
fetch('/api/player/effects/0/parameters/strength', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value: 8.5 })
});

// Remove Effect
fetch('/api/player/effects/0', {
    method: 'DELETE'
});
```

## Styling

The UI uses Bootstrap 5 with custom CSS variables for theming:

```css
.effect-item {
    background: var(--panel-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 1rem;
}

.effect-card:hover {
    background: var(--hover-bg);
    border-color: var(--primary-color);
    transform: translateX(4px);
}
```

## Performance Notes

### Auto-Refresh Strategy
- Effect chain refreshes every 2 seconds
- Only updates if changes detected
- Minimal API calls (no polling on parameter updates)

### Parameter Updates
- Sent immediately on change
- Debouncing not implemented (slider events can fire rapidly)
- Consider adding debouncing for slider controls if performance issues occur

### Optimization Opportunities
```javascript
// Current: Immediate update
oninput="updateParameter(0, 'strength', this.value)"

// Potential: Debounced update (300ms delay)
oninput="debounce(() => updateParameter(0, 'strength', this.value), 300)"
```

## Browser Compatibility

Tested with:
- ✅ Chrome 120+
- ✅ Firefox 121+
- ✅ Edge 120+
- ✅ Safari 17+

Required features:
- ES6 JavaScript (async/await, arrow functions)
- Fetch API
- CSS Grid
- HTML5 Input types (range, color)

## Troubleshooting

### Problem: Effects not loading
**Solution**: Check browser console for API errors
```javascript
// Console output should show:
🎨 Initializing Effects Panel...
✅ Loaded X effect plugins
```

### Problem: Parameter updates not working
**Solution**: Verify REST API is responding
```bash
curl http://localhost:5000/api/player/effects/0/parameters/strength \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"value": 10.0}'
```

### Problem: UI not refreshing
**Solution**: Check auto-refresh interval is running
```javascript
console.log(updateInterval); // Should show interval ID (number)
```

### Problem: Control not generated for parameter
**Solution**: Verify parameter type is valid
```python
# Check plugin definition
PARAMETERS = [
    {
        "name": "param",
        "type": ParameterType.FLOAT,  # Must be valid ParameterType enum
        # ...
    }
]
```

## Future Enhancements

### Phase 4: Advanced Features
- 🎭 **Effect Presets**: Save/load parameter configurations
- 📋 **Effect Templates**: Pre-configured effect chains
- 🔄 **Drag & Drop Reordering**: Change effect sequence
- 🎚️ **Master Controls**: Enable/disable effects without removal
- 📊 **Performance Monitor**: FPS impact per effect
- 🎨 **Visual Preview**: Thumbnails showing effect result
- 🔍 **Effect Search**: Filter available effects
- 📦 **Effect Categories**: Group by type (blur, color, distortion, etc.)

### Phase 5: Pro Features
- 🎬 **Keyframe Animation**: Animate parameters over time
- 🔗 **Parameter Linking**: Connect multiple parameters
- 📈 **Parameter Curves**: Non-linear parameter mapping
- 🎭 **LFO Modulation**: Audio-reactive parameters
- 💾 **Effect History**: Undo/redo changes
- 🌐 **Multi-User Sync**: Collaborate on effect chains

## Related Documentation

- [PLUGIN_SYSTEM.md](PLUGIN_SYSTEM.md) - Plugin architecture and API reference
- [EFFECT_PIPELINE.md](EFFECT_PIPELINE.md) - Effect chain processing details
- [USAGE.md](USAGE.md) - General Flux usage guide

## Testing

### Manual Testing Checklist
- [ ] Load effects panel
- [ ] Add effect to chain
- [ ] Adjust parameter (slider)
- [ ] Toggle boolean parameter
- [ ] Select dropdown option
- [ ] Remove effect
- [ ] Clear all effects
- [ ] Add multiple effects
- [ ] Verify sequential processing
- [ ] Test with video playing
- [ ] Test parameter constraints (min/max)
- [ ] Verify auto-refresh works

### Automated Testing
```powershell
# Run effect pipeline tests
.\test_effect_pipeline.ps1

# Run live effect test
.\test_effect_live.ps1
```

## Changelog

### v2.3.0 (Current)
- ✅ Initial Effects UI implementation
- ✅ Dynamic parameter control generation
- ✅ 7 parameter types supported
- ✅ Real-time updates
- ✅ Auto-refresh every 2 seconds
- ✅ Bootstrap 5 styling
- ✅ Responsive layout
- ✅ Empty states
- ✅ Menu bar integration

---

**Status**: ✅ Phase 3 Complete - UI Generation Functional
**Last Updated**: 2024
**Author**: GitHub Copilot
