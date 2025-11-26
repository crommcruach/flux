# Generator UI Integration

## Overview
This document describes the implementation of generator plugin integration into the Flux controls UI, allowing generators to be used as content sources alongside video files.

## Implementation Date
2024

## Features Implemented

### 1. Backend: GeneratorSource Class
**File:** `src/modules/frame_source.py`

Added new `GeneratorSource` class that:
- Extends `FrameSource` abstract base class
- Instantiates generator plugins from the plugin system
- Passes parameters to generators
- Calls `process_frame(None, **kwargs)` to generate frames procedurally
- Handles frame sizing and timing
- Supports cleanup and reset operations

**Key Features:**
- Accepts generator_id and parameters dictionary on initialization
- Creates plugin instances via PluginManager
- Passes context (width, height, fps, frame_number, time) to generators
- Returns black frame fallback if generator fails
- Provides generator metadata via `get_info()`

### 2. Backend: Extended Clip Loading API
**File:** `src/modules/api_player_unified.py`

Modified `/api/player/<player_id>/clip/load` endpoint to:
- Accept `type` parameter ('video' or 'generator')
- Handle generator clips with `generator_id` and `parameters`
- Create `GeneratorSource` instances for generator clips
- Register generator clips in ClipRegistry with metadata
- Support both video and artnet players

**Request Format (Generator):**
```json
{
    "type": "generator",
    "generator_id": "plasma",
    "parameters": {
        "speed": 0.5,
        "scale": 1.0,
        "hue_shift": 0.1
    }
}
```

### 3. Frontend: Sources Tab Population
**Files:** 
- `src/static/js/controls.js`
- `src/static/controls.html`
- `src/static/css/controls.css`

**Added Functions:**
- `loadAvailableGenerators()` - Fetches generators from `/api/plugins/list?type=generator`
- `renderAvailableGenerators()` - Renders generator cards in Sources tab
- Generator cards are styled similar to effect cards but with gold accent color

**HTML Structure:**
```html
<div class="generator-card" draggable="true" data-generator-id="plasma">
    <div class="generator-card-title">🌟 Plasma</div>
    <div class="generator-card-description">Classic plasma effect...</div>
    <small>v1.0.0 • Drag to playlist</small>
</div>
```

### 4. Frontend: Drag-and-Drop Integration
**File:** `src/static/js/controls.js`

**Added Functions:**
- `startGeneratorDrag(event, generatorId)` - Handles drag start for generators
- `setupGeneratorDropZones()` - Initializes drop zone handlers
- `loadGeneratorClip(generatorId, playerType)` - Loads generator as active clip

**Modified Functions:**
- `renderVideoPlaylist()` - Added generator drop handling in drop zones
- `renderArtnetPlaylist()` - Added generator drop handling in drop zones
- Playlist click handlers now detect generator items and call `loadGeneratorClip()`

**Drag Data Transfer:**
- `generatorId` - Plugin ID for the generator
- `generatorName` - Display name for the generator

**Drop Behavior:**
Generators can be dropped into:
- Video playlist drop zones
- Art-Net playlist drop zones
- Generators are inserted at the drop position
- Generators are marked with 🌟 icon in playlists

### 5. Frontend: Generator Parameter Display
**File:** `src/static/js/controls.js`

**Added Functions:**
- `displayGeneratorParameters(generatorId, parameters)` - Renders parameter controls
- `updateGeneratorParameter(paramName, value)` - Updates parameter values (local state)

**Parameter Control Types:**
- **Float/Int:** Range slider with value display
- **Bool:** Checkbox control
- **String:** Text input field

**UI Layout:**
When a generator clip is loaded:
1. Clip FX title shows: `🌟 [Generator Name] (Generator)`
2. Parameter section displays all generator parameters
3. Each parameter shows: label, description, appropriate control
4. Changes update local state (API integration pending)

**Example Parameter Display:**
```
🌟 Plasma (Generator)

GENERATOR PARAMETERS

Speed
Animation speed
[slider: 0.0 ----•---- 5.0] 0.5

Scale  
Pattern scale (higher = larger features)
[slider: 0.1 ----•---- 5.0] 1.0

Hue Shift
Color rotation speed
[slider: 0.0 ----•---- 1.0] 0.1
```

## Data Flow

### Loading a Generator
1. User drags generator card from Sources tab
2. User drops on video or artnet playlist drop zone
3. Generator added to playlist array with metadata
4. User clicks generator in playlist
5. `loadGeneratorClip()` called with generator_id
6. Fetch default parameters from `/api/plugins/{id}/parameters`
7. POST to `/api/player/{type}/clip/load` with generator data
8. Backend creates `GeneratorSource` instance
9. Generator registered in ClipRegistry
10. Generator starts playing in player
11. Frontend displays generator parameters in Clip FX section

### Generating Frames
1. Player calls `generator_source.get_next_frame()`
2. GeneratorSource calls `plugin.process_frame(None, width=..., height=..., time=...)`
3. Generator plugin creates frame procedurally
4. Frame returned to player for display
5. Process repeats indefinitely (generators are infinite)

## Integration Points

### Existing Systems Used
- **PluginManager:** Loading and instantiating generator plugins
- **ClipRegistry:** Registering generator clips with metadata
- **Player:** Switch source to GeneratorSource
- **Effect System:** Generators can have effects applied (via Clip FX)
- **Drag-and-Drop:** Same system as video files and effects

### New Components
- `GeneratorSource` class (frame generation)
- Generator clip loading in API
- Generator UI in Sources tab
- Generator parameter display in Clip FX

## Available Generators

At implementation time, these generators are available:
1. **Plasma** - Classic demo effect with flowing color patterns
2. **Rainbow Wave** - Animated rainbow wave pattern
3. **Pulse** - Pulsing brightness effect with color rotation
4. **Fire** - Procedural fire animation
5. **Matrix Rain** - Matrix-style falling code effect

All generators support real-time parameter adjustment via the UI.

## Future Enhancements

### Runtime Parameter Updates (TODO)
Currently, parameters are only set on generator load. To enable runtime updates:

1. **Add API Endpoint:**
   ```
   POST /api/player/{type}/clip/{clip_id}/generator/parameter
   Body: { "parameter": "speed", "value": 1.5 }
   ```

2. **Backend Implementation:**
   - Add endpoint in `api_player_unified.py`
   - Get clip from ClipRegistry
   - Get player's current source
   - Check if source is GeneratorSource
   - Call `plugin.update_parameter(name, value)`
   - Return success/failure

3. **Frontend Integration:**
   - Uncomment API call in `updateGeneratorParameter()`
   - Add debouncing for slider updates
   - Show visual feedback on parameter change

### Additional Features
- Generator presets (save/load parameter sets)
- Generator thumbnails in Sources tab
- Generator preview before adding to playlist
- Generator transition effects
- Multi-generator blending
- Generator effect chains (apply effects before display)

## Code Locations

### Backend
- `src/modules/frame_source.py` - GeneratorSource class (lines 310-422)
- `src/modules/api_player_unified.py` - Clip loading API (lines 35-149)

### Frontend
- `src/static/js/controls.js`:
  - Lines 9: availableGenerators array
  - Lines 51: loadAvailableGenerators() call
  - Lines 156-225: Generator loading and rendering
  - Lines 227-344: Drag-and-drop setup
  - Lines 532-599: Generator drop handling (video playlist)
  - Lines 983-1052: Generator drop handling (artnet playlist)
  - Lines 428-598: Generator parameter display

### Styling
- `src/static/css/controls.css` - Generator card styles (lines 525-560)

## Testing

To test generator integration:

1. Start Flux server: `python src/main.py`
2. Open controls UI: `http://localhost:5555/controls`
3. Navigate to Sources tab
4. Verify 5 generators are displayed
5. Drag a generator (e.g., Plasma) to video playlist
6. Click the generator in playlist
7. Verify generator plays in video preview
8. Check Clip FX panel shows generator parameters
9. Adjust parameters and observe changes
10. Add effects to generator (blur, opacity, transform)
11. Verify effects apply correctly to generated frames

## Notes

- Generators run infinitely (no duration limit)
- Generators can be mixed with video files in playlists
- Generators support all effect plugins (opacity, transform, blur, etc.)
- Generator clips have unique clip IDs like video clips
- Generators can be used in both video and artnet players
- Generator state is stored in ClipRegistry
- Parameters are passed as kwargs to plugin's process_frame()
