# ArtNet Output Routing - Frontend Prototype

This prototype demonstrates the user interface for the ArtNet output routing system described in `docs/ARTNET_OUTPUT_ROUTING.md`.

## Features

### Left Panel
- **ArtNet Objects List**: Shows all objects from session state with:
  - Checkboxes for selection
  - Object name and type
  - Point count and universe range
  - Visual selection state
  
- **ArtNet Outputs List**: Shows configured outputs with:
  - Active/inactive status indicator
  - Output name, IP, and universe
  - Number of assigned objects
  - Selection state

### Center Panel - Canvas Preview
- Real-time visualization of objects
- Three view modes:
  - **All Objects**: Show all available objects
  - **Selected Only**: Show only checked objects
  - **Output Preview**: Show objects assigned to selected output
- Optional overlays:
  - **Point IDs**: Display point numbers on canvas
  - **Universe Bounds**: Show universe boundaries and ranges
- Color-coded objects for easy identification
- Connection lines for circles, lines, and star shapes

### Right Panel - Properties
- Edit output properties (name, IP, universe, FPS)
- View and manage assigned objects
- Remove objects from output
- Assign new objects to output
- Test output functionality
- Delete output

## Mock Data

The prototype includes 5 mock objects:
1. **Matrix 1**: 16x8 LED matrix (128 points, U1-2)
2. **Circle LED**: 60-point circular arrangement (U3-4)
3. **LED Strip Left**: 40-point vertical line (U5)
4. **LED Strip Right**: 40-point vertical line (U6)
5. **Star Shape**: 5-pointed star (30 points per edge, U7)

2 mock outputs:
1. **Main Output**: 192.168.1.10, U1, objects: Matrix 1, Circle LED
2. **Secondary Output**: 192.168.1.11, U5, objects: LED Strip Left, LED Strip Right

## Usage

1. Open `artnet-output-prototype.html` in a web browser
2. Click objects in the left panel to select them
3. Click outputs to view/edit properties
4. Use toolbar buttons to change view modes
5. Add new outputs with the "+ Add Output" button
6. Assign objects to outputs via the properties panel

## Interactions

### Object Selection
- Click object row to toggle selection
- Check/uncheck checkbox
- Selected objects highlight in canvas

### Output Management
- Click output to select and view properties
- Edit properties directly in right panel
- Use "Assign Objects" to add objects
- Click "×" next to assigned object to remove
- "Test Output" simulates sending test pattern
- "Delete Output" removes the output

### Canvas Controls
- **All Objects**: Default view showing everything
- **Selected Only**: Filter to checked objects only
- **Output Preview**: Show objects for selected output
- **Point IDs**: Toggle point number labels
- **Universe Bounds**: Toggle universe boundary boxes

## Integration Notes

When implementing the real system:

1. Replace mock data with API calls:
   - `GET /api/artnet/objects` → Load objects
   - `GET /api/artnet/outputs` → Load outputs
   - `POST /api/artnet/outputs` → Create output
   - `PUT /api/artnet/outputs/<id>` → Update output
   - `DELETE /api/artnet/outputs/<id>` → Delete output

2. Add WebSocket for real-time preview:
   - Connect to player WebSocket
   - Receive frame updates
   - Update canvas with actual video colors

3. Add validation:
   - IP address format validation
   - Universe range conflicts
   - Object assignment conflicts

4. Add features:
   - Drag & drop for object assignment
   - Object grouping
   - Output templates
   - Export/import configurations
   - Undo/redo support

## File Structure

```
snippets/artnet-output/
├── artnet-output-prototype.html  # Main prototype file (self-contained)
└── README.md                      # This file
```

## Testing Checklist

- [x] Object list renders correctly
- [x] Output list renders correctly
- [x] Canvas draws all object types
- [x] Object selection works
- [x] Output selection works
- [x] Properties panel updates
- [x] Add output modal works
- [x] Edit output works
- [x] Delete output works
- [x] Assign objects works
- [x] Remove objects works
- [x] View mode switching works
- [x] Point ID overlay works
- [x] Universe bounds overlay works
- [x] Color coding consistent
- [x] Responsive layout
- [x] Dark theme matches VS Code

## Next Steps

1. Review UX with team
2. Gather feedback on:
   - Layout and information density
   - Color scheme and contrast
   - Interaction patterns
   - Missing features
3. Iterate on design
4. Begin backend implementation (Phase 1)
5. Integrate frontend with real APIs
