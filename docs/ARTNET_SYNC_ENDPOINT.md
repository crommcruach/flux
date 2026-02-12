# ArtNet Routing - Sync Endpoint Design

## Overview

The ArtNet routing system calculates LED coordinates **on the backend** from editor shape parameters. This means whenever shapes change in the editor, you must call the **sync endpoint** to recalculate pixel positions.

---

## Primary Sync Method

### `sync_from_editor_shapes(remove_orphaned=False)`

**Purpose:** Recalculate all LED coordinates from current editor shapes in session state.

**What it does:**
1. ✅ Reads `session_state.editor.shapes[]`
2. ✅ Creates new objects for new shapes
3. ✅ Updates existing objects (regenerates coordinates)
4. ✅ Preserves user-configured LED properties (type, white detection, color correction, custom names)
5. ✅ Optionally removes objects whose shapes were deleted

**Returns:**
```python
{
    'created': [ArtNetObject, ...],    # Newly created objects
    'updated': [ArtNetObject, ...],    # Updated objects
    'removed': ['obj-id', ...]         # Removed object IDs (if remove_orphaned=True)
}
```

---

## When to Call Sync Endpoint

### 1. **Shape Modified in Editor** ❗ REQUIRED
**Trigger:** User moves, resizes, rotates, or changes properties of a shape
**Endpoint:** `POST /api/artnet/routing/sync`
**Behavior:** Regenerates coordinates for that object, preserves LED config

**Example:**
```javascript
// After shape is moved/resized in editor
await fetch('/api/artnet/routing/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ removeOrphaned: false })
});
```

---

### 2. **Shape Added to Editor** ❗ REQUIRED
**Trigger:** User creates new shape (matrix, circle, line, etc.)
**Endpoint:** `POST /api/artnet/routing/sync`
**Behavior:** Creates new ArtNet object with default LED config (RGB, 3 channels)

**Example:**
```javascript
// After new shape is added
await fetch('/api/artnet/routing/sync', {
    method: 'POST',
    body: JSON.stringify({ removeOrphaned: false })
});
```

---

### 3. **Shape Deleted in Editor** ❗ REQUIRED
**Trigger:** User deletes shape
**Endpoint:** `POST /api/artnet/routing/sync` with `removeOrphaned: true`
**Behavior:** Removes corresponding ArtNet object and all output assignments

**Example:**
```javascript
// After shape is deleted
await fetch('/api/artnet/routing/sync', {
    method: 'POST',
    body: JSON.stringify({ removeOrphaned: true })  // ⚠️ Important!
});
```

**Alternative (explicit delete):**
```javascript
// If you know the object ID, you can delete directly
await fetch(`/api/artnet/routing/objects/${objectId}`, {
    method: 'DELETE'
});
```

---

### 4. **Session Loaded/Restored** ❗ REQUIRED
**Trigger:** User loads saved session or page reloads
**Endpoint:** `POST /api/artnet/routing/sync`
**Behavior:** Regenerates all objects from restored editor shapes

**Example:**
```javascript
// After session restore
async function onSessionLoaded() {
    // Session state already restored by backend
    
    // Regenerate ArtNet objects from shapes
    const response = await fetch('/api/artnet/routing/sync', {
        method: 'POST',
        body: JSON.stringify({ removeOrphaned: true })
    });
    
    const data = await response.json();
    console.log(`Synced: ${data.created.length} created, ${data.updated.length} updated`);
}
```

---

### 5. **Manual Recalculation** 🔧 OPTIONAL
**Trigger:** User clicks "Refresh" or "Recalculate" button
**Endpoint:** `POST /api/artnet/routing/sync`
**Behavior:** Forcefully regenerates all objects (useful for debugging)

---

## Important: What Gets Preserved vs Regenerated

### ✅ Preserved on Sync (User Configuration)
- LED type (RGB, RGBW, RGBAW, etc.)
- Channel order (RGB, GRB, RGBW, etc.)
- White detection settings (mode, threshold, behavior)
- Color correction (brightness, contrast, RGB adjustments)
- Input layer assignment
- Master/slave linking
- **Custom object names** (if user renamed the object)
- Output assignments

### 🔄 Regenerated on Sync (From Shape Parameters)
- LED coordinates (x, y positions)
- Point count (based on shape size)
- Universe range (based on LED count + type)
- Object type (matrix, circle, line, etc.)

---

## REST API Endpoint

### `POST /api/artnet/routing/sync`

**Request Body:**
```json
{
    "removeOrphaned": false  // true = delete objects with missing shapes
}
```

**Response:**
```json
{
    "success": true,
    "created": [
        {
            "id": "obj-abc123",
            "name": "Matrix Left",
            "sourceShapeId": "shape-1",
            "type": "matrix",
            "points": [...],
            "ledType": "RGB",
            "universeStart": 1,
            "universeEnd": 2
        }
    ],
    "updated": [
        {
            "id": "obj-def456",
            "name": "Circle Right",
            "sourceShapeId": "shape-2",
            "points": [...]
        }
    ],
    "removed": ["obj-old789"],
    "summary": {
        "createdCount": 1,
        "updatedCount": 1,
        "removedCount": 1
    }
}
```

---

## Performance Considerations

### Is Recalculation Expensive?

**Short answer:** No, it's very fast.

**Details:**
- Matrix 10×10: ~100 points, <1ms
- Circle 60 points: ~60 points, <1ms
- Complex scene (50 shapes): ~5000 points total, <20ms

**Recommendation:** Call sync endpoint liberally. Don't worry about performance.

### Debouncing (Frontend)

If shapes change rapidly (e.g., dragging), debounce the sync call:

```javascript
let syncTimeout = null;

function onShapeChanged() {
    // Clear previous timeout
    clearTimeout(syncTimeout);
    
    // Debounce 500ms
    syncTimeout = setTimeout(async () => {
        await fetch('/api/artnet/routing/sync', {
            method: 'POST',
            body: JSON.stringify({ removeOrphaned: false })
        });
    }, 500);
}
```

---

## Workflow Examples

### Example 1: User Moves Shape
```
1. User drags matrix in editor
2. Editor updates shape.x, shape.y in session state
3. Frontend calls: POST /api/artnet/routing/sync (after debounce)
4. Backend regenerates LED coordinates
5. Frontend refreshes object list (optional - LED positions updated)
```

### Example 2: User Deletes Shape
```
1. User clicks delete button in editor
2. Editor removes shape from session_state.editor.shapes[]
3. Frontend calls: POST /api/artnet/routing/sync?removeOrphaned=true
4. Backend removes corresponding ArtNet object
5. Backend removes object from all output assignments
6. Frontend refreshes object list
```

### Example 3: Page Reload
```
1. Backend restores session state from file
2. Frontend loads page
3. Frontend calls: POST /api/artnet/routing/sync?removeOrphaned=true
4. Backend regenerates all objects from restored shapes
5. Frontend displays ArtNet objects
```

---

## Error Handling

### No Shapes in Editor
```json
{
    "success": true,
    "created": [],
    "updated": [],
    "removed": [],
    "summary": { "createdCount": 0, "updatedCount": 0, "removedCount": 0 }
}
```

### Shape Missing Required Parameters
Backend will use defaults:
- size: 100
- x, y: 0
- rotation: 0
- scaleX, scaleY: 1

### Object Already Exists (Idempotent)
Sync is safe to call multiple times. If object exists, it updates. If not, it creates.

---

## Testing Sync Behavior

All sync scenarios are tested in `tests/test_artnet_routing.py`:

✅ `test_routing_manager_sync_from_editor` - Creates 2 objects from shapes  
✅ `test_routing_manager_update_shape_sync` - Updates coordinates, preserves config  
✅ `test_routing_manager_orphaned_objects` - Removes objects for deleted shapes  

Run tests:
```bash
python tests/test_artnet_routing.py
```

---

## Summary

**✅ Always call sync when:**
- Shape added
- Shape modified (moved/resized/rotated)
- Shape deleted (with `removeOrphaned: true`)
- Session loaded

**✅ Sync is fast:** <20ms for complex scenes

**✅ Sync is safe:** Idempotent, preserves user config

**✅ Use `removeOrphaned: true`** when:
- Shape deleted in editor
- Session restored (cleanup old objects)

**✅ Use `removeOrphaned: false`** when:
- Shape modified (default behavior)
- Shape added
- Manual refresh
