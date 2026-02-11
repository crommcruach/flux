# 🔵 Legacy Dots Export Logic - BACKUP

**Date:** 2026-02-05  
**Status:** 🗄️ Archived - No longer used in editor  
**Reason:** Dots distribution moved to Art-Net Output Routing page

---

## 📝 Overview

This logic was previously used in `editor.js` to export `punkte_export.json` with calculated LED coordinates.

**New approach:**
- ✅ Editor stores **shape parameters only** in session state
- ✅ Art-Net Output Routing page calculates dots and handles universe mapping
- ❌ Editor no longer exports `punkte_export.json`

---

## 🔧 Original Export Function

**File:** `frontend/js/editor.js` (DEPRECATED)

```javascript
// ========================================
// EXPORT FUNCTION - LEGACY (NO LONGER USED)
// ========================================
function exportPoints() {
    if (shapes.length === 0) { 
        alert('Keine Objekte vorhanden!'); 
        return; 
    }

    const exportData = {
        canvas: {
            width: actualCanvasWidth,
            height: actualCanvasHeight
        },
        objects: []
    };

    let totalPoints = 0;
    let filteredPoints = 0;

    for (let i = 0; i < shapes.length; i++) {
        const s = shapes[i];
        
        // Get points based on shape type
        const pts = (s.type === 'line') ? getLinePoints(s) : 
                    (s.type === 'arc') ? getArcPoints(s) : 
                    (s.type === 'freehand') ? getFreehandPoints(s) : 
                    getShapePoints(s);

        const points = [];
        
        pts.forEach((pt, j) => {
            // Transform local coordinates to world coordinates
            const [gx, gy] = localToWorld(s, pt[0], pt[1]);
            totalPoints++;
            
            // Only export points within canvas bounds
            if (gx >= 0 && gx < actualCanvasWidth && gy >= 0 && gy < actualCanvasHeight) {
                points.push({
                    id: j + 1,
                    x: Math.round(gx),
                    y: Math.round(gy)
                });
            } else {
                filteredPoints++;
            }
        });

        if (points.length > 0) {
            exportData.objects.push({
                id: s.id,
                points: points
            });
        }
    }

    // Show warning if points were filtered
    if (filteredPoints > 0) {
        showToast(`⚠️ ${filteredPoints} von ${totalPoints} Punkten außerhalb des Canvas wurden nicht exportiert`, 'warning');
    }

    // Create download
    const jsonString = JSON.stringify(exportData, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'punkte_export.json';
    a.click();
    URL.revokeObjectURL(url);
}
```

---

## 📊 Legacy Export Format

**File:** `data/punkte_export.json`

```json
{
  "canvas": {
    "width": 1920,
    "height": 1080
  },
  "objects": [
    {
      "id": "shape-1",
      "points": [
        {"id": 1, "x": 450, "y": 350},
        {"id": 2, "x": 470, "y": 350},
        {"id": 3, "x": 490, "y": 350}
      ]
    },
    {
      "id": "shape-2",
      "points": [
        {"id": 1, "x": 800, "y": 450},
        {"id": 2, "x": 815, "y": 462},
        {"id": 3, "x": 825, "y": 480}
      ]
    }
  ]
}
```

---

## 🔄 Dots Distribution Logic (STILL ACTIVE)

**These functions remain in `editor.js` and will be reused by Art-Net Output Routing page:**

### Main Point Generators

```javascript
/**
 * Get points for any shape type
 * @param {Object} s - Shape object
 * @returns {Array} Array of [x, y] local coordinates
 */
function getShapePoints(s) {
    // Use modular generators if available
    if (PointGenerators[s.type]) {
        return PointGenerators[s.type](s);
    }

    const pts = [];
    const count = Math.max(1, s.pointCount || 1);

    // Matrix - Grid of points
    if (s.type === 'matrix') {
        const rows = Math.max(1, s.rows || 1);
        const cols = Math.max(1, s.cols || 1);
        const half = s.size / 2;
        const pattern = s.pattern || 'zigzag-left';
        const tempPts = [];

        // Generate all points in a 2D array
        for (let r = 0; r < rows; r++) {
            tempPts[r] = [];
            const ty = rows === 1 ? 0.5 : (r / (rows - 1));
            const y = -half + ty * s.size;
            for (let c = 0; c < cols; c++) {
                const tx = cols === 1 ? 0.5 : (c / (cols - 1));
                const x = -half + tx * s.size;
                tempPts[r][c] = [x, y];
            }
        }

        // Apply wiring pattern
        if (pattern === 'zigzag-left') {
            for (let r = 0; r < rows; r++) {
                if (r % 2 === 0) {
                    for (let c = 0; c < cols; c++) pts.push(tempPts[r][c]);
                } else {
                    for (let c = cols - 1; c >= 0; c--) pts.push(tempPts[r][c]);
                }
            }
        } else if (pattern === 'zigzag-right') {
            for (let r = 0; r < rows; r++) {
                if (r % 2 === 0) {
                    for (let c = cols - 1; c >= 0; c--) pts.push(tempPts[r][c]);
                } else {
                    for (let c = 0; c < cols; c++) pts.push(tempPts[r][c]);
                }
            }
        } else if (pattern === 'zigzag-top') {
            for (let c = 0; c < cols; c++) {
                if (c % 2 === 0) {
                    for (let r = 0; r < rows; r++) pts.push(tempPts[r][c]);
                } else {
                    for (let r = rows - 1; r >= 0; r--) pts.push(tempPts[r][c]);
                }
            }
        } else if (pattern === 'zigzag-bottom') {
            for (let c = 0; c < cols; c++) {
                if (c % 2 === 0) {
                    for (let r = rows - 1; r >= 0; r--) pts.push(tempPts[r][c]);
                } else {
                    for (let r = 0; r < rows; r++) pts.push(tempPts[r][c]);
                }
            }
        } else if (pattern === 'snake') {
            for (let r = 0; r < rows; r++) {
                for (let c = 0; c < cols; c++) {
                    pts.push(tempPts[r][c]);
                }
            }
        }
        return pts;
    }

    // Circle - Points around circumference
    if (s.type === 'circle') {
        const radius = s.size / 2;
        for (let i = 0; i < count; i++) {
            const angle = (i / count) * Math.PI * 2;
            pts.push([Math.cos(angle) * radius, Math.sin(angle) * radius]);
        }
        return pts;
    }

    // Star - Points along star edges
    if (s.type === 'star') {
        const spikes = Math.max(2, s.spikes || 5);
        const outer = s.size / 2;
        const inner = outer * (s.innerRatio || 0.5);
        const verts = [];
        let rot = -Math.PI / 2;
        const step = Math.PI / spikes;
        
        for (let i = 0; i < spikes; i++) {
            verts.push([Math.cos(rot) * outer, Math.sin(rot) * outer]);
            rot += step;
            verts.push([Math.cos(rot) * inner, Math.sin(rot) * inner]);
            rot += step;
        }
        
        const edges = [];
        for (let i = 0; i < verts.length; i++) {
            edges.push([verts[i], verts[(i + 1) % verts.length]]);
        }
        return distributeAlongEdges(s, edges, count);
    }

    // Polygon - Points along polygon edges
    if (s.type === 'polygon') {
        const sides = Math.max(3, s.sides || 6);
        const radius = s.size / 2;
        const verts = [];
        const angleStep = (Math.PI * 2) / sides;
        let rot = -Math.PI / 2;
        
        for (let i = 0; i < sides; i++) {
            verts.push([Math.cos(rot) * radius, Math.sin(rot) * radius]);
            rot += angleStep;
        }
        
        const edges = [];
        for (let i = 0; i < verts.length; i++) {
            edges.push([verts[i], verts[(i + 1) % verts.length]]);
        }
        return distributeAlongEdges(s, edges, count);
    }

    return pts;
}

/**
 * Get points for line shapes
 */
function getLinePoints(s) {
    if (s.linePoints && s.linePoints.length > 0) {
        const pts = [];
        const totalPoints = Math.max(2, s.pointCount || s.linePoints.length);
        const segments = s.linePoints.length - 1;
        
        if (segments === 0) {
            return Array(totalPoints).fill([s.linePoints[0].x - s.size/2, s.linePoints[0].y - s.size/2]);
        }
        
        for (let i = 0; i < totalPoints; i++) {
            const t = i / (totalPoints - 1);
            const segmentFloat = t * segments;
            const segmentIndex = Math.min(Math.floor(segmentFloat), segments - 1);
            const segmentT = segmentFloat - segmentIndex;
            
            const p1 = s.linePoints[segmentIndex];
            const p2 = s.linePoints[segmentIndex + 1];
            
            const x = p1.x + segmentT * (p2.x - p1.x) - s.size / 2;
            const y = p1.y + segmentT * (p2.y - p1.y) - s.size / 2;
            
            pts.push([x, y]);
        }
        return pts;
    }
    
    const start = [-s.size / 2, 0], end = [s.size / 2, 0];
    const pts = [];
    const count = Math.max(2, s.pointCount || 2);
    for (let i = 0; i < count; i++) {
        const t = i / (count - 1);
        pts.push([start[0] + t * (end[0] - start[0]), 0]);
    }
    return pts;
}

/**
 * Get points for arc shapes (bezier curves)
 */
function getArcPoints(s) {
    const start = [-s.size / 2, 0], end = [s.size / 2, 0];
    const bez = t => {
        // Bezier curve implementation...
        // (Full implementation in editor.js)
    };
    
    const pts = [];
    const count = Math.max(2, s.pointCount || 10);
    for (let i = 0; i < count; i++) {
        const t = i / (count - 1);
        pts.push(bez(t));
    }
    return pts;
}

/**
 * Get points for freehand shapes
 */
function getFreehandPoints(s) {
    if (!s.freehandPoints || s.freehandPoints.length === 0) {
        return [[0, 0]];
    }
    
    const count = Math.max(2, s.pointCount || s.freehandPoints.length);
    return resampleFreehandPoints(s.freehandPoints, count);
}
```

### Helper Functions

```javascript
/**
 * Transform local shape coordinates to world coordinates
 * @param {Object} s - Shape object
 * @param {Number} lx - Local x coordinate
 * @param {Number} ly - Local y coordinate
 * @returns {Array} [x, y] world coordinates
 */
function localToWorld(s, lx, ly) {
    const cosA = Math.cos(s.rotation);
    const sinA = Math.sin(s.rotation);
    const sx = lx * s.scaleX;
    const sy = ly * s.scaleY;
    const x = s.x + (sx * cosA - sy * sinA);
    const y = s.y + (sx * sinA + sy * cosA);
    return [x, y];
}

/**
 * Distribute points evenly along a series of edges
 * @param {Object} s - Shape object
 * @param {Array} edges - Array of edge pairs [[p1, p2], ...]
 * @param {Number} count - Total points to distribute
 * @returns {Array} Array of [x, y] coordinates
 */
function distributeAlongEdges(s, edges, count) {
    if (edges.length === 0) return [];
    
    // Calculate total length
    let totalLen = 0;
    const lengths = edges.map(e => {
        const dx = e[1][0] - e[0][0];
        const dy = e[1][1] - e[0][1];
        const len = Math.sqrt(dx * dx + dy * dy);
        totalLen += len;
        return len;
    });
    
    const pts = [];
    for (let i = 0; i < count; i++) {
        const targetDist = (i / Math.max(1, count - 1)) * totalLen;
        let accumulated = 0;
        
        for (let j = 0; j < edges.length; j++) {
            const nextAccumulated = accumulated + lengths[j];
            if (targetDist <= nextAccumulated || j === edges.length - 1) {
                const t = lengths[j] > 0 ? (targetDist - accumulated) / lengths[j] : 0;
                const [p0, p1] = edges[j];
                const x = p0[0] + t * (p1[0] - p0[0]);
                const y = p0[1] + t * (p1[1] - p0[1]);
                pts.push([x, y]);
                break;
            }
            accumulated = nextAccumulated;
        }
    }
    
    return pts;
}
```

---

## 🔄 Migration Path

### OLD System (Editor exports dots):
```
1. User creates shapes in editor
2. User clicks "Export Points"
3. Frontend calculates dots
4. Downloads punkte_export.json
5. User manually uploads to backend
6. Backend loads dots for Art-Net output
```

### NEW System (Art-Net page generates dots):
```
1. User creates shapes in editor
2. Auto-saved to session state (shapes only)
3. User opens Art-Net Output Routing page
4. Frontend loads shapes from session
5. Frontend calculates dots using same logic
6. User maps dots to Art-Net universes
7. Auto-saved to output routing config
8. Backend uses routing config for Art-Net
```

---

## ✅ What Changes

| Component | OLD | NEW |
|-----------|-----|-----|
| **Editor** | Exports punkte_export.json | Only saves shape parameters |
| **Session State** | Not used | Stores editor.shapes[] |
| **Dots Calculation** | On export only | On-demand in Art-Net page |
| **punkte_export.json** | Required file | Deprecated (not generated) |
| **Art-Net Config** | Uses dots file | Uses shapes + calculates dots |

---

## 📦 Functions to Keep Active

**These stay in `editor.js` (needed for rendering):**
- ✅ `getShapePoints(s)` - Calculate dots for any shape
- ✅ `getLinePoints(s)` - Line/polyline dots
- ✅ `getArcPoints(s)` - Arc/bezier dots
- ✅ `getFreehandPoints(s)` - Freehand dots
- ✅ `localToWorld(s, lx, ly)` - Coordinate transformation
- ✅ `distributeAlongEdges(s, edges, count)` - Edge distribution helper
- ✅ `PointGenerators` object - Modular generators

**These will be deprecated:**
- ❌ `exportPoints()` - No longer exports JSON file
- ❌ Download functionality - Not needed

---

## 🎯 Next Steps

1. ✅ Document this logic (DONE - this file)
2. ⏳ Update CANVAS_EDITOR_SESSION_STATE_PLAN.md to remove output.artnet.objects
3. ⏳ Keep dots calculation functions active in editor.js
4. ⏳ Art-Net Output Routing page will import/reuse these functions
5. ⏳ Deprecate manual export button (or keep for legacy compatibility)

---

**End of Legacy Documentation**
