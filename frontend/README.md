# Static Files Structure

## Directory Structure

```
static/
├── js/                      # JavaScript Modules
│   ├── constants.js        # Constants and configuration
│   ├── state.js           # Global state
│   ├── utils.js           # Helper functions
│   ├── stroke-font.js     # Vector-based fonts
│   ├── shapes.js          # Shape generator (planned)
│   ├── renderer.js        # Canvas rendering (planned)
│   ├── handlers.js        # Event handlers (planned)
│   └── ui.js              # UI updates (planned)
├── bootstrap-icons/        # Bootstrap icon library
├── controls.html          # Video controls interface
├── controls.js            # Video controls logic
├── editor.js              # Main editor (to be refactored)
├── index.html             # Main page
├── styles.css             # CSS styles
├── favicon.svg            # Favicon
└── logo.svg               # Logo

## Modules

### constants.js
Central constants:
- `MIN_SCALE`, `MAX_SCALE` - Scale limits
- `HANDLE` - Handle configuration
- `COLORS` - Color palette
- `TOOLTIP` - Tooltip configuration
- `POINT` - Point rendering configuration

### state.js
Global state and state management:
- Shape management (`shapes`, `selectedShape`, `selectedShapes`)
- Grouping (`groups`, `groupCounter`)
- Drag state (`dragMode`, `offsetX`, `offsetY`, etc.)
- Rendering state (`needsRedraw`, `hoveredPoint`, etc.)
- Icon images
- State setter functions
- `loadIcons()` - Loads all icon images

### utils.js
Helper functions:
- `markForRedraw()` - Marks canvas for redrawing
- `localToWorld()` - Transforms local to world coordinates
- `worldToLocal()` - Transforms world to local coordinates
- `worldLenBetweenLocal()` - Calculates world distance between local points
- `distributeAlongEdges()` - Distributes points evenly along edges

### stroke-font.js
Vector-based letter definitions:
- `STROKE_FONT` - Object with letters A-Z, 0-9, special characters
- `LETTER_WIDTHS` - Letter widths
- `DEFAULT_LETTER_SPACING` - Default letter spacing

## Migration Status

✅ Created:
- `constants.js` - Complete
- `state.js` - Complete
- `utils.js` - Complete
- `stroke-font.js` - Present

🔄 In progress:
- Refactoring `editor.js` into further modules

## Next Steps

1. Extract shape generators into `shapes.js`
2. Extract rendering logic into `renderer.js`
3. Extract event handlers into `handlers.js`
4. Extract UI update logic into `ui.js`
5. Update `index.html` for ES6 modules
6. Erstelle `main.js` als Einstiegspunkt
