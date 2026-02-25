// ========================================
// IMPORTS
// ========================================
import { showToast, initErrorLogging, initWebSocket } from './common.js';
import { debug, loadDebugConfig } from './logger.js';

// ========================================
// TASTATUR-SHORTCUTS
// ========================================
// Entf/Backspace: Ausgewählte Form(en) löschen
// Strg+D: Ausgewählte Form(en) duplizieren
// Strg+S: Projekt speichern (lokal)

// Initialize error logging
initErrorLogging();

document.addEventListener('keydown', function(e) {
    // Fokus auf Input-Felder ignorieren
    if (document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA')) return;

    // Löschen
    if ((e.key === 'Delete' || e.key === 'Backspace') && (selectedShape || selectedShapes.length > 0)) {
        e.preventDefault();
        deleteSelectedShape();
    }
    // Duplizieren (Strg+D)
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'd' && (selectedShape || selectedShapes.length > 0)) {
        e.preventDefault();
        duplicateSelectedShape();
    }
    // Speichern (Strg+S)
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        saveProject();
        showToast('Projekt lokal gespeichert', 'success');
    }
});

// ========================================
// CONSTANTS & CONFIGURATION
// ========================================
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');

// Canvas overflow buffer (extra space around canvas for out-of-bounds objects)
const CANVAS_OVERFLOW = 500; // pixels of extra space on each side
let actualCanvasWidth = 1920; // The actual work area width
let actualCanvasHeight = 1080; // The actual work area height

// Scale limits
const MIN_SCALE = 0.3;
const MAX_SCALE = 10;

// Handle configuration
const HANDLE = {
    SIZE: 7,
    SIZE_OUTER: 11,  // Outer ring for rotation
    DISTANCE: 26,
    DISTANCE_Y: 50,
    DISTANCE_SCALE_Y: 50,
    HIT_RADIUS: 12,
    HIT_RADIUS_OUTER: 16,  // Outer ring hit detection
    CONTROL_RADIUS: 10,
    ICON_SIZE_MULTIPLIER: 3
};

// Colors
const COLORS = {
    CONNECTION_LINE: 'red',
    HANDLE_CORNER_FILL: 'rgba(0, 255, 255, 0.3)',
    HANDLE_CORNER_STROKE: 'cyan',
    HANDLE_ICON_TINT: 'cyan',
    HANDLE_FLIP_FALLBACK: '#9933ff',
    HANDLE_ROTATE_FALLBACK: 'orange',
    HANDLE_SCALE_Y_FALLBACK: 'lime',
    CONTROL_HANDLE_PRIMARY: 'green',
    CONTROL_HANDLE_SECONDARY: 'darkgreen',
    CONTROL_HANDLE_TERTIARY: 'forestgreen',
    POINT_FIRST: 'cyan',
    POINT_LAST: 'magenta',
    POINT_DEFAULT: 'blue',
    POINT_HOVER: 'yellow',
    TOOLTIP_BG: 'rgba(0, 0, 0, 0.8)',
    TOOLTIP_BORDER: 'yellow',
    TOOLTIP_TEXT: 'white',
    SHAPE_DEFAULT: 'cyan'
};

// Tooltip configuration
const TOOLTIP = {
    PADDING: 8,
    FONT_SIZE: 14,
    OFFSET_Y: 10,
    MIN_MARGIN: 5
};

// Point rendering
const POINT = {
    RADIUS: 3,
    HIT_RADIUS: 8
};

// ========================================
// GLOBAL STATE [Lines 263-272]
// ========================================
let shapes = [];
let selectedShape = null;
let selectedShapes = []; // Multiple selection support
let groups = []; // Groups of shapes
let groupCounter = 1;
let dragMode = null;
let offsetX = 0, offsetY = 0;
let shapeCounter = 1;
let needsRedraw = true;
let hoveredPoint = null; // For tooltip: {shape, pointIndex, x, y}
let hoveredHandle = null; // For handle hover feedback
let scaleHandleIndex = null;
let showConnectionLines = true; // Toggle for connection lines between objects
let dragStartX = 0, dragStartY = 0;
let dragStartRotation = 0;
let dragStartScaleX = 0, dragStartScaleY = 0;
let selectionBox = null; // For marquee selection: {startX, startY, endX, endY}
let backgroundImage = null;
let backgroundImagePath = null; // Path to current background image on server
let flipIconImage = null; // Bootstrap icon for flip handle
let rotateIconImage = null; // Bootstrap icon for rotate handle
let scaleYIconImage = null; // Bootstrap icon for Y-axis scale handle
let scaleXIconImage = null; // Bootstrap icon for X-axis scale handle

// Expose to window for external modules (e.g., led-mapper.js)
window.shapes = shapes;
window.shapeCounter = shapeCounter;
window.selectedShape = selectedShape;

// Canvas zoom and pan
let canvasZoom = 1.0;
let canvasOffsetX = 0;
let canvasOffsetY = 0;
let isPanning = false;
let panStartX = 0;
let panStartY = 0;

// Freehand drawing
let isFreehandMode = false;
let freehandPoints = [];
let isDrawing = false;

// Snapping features
let snapToGrid = true;
let snapToObjects = true;
let allowOutOfBounds = false;
let gridSize = 10;
let showGrid = true;
const SNAP_DISTANCE = 5; // Pixels threshold for object snapping
let snapLines = []; // Temporary snap guide lines: [{x1, y1, x2, y2, type}]

// Load flip icon
const flipIcon = new Image();
flipIcon.src = 'bootstrap-icons/symmetry-vertical.svg';
flipIcon.onload = function () {
    flipIconImage = flipIcon;
    markForRedraw();
};

// Load rotate icon
const rotateIcon = new Image();
rotateIcon.src = 'bootstrap-icons/arrow-clockwise.svg';
rotateIcon.onload = function () {
    rotateIconImage = rotateIcon;
    markForRedraw();
};

// Load scale Y icon
const scaleYIcon = new Image();
scaleYIcon.src = 'bootstrap-icons/arrows-vertical.svg';
scaleYIcon.onload = function () {
    scaleYIconImage = scaleYIcon;
    markForRedraw();
};

// Load scale X icon
const scaleXIcon = new Image();
scaleXIcon.src = 'bootstrap-icons/arrows.svg';
scaleXIcon.onload = function () {
    scaleXIconImage = scaleXIcon;
    markForRedraw();
};

// ========================================
// UTILITY FUNCTIONS [Lines 282-310]
// ========================================
function markForRedraw() { needsRedraw = true; }

function updateToolbarSections() {
    const matrixSection = document.getElementById('matrixSection');
    const starSection = document.getElementById('starSection');
    const polygonSection = document.getElementById('polygonSection');
    const arcSection = document.getElementById('arcSection');

    matrixSection.style.display = (selectedShape && selectedShape.type === 'matrix') ? 'block' : 'none';
    starSection.style.display = (selectedShape && selectedShape.type === 'star') ? 'block' : 'none';
    polygonSection.style.display = (selectedShape && selectedShape.type === 'polygon') ? 'block' : 'none';
    arcSection.style.display = (selectedShape && selectedShape.type === 'arc') ? 'block' : 'none';

    if (selectedShape) {
        if (selectedShape.type === 'matrix') {
            document.getElementById('matrixRows').value = selectedShape.rows;
            document.getElementById('matrixCols').value = selectedShape.cols;
            document.getElementById('matrixPattern').value = selectedShape.pattern || 'zigzag-left';
        } else if (selectedShape.type === 'star') {
            document.getElementById('starSpikes').value = selectedShape.spikes || 5;
        } else if (selectedShape.type === 'polygon') {
            document.getElementById('polygonSides').value = selectedShape.sides || 6;
        } else if (selectedShape.type === 'arc') {
            document.getElementById('arcControls').value = selectedShape.controlPoints || 1;
        }
    }
}

document.getElementById('canvasSize').addEventListener('change', e => {
    const value = e.target.value;
    const customWidth = document.getElementById('customWidth');
    const customHeight = document.getElementById('customHeight');
    const customApply = document.getElementById('customApply');
    
    if (value === 'custom') {
        // Show custom size inputs
        customWidth.style.display = 'inline-block';
        customHeight.style.display = 'inline-block';
        customApply.style.display = 'inline-block';
        customWidth.value = canvas.width;
        customHeight.value = canvas.height;
    } else {
        // Hide custom inputs and apply preset size
        customWidth.style.display = 'none';
        customHeight.style.display = 'none';
        customApply.style.display = 'none';
        const [w, h] = value.split('x').map(Number);
        setCanvasSize(w, h);
        markForRedraw(); 
        updateObjectList();
    }
});

function applyCustomCanvasSize() {
    const width = parseInt(document.getElementById('customWidth').value);
    const height = parseInt(document.getElementById('customHeight').value);
    
    if (!width || !height || width < 100 || width > 10000 || height < 100 || height > 10000) {
        showToast('Bitte geben Sie gültige Abmessungen ein (100-10000 Pixel)', 'warning');
        return;
    }
    
    setCanvasSize(width, height);
    markForRedraw();
    updateObjectList();
    
    showToast(`Canvas-Größe: ${width} × ${height}`, 'success');
}

function setCanvasSize(width, height) {
    actualCanvasWidth = width;
    actualCanvasHeight = height;
    
    if (allowOutOfBounds) {
        // Expand canvas to include overflow area
        canvas.width = width + (CANVAS_OVERFLOW * 2);
        canvas.height = height + (CANVAS_OVERFLOW * 2);
    } else {
        // Use exact size
        canvas.width = width;
        canvas.height = height;
    }
}

function updateCanvasOverflow() {
    // Reapply canvas size with current overflow setting
    setCanvasSize(actualCanvasWidth, actualCanvasHeight);
    markForRedraw();
}

// ========================================
// EVENT LISTENERS - UI Controls [Lines 311-415]
// ========================================

// Theme Toggle wird jetzt über menu-loader.js gehandhabt

// Connection lines toggle
document.getElementById('showConnectionLines').addEventListener('change', e => {
    showConnectionLines = e.target.checked;
    markForRedraw();
});

// Snapping controls
document.getElementById('snapToGrid').addEventListener('change', e => {
    snapToGrid = e.target.checked;
    markForRedraw();
});

document.getElementById('showGrid').addEventListener('change', e => {
    showGrid = e.target.checked;
    markForRedraw();
});

document.getElementById('gridSize').addEventListener('change', e => {
    gridSize = parseInt(e.target.value, 10);
    markForRedraw();
});

document.getElementById('snapToObjects').addEventListener('change', e => {
    snapToObjects = e.target.checked;
});

document.getElementById('allowOutOfBounds').addEventListener('change', e => {
    allowOutOfBounds = e.target.checked;
    updateCanvasOverflow();
});

document.getElementById('bgImageInput').addEventListener('change', e => {
    const file = e.target.files[0];
    if (file) {
        uploadBackground(file);
    }
});

function clearBackgroundImage() {
    backgroundImage = null;
    backgroundImagePath = null;
    document.getElementById('bgImageInput').value = '';
    markForRedraw();
    saveEditorStateToSession();
}

const pointCountInput = document.getElementById('pointCount');
const pointCountNumber = document.getElementById('pointCountNumber');

// Snap slider to 15-step increments on change (after release)
pointCountInput.addEventListener('change', e => {
    const rawValue = parseInt(e.target.value, 10);
    const snappedValue = Math.round(rawValue / 15) * 15;
    const finalValue = Math.max(2, Math.min(512, snappedValue));
    e.target.value = finalValue;
    pointCountNumber.value = finalValue;
    if (selectedShape && selectedShape.type !== 'matrix') {
        selectedShape.pointCount = finalValue;
        // Für Freihand-Formen: Punkte neu samplen
        if (selectedShape.type === 'freehand' && selectedShape.freehandPoints) {
            selectedShape.freehandPoints = resampleFreehandPoints(selectedShape.freehandPoints, finalValue);
        }
        markForRedraw(); updateObjectList();
    }
});

// Live update number display while dragging
pointCountInput.addEventListener('input', e => {
    const value = parseInt(e.target.value, 10);
    pointCountNumber.value = value;
});

pointCountNumber.addEventListener('input', e => {
    let value = parseInt(e.target.value, 10);
    if (isNaN(value)) return;
    value = Math.max(2, Math.min(512, value));
    pointCountInput.value = value;
    if (selectedShape && selectedShape.type !== 'matrix') {
        selectedShape.pointCount = value;
        // Für Freihand-Formen: Punkte neu samplen
        if (selectedShape.type === 'freehand' && selectedShape.freehandPoints) {
            selectedShape.freehandPoints = resampleFreehandPoints(selectedShape.freehandPoints, value);
        }
        markForRedraw(); updateObjectList();
    }
});

document.getElementById('matrixRows').addEventListener('input', e => {
    if (selectedShape && selectedShape.type === 'matrix') {
        selectedShape.rows = Math.max(1, Math.min(128, parseInt(e.target.value) || 1));
        markForRedraw(); updateObjectList();
    }
});
document.getElementById('matrixCols').addEventListener('input', e => {
    if (selectedShape && selectedShape.type === 'matrix') {
        selectedShape.cols = Math.max(1, Math.min(128, parseInt(e.target.value) || 1));
        markForRedraw(); updateObjectList();
    }
});
document.getElementById('matrixPattern').addEventListener('change', e => {
    if (selectedShape && selectedShape.type === 'matrix') {
        selectedShape.pattern = e.target.value;
        markForRedraw(); updateObjectList();
    }
});

document.getElementById('starSpikes').addEventListener('input', e => {
    if (selectedShape && selectedShape.type === 'star') {
        selectedShape.spikes = Math.max(2, Math.min(32, parseInt(e.target.value) || 5));
        markForRedraw(); updateObjectList();
    }
});

document.getElementById('polygonSides').addEventListener('input', e => {
    if (selectedShape && selectedShape.type === 'polygon') {
        selectedShape.sides = Math.max(3, Math.min(12, parseInt(e.target.value) || 6));
        markForRedraw(); updateObjectList();
    }
});

document.getElementById('arcControls').addEventListener('input', e => {
    if (selectedShape && selectedShape.type === 'arc') {
        const numControls = Math.max(1, Math.min(3, parseInt(e.target.value) || 1));
        selectedShape.controlPoints = numControls;
        // Initialize control points array
        if (!Array.isArray(selectedShape.controls)) {
            selectedShape.controls = [];
        }
        while (selectedShape.controls.length < numControls) {
            selectedShape.controls.push({ x: 0, y: -selectedShape.size / 2 - selectedShape.controls.length * 20 });
        }
        selectedShape.controls = selectedShape.controls.slice(0, numControls);
        markForRedraw(); updateObjectList();
    }
});

function addShape(type) {
    const shapeId = `shape-${shapeCounter++}`;
    
    // Update window reference
    window.shapeCounter = shapeCounter;
    const typeNames = {
        rect: 'Rechteck',
        circle: 'Kreis',
        triangle: 'Dreieck',
        polygon: 'Polygon',
        line: 'Linie',
        arc: 'Bogen',
        matrix: 'Matrix',
        star: 'Stern'
    };
    const base = {
        id: shapeId,
        name: typeNames[type] || type,
        type,
        x: 300, y: 200,
        size: 120,
        rotation: 0,
        scaleX: 1, scaleY: 1,
        color: 'cyan',
        pointCount: parseInt(pointCountInput.value, 10)
    };
    if (type === 'arc') {
        const numControls = Math.max(1, parseInt(document.getElementById('arcControls').value) || 1);
        base.controlPoints = numControls;
        base.controls = [];
        for (let i = 0; i < numControls; i++) {
            base.controls.push({ x: 0, y: -base.size / 2 - i * 20 });
        }
        // Keep old control for backwards compatibility
        base.control = base.controls[0];
    }
    if (type === 'matrix') {
        base.rows = Math.max(1, parseInt(document.getElementById('matrixRows').value) || 4);
        base.cols = Math.max(1, parseInt(document.getElementById('matrixCols').value) || 4);
        base.pattern = document.getElementById('matrixPattern').value || 'zigzag-left';
        base.scaleX = base.scaleY = 1;
    }
    // neu: Stern-spezifische Defaults
    if (type === 'star') {
        base.spikes = Math.max(2, parseInt(document.getElementById('starSpikes').value) || 5);
        base.innerRatio = 0.5; // inner radius as ratio of outer radius
    }
    // Polygon-spezifische Defaults
    if (type === 'polygon') {
        base.sides = Math.max(3, parseInt(document.getElementById('polygonSides').value) || 6);
    }
    shapes.push(base);
    selectedShape = base;
    updateToolbarSections();
    markForRedraw(); updateObjectList();
    saveEditorStateToSession();  // Auto-save
}

// ========================================
// SHAPE OPERATIONS [Lines 435-490]
// ========================================
function resetSelectedShape() {
    const shapesToReset = selectedShapes.length > 0 ? selectedShapes : (selectedShape ? [selectedShape] : []);

    if (shapesToReset.length === 0) {
        showToast('Keine Form ausgewählt!', 'warning');
        return;
    }

    for (const s of shapesToReset) {
        s.rotation = 0;
        s.scaleX = 1;
        s.scaleY = 1;
        s.size = 120;
        if (s.type === 'arc') {
            if (s.controls && s.controls.length > 0) {
                for (let i = 0; i < s.controls.length; i++) {
                    s.controls[i] = { x: 0, y: -s.size / 2 - i * 20 };
                }
                s.control = s.controls[0];
            } else {
                s.control = { x: 0, y: -s.size / 2 };
            }
        }
        if (s.type === 'star') {
            s.innerRatio = 0.5;
        }
    }

    showToast('Form(en) zurückgesetzt', 'success');
    markForRedraw(); updateObjectList();
    saveEditorStateToSession();  // Auto-save
}

function selectAllShapes() {
    if (shapes.length === 0) { alert('Keine Objekte vorhanden!'); return; }
    selectedShapes = [...shapes];
    selectedShape = shapes[shapes.length - 1]; // Keep single selection for compatibility
    updateToolbarSections();
    markForRedraw();
    updateObjectList();
}

function deleteSelectedShape() {
    if (selectedShapes.length > 0) {
        // Delete all selected shapes
        shapes = shapes.filter(s => !selectedShapes.includes(s));
        selectedShape = null;
        selectedShapes = [];
    } else if (selectedShape) {
        // Delete single selected shape
        shapes = shapes.filter(s => s !== selectedShape);
        selectedShape = null;
    } else {
        showToast('Keine Form ausgewählt!', 'warning');
        return;
    }
    updateToolbarSections();
    markForRedraw(); updateObjectList();
    saveEditorStateToSession();  // Auto-save
}

function fitToCanvas() {
    const shapesToFit = selectedShapes.length > 0 ? selectedShapes : (selectedShape ? [selectedShape] : []);

    if (shapesToFit.length === 0) {
        showToast('Keine Form ausgewählt!', 'warning');
        return;
    }

    for (const s of shapesToFit) {
        // Position in center of canvas
        s.x = canvas.width / 2;
        s.y = canvas.height / 2;
        
        // Calculate required scale to fit canvas (asymmetric)
        // Scale X to fit canvas width
        const scaleX = canvas.width / s.size;
        // Scale Y to fit canvas height
        const scaleY = canvas.height / s.size;
        
        s.scaleX = scaleX;
        s.scaleY = scaleY;
    }

    showToast(`${shapesToFit.length} Form(en) an Canvas angepasst`, 'success');
    markForRedraw();
    updateObjectList();
    saveEditorStateToSession();  // Auto-save
}

function duplicateSelectedShape() {
    const shapesToDuplicate = selectedShapes.length > 0 ? selectedShapes : (selectedShape ? [selectedShape] : []);

    if (shapesToDuplicate.length === 0) {
        showToast('Keine Form ausgewählt!', 'warning');
        return;
    }

    const newShapes = [];

    for (const s of shapesToDuplicate) {
        // Create a deep copy of the shape
        const duplicate = JSON.parse(JSON.stringify(s));

        // Give it a new ID
        duplicate.id = `shape-${shapeCounter++}`;

        // Offset the position: 20px right and 20px down
        duplicate.x += 20;
        duplicate.y += 20;

        // Add to shapes array
        shapes.push(duplicate);
        newShapes.push(duplicate);
    }

    // Select the duplicated shapes
    if (newShapes.length === 1) {
        selectedShape = newShapes[0];
        selectedShapes = [];
    } else {
        selectedShapes = newShapes;
        selectedShape = newShapes[newShapes.length - 1];
    }

    updateToolbarSections();
    markForRedraw();
    updateObjectList();
    saveEditorStateToSession();  // Auto-save
}

// ========================================
// FREEHAND DRAWING [Freihand-Zeichnen]
// ========================================
function toggleFreehandDrawing() {
    isFreehandMode = !isFreehandMode;
    const btn = document.getElementById('freehandBtn');
    
    if (isFreehandMode) {
        btn.classList.remove('btn-warning');
        btn.classList.add('btn-success');
        selectedShape = null;
        selectedShapes = [];
        canvas.style.cursor = 'crosshair';
        showToast('Freihand-Modus aktiviert. Zeichnen Sie mit der Maus.', 'info');
    } else {
        btn.classList.remove('btn-success');
        btn.classList.add('btn-warning');
        canvas.style.cursor = 'default';
        showToast('Freihand-Modus deaktiviert', 'info');
    }
    
    markForRedraw();
    updateObjectList();
}

function startFreehandDrawing(mx, my) {
    isDrawing = true;
    freehandPoints = [{ x: mx, y: my }];
}

function continueFreehandDrawing(mx, my) {
    if (!isDrawing) return;
    
    const lastPoint = freehandPoints[freehandPoints.length - 1];
    const distance = Math.sqrt(Math.pow(mx - lastPoint.x, 2) + Math.pow(my - lastPoint.y, 2));
    
    // Only add point if moved at least 2 pixels (to reduce clutter)
    if (distance > 2) {
        freehandPoints.push({ x: mx, y: my });
        markForRedraw();
    }
}

function finishFreehandDrawing() {
    if (!isDrawing || freehandPoints.length < 2) {
        isDrawing = false;
        freehandPoints = [];
        return;
    }
    
    isDrawing = false;
    
    // Calculate bounding box
    const minX = Math.min(...freehandPoints.map(p => p.x));
    const maxX = Math.max(...freehandPoints.map(p => p.x));
    const minY = Math.min(...freehandPoints.map(p => p.y));
    const maxY = Math.max(...freehandPoints.map(p => p.y));
    
    const width = maxX - minX;
    const height = maxY - minY;
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    
    // Convert absolute coordinates to relative (centered around origin)
    const relativePoints = freehandPoints.map(p => ({
        x: p.x - centerX,
        y: p.y - centerY
    }));
    
    // Get desired point count from slider
    const desiredPointCount = parseInt(pointCountInput.value, 10) || freehandPoints.length;
    
    // Resample points to match desired count
    const resampledPoints = resampleFreehandPoints(relativePoints, desiredPointCount);
    
    // Create a new freehand shape
    const freehandShape = {
        id: `shape-${shapeCounter++}`,
        type: 'freehand',
        name: `Freihand ${shapeCounter - 1}`,
        x: centerX,
        y: centerY,
        size: Math.max(width, height),
        rotation: 0,
        scaleX: 1,
        scaleY: 1,
        color: 'cyan',
        pointCount: desiredPointCount,
        freehandPoints: resampledPoints
    };
    
    shapes.push(freehandShape);
    selectedShape = freehandShape;
    freehandPoints = [];
    
    // Deaktiviere Freihand-Modus nach jeder Zeichnung
    isFreehandMode = false;
    const btn = document.getElementById('freehandBtn');
    btn.classList.remove('btn-success');
    btn.classList.add('btn-warning');
    canvas.style.cursor = 'default';
    
    showToast(`Freihand-Form mit ${desiredPointCount} Punkten erstellt`, 'success');
    markForRedraw();
    updateObjectList();
}

// ========================================
// PROJECT SAVE/LOAD [Lines 493-535]
// ========================================
function saveProject() {
    const projectName = document.getElementById('projectName').value || 'Mein Projekt';
    const timestamp = new Date().toISOString();

    // Convert background image to base64 if present
    let bgImageData = null;
    if (backgroundImage) {
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = backgroundImage.width;
        tempCanvas.height = backgroundImage.height;
        const tempCtx = tempCanvas.getContext('2d');
        tempCtx.drawImage(backgroundImage, 0, 0);
        bgImageData = tempCanvas.toDataURL('image/png');
    }

    const projectData = {
        projectName: projectName,
        version: '1.1',
        savedAt: timestamp,
        canvas: {
            width: canvas.width,
            height: canvas.height
        },
        backgroundImage: bgImageData,
        settings: {
            snapToGrid: snapToGrid,
            snapToObjects: snapToObjects,
            allowOutOfBounds: allowOutOfBounds,
            gridSize: gridSize,
            showGrid: showGrid,
            showConnectionLines: showConnectionLines
        },
        shapes: shapes.map(s => ({
            type: s.type,
            name: s.name,
            id: s.id,
            x: s.x,
            y: s.y,
            size: s.size,
            rotation: s.rotation,
            scaleX: s.scaleX,
            scaleY: s.scaleY,
            color: s.color,
            pointCount: s.pointCount,
            rows: s.rows,
            cols: s.cols,
            rowSpacing: s.rowSpacing,
            colSpacing: s.colSpacing,
            spikes: s.spikes,
            innerRatio: s.innerRatio,
            control: s.control,
            controls: s.controls,
            controlPoints: s.controlPoints,
            freehandPoints: s.freehandPoints
        }))
    };

    const blob = new Blob([JSON.stringify(projectData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${projectName.replace(/[^a-z0-9]/gi, '_')}_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast('Projekt lokal gespeichert', 'success');
}

// Save project to server
async function saveProjectToServer() {
    const projectName = document.getElementById('projectName').value || 'Mein Projekt';
    const timestamp = new Date().toISOString();

    // Convert background image to base64 if present
    let bgImageData = null;
    if (backgroundImage) {
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = backgroundImage.width;
        tempCanvas.height = backgroundImage.height;
        const tempCtx = tempCanvas.getContext('2d');
        tempCtx.drawImage(backgroundImage, 0, 0);
        bgImageData = tempCanvas.toDataURL('image/png');
    }

    const projectData = {
        projectName: projectName,
        version: '1.0',
        savedAt: timestamp,
        canvas: {
            width: canvas.width,
            height: canvas.height
        },
        backgroundImage: bgImageData,
        shapes: shapes.map(s => ({
            type: s.type,
            name: s.name,
            id: s.id,
            x: s.x,
            y: s.y,
            size: s.size,
            rotation: s.rotation,
            scaleX: s.scaleX,
            scaleY: s.scaleY,
            color: s.color,
            pointCount: s.pointCount,
            rows: s.rows,
            cols: s.cols,
            rowSpacing: s.rowSpacing,
            colSpacing: s.colSpacing,
            spikes: s.spikes,
            innerRatio: s.innerRatio,
            control: s.control,
            controls: s.controls,
            controlPoints: s.controlPoints,
            freehandPoints: s.freehandPoints
        }))
    };

    try {
        const response = await fetch('/api/projects/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(projectData)
        });

        // Check if response is OK
        if (!response.ok) {
            const text = await response.text();
            throw new Error(`Server error (${response.status}): ${text.substring(0, 100)}`);
        }

        const result = await response.json();
        
        if (result.success) {
            showToast(result.message, 'success');
        } else {
            showToast(`Fehler beim Speichern: ${result.error}`, 'error');
        }
    } catch (error) {
        console.error('Error saving project to server:', error);
        showToast(`Fehler beim Speichern: ${error.message}`, 'error', 5000);
    }
}

// Initialize project manager modal
let projectManagerModal = null;

function initializeProjectModal() {
    if (!window.ModalManager) {
        debug.warn('⚠️ ModalManager not loaded yet, retrying...');
        setTimeout(initializeProjectModal, 100);
        return;
    }
    
    projectManagerModal = ModalManager.create({
        id: 'projectManagerModal',
        title: '📂 Projektverwaltung',
        content: '<div class="text-center py-4"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Lädt...</span></div></div>',
        size: 'lg',
        buttons: [
            {
                label: 'Schließen',
                class: 'btn btn-secondary',
                callback: (modal) => modal.hide()
            }
        ],
        onShow: () => refreshProjectList()
    });
    
    debug.log('✅ Project manager modal initialized');
}

// Call initialization when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeProjectModal);
} else {
    initializeProjectModal();
}

// Show project manager modal
function showProjectManager() {
    if (!projectManagerModal) {
        console.error('❌ Project manager modal not initialized');
        return;
    }
    
    projectManagerModal.show();
}

// Refresh project list
async function refreshProjectList() {
    if (!projectManagerModal) {
        console.error('❌ Project manager modal not initialized');
        return;
    }
    
    projectManagerModal.showLoading('Lädt Projekte...');

    try {
        const response = await fetch('/api/projects');
        const result = await response.json();

        if (result.success && result.projects.length > 0) {
            let html = '<div class="list-group">';
            
            for (const project of result.projects) {
                const date = new Date(project.savedAt).toLocaleString('de-DE');
                const size = (project.size / 1024).toFixed(1);
                
                html += `
                    <div class="list-group-item">
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="flex-grow-1">
                                <h6 class="mb-1">${escapeHtml(project.projectName)}</h6>
                                <small class="text-muted">
                                    ${date} • ${project.shapeCount} Objekte • ${size} KB
                                </small>
                            </div>
                            <div class="btn-group btn-group-sm" role="group">
                                <button class="btn btn-primary" onclick="loadProjectFromServer('${project.filename}')" title="Laden">
                                    📂 Laden
                                </button>
                                <button class="btn btn-info" onclick="downloadProjectFromServer('${project.filename}')" title="Herunterladen">
                                    ⬇️
                                </button>
                                <button class="btn btn-danger" onclick="deleteProjectFromServer('${project.filename}')" title="Löschen">
                                    🗑️
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            html += '</div>';
            
            // Add refresh button at the top
            const contentHtml = `
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h6>Gespeicherte Projekte</h6>
                    <button class="btn btn-primary btn-sm" onclick="refreshProjectList()" title="Aktualisieren">🔄</button>
                </div>
                ${html}
            `;
            
            projectManagerModal.setContent(contentHtml);
        } else {
            projectManagerModal.setContent('<div class="alert alert-info">Keine gespeicherten Projekte gefunden.</div>');
        }
    } catch (error) {
        console.error('Error loading projects:', error);
        projectManagerModal.setContent(`<div class="alert alert-danger">Fehler beim Laden: ${error.message}</div>`);
    }
}

// Load project from server
async function loadProjectFromServer(filename) {
    try {
        const response = await fetch(`/api/projects/load/${filename}`);
        const result = await response.json();

        if (result.success) {
            loadProject(result.data);
            projectManagerModal?.hide();
            showToast('Projekt geladen', 'success');
        } else {
            showToast(`Fehler beim Laden: ${result.error}`, 'error');
        }
    } catch (error) {
        console.error('Error loading project:', error);
        showToast(`Fehler beim Laden: ${error.message}`, 'error');
    }
}

// Download project from server
async function downloadProjectFromServer(filename) {
    try {
        window.location.href = `/api/projects/download/${filename}`;
    } catch (error) {
        console.error('Error downloading project:', error);
        showToast(`Fehler beim Herunterladen: ${error.message}`, 'error');
    }
}

// Delete project from server
async function deleteProjectFromServer(filename) {
    if (!confirm(`Projekt "${filename}" wirklich löschen?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/projects/delete/${filename}`, {
            method: 'DELETE'
        });
        const result = await response.json();

        if (result.success) {
            showToast('Projekt gelöscht', 'success');
            await refreshProjectList();
        } else {
            showToast(`Fehler beim Löschen: ${result.error}`, 'error');
        }
    } catch (error) {
        console.error('Error deleting project:', error);
        showToast(`Fehler beim Löschen: ${error.message}`, 'error');
    }
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function loadProject(projectData) {
    try {
        // Reset current state
        shapes = [];
        selectedShape = null;
        selectedShapes = [];
        backgroundImage = null;
        shapeCounter = 1;

        // Set canvas size
        if (projectData.canvas) {
            setCanvasSize(projectData.canvas.width, projectData.canvas.height);

            // Update canvas size dropdown
            const sizeSelect = document.getElementById('canvasSize');
            const sizeValue = `${projectData.canvas.width}x${projectData.canvas.height}`;
            if ([...sizeSelect.options].some(opt => opt.value === sizeValue)) {
                sizeSelect.value = sizeValue;
            }
        }

        // Load background image
        if (projectData.backgroundImage) {
            const img = new Image();
            img.onload = () => {
                backgroundImage = img;
                markForRedraw();
            };
            img.src = projectData.backgroundImage;
        }

        // Load shapes
        if (projectData.shapes && Array.isArray(projectData.shapes)) {
            projectData.shapes.forEach(shapeData => {
                const s = {
                    type: shapeData.type,
                    name: shapeData.name || `Shape ${shapeCounter++}`,
                    id: shapeData.id || `shape-${shapeCounter}`,
                    x: shapeData.x || 0,
                    y: shapeData.y || 0,
                    size: shapeData.size || 120,
                    rotation: shapeData.rotation || 0,
                    scaleX: shapeData.scaleX || 1,
                    scaleY: shapeData.scaleY || 1,
                    color: shapeData.color || '#000',
                    pointCount: shapeData.pointCount || 30
                };

                // Type-specific properties
                if (shapeData.type === 'matrix') {
                    s.rows = shapeData.rows || 3;
                    s.cols = shapeData.cols || 3;
                    s.rowSpacing = shapeData.rowSpacing || 50;
                    s.colSpacing = shapeData.colSpacing || 50;
                }
                if (shapeData.type === 'star') {
                    s.spikes = shapeData.spikes || 5;
                    s.innerRatio = shapeData.innerRatio || 0.5;
                }
                if (shapeData.type === 'arc') {
                    s.controlPoints = shapeData.controlPoints || 1;
                    s.controls = shapeData.controls || [{ x: 0, y: -s.size / 2 }];
                    s.control = shapeData.control || s.controls[0];
                }
                if (shapeData.type === 'freehand') {
                    s.freehandPoints = shapeData.freehandPoints || [];
                }

                shapes.push(s);
            });
        }

        // Update project name if provided
        if (projectData.projectName) {
            document.getElementById('projectName').value = projectData.projectName;
        }

        // Load settings if available
        if (projectData.settings) {
            snapToGrid = projectData.settings.snapToGrid || false;
            snapToObjects = projectData.settings.snapToObjects || false;
            allowOutOfBounds = projectData.settings.allowOutOfBounds || false;
            gridSize = projectData.settings.gridSize || 10;
            showGrid = projectData.settings.showGrid || false;
            showConnectionLines = projectData.settings.showConnectionLines !== undefined ? projectData.settings.showConnectionLines : true;
            
            // Update UI
            document.getElementById('snapToGrid').checked = snapToGrid;
            document.getElementById('snapToObjects').checked = snapToObjects;
            document.getElementById('allowOutOfBounds').checked = allowOutOfBounds;
            document.getElementById('gridSize').value = gridSize;
            document.getElementById('showGrid').checked = showGrid;
            document.getElementById('showConnectionLines').checked = showConnectionLines;
        }

        markForRedraw();
        updateObjectList();
        updateToolbarSections();

        showToast(`Projekt "${projectData.projectName || 'Unbenannt'}" geladen`, 'success');
    } catch (error) {
        showToast('Fehler beim Laden des Projekts: ' + error.message, 'error');
        console.error(error);
    }
}

// ========================================
// EXPORT FUNCTION [Lines 600-650]
// ========================================
function exportPoints() {
    if (shapes.length === 0) { alert('Keine Objekte vorhanden!'); return; }

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
        const pts = (s.type === 'line') ? getLinePoints(s) : 
                    (s.type === 'arc') ? getArcPoints(s) : 
                    (s.type === 'freehand') ? getFreehandPoints(s) : 
                    getShapePoints(s);

        const points = [];
        
        pts.forEach((pt, j) => {
            const [gx, gy] = localToWorld(s, pt[0], pt[1]);
            totalPoints++;
            
            // Only export points within work area bounds
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

// ========================================
// SESSION STATE AUTO-SAVE
// ========================================
const AUTO_SAVE_DELAY = 1000; // 1 second debounce

/**
 * Save current editor state to backend session state
 */
async function saveEditorStateToSession() {
    const editorState = {
        version: '2.0',
        canvas: {
            width: actualCanvasWidth,
            height: actualCanvasHeight
        },
        backgroundImagePath: backgroundImagePath || null,
        viewport: {
            zoom: canvasZoom,
            offsetX: canvasOffsetX,
            offsetY: canvasOffsetY
        },
        selection: {
            selectedShapeIds: selectedShapes.map(s => s.id),
            primaryShapeId: selectedShape ? selectedShape.id : null
        },
        settings: {
            snapToGrid: snapToGrid,
            snapToObjects: snapToObjects,
            allowOutOfBounds: allowOutOfBounds,
            gridSize: gridSize,
            showGrid: showGrid,
            showConnectionLines: showConnectionLines
        },
        shapes: shapes.map(s => ({
            id: s.id,
            alias: s.alias,
            type: s.type,
            name: s.name,
            x: Math.round(s.x),
            y: Math.round(s.y),
            size: s.size,
            rotation: s.rotation,
            scaleX: s.scaleX,
            scaleY: s.scaleY,
            color: s.color,
            pointCount: s.pointCount,
            rows: s.rows,
            cols: s.cols,
            rowSpacing: s.rowSpacing,
            colSpacing: s.colSpacing,
            pattern: s.pattern,
            spikes: s.spikes,
            innerRatio: s.innerRatio,
            sides: s.sides,
            control: s.control,
            controls: s.controls,
            controlPoints: s.controlPoints,
            freehandPoints: s.freehandPoints
        })),
        groups: groups,
        savedAt: new Date().toISOString()
    };

    try {
        await window.sessionStateManager.saveEditor(editorState, {
            debounce: AUTO_SAVE_DELAY,
            onStatusChange: updateAutoSaveStatus
        });
    } catch (error) {
        console.error('Save failed:', error);
        updateAutoSaveStatus('error');
    }
}

/**
 * Update auto-save status badge
 */
function updateAutoSaveStatus(status) {
    const badge = document.getElementById('autoSaveStatus');
    if (!badge) return;
    
    switch (status) {
        case 'saving':
            badge.className = 'badge bg-warning';
            badge.textContent = '⏳ Speichert...';
            break;
        case 'saved':
            badge.className = 'badge bg-success';
            badge.textContent = '✓ Gespeichert';
            break;
        case 'error':
            badge.className = 'badge bg-danger';
            badge.textContent = '❌ Fehler';
            break;
    }
}

/**
 * Load editor state from session on page load
 */
async function loadEditorStateFromSession() {
    try {
        // Ensure sessionStateManager exists
        if (!window.sessionStateManager) {
            console.error('SessionStateManager not available - cannot restore state');
            return;
        }
        
        // Wait for session state to be fully loaded
        await window.sessionStateManager.load();
        
        const state = window.sessionStateManager.get('editor');
        if (!state) {
            console.debug('No editor state found - using defaults');
            // Set dropdown to match default canvas size
            const sizeSelect = document.getElementById('canvasSize');
            const defaultSize = `${actualCanvasWidth}x${actualCanvasHeight}`;
            if ([...sizeSelect.options].some(opt => opt.value === defaultSize)) {
                sizeSelect.value = defaultSize;
            }
            // Auto-fit and center canvas on fresh start
            fitCanvasToViewport();
            return;
        }

        // Restore canvas size
        if (state.canvas) {
            setCanvasSize(state.canvas.width, state.canvas.height);
            
            const sizeSelect = document.getElementById('canvasSize');
            const sizeValue = `${state.canvas.width}x${state.canvas.height}`;
            if ([...sizeSelect.options].some(opt => opt.value === sizeValue)) {
                sizeSelect.value = sizeValue;
            } else {
                sizeSelect.value = 'custom';
                document.getElementById('customWidth').value = state.canvas.width;
                document.getElementById('customHeight').value = state.canvas.height;
            }
        }

        // Restore background image
        if (state.backgroundImagePath) {
            backgroundImagePath = state.backgroundImagePath;
            const img = new Image();
            img.onload = () => {
                backgroundImage = img;
                markForRedraw();
            };
            img.src = '/' + state.backgroundImagePath;
        }
        
        // Restore settings
        if (state.settings) {
            snapToGrid = state.settings.snapToGrid ?? true;
            snapToObjects = state.settings.snapToObjects ?? true;
            allowOutOfBounds = state.settings.allowOutOfBounds ?? false;
            gridSize = state.settings.gridSize ?? 10;
            showGrid = state.settings.showGrid ?? true;
            showConnectionLines = state.settings.showConnectionLines ?? true;
            
            const snapToGridEl = document.getElementById('snapToGrid');
            const snapToObjectsEl = document.getElementById('snapToObjects');
            const allowOutOfBoundsEl = document.getElementById('allowOutOfBounds');
            const gridSizeEl = document.getElementById('gridSize');
            const showGridEl = document.getElementById('showGrid');
            const showConnectionLinesEl = document.getElementById('showConnectionLines');
            
            if (snapToGridEl) snapToGridEl.checked = snapToGrid;
            if (snapToObjectsEl) snapToObjectsEl.checked = snapToObjects;
            if (allowOutOfBoundsEl) allowOutOfBoundsEl.checked = allowOutOfBounds;
            if (gridSizeEl) gridSizeEl.value = gridSize;
            if (showGridEl) showGridEl.checked = showGrid;
            if (showConnectionLinesEl) showConnectionLinesEl.checked = showConnectionLines;
        }
        
        // Restore shapes
        if (state.shapes) {
            shapes = state.shapes;
            // Update window reference to new shapes array
            window.shapes = shapes;
            // Migrate shapes without names
            shapes.forEach(s => {
                if (!s.name) {
                    const typeNames = {
                        rect: 'Rechteck',
                        circle: 'Kreis',
                        triangle: 'Dreieck',
                        polygon: 'Polygon',
                        line: 'Linie',
                        arc: 'Bogen',
                        matrix: 'Matrix',
                        star: 'Stern',
                        freehand: 'Freihand'
                    };
                    s.name = typeNames[s.type] || s.id;
                }
            });
            shapeCounter = Math.max(...shapes.map(s => parseInt(s.id.split('-')[1]) || 0), 0) + 1;
            // Update window shapeCounter reference
            window.shapeCounter = shapeCounter;
        }
        
        // Restore groups
        if (state.groups) {
            groups = state.groups;
            groupCounter = groups.length + 1;
        }
        
        // Restore viewport (zoom and pan)
        if (state.viewport) {
            canvasZoom = state.viewport.zoom ?? 1.0;
            canvasOffsetX = state.viewport.offsetX ?? 0;
            canvasOffsetY = state.viewport.offsetY ?? 0;
            updateCanvasSize();
            updateZoomDisplay();
        } else {
            // No saved viewport - auto-fit and center the canvas
            fitCanvasToViewport();
        }
        
        // Restore selection state
        if (state.selection) {
            // Restore multi-selection
            if (state.selection.selectedShapeIds && state.selection.selectedShapeIds.length > 0) {
                selectedShapes = shapes.filter(s => state.selection.selectedShapeIds.includes(s.id));
            }
            // Restore primary selection
            if (state.selection.primaryShapeId) {
                const primaryShape = shapes.find(s => s.id === state.selection.primaryShapeId);
                if (primaryShape) {
                    selectedShape = primaryShape;
                }
            }
        }
        
        markForRedraw();
        updateObjectList();
        updateProjectStats();
        
        console.log('✅ Editor state loaded from session');
        showToast('Editor state restored', 'success');
        
    } catch (error) {
        console.error('Failed to load editor state:', error);
    }
}

/**
 * Upload background image
 */
async function uploadBackground(file) {
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/api/backgrounds/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            backgroundImagePath = result.path;
            
            // Load and display image
            const img = new Image();
            img.onload = () => {
                backgroundImage = img;
                markForRedraw();
                showToast(`Background uploaded: ${result.filename}`, 'success');
                saveEditorStateToSession();
            };
            img.src = '/' + result.path;
        } else {
            showToast(`Upload failed: ${result.error}`, 'error');
        }
        
    } catch (error) {
        console.error('Background upload error:', error);
        showToast('Upload error', 'error');
    }
}

// Call on page load
window.addEventListener('load', () => {
    // Initialize WebSocket for LED Mapper and other features
    initWebSocket({});
    
    loadEditorStateFromSession();
});

// ========================================
// DRAWING FUNCTIONS [Lines 544-640]
// ========================================
function draw() {
    if (!needsRedraw) return;
    needsRedraw = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Calculate offset for centered work area
    const offsetX = allowOutOfBounds ? CANVAS_OVERFLOW : 0;
    const offsetY = allowOutOfBounds ? CANVAS_OVERFLOW : 0;

    // Draw overflow area (dimmed background)
    if (allowOutOfBounds) {
        ctx.save();
        ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.restore();
        
        // Draw work area background
        ctx.save();
        ctx.fillStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.fillRect(offsetX, offsetY, actualCanvasWidth, actualCanvasHeight);
        ctx.restore();
    }

    // Draw background image if present
    if (backgroundImage) {
        ctx.save();
        ctx.drawImage(backgroundImage, offsetX, offsetY, actualCanvasWidth, actualCanvasHeight);
        ctx.restore();
    }
    
    // Draw grid if enabled (only in work area)
    if (showGrid && gridSize > 0) {
        ctx.save();
        ctx.strokeStyle = 'rgba(100, 100, 100, 0.3)';
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 2]);
        
        // Vertical lines
        for (let x = 0; x <= actualCanvasWidth; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x + offsetX, offsetY);
            ctx.lineTo(x + offsetX, offsetY + actualCanvasHeight);
            ctx.stroke();
        }
        
        // Horizontal lines
        for (let y = 0; y <= actualCanvasHeight; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(offsetX, y + offsetY);
            ctx.lineTo(offsetX + actualCanvasWidth, y + offsetY);
            ctx.stroke();
        }
        
        ctx.setLineDash([]);
        ctx.restore();
    }
    
    // Draw canvas boundary (work area)
    ctx.save();
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.8)';
    ctx.lineWidth = 3;
    ctx.strokeRect(offsetX, offsetY, actualCanvasWidth, actualCanvasHeight);
    ctx.restore();

    // Apply transform for overflow mode
    ctx.save();
    if (allowOutOfBounds) {
        ctx.translate(offsetX, offsetY);
    }

    for (const s of shapes) {
        // Check if shape is out of bounds (relative to work area)
        const halfW = (s.size * Math.abs(s.scaleX)) / 2;
        const halfH = (s.size * Math.abs(s.scaleY)) / 2;
        const isOutOfBounds = s.x - halfW < 0 || s.x + halfW > actualCanvasWidth || 
                              s.y - halfH < 0 || s.y + halfH > actualCanvasHeight;
        
        ctx.save();
        
        // Tint out-of-bounds shapes differently
        if (isOutOfBounds && allowOutOfBounds) {
            ctx.globalAlpha = 0.5;
        }
        
        ctx.translate(s.x, s.y);
        ctx.rotate(s.rotation);
        ctx.scale(s.scaleX, s.scaleY);
        ctx.strokeStyle = isOutOfBounds ? '#ff6b6b' : s.color; // Red tint for out-of-bounds
        ctx.lineWidth = 2 / Math.max(s.scaleX, s.scaleY);

        if (s.type === 'rect') ctx.strokeRect(-s.size / 2, -s.size / 2, s.size, s.size);
        else if (s.type === 'circle') { ctx.beginPath(); ctx.arc(0, 0, s.size / 2, 0, Math.PI * 2); ctx.stroke(); }
        else if (s.type === 'triangle') { ctx.beginPath(); ctx.moveTo(-s.size / 2, s.size / 2); ctx.lineTo(s.size / 2, s.size / 2); ctx.lineTo(0, -s.size / 2); ctx.closePath(); ctx.stroke(); }
        else if (s.type === 'line') {
            ctx.beginPath();
            if (s.linePoints && s.linePoints.length > 0) {
                // Polyline from text tool
                ctx.moveTo(s.linePoints[0].x - s.size / 2, s.linePoints[0].y - s.size / 2);
                for (let i = 1; i < s.linePoints.length; i++) {
                    ctx.lineTo(s.linePoints[i].x - s.size / 2, s.linePoints[i].y - s.size / 2);
                }
            } else {
                // Simple line
                ctx.moveTo(-s.size / 2, 0);
                ctx.lineTo(s.size / 2, 0);
            }
            ctx.stroke();
        }
        else if (s.type === 'arc') {
            ctx.beginPath();
            ctx.moveTo(-s.size / 2, 0);
            // Support multiple control points
            if (s.controls && s.controls.length > 0) {
                if (s.controls.length === 1) {
                    ctx.quadraticCurveTo(s.controls[0].x, s.controls[0].y, s.size / 2, 0);
                } else if (s.controls.length === 2) {
                    // Cubic bezier with 2 control points
                    ctx.bezierCurveTo(s.controls[0].x, s.controls[0].y, s.controls[1].x, s.controls[1].y, s.size / 2, 0);
                } else if (s.controls.length === 3) {
                    // Approximate with two cubic beziers
                    const mid = 0;
                    ctx.bezierCurveTo(s.controls[0].x, s.controls[0].y, s.controls[1].x, s.controls[1].y, mid, s.controls[1].y);
                    ctx.bezierCurveTo(s.controls[1].x, s.controls[1].y, s.controls[2].x, s.controls[2].y, s.size / 2, 0);
                }
            } else if (s.control) {
                // Backwards compatibility
                ctx.quadraticCurveTo(s.control.x, s.control.y, s.size / 2, 0);
            }
            ctx.stroke();
        }
        else if (s.type === 'matrix') {
            ctx.strokeRect(-s.size / 2, -s.size / 2, s.size, s.size);
            const rows = s.rows, cols = s.cols;
            for (let r = 0; r < rows; r++) {
                const ty = rows === 1 ? 0.5 : r / (rows - 1);
                const y = -s.size / 2 + ty * s.size;
                ctx.beginPath();
                ctx.moveTo(-s.size / 2, y); ctx.lineTo(s.size / 2, y); ctx.stroke();
            }
            for (let c = 0; c < cols; c++) {
                const tx = cols === 1 ? 0.5 : c / (cols - 1);
                const x = -s.size / 2 + tx * s.size;
                ctx.beginPath();
                ctx.moveTo(x, -s.size / 2); ctx.lineTo(x, s.size / 2); ctx.stroke();
            }
        }
        else if (s.type === 'star') {
            // draw star path centered at 0,0
            const spikes = Math.max(2, s.spikes || 5);
            const outer = s.size / 2;
            const inner = outer * (s.innerRatio || 0.5);
            ctx.beginPath();
            let rot = -Math.PI / 2; // start top
            const step = Math.PI / spikes;
            ctx.moveTo(Math.cos(rot) * outer, Math.sin(rot) * outer);
            for (let i = 0; i < spikes; i++) {
                const ox = Math.cos(rot) * outer, oy = Math.sin(rot) * outer;
                rot += step;
                const ix = Math.cos(rot) * inner, iy = Math.sin(rot) * inner;
                ctx.lineTo(ox, oy);
                ctx.lineTo(ix, iy);
                rot += step;
            }
            ctx.closePath();
            ctx.stroke();
        }
        else if (s.type === 'polygon') {
            // draw polygon path centered at 0,0
            const sides = Math.max(3, s.sides || 6);
            const radius = s.size / 2;
            const angleStep = (Math.PI * 2) / sides;
            let rot = -Math.PI / 2; // start top
            ctx.beginPath();
            ctx.moveTo(Math.cos(rot) * radius, Math.sin(rot) * radius);
            for (let i = 1; i < sides; i++) {
                rot += angleStep;
                ctx.lineTo(Math.cos(rot) * radius, Math.sin(rot) * radius);
            }
            ctx.closePath();
            ctx.stroke();
        }
        else if (s.type === 'freehand') {
            // draw freehand path
            if (s.freehandPoints && s.freehandPoints.length > 1) {
                ctx.beginPath();
                ctx.moveTo(s.freehandPoints[0].x, s.freehandPoints[0].y);
                for (let i = 1; i < s.freehandPoints.length; i++) {
                    ctx.lineTo(s.freehandPoints[i].x, s.freehandPoints[i].y);
                }
                ctx.stroke();
            }
        }

        if (s.type === 'line') drawPoints(getLinePoints(s), s);
        else if (s.type === 'arc') drawPoints(getArcPoints(s), s);
        else if (s.type === 'matrix') drawPoints(getShapePoints(s), s);
        else if (s.type === 'freehand') drawPoints(getFreehandPoints(s), s);
        else drawPoints(getShapePoints(s), s);

        if (selectedShape === s) {
            drawHandles(s);
            if (s.type === 'arc') drawControlHandles(s);
        }

        // Draw selection indicator for multi-select
        if (selectedShapes.includes(s) && selectedShape !== s) {
            ctx.strokeStyle = '#0d6efd';
            ctx.lineWidth = 3 / Math.max(s.scaleX, s.scaleY);
            ctx.strokeRect(-s.size / 2, -s.size / 2, s.size, s.size);
        }

        ctx.restore();
    }

    // Draw connection lines between objects (last point of object N to first point of object N+1)
    if (showConnectionLines) {
        ctx.save();
        for (let i = 0; i < shapes.length - 1; i++) {
            const currentShape = shapes[i];
            const nextShape = shapes[i + 1];

            // Get points for current and next shape
            let currentPoints, nextPoints;
            if (currentShape.type === 'line') currentPoints = getLinePoints(currentShape);
            else if (currentShape.type === 'arc') currentPoints = getArcPoints(currentShape);
            else if (currentShape.type === 'freehand') currentPoints = getFreehandPoints(currentShape);
            else currentPoints = getShapePoints(currentShape);

            if (nextShape.type === 'line') nextPoints = getLinePoints(nextShape);
            else if (nextShape.type === 'arc') nextPoints = getArcPoints(nextShape);
            else if (nextShape.type === 'freehand') nextPoints = getFreehandPoints(nextShape);
            else nextPoints = getShapePoints(nextShape);

            if (currentPoints.length > 0 && nextPoints.length > 0) {
                // Get last point of current shape
                const lastPoint = currentPoints[currentPoints.length - 1];
                const [lastX, lastY] = localToWorld(currentShape, lastPoint[0], lastPoint[1]);

                // Get first point of next shape
                const firstPoint = nextPoints[0];
                const [firstX, firstY] = localToWorld(nextShape, firstPoint[0], firstPoint[1]);

                // Draw connection line (skip if this shape starts a new 8-universe connection)
                if (!shapeUniverseBreaks.has(i + 1)) {
                    ctx.beginPath();
                    ctx.moveTo(lastX, lastY);
                    ctx.lineTo(firstX, firstY);
                    ctx.strokeStyle = COLORS.CONNECTION_LINE;
                    ctx.lineWidth = 1;
                    ctx.stroke();
                }
            }
        }
        ctx.restore();
    }
    
    // Draw snap guide lines - before restoring transform
    if (snapLines.length > 0) {
        ctx.save();
        ctx.strokeStyle = 'rgba(255, 0, 255, 0.6)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        
        for (const line of snapLines) {
            ctx.beginPath();
            ctx.moveTo(line.x1, line.y1);
            ctx.lineTo(line.x2, line.y2);
            ctx.stroke();
        }
        
        ctx.setLineDash([]);
        ctx.restore();
    }
    
    // Draw selection box (marquee) - before restoring transform
    if (selectionBox) {
        ctx.save();
        ctx.strokeStyle = 'rgba(0, 123, 255, 0.8)';
        ctx.fillStyle = 'rgba(0, 123, 255, 0.1)';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        
        const x = Math.min(selectionBox.startX, selectionBox.endX);
        const y = Math.min(selectionBox.startY, selectionBox.endY);
        const w = Math.abs(selectionBox.endX - selectionBox.startX);
        const h = Math.abs(selectionBox.endY - selectionBox.startY);
        
        ctx.fillRect(x, y, w, h);
        ctx.strokeRect(x, y, w, h);
        ctx.restore();
    }
    
    // Restore transform (end of shapes drawing)
    ctx.restore();

    // Draw tooltip for hovered point (in world coordinates, not transformed)
    if (hoveredPoint) {
        const pointLabel = `P${hoveredPoint.pointIndex + 1}`;

        ctx.save();
        ctx.font = `${TOOLTIP.FONT_SIZE}px Arial`;
        ctx.textBaseline = 'top';

        const textWidth = ctx.measureText(pointLabel).width;
        const boxWidth = textWidth + TOOLTIP.PADDING * 2;
        const boxHeight = TOOLTIP.FONT_SIZE + TOOLTIP.PADDING * 2;

        // Apply offset if in overflow mode
        const offsetX = allowOutOfBounds ? CANVAS_OVERFLOW : 0;
        const offsetY = allowOutOfBounds ? CANVAS_OVERFLOW : 0;

        // Position tooltip above the point (with offset)
        let tooltipX = hoveredPoint.x + offsetX - boxWidth / 2;
        let tooltipY = hoveredPoint.y + offsetY - boxHeight - TOOLTIP.OFFSET_Y;

        // Keep tooltip within canvas bounds
        tooltipX = Math.max(TOOLTIP.MIN_MARGIN, Math.min(canvas.width - boxWidth - TOOLTIP.MIN_MARGIN, tooltipX));
        tooltipY = Math.max(TOOLTIP.MIN_MARGIN, tooltipY);

        // Draw tooltip background
        ctx.fillStyle = COLORS.TOOLTIP_BG;
        ctx.fillRect(tooltipX, tooltipY, boxWidth, boxHeight);

        // Draw tooltip border
        ctx.strokeStyle = COLORS.TOOLTIP_BORDER;
        ctx.lineWidth = 1;
        ctx.strokeRect(tooltipX, tooltipY, boxWidth, boxHeight);

        // Draw tooltip text
        ctx.fillStyle = COLORS.TOOLTIP_TEXT;
        ctx.fillText(pointLabel, tooltipX + TOOLTIP.PADDING, tooltipY + TOOLTIP.PADDING);

        ctx.restore();
    }

    // Draw freehand drawing in progress
    if (isFreehandMode && isDrawing && freehandPoints.length > 1) {
        ctx.save();
        ctx.strokeStyle = 'rgba(0, 255, 255, 0.8)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(freehandPoints[0].x, freehandPoints[0].y);
        for (let i = 1; i < freehandPoints.length; i++) {
            ctx.lineTo(freehandPoints[i].x, freehandPoints[i].y);
        }
        ctx.stroke();
        ctx.restore();
    }
}

function loop() { requestAnimationFrame(loop); draw(); }

// Initialize canvas with overflow on startup
setCanvasSize(actualCanvasWidth, actualCanvasHeight);

loop();

// ========================================
// POINT GENERATION & UTILITIES [Lines 652-900]
// ========================================
function drawPoints(points, s) {
    // Points scale with object but keep constant visual pixel size
    // Adjust radius based on scale AND display scale to maintain constant size in pixels
    const rect = canvas.getBoundingClientRect();
    const displayScale = Math.min(canvas.width / rect.width, canvas.height / rect.height);
    const scale = Math.max(Math.abs(s.scaleX), Math.abs(s.scaleY));
    const radius = (POINT.RADIUS * displayScale) / scale;  // Compensate for both scales

    for (let i = 0; i < points.length; i++) {
        const p = points[i];
        ctx.beginPath();
        ctx.arc(p[0], p[1], radius, 0, Math.PI * 2);
        ctx.fillStyle = (i === 0) ? COLORS.POINT_FIRST : (i === points.length - 1) ? COLORS.POINT_LAST : COLORS.POINT_DEFAULT;
        ctx.fill();

        // Highlight hovered point
        if (hoveredPoint && hoveredPoint.shape === s && hoveredPoint.pointIndex === i) {
            ctx.strokeStyle = COLORS.POINT_HOVER;
            ctx.lineWidth = 2 / scale;
            ctx.stroke();
        }
    }
}

function findPointAtMouse(mx, my) {
    // Check all shapes for points near the mouse
    for (const s of shapes) {
        let points;
        if (s.type === 'line') points = getLinePoints(s);
        else if (s.type === 'arc') points = getArcPoints(s);
        else points = getShapePoints(s);

        const scale = Math.max(Math.abs(s.scaleX), Math.abs(s.scaleY));
        const hitRadius = POINT.HIT_RADIUS / scale; // Slightly larger than visual radius for easier hovering

        for (let i = 0; i < points.length; i++) {
            const [wx, wy] = localToWorld(s, points[i][0], points[i][1]);
            const dist = Math.hypot(mx - wx, my - wy);
            if (dist <= hitRadius) {
                return { shape: s, pointIndex: i, x: wx, y: wy };
            }
        }
    }
    return null;
}

/* Point generation */
function localToWorld(s, lx, ly) {
    const cosA = Math.cos(s.rotation), sinA = Math.sin(s.rotation);
    const sx = lx * s.scaleX, sy = ly * s.scaleY;
    const x = s.x + (sx * cosA - sy * sinA);
    const y = s.y + (sx * sinA + sy * cosA);
    return [x, y];
}

// Transform handle position to world space (without scaling the handle offset)
function handleToWorld(s, lx, ly) {
    const cosA = Math.cos(s.rotation), sinA = Math.sin(s.rotation);
    const x = s.x + (lx * cosA - ly * sinA);
    const y = s.y + (lx * sinA + ly * cosA);
    return [x, y];
}

function worldToLocal(s, wx, wy) {
    const dx = wx - s.x, dy = wy - s.y;
    const cosA = Math.cos(-s.rotation), sinA = Math.sin(-s.rotation);
    const rx = dx * cosA - dy * sinA;
    const ry = dx * sinA + dy * cosA;
    return [rx / s.scaleX, ry / s.scaleY];
}

function worldLenBetweenLocal(s, a, b) {
    const dx = (b[0] - a[0]) * s.scaleX;
    const dy = (b[1] - a[1]) * s.scaleY;
    return Math.hypot(dx, dy);
}

function distributeAlongEdges(s, edges, count) {
    const points = [];
    const lengths = edges.map(([a, b]) => worldLenBetweenLocal(s, a, b));
    const perimeter = lengths.reduce((a, b) => a + b, 0);
    if (perimeter === 0) {
        for (let i = 0; i < count; i++) points.push(edges[0][0].slice());
        return points;
    }
    const step = perimeter / count;
    let dist = 0;
    for (let i = 0; i < count; i++) {
        let remaining = dist;
        for (let ei = 0; ei < edges.length; ei++) {
            const [a, b] = edges[ei];
            const len = lengths[ei];
            if (remaining <= len) {
                const t = len === 0 ? 0 : (remaining / len);
                points.push([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
                break;
            }
            remaining -= len;
        }
        dist += step;
    }
    return points;
}

// ========================================
// SNAPPING FUNCTIONS
// ========================================
function snapPosition(x, y, excludeShape = null) {
    snapLines = []; // Clear previous snap lines
    let snappedX = x;
    let snappedY = y;
    
    // Grid snapping
    if (snapToGrid) {
        snappedX = Math.round(x / gridSize) * gridSize;
        snappedY = Math.round(y / gridSize) * gridSize;
    }
    
    // Object snapping
    if (snapToObjects && excludeShape) {
        const shapesToCheck = shapes.filter(s => s !== excludeShape && !selectedShapes.includes(s));
        
        for (const shape of shapesToCheck) {
            const halfW = (shape.size * Math.abs(shape.scaleX)) / 2;
            const halfH = (shape.size * Math.abs(shape.scaleY)) / 2;
            
            // Calculate shape boundaries
            const left = shape.x - halfW;
            const right = shape.x + halfW;
            const top = shape.y - halfH;
            const bottom = shape.y + halfH;
            const centerX = shape.x;
            const centerY = shape.y;
            
            // Horizontal snapping (X-axis)
            if (Math.abs(snappedX - left) < SNAP_DISTANCE) {
                snappedX = left;
                snapLines.push({ x1: left, y1: 0, x2: left, y2: actualCanvasHeight, type: 'vertical' });
            } else if (Math.abs(snappedX - right) < SNAP_DISTANCE) {
                snappedX = right;
                snapLines.push({ x1: right, y1: 0, x2: right, y2: actualCanvasHeight, type: 'vertical' });
            } else if (Math.abs(snappedX - centerX) < SNAP_DISTANCE) {
                snappedX = centerX;
                snapLines.push({ x1: centerX, y1: 0, x2: centerX, y2: actualCanvasHeight, type: 'vertical' });
            }
            
            // Vertical snapping (Y-axis)
            if (Math.abs(snappedY - top) < SNAP_DISTANCE) {
                snappedY = top;
                snapLines.push({ x1: 0, y1: top, x2: actualCanvasWidth, y2: top, type: 'horizontal' });
            } else if (Math.abs(snappedY - bottom) < SNAP_DISTANCE) {
                snappedY = bottom;
                snapLines.push({ x1: 0, y1: bottom, x2: actualCanvasWidth, y2: bottom, type: 'horizontal' });
            } else if (Math.abs(snappedY - centerY) < SNAP_DISTANCE) {
                snappedY = centerY;
                snapLines.push({ x1: 0, y1: centerY, x2: actualCanvasWidth, y2: centerY, type: 'horizontal' });
            }
        }
    }
    
    return { x: snappedX, y: snappedY };
}

function constrainToBounds(shape) {
    if (allowOutOfBounds) return; // Skip bounds checking
    
    const halfW = (shape.size * Math.abs(shape.scaleX)) / 2;
    const halfH = (shape.size * Math.abs(shape.scaleY)) / 2;
    
    shape.x = Math.round(Math.max(halfW, Math.min(actualCanvasWidth - halfW, shape.x)));
    shape.y = Math.round(Math.max(halfH, Math.min(actualCanvasHeight - halfH, shape.y)));
}

// ========================================
// POINT GENERATORS - Modular point generation by shape type
// ========================================
const PointGenerators = {
    matrix: function (s) {
        const pts = [];
        const rows = Math.max(1, s.rows || 1), cols = Math.max(1, s.cols || 1);
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

        // Apply the selected pattern
        const patterns = {
            'zigzag-left': () => {
                for (let r = 0; r < rows; r++) {
                    if (r % 2 === 0) {
                        for (let c = 0; c < cols; c++) pts.push(tempPts[r][c]);
                    } else {
                        for (let c = cols - 1; c >= 0; c--) pts.push(tempPts[r][c]);
                    }
                }
            },
            'zigzag-right': () => {
                for (let r = 0; r < rows; r++) {
                    if (r % 2 === 0) {
                        for (let c = cols - 1; c >= 0; c--) pts.push(tempPts[r][c]);
                    } else {
                        for (let c = 0; c < cols; c++) pts.push(tempPts[r][c]);
                    }
                }
            },
            'zigzag-top': () => {
                for (let c = 0; c < cols; c++) {
                    if (c % 2 === 0) {
                        for (let r = 0; r < rows; r++) pts.push(tempPts[r][c]);
                    } else {
                        for (let r = rows - 1; r >= 0; r--) pts.push(tempPts[r][c]);
                    }
                }
            },
            'zigzag-bottom': () => {
                for (let c = 0; c < cols; c++) {
                    if (c % 2 === 0) {
                        for (let r = rows - 1; r >= 0; r--) pts.push(tempPts[r][c]);
                    } else {
                        for (let r = 0; r < rows; r++) pts.push(tempPts[r][c]);
                    }
                }
            },
            'raster': () => {
                for (let r = 0; r < rows; r++) {
                    for (let c = 0; c < cols; c++) {
                        pts.push(tempPts[r][c]);
                    }
                }
            }
        };

        (patterns[pattern] || patterns['raster'])();
        return pts;
    },

    circle: function (s) {
        const pts = [];
        const count = Math.max(1, s.pointCount || 1);
        const rx = s.size / 2, ry = s.size / 2;
        const sampleN = Math.max(128, count * 6);
        const samples = [];
        for (let i = 0; i <= sampleN; i++) {
            const a = (i / sampleN) * Math.PI * 2;
            samples.push([Math.cos(a) * rx, Math.sin(a) * ry]);
        }
        const cum = [0];
        for (let i = 1; i < samples.length; i++) cum.push(cum[i - 1] + worldLenBetweenLocal(s, samples[i - 1], samples[i]));
        const total = cum[cum.length - 1];
        if (total === 0) return samples.slice(0, count);
        for (let i = 0; i < count; i++) {
            const target = (i / count) * total;
            let idx = 0;
            while (idx < cum.length - 1 && cum[idx + 1] < target) idx++;
            const segLen = cum[idx + 1] - cum[idx];
            const t = segLen === 0 ? 0 : ((target - cum[idx]) / segLen);
            const a = samples[idx], b = samples[idx + 1];
            pts.push([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
        }
        return pts;
    },

    rect: function (s) {
        const count = Math.max(1, s.pointCount || 1);
        const half = s.size / 2;
        const v = [[-half, -half], [half, -half], [half, half], [-half, half]];
        const edges = [[v[0], v[1]], [v[1], v[2]], [v[2], v[3]], [v[3], v[0]]];
        return distributeAlongEdges(s, edges, count);
    },

    triangle: function (s) {
        const count = Math.max(1, s.pointCount || 1);
        const half = s.size / 2;
        const verts = [[-half, half], [half, half], [0, -half]];
        const edges = [[verts[0], verts[1]], [verts[1], verts[2]], [verts[2], verts[0]]];
        return distributeAlongEdges(s, edges, count);
    },

    star: function (s) {
        const count = Math.max(1, s.pointCount || 1);
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
};

function getShapePoints(s) {
    // Use modular generators if available
    if (PointGenerators[s.type]) {
        return PointGenerators[s.type](s);
    }

    // Fallback to original implementation
    const pts = [];
    const count = Math.max(1, s.pointCount || 1);

    if (s.type === 'matrix') {
        const rows = Math.max(1, s.rows || 1), cols = Math.max(1, s.cols || 1);
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

        // Apply the selected pattern
        if (pattern === 'zigzag-left') {
            // Zigzag starting from left: row by row, alternating direction
            for (let r = 0; r < rows; r++) {
                if (r % 2 === 0) {
                    // Even rows: left to right
                    for (let c = 0; c < cols; c++) pts.push(tempPts[r][c]);
                } else {
                    // Odd rows: right to left
                    for (let c = cols - 1; c >= 0; c--) pts.push(tempPts[r][c]);
                }
            }
        } else if (pattern === 'zigzag-right') {
            // Zigzag starting from right: row by row, alternating direction
            for (let r = 0; r < rows; r++) {
                if (r % 2 === 0) {
                    // Even rows: right to left
                    for (let c = cols - 1; c >= 0; c--) pts.push(tempPts[r][c]);
                } else {
                    // Odd rows: left to right
                    for (let c = 0; c < cols; c++) pts.push(tempPts[r][c]);
                }
            }
        } else if (pattern === 'zigzag-top') {
            // Zigzag starting from top: column by column, alternating direction
            for (let c = 0; c < cols; c++) {
                if (c % 2 === 0) {
                    // Even columns: top to bottom
                    for (let r = 0; r < rows; r++) pts.push(tempPts[r][c]);
                } else {
                    // Odd columns: bottom to top
                    for (let r = rows - 1; r >= 0; r--) pts.push(tempPts[r][c]);
                }
            }
        } else if (pattern === 'zigzag-bottom') {
            // Zigzag starting from bottom: column by column, alternating direction
            for (let c = 0; c < cols; c++) {
                if (c % 2 === 0) {
                    // Even columns: bottom to top
                    for (let r = rows - 1; r >= 0; r--) pts.push(tempPts[r][c]);
                } else {
                    // Odd columns: top to bottom
                    for (let r = 0; r < rows; r++) pts.push(tempPts[r][c]);
                }
            }
        } else {
            // Default: raster pattern (left to right, top to bottom)
            for (let r = 0; r < rows; r++) {
                for (let c = 0; c < cols; c++) {
                    pts.push(tempPts[r][c]);
                }
            }
        }
        return pts;
    }

    if (s.type === 'circle') {
        const rx = s.size / 2, ry = s.size / 2;
        const sampleN = Math.max(128, count * 6);
        const samples = [];
        for (let i = 0; i <= sampleN; i++) {
            const a = (i / sampleN) * Math.PI * 2;
            samples.push([Math.cos(a) * rx, Math.sin(a) * ry]);
        }
        const cum = [0];
        for (let i = 1; i < samples.length; i++) cum.push(cum[i - 1] + worldLenBetweenLocal(s, samples[i - 1], samples[i]));
        const total = cum[cum.length - 1];
        if (total === 0) return samples.slice(0, count);
        for (let i = 0; i < count; i++) {
            const target = (i / count) * total;
            let idx = 0;
            while (idx < cum.length - 1 && cum[idx + 1] < target) idx++;
            const segLen = cum[idx + 1] - cum[idx];
            const t = segLen === 0 ? 0 : ((target - cum[idx]) / segLen);
            const a = samples[idx], b = samples[idx + 1];
            pts.push([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
        }
        return pts;
    }

    if (s.type === 'rect') {
        const half = s.size / 2;
        const v = [[-half, -half], [half, -half], [half, half], [-half, half]];
        const edges = [[v[0], v[1]], [v[1], v[2]], [v[2], v[3]], [v[3], v[0]]];
        return distributeAlongEdges(s, edges, count);
    }

    if (s.type === 'triangle') {
        const half = s.size / 2;
        const verts = [[-half, half], [half, half], [0, -half]];
        const edges = [[verts[0], verts[1]], [verts[1], verts[2]], [verts[2], verts[0]]];
        return distributeAlongEdges(s, edges, count);
    }

    // neu: Stern - erzeugt Eckpunkte (outer/inner) und verteilt Punkte entlang der Kanten
    if (s.type === 'star') {
        const count = Math.max(1, s.pointCount || 1);
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

    // Polygon - erzeugt gleichmäßiges N-Eck und verteilt Punkte entlang der Kanten
    if (s.type === 'polygon') {
        const count = Math.max(1, s.pointCount || 1);
        const sides = Math.max(3, s.sides || 6);
        const radius = s.size / 2;
        const verts = [];
        const angleStep = (Math.PI * 2) / sides;
        let rot = -Math.PI / 2; // Start at top
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

function getLinePoints(s) {
    // Check if this is a polyline (from text tool)
    if (s.linePoints && s.linePoints.length > 0) {
        const pts = [];
        const totalPoints = Math.max(2, s.pointCount || s.linePoints.length);
        const segments = s.linePoints.length - 1;
        
        if (segments === 0) {
            // Single point - return it multiple times
            return Array(totalPoints).fill([s.linePoints[0].x - s.size/2, s.linePoints[0].y - s.size/2]);
        }
        
        // Distribute points along the polyline segments
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
    
    // Default simple line
    const start = [-s.size / 2, 0], end = [s.size / 2, 0];
    const pts = [];
    const count = Math.max(2, s.pointCount || 2);
    for (let i = 0; i < count; i++) {
        const t = i / (count - 1);
        pts.push([start[0] + t * (end[0] - start[0]), 0]);
    }
    return pts;
}

function getArcPoints(s) {
    const start = [-s.size / 2, 0], end = [s.size / 2, 0];

    // Bezier curve function based on number of control points
    const bez = t => {
        if (s.controls && s.controls.length > 0) {
            const ctrls = s.controls;
            if (ctrls.length === 1) {
                // Quadratic bezier
                const mt = 1 - t;
                const x = mt * mt * start[0] + 2 * mt * t * ctrls[0].x + t * t * end[0];
                const y = mt * mt * start[1] + 2 * mt * t * ctrls[0].y + t * t * end[1];
                return [x, y];
            } else if (ctrls.length === 2) {
                // Cubic bezier
                const mt = 1 - t;
                const mt2 = mt * mt;
                const mt3 = mt2 * mt;
                const t2 = t * t;
                const t3 = t2 * t;
                const x = mt3 * start[0] + 3 * mt2 * t * ctrls[0].x + 3 * mt * t2 * ctrls[1].x + t3 * end[0];
                const y = mt3 * start[1] + 3 * mt2 * t * ctrls[0].y + 3 * mt * t2 * ctrls[1].y + t3 * end[1];
                return [x, y];
            } else {
                // 3 control points - use composite bezier
                if (t < 0.5) {
                    const t2 = t * 2;
                    const mt = 1 - t2;
                    const mt2 = mt * mt;
                    const mt3 = mt2 * mt;
                    const tt2 = t2 * t2;
                    const tt3 = tt2 * t2;
                    const mid = [0, ctrls[1].y];
                    const x = mt3 * start[0] + 3 * mt2 * t2 * ctrls[0].x + 3 * mt * tt2 * ctrls[1].x + tt3 * mid[0];
                    const y = mt3 * start[1] + 3 * mt2 * t2 * ctrls[0].y + 3 * mt * tt2 * ctrls[1].y + tt3 * mid[1];
                    return [x, y];
                } else {
                    const t2 = (t - 0.5) * 2;
                    const mt = 1 - t2;
                    const mt2 = mt * mt;
                    const mt3 = mt2 * mt;
                    const tt2 = t2 * t2;
                    const tt3 = tt2 * t2;
                    const mid = [0, ctrls[1].y];
                    const x = mt3 * mid[0] + 3 * mt2 * t2 * ctrls[1].x + 3 * mt * tt2 * ctrls[2].x + tt3 * end[0];
                    const y = mt3 * mid[1] + 3 * mt2 * t2 * ctrls[1].y + 3 * mt * tt2 * ctrls[2].y + tt3 * end[1];
                    return [x, y];
                }
            }
        } else if (s.control) {
            // Backwards compatibility
            const mt = 1 - t;
            const x = mt * mt * start[0] + 2 * mt * t * s.control.x + t * t * end[0];
            const y = mt * mt * start[1] + 2 * mt * t * s.control.y + t * t * end[1];
            return [x, y];
        }
        return [start[0] + t * (end[0] - start[0]), start[1] + t * (end[1] - start[1])];
    };

    const count = Math.max(2, s.pointCount || 2);
    const sampleN = Math.max(200, count * 8);
    const samples = [];
    for (let i = 0; i <= sampleN; i++) samples.push(bez(i / sampleN));
    const cum = [0];
    for (let i = 1; i < samples.length; i++) cum.push(cum[i - 1] + worldLenBetweenLocal(s, samples[i - 1], samples[i]));
    const total = cum[cum.length - 1];
    if (total === 0) {
        const pts = [];
        for (let i = 0; i < count; i++) pts.push(bez(i / (count - 1)));
        return pts;
    }
    const pts = [];
    for (let i = 0; i < count; i++) {
        const target = (i / (count - 1)) * total;
        let idx = 0;
        while (idx < cum.length - 1 && cum[idx + 1] < target) idx++;
        const segLen = cum[idx + 1] - cum[idx];
        const t = segLen === 0 ? 0 : ((target - cum[idx]) / segLen);
        const a = samples[idx], b = samples[idx + 1];
        pts.push([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
    }
    return pts;
}

function getFreehandPoints(s) {
    if (!s.freehandPoints || s.freehandPoints.length === 0) {
        return [];
    }
    
    // Return the freehand points as-is (they're already in local coordinates)
    return s.freehandPoints.map(p => [p.x, p.y]);
}

function resampleFreehandPoints(points, targetCount) {
    if (points.length === 0 || targetCount < 2) return points;
    if (points.length === targetCount) return points;
    
    // Calculate cumulative distances
    const distances = [0];
    for (let i = 1; i < points.length; i++) {
        const dx = points[i].x - points[i - 1].x;
        const dy = points[i].y - points[i - 1].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        distances.push(distances[i - 1] + dist);
    }
    
    const totalLength = distances[distances.length - 1];
    if (totalLength === 0) return points.slice(0, targetCount);
    
    // Resample points evenly along the path
    const resampled = [];
    for (let i = 0; i < targetCount; i++) {
        const targetDist = (i / (targetCount - 1)) * totalLength;
        
        // Find the segment containing this distance
        let segmentIndex = 0;
        while (segmentIndex < distances.length - 1 && distances[segmentIndex + 1] < targetDist) {
            segmentIndex++;
        }
        
        // Interpolate within the segment
        if (segmentIndex >= points.length - 1) {
            resampled.push({ ...points[points.length - 1] });
        } else {
            const segmentStart = distances[segmentIndex];
            const segmentEnd = distances[segmentIndex + 1];
            const segmentLength = segmentEnd - segmentStart;
            
            const t = segmentLength === 0 ? 0 : (targetDist - segmentStart) / segmentLength;
            const p1 = points[segmentIndex];
            const p2 = points[segmentIndex + 1];
            
            resampled.push({
                x: p1.x + t * (p2.x - p1.x),
                y: p1.y + t * (p2.y - p1.y)
            });
        }
    }
    
    return resampled;
}

/* Handles & interaction */
function drawHandles(s) {
    // Calculate handle size based on canvas display size (not canvas resolution)
    const rect = canvas.getBoundingClientRect();
    const displayScale = Math.min(canvas.width / rect.width, canvas.height / rect.height);
    const baseHandleSize = HANDLE.SIZE * displayScale;
    
    // Icon size stays constant regardless of object scale
    const iconSize = baseHandleSize * HANDLE.ICON_SIZE_MULTIPLIER;

    // For line and arc objects, use tighter bounding box
    let halfW = s.size / 2;
    let halfH = s.size / 2;
    
    if (s.type === 'line' || s.type === 'arc') {
        // For lines and arcs, use a much smaller height for the bounding box
        halfW = s.size / 2;
        halfH = 20; // Fixed small height for better usability
    }

    const corners = [[-halfW, -halfH], [halfW, -halfH], [halfW, halfH], [-halfW, halfH]];
    const outerHandleSize = HANDLE.SIZE_OUTER * displayScale;
    const innerSquareSize = baseHandleSize * 0.7; // 30% smaller
    
    for (let i = 0; i < corners.length; i++) {
        const [x, y] = corners[i];
        // Draw corner handles with inverse scale to keep them constant size
        ctx.save();
        ctx.translate(x, y);
        ctx.scale(1 / s.scaleX, 1 / s.scaleY);
        
        // Check if this corner is being hovered
        const isRotateHovered = hoveredHandle === `rotate-${i}`;
        const isScaleHovered = hoveredHandle === `scale-${i}`;
        
        // Outer ring for rotation (cyan, 30% opacity or full on hover)
        ctx.fillStyle = isRotateHovered ? 'rgba(0, 255, 255, 1.0)' : 'rgba(0, 255, 255, 0.3)';
        ctx.beginPath();
        ctx.arc(0, 0, outerHandleSize, 0, Math.PI * 2);
        ctx.fill();
        
        // Outer ring border
        ctx.strokeStyle = 'cyan';
        ctx.lineWidth = 1.5;
        ctx.stroke();
        
        // Inner square for scaling (cyan, full opacity on hover)
        ctx.fillStyle = isScaleHovered ? 'rgba(0, 255, 255, 1.0)' : COLORS.HANDLE_CORNER_FILL;
        ctx.fillRect(-innerSquareSize, -innerSquareSize, innerSquareSize * 2, innerSquareSize * 2);

        // Inner square outline
        ctx.strokeStyle = isScaleHovered ? 'cyan' : COLORS.HANDLE_CORNER_STROKE;
        ctx.lineWidth = 1;
        ctx.strokeRect(-innerSquareSize, -innerSquareSize, innerSquareSize * 2, innerSquareSize * 2);
        ctx.restore();
    }
    
    // Edge scale handles - squares on all 4 sides
    const squareSize = baseHandleSize * 1.2;
    
    // Right edge scale handle
    ctx.save();
    ctx.translate(halfW, 0);
    ctx.scale(1 / s.scaleX, 1 / s.scaleY);
    ctx.fillStyle = COLORS.HANDLE_CORNER_FILL;
    ctx.fillRect(-squareSize / 2, -squareSize / 2, squareSize, squareSize);
    ctx.strokeStyle = COLORS.HANDLE_CORNER_STROKE;
    ctx.lineWidth = 1.5;
    ctx.strokeRect(-squareSize / 2, -squareSize / 2, squareSize, squareSize);
    ctx.restore();
    
    // Left edge scale handle
    ctx.save();
    ctx.translate(-halfW, 0);
    ctx.scale(1 / s.scaleX, 1 / s.scaleY);
    ctx.fillStyle = COLORS.HANDLE_CORNER_FILL;
    ctx.fillRect(-squareSize / 2, -squareSize / 2, squareSize, squareSize);
    ctx.strokeStyle = COLORS.HANDLE_CORNER_STROKE;
    ctx.lineWidth = 1.5;
    ctx.strokeRect(-squareSize / 2, -squareSize / 2, squareSize, squareSize);
    ctx.restore();
    
    // Top and bottom edge scale handles (skip for lines - they're 1-dimensional)
    if (s.type !== 'line') {
        // Top edge scale handle
        ctx.save();
        ctx.translate(0, -halfH);
        ctx.scale(1 / s.scaleX, 1 / s.scaleY);
        ctx.fillStyle = COLORS.HANDLE_CORNER_FILL;
        ctx.fillRect(-squareSize / 2, -squareSize / 2, squareSize, squareSize);
        ctx.strokeStyle = COLORS.HANDLE_CORNER_STROKE;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(-squareSize / 2, -squareSize / 2, squareSize, squareSize);
        ctx.restore();
        
        // Bottom edge scale handle
        ctx.save();
        ctx.translate(0, halfH);
        ctx.scale(1 / s.scaleX, 1 / s.scaleY);
        ctx.fillStyle = COLORS.HANDLE_CORNER_FILL;
        ctx.fillRect(-squareSize / 2, -squareSize / 2, squareSize, squareSize);
        ctx.strokeStyle = COLORS.HANDLE_CORNER_STROKE;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(-squareSize / 2, -squareSize / 2, squareSize, squareSize);
        ctx.restore();
    }
}

function drawControlHandles(s) {
    const rect = canvas.getBoundingClientRect();
    const displayScale = Math.min(canvas.width / rect.width, canvas.height / rect.height);
    const baseHandleSize = 6 * displayScale;

    const colors = [
        COLORS.CONTROL_HANDLE_PRIMARY,
        COLORS.CONTROL_HANDLE_SECONDARY,
        COLORS.CONTROL_HANDLE_TERTIARY
    ];

    if (s.controls && s.controls.length > 0) {
        for (let i = 0; i < s.controls.length; i++) {
            ctx.save();
            ctx.translate(s.controls[i].x, s.controls[i].y);
            ctx.scale(1 / s.scaleX, 1 / s.scaleY);
            ctx.fillStyle = colors[i] || COLORS.CONTROL_HANDLE_PRIMARY;
            ctx.beginPath();
            ctx.arc(0, 0, baseHandleSize, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        }
    } else if (s.control) {
        // Backwards compatibility
        ctx.save();
        ctx.translate(s.control.x, s.control.y);
        ctx.scale(1 / s.scaleX, 1 / s.scaleY);
        ctx.fillStyle = COLORS.CONTROL_HANDLE_PRIMARY;
        ctx.beginPath();
        ctx.arc(0, 0, baseHandleSize, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }
}

// Search top-down for a handle under the mouse. Returns { shape, handle } or null
function findHandleAcrossShapes(mx, my) {
    for (let i = shapes.length - 1; i >= 0; i--) {
        const s = shapes[i];
        const h = findHandle(s, mx, my);
        if (h) return { shape: s, handle: h };
    }
    return null;
}

// ========================================
// CANVAS EVENT HANDLERS [Lines 958-1150]
// ========================================
canvas.addEventListener('mousedown', e => {
    // Ignore canvas events if an input field is focused
    if (document.activeElement && document.activeElement.tagName === 'INPUT') return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const [mx, my] = screenToCanvas((e.clientX - rect.left) * scaleX, (e.clientY - rect.top) * scaleY);
    dragStartX = mx;
    dragStartY = my;

    // Handle freehand drawing mode
    if (isFreehandMode) {
        startFreehandDrawing(mx, my);
        return;
    }

    // First, check if we clicked on any handle (top-down): this should not deselect shapes
    const hit = findHandleAcrossShapes(mx, my);
    if (hit) {
        selectedShape = hit.shape;
        if (selectedShape.type !== 'matrix') {
            pointCountInput.value = selectedShape.pointCount;
            pointCountNumber.value = selectedShape.pointCount;
        }
        if (selectedShape.type === 'matrix') {
            document.getElementById('matrixRows').value = selectedShape.rows;
            document.getElementById('matrixCols').value = selectedShape.cols;
        }
        const handle = hit.handle;
        if (handle === 'scaleRight' || handle === 'scaleLeft' || handle === 'scaleTop' || handle === 'scaleBottom') {
            dragMode = handle;
            dragStartScaleX = selectedShape.scaleX;
            dragStartScaleY = selectedShape.scaleY;
            dragStartX = selectedShape.x;
            dragStartY = selectedShape.y;
        } else if (handle && handle.startsWith('rotate-')) {
            // Rotation from corner handle
            dragMode = 'rotate';
            dragStartRotation = selectedShape.rotation;
        } else if (handle && handle.startsWith('scale')) {
            dragMode = 'scale';
            scaleHandleIndex = parseInt(handle.split('-')[1], 10);
            dragStartScaleX = selectedShape.scaleX;
            dragStartScaleY = selectedShape.scaleY;
            dragStartX = selectedShape.x;
            dragStartY = selectedShape.y;
        } else if (handle === 'control' || handle.startsWith('control-')) {
            dragMode = 'control';
            if (handle.startsWith('control-')) {
                dragMode = 'control-' + handle.split('-')[1];
            }
        }
        offsetX = mx - selectedShape.x; offsetY = my - selectedShape.y;
    } else {
        // No handle clicked — treat as body-click (select/deselect by shape hit-test)
        const body = findShape(mx, my);
        selectedShape = body;
        if (selectedShape) {
            // If shape is in a group, select entire group
            if (selectedShape.groupId) {
                selectGroup(selectedShape);
            } else {
                selectedShapes = [];
            }
            
            if (selectedShape.type !== 'matrix') {
                pointCountInput.value = selectedShape.pointCount;
                pointCountNumber.value = selectedShape.pointCount;
            }
            dragMode = 'move';
            offsetX = mx - selectedShape.x; offsetY = my - selectedShape.y;
        } else {
            // Start marquee selection
            dragMode = 'marquee';
            selectionBox = { startX: mx, startY: my, endX: mx, endY: my };
            selectedShapes = [];
            selectedShape = null;
        }
    }
    updateToolbarSections();
    markForRedraw(); updateObjectList();
});

canvas.addEventListener('mousemove', e => {
    // Ignore canvas events if an input field is focused
    if (document.activeElement && document.activeElement.tagName === 'INPUT') return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const [mx, my] = screenToCanvas((e.clientX - rect.left) * scaleX, (e.clientY - rect.top) * scaleY);

    // Handle freehand drawing mode
    if (isFreehandMode && isDrawing) {
        continueFreehandDrawing(mx, my);
        return;
    }

    // Check for point hover (for tooltip)
    const prevHoveredPoint = hoveredPoint;
    hoveredPoint = findPointAtMouse(mx, my);
    if (hoveredPoint !== prevHoveredPoint) {
        markForRedraw();
    }

    // Handle marquee selection
    if (dragMode === 'marquee') {
        if (selectionBox) {
            selectionBox.endX = mx;
            selectionBox.endY = my;
            markForRedraw();
        }
        canvas.style.cursor = 'se-resize';
        return;
    }

    // Cursor-Feedback auch wenn nichts selected ist
    if (!selectedShape) {
        hoveredHandle = null;
        canvas.style.cursor = 'crosshair';
        return;
    }

    const handle = findHandle(selectedShape, mx, my);
    
    // Update hovered handle and request redraw if changed
    if (hoveredHandle !== handle) {
        hoveredHandle = handle;
        markForRedraw();
    }

    // Cursor je nach Handle-Typ ändern
    if (handle && handle.startsWith('rotate-')) {
        canvas.style.cursor = 'grabbing';
    } else if (handle === 'scaleRight' || handle === 'scaleLeft') {
        canvas.style.cursor = 'ew-resize';
    } else if (handle === 'scaleTop' || handle === 'scaleBottom') {
        canvas.style.cursor = 'ns-resize';
    } else if (handle && handle.startsWith('scale')) {
        canvas.style.cursor = 'nwse-resize';
    } else if (handle === 'control' || (handle && handle.startsWith('control-'))) {
        canvas.style.cursor = 'grab';
    } else if (dragMode === 'move') {
        canvas.style.cursor = 'grabbing';
    } else {
        // Check if over shape body
        const [lx, ly] = worldToLocal(selectedShape, mx, my);
        if (Math.abs(lx) <= selectedShape.size / 2 && Math.abs(ly) <= selectedShape.size / 2) {
            canvas.style.cursor = 'grab';
        } else {
            canvas.style.cursor = 'crosshair';
        }
    }

    // Actual drag handling
    if (dragMode === 'marquee') {
        // Update selection box
        if (selectionBox) {
            selectionBox.endX = mx;
            selectionBox.endY = my;
            markForRedraw();
        }
        return;
    }

    if (!selectedShape) return;

    if (dragMode === 'move') {
        let nx = mx - offsetX;
        let ny = my - offsetY;
        
        // Apply snapping to the primary shape
        if (snapToGrid || snapToObjects) {
            const snapped = snapPosition(nx, ny, selectedShape);
            nx = snapped.x;
            ny = snapped.y;
        }
        
        const dx = nx - selectedShape.x;
        const dy = ny - selectedShape.y;
        
        // Move all selected shapes (for grouped movement)
        const shapesToMove = selectedShapes.length > 0 ? selectedShapes : [selectedShape];
        
        shapesToMove.forEach(shape => {
            shape.x = Math.round(shape.x + dx);
            shape.y = Math.round(shape.y + dy);
            
            // Apply bounds constraints
            constrainToBounds(shape);
        });
        
        markForRedraw();
    } else if (dragMode === 'rotate') {
        const dx = mx - selectedShape.x, dy = my - selectedShape.y;
        const currentAngle = Math.atan2(dy, dx);
        const initialAngle = Math.atan2(dragStartY - selectedShape.y, dragStartX - selectedShape.x);
        const angleDelta = currentAngle - initialAngle;
        const newRotation = dragStartRotation + angleDelta;
        
        // Snap to 15° increments
        const snapAngle = 15 * Math.PI / 180; // 15 degrees in radians
        selectedShape.rotation = Math.round(newRotation / snapAngle) * snapAngle;
        
        markForRedraw();
    } else if (dragMode === 'scale') {
        // Corner scaling - keep opposite corner fixed
        const half = selectedShape.size / 2;
        const halfH = (selectedShape.type === 'line' || selectedShape.type === 'arc') ? 20 : half;
        
        // Define corners: 0=TL, 1=TR, 2=BR, 3=BL
        const corners = [[-half, -halfH], [half, -halfH], [half, halfH], [-half, halfH]];
        const oppositeIndex = (scaleHandleIndex + 2) % 4; // Opposite corner
        const [oppX, oppY] = corners[oppositeIndex];
        
        // Calculate opposite corner position in world space at drag start
        const cosA = Math.cos(selectedShape.rotation);
        const sinA = Math.sin(selectedShape.rotation);
        const oppWorldStartX = dragStartX + (oppX * dragStartScaleX * cosA - oppY * dragStartScaleY * sinA);
        const oppWorldStartY = dragStartY + (oppX * dragStartScaleX * sinA + oppY * dragStartScaleY * cosA);
        
        // Vector from opposite corner to mouse
        const toMouseX = mx - oppWorldStartX;
        const toMouseY = my - oppWorldStartY;
        
        // Calculate new scale based on distance from opposite corner
        // Project mouse vector onto rotated axes
        const localMouseX = (toMouseX * cosA + toMouseY * sinA);
        const localMouseY = (-toMouseX * sinA + toMouseY * cosA);
        
        // Calculate scale for each axis
        // The full distance from opposite corner to dragged corner is the shape size
        let newScaleX = dragStartScaleX;
        let newScaleY = dragStartScaleY;
        
        // Scale X: distance from opposite corner divided by full width
        newScaleX = Math.abs(localMouseX / selectedShape.size);
        newScaleX = Math.max(MIN_SCALE, Math.min(MAX_SCALE, newScaleX)) * Math.sign(dragStartScaleX);
        
        // Scale Y: distance from opposite corner divided by full height
        const fullHeight = halfH * 2;
        newScaleY = Math.abs(localMouseY / fullHeight);
        newScaleY = Math.max(MIN_SCALE, Math.min(MAX_SCALE, newScaleY)) * Math.sign(dragStartScaleY);
        
        // For matrix, use uniform scaling
        if (selectedShape.type === 'matrix') {
            const avgScale = (newScaleX + newScaleY) / 2;
            newScaleX = newScaleY = avgScale;
        }
        
        // Calculate new center position to keep opposite corner fixed
        const oppWorldNewX = dragStartX + (oppX * newScaleX * cosA - oppY * newScaleY * sinA);
        const oppWorldNewY = dragStartY + (oppX * newScaleX * sinA + oppY * newScaleY * cosA);
        
        // Adjust position to maintain opposite corner position
        selectedShape.x = dragStartX + (oppWorldStartX - oppWorldNewX);
        selectedShape.y = dragStartY + (oppWorldStartY - oppWorldNewY);
        selectedShape.scaleX = newScaleX;
        selectedShape.scaleY = newScaleY;
        markForRedraw();
    } else if (dragMode === 'scaleRight') {
        // Scale right edge, keeping left edge fixed
        const toMouseX = mx - dragStartX;
        const toMouseY = my - dragStartY;
        const cosA = Math.cos(selectedShape.rotation);
        const sinA = Math.sin(selectedShape.rotation);
        const projX = (toMouseX * cosA + toMouseY * sinA) / (selectedShape.size / 2);
        const newScaleX = Math.max(MIN_SCALE, Math.min(MAX_SCALE, Math.abs(projX))) * Math.sign(dragStartScaleX);
        
        // Calculate center shift to keep left edge fixed
        // Left edge is at local (-halfSize, 0), which in world is center + rotate(-halfSize * scaleX, 0)
        const totalShift = (selectedShape.size / 2) * (newScaleX - dragStartScaleX);
        selectedShape.x = dragStartX + totalShift * cosA;
        selectedShape.y = dragStartY + totalShift * sinA;
        selectedShape.scaleX = newScaleX;
        markForRedraw();
    } else if (dragMode === 'scaleLeft') {
        // Scale left edge, keeping right edge fixed
        const toMouseX = mx - dragStartX;
        const toMouseY = my - dragStartY;
        const cosA = Math.cos(selectedShape.rotation);
        const sinA = Math.sin(selectedShape.rotation);
        const projX = (toMouseX * cosA + toMouseY * sinA) / (selectedShape.size / 2);
        const newScaleX = Math.max(MIN_SCALE, Math.min(MAX_SCALE, Math.abs(projX))) * Math.sign(dragStartScaleX);
        
        // Calculate center shift to keep right edge fixed
        // Right edge is at local (+halfSize, 0), which in world is center + rotate(+halfSize * scaleX, 0)
        const totalShift = -(selectedShape.size / 2) * (newScaleX - dragStartScaleX);
        selectedShape.x = dragStartX + totalShift * cosA;
        selectedShape.y = dragStartY + totalShift * sinA;
        selectedShape.scaleX = newScaleX;
        markForRedraw();
    } else if (dragMode === 'scaleTop') {
        // Scale top edge, keeping bottom edge fixed
        const toMouseX = mx - dragStartX;
        const toMouseY = my - dragStartY;
        const cosA = Math.cos(selectedShape.rotation);
        const sinA = Math.sin(selectedShape.rotation);
        const halfH = (selectedShape.type === 'line' || selectedShape.type === 'arc') ? 20 : selectedShape.size / 2;
        const projY = (-toMouseX * sinA + toMouseY * cosA) / halfH;
        const newScaleY = Math.max(MIN_SCALE, Math.min(MAX_SCALE, Math.abs(projY))) * Math.sign(dragStartScaleY);
        
        // Calculate center shift to keep bottom edge fixed
        // Bottom edge is at local (0, +halfH), rotation transforms Y to (-Y*sin, Y*cos)
        const totalShift = -halfH * (newScaleY - dragStartScaleY);
        selectedShape.x = dragStartX - totalShift * sinA;
        selectedShape.y = dragStartY + totalShift * cosA;
        selectedShape.scaleY = newScaleY;
        markForRedraw();
    } else if (dragMode === 'scaleBottom') {
        // Scale bottom edge, keeping top edge fixed
        const toMouseX = mx - dragStartX;
        const toMouseY = my - dragStartY;
        const cosA = Math.cos(selectedShape.rotation);
        const sinA = Math.sin(selectedShape.rotation);
        const halfH = (selectedShape.type === 'line' || selectedShape.type === 'arc') ? 20 : selectedShape.size / 2;
        const projY = (-toMouseX * sinA + toMouseY * cosA) / halfH;
        const newScaleY = Math.max(MIN_SCALE, Math.min(MAX_SCALE, Math.abs(projY))) * Math.sign(dragStartScaleY);
        
        // Calculate center shift to keep top edge fixed
        // Top edge is at local (0, -halfH), rotation transforms Y to (-Y*sin, Y*cos)
        const totalShift = halfH * (newScaleY - dragStartScaleY);
        selectedShape.x = dragStartX - totalShift * sinA;
        selectedShape.y = dragStartY + totalShift * cosA;
        selectedShape.scaleY = newScaleY;
        markForRedraw();
    } else if (dragMode === 'control' && selectedShape.type === 'arc') {
        // Backwards compatibility
        const [lx, ly] = worldToLocal(selectedShape, mx, my);
        selectedShape.control.x = lx; selectedShape.control.y = ly;
        if (selectedShape.controls && selectedShape.controls.length > 0) {
            selectedShape.controls[0] = { x: lx, y: ly };
        }
        markForRedraw();
    } else if (dragMode && dragMode.startsWith('control-') && selectedShape.type === 'arc') {
        // Handle specific control point
        const controlIndex = parseInt(dragMode.split('-')[1]);
        const [lx, ly] = worldToLocal(selectedShape, mx, my);
        if (selectedShape.controls && selectedShape.controls[controlIndex]) {
            selectedShape.controls[controlIndex].x = lx;
            selectedShape.controls[controlIndex].y = ly;
            // Update old control for backwards compatibility
            if (controlIndex === 0) {
                selectedShape.control = { x: lx, y: ly };
            }
        }
        markForRedraw();
    } else if (dragMode === 'flip') {
        // Flip based on mouse movement direction
        const dx = mx - dragStartX;
        const dy = my - dragStartY;
        const distance = Math.hypot(dx, dy);

        if (distance > 20) {
            // Determine direction and flip accordingly
            if (Math.abs(dx) > Math.abs(dy)) {
                // Horizontal flip
                selectedShape.scaleX = -selectedShape.scaleX;
            } else {
                // Vertical flip
                selectedShape.scaleY = -selectedShape.scaleY;
            }
            dragMode = null; // End flip mode after flip
            markForRedraw();
            updateObjectList();
        }
    }
});

canvas.addEventListener('mouseup', () => {
    // Ignore canvas events if an input field is focused
    if (document.activeElement && document.activeElement.tagName === 'INPUT') return;

    // Handle freehand drawing mode
    if (isFreehandMode && isDrawing) {
        finishFreehandDrawing();
        return;
    }

    if (dragMode === 'marquee' && selectionBox) {
        // Select all shapes within the selection box
        const minX = Math.min(selectionBox.startX, selectionBox.endX);
        const maxX = Math.max(selectionBox.startX, selectionBox.endX);
        const minY = Math.min(selectionBox.startY, selectionBox.endY);
        const maxY = Math.max(selectionBox.startY, selectionBox.endY);
        
        selectedShapes = shapes.filter(s => {
            return s.x >= minX && s.x <= maxX && s.y >= minY && s.y <= maxY;
        });
        
        if (selectedShapes.length > 0) {
            selectedShape = selectedShapes[selectedShapes.length - 1];
            if (selectedShape.type !== 'matrix') {
                pointCountInput.value = selectedShape.pointCount;
                pointCountNumber.value = selectedShape.pointCount;
            }
        } else {
            selectedShape = null;
        }
        
        selectionBox = null;
        updateToolbarSections();
        updateObjectList();
        markForRedraw();
    }

    // Save state after any drag operation that modified shapes
    const hadDragMode = dragMode !== null;
    dragMode = null;
    scaleHandleIndex = null;
    
    if (hadDragMode) {
        updateObjectList();
        saveEditorStateToSession();
    }
});

function findShape(mx, my) {
    for (let i = shapes.length - 1; i >= 0; i--) {
        const s = shapes[i];
        const [lx, ly] = worldToLocal(s, mx, my);
        if (Math.abs(lx) <= s.size / 2 && Math.abs(ly) <= s.size / 2) return s;
    }
    return null;
}

function findHandle(s, mx, my) {
    // Use tighter bounding box for line and arc objects
    const halfSize = s.size / 2;
    const halfH = (s.type === 'line' || s.type === 'arc') ? 20 : halfSize;

    // Control handles for arc (support multiple)
    if (s.type === 'arc') {
        if (s.controls && s.controls.length > 0) {
            for (let i = 0; i < s.controls.length; i++) {
                const [wx, wy] = localToWorld(s, s.controls[i].x, s.controls[i].y);
                if (Math.hypot(mx - wx, my - wy) < HANDLE.CONTROL_RADIUS) return `control-${i}`;
            }
        } else if (s.control) {
            // Backwards compatibility
            const [wx, wy] = localToWorld(s, s.control.x, s.control.y);
            if (Math.hypot(mx - wx, my - wy) < HANDLE.CONTROL_RADIUS) return 'control';
        }
    }

    // Edge scale handles - keep opposite edge fixed
    const [scaleRightX, scaleRightY] = localToWorld(s, halfSize, 0);
    if (Math.hypot(mx - scaleRightX, my - scaleRightY) < HANDLE.HIT_RADIUS) return 'scaleRight';
    
    const [scaleLeftX, scaleLeftY] = localToWorld(s, -halfSize, 0);
    if (Math.hypot(mx - scaleLeftX, my - scaleLeftY) < HANDLE.HIT_RADIUS) return 'scaleLeft';
    
    // Top and bottom edge scale handles (skip for lines - they're 1-dimensional)
    if (s.type !== 'line') {
        const [scaleTopX, scaleTopY] = localToWorld(s, 0, -halfH);
        if (Math.hypot(mx - scaleTopX, my - scaleTopY) < HANDLE.HIT_RADIUS) return 'scaleTop';
        
        const [scaleBottomX, scaleBottomY] = localToWorld(s, 0, halfH);
        if (Math.hypot(mx - scaleBottomX, my - scaleBottomY) < HANDLE.HIT_RADIUS) return 'scaleBottom';
    }

    // Corner handles - dual ring (outer = rotate, inner = scale)
    const corners = [[-halfSize, -halfH], [halfSize, -halfH], [halfSize, halfH], [-halfSize, halfH]];
    for (let i = 0; i < corners.length; i++) {
        const [cx, cy] = corners[i];
        const [worldX, worldY] = localToWorld(s, cx, cy);
        const dist = Math.hypot(mx - worldX, my - worldY);
        
        // Outer ring = rotation
        if (dist < HANDLE.HIT_RADIUS_OUTER && dist >= HANDLE.HIT_RADIUS) {
            return `rotate-${i}`;
        }
        // Inner circle = scale
        if (dist < HANDLE.HIT_RADIUS) {
            return `scale-${i}`;
        }
    }
    return null;
}

// ========================================
// UI UPDATE FUNCTIONS [Lines 1253-1479]
// ========================================
function updateObjectList() {
    const container = document.getElementById('objectList');
    container.innerHTML = '';
    for (let i = 0; i < shapes.length; i++) {
        const s = shapes[i];
        const div = document.createElement('div');
        const isSelected = selectedShape === s || selectedShapes.includes(s);
        div.className = `shape-item ${isSelected ? 'selected' : ''}`;
        div.style.cursor = 'grab';
        div.draggable = false; // Start with draggable disabled
        div.dataset.shapeIndex = i;
        
        // Dynamically enable/disable dragging based on what element is under the mouse
        div.addEventListener('mouseenter', (e) => {
            const target = e.target;
            if (target.tagName !== 'INPUT' && target.tagName !== 'BUTTON' && 
                !target.closest('input') && !target.closest('button')) {
                div.draggable = true;
            }
        });
        
        div.addEventListener('mouseover', (e) => {
            const target = e.target;
            if (target.tagName === 'INPUT' || target.tagName === 'BUTTON' || 
                target.closest('input') || target.closest('button')) {
                div.draggable = false;
                div.style.cursor = 'default';
            } else {
                div.draggable = true;
                div.style.cursor = 'grab';
            }
        });
        
        div.onclick = (e) => {
            // Ignore clicks on input fields
            if (e.target.tagName === 'INPUT') {
                return;
            }
            
            if (e.ctrlKey || e.metaKey) {
                // Strg+Klick: Multi-Selektion
                if (selectedShapes.includes(s)) {
                    // Bereits selektiert -> entfernen
                    selectedShapes = selectedShapes.filter(shape => shape !== s);
                    if (selectedShape === s) {
                        selectedShape = selectedShapes.length > 0 ? selectedShapes[0] : null;
                    }
                } else {
                    // Neu hinzufügen
                    if (!selectedShapes.includes(s)) {
                        selectedShapes.push(s);
                    }
                    selectedShape = s;
                }
            } else {
                // Normal-Klick: Einzelselektion
                selectedShape = s;
                selectedShapes = [];
                
                // Wenn Teil einer Gruppe, ganze Gruppe selektieren
                if (s.groupId) {
                    selectGroup(s);
                }
            }
            updateToolbarSections();
            markForRedraw();
            updateObjectList();
        };

        // Drag & Drop handlers
        div.addEventListener('dragstart', (e) => {
            // Prevent drag if started from input field or interactive element
            if (e.target.tagName === 'INPUT' || 
                e.target.tagName === 'BUTTON' || 
                e.target.closest('input') || 
                e.target.closest('button')) {
                e.preventDefault();
                return false;
            }
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', i);
            div.style.opacity = '0.4';
        });

        div.addEventListener('dragend', (e) => {
            div.style.opacity = '1';
        });

        div.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        });

        div.addEventListener('drop', (e) => {
            e.preventDefault();
            const fromIndex = parseInt(e.dataTransfer.getData('text/plain'));
            const toIndex = parseInt(div.dataset.shapeIndex);

            if (fromIndex !== toIndex) {
                // Reorder shapes array
                const [movedShape] = shapes.splice(fromIndex, 1);
                shapes.splice(toIndex, 0, movedShape);
                markForRedraw();
                updateObjectList();
            }
        });

        // Initialize collapsed state
        if (s.collapsed === undefined) s.collapsed = true;

        // Title with toggle button
        const titleBar = document.createElement('div');
        titleBar.style.display = 'flex';
        titleBar.style.justifyContent = 'space-between';
        titleBar.style.alignItems = 'center';
        titleBar.style.pointerEvents = 'none'; // Allow drag on entire div

        // Calculate universe and channel range for this shape
        let channelStart = 1;
        for (let j = 0; j < i; j++) {
            const prevShape = shapes[j];
            const prevPts = (prevShape.type === 'line') ? getLinePoints(prevShape) : 
                           (prevShape.type === 'freehand') ? getFreehandPoints(prevShape) : 
                           getShapePoints(prevShape);
            channelStart += prevPts.length * 3;
        }
        
        const currentPts = (s.type === 'line') ? getLinePoints(s) : 
                          (s.type === 'freehand') ? getFreehandPoints(s) : 
                          getShapePoints(s);
        const channelEnd = channelStart + currentPts.length * 3 - 1;
        const universeNum = Math.floor((channelStart - 1) / 510) + 1;
        
        const title = document.createElement('div');
        title.className = 'shape-item-title';
        title.style.display = 'flex';
        title.style.flexDirection = 'column';
        title.style.gap = '0.2rem';
        title.style.flex = '1';
        title.style.minWidth = '0';
        
        // Editable name field
        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.value = s.name || s.id;
        nameInput.className = 'shape-name-input';
        nameInput.draggable = false; // Prevent drag on input
        nameInput.style.background = 'transparent';
        nameInput.style.border = 'none';
        nameInput.style.color = 'inherit';
        nameInput.style.fontSize = 'inherit';
        nameInput.style.fontWeight = '600';
        nameInput.style.padding = '0';
        nameInput.style.outline = 'none';
        nameInput.style.pointerEvents = 'auto';
        nameInput.style.cursor = 'text';
        nameInput.style.width = '100%';
        nameInput.addEventListener('click', (e) => e.stopPropagation());
        nameInput.addEventListener('mousedown', (e) => e.stopPropagation());
        nameInput.addEventListener('input', (e) => {
            s.name = e.target.value;
            saveEditorStateToSession();
        });
        nameInput.addEventListener('focus', (e) => {
            e.stopPropagation();
            e.target.style.borderBottom = '1px solid var(--primary-color)';
        });
        nameInput.addEventListener('blur', (e) => {
            e.target.style.borderBottom = 'none';
        });
        
        // Channel info
        const channelInfo = document.createElement('div');
        channelInfo.style.fontSize = '0.7rem';
        channelInfo.style.color = '#adb5bd';
        channelInfo.style.fontWeight = '400';
        channelInfo.textContent = `${s.id} - U${universeNum}, C${channelStart}-${channelEnd}`;
        
        title.appendChild(nameInput);
        title.appendChild(channelInfo);

        const toggleBtn = document.createElement('button');
        toggleBtn.textContent = s.collapsed ? '▼' : '▲';
        toggleBtn.draggable = false;
        toggleBtn.style.background = 'none';
        toggleBtn.style.border = 'none';
        toggleBtn.style.cursor = 'pointer';
        toggleBtn.style.fontSize = '0.8rem';
        toggleBtn.style.padding = '0.25rem 0.5rem';
        toggleBtn.style.color = 'var(--text-primary)';
        toggleBtn.style.pointerEvents = 'auto';
        toggleBtn.onclick = (e) => {
            e.stopPropagation();
            s.collapsed = !s.collapsed;
            updateObjectList();
        };

        titleBar.appendChild(title);
        titleBar.appendChild(toggleBtn);
        div.appendChild(titleBar);

        // Content container (collapsible)
        const contentContainer = document.createElement('div');
        contentContainer.style.display = s.collapsed ? 'none' : 'block';

        // Editierbare Felder
        const fieldsContainer = document.createElement('div');
        fieldsContainer.style.display = 'grid';
        fieldsContainer.style.gridTemplateColumns = '1fr 1fr';
        fieldsContainer.style.gap = '0.35rem';
        fieldsContainer.style.marginBottom = '0.5rem';
        fieldsContainer.style.fontSize = '0.75rem';

        const createEditField = (label, value, onChange, type = 'number') => {
            const wrapper = document.createElement('div');
            wrapper.style.display = 'flex';
            wrapper.style.flexDirection = 'column';
            wrapper.style.gap = '0.15rem';

            const labelEl = document.createElement('label');
            labelEl.textContent = label;
            labelEl.style.fontWeight = '600';
            labelEl.style.fontSize = '0.6rem';
            labelEl.style.color = '#adb5bd';
            labelEl.style.lineHeight = '1';

            if (type === 'slider') {
                // Create slider with value display
                const sliderContainer = document.createElement('div');
                sliderContainer.style.display = 'flex';
                sliderContainer.style.alignItems = 'center';
                sliderContainer.style.gap = '0.3rem';

                const input = document.createElement('input');
                input.type = 'range';
                input.className = 'form-range';
                input.draggable = false;
                input.style.flex = '1';
                input.style.height = '0.4rem';

                const valueDisplay = document.createElement('span');
                valueDisplay.style.fontSize = '0.6rem';
                valueDisplay.style.fontWeight = '600';
                valueDisplay.style.minWidth = '2.5rem';
                valueDisplay.style.textAlign = 'right';
                valueDisplay.style.color = '#adb5bd';

                if (label.includes('Rot')) {
                    input.min = '0';
                    input.max = '360';
                    input.step = '1';
                    input.value = value;
                    valueDisplay.textContent = `${Math.round(value)}°`;
                } else {
                    input.min = String(MIN_SCALE);
                    input.max = String(MAX_SCALE);
                    input.step = '0.1';
                    input.value = value;
                    valueDisplay.textContent = value.toFixed(2);
                }

                input.addEventListener('input', (e) => {
                    const val = parseFloat(e.target.value);
                    if (label.includes('Rot')) {
                        valueDisplay.textContent = `${Math.round(val)}°`;
                    } else {
                        valueDisplay.textContent = val.toFixed(2);
                    }
                    onChange(val);
                    markForRedraw();
                    saveEditorStateToSession();
                });
                input.addEventListener('mousedown', (e) => e.stopPropagation());

                sliderContainer.appendChild(input);
                sliderContainer.appendChild(valueDisplay);
                wrapper.appendChild(labelEl);
                wrapper.appendChild(sliderContainer);
            } else if (type === 'integer') {
                // Integer input (for pixel coordinates)
                const input = document.createElement('input');
                input.type = 'number';
                input.draggable = false;
                input.value = value;
                input.step = '1';
                input.style.padding = '0.2rem 0.3rem';
                input.style.fontSize = '0.65rem';
                input.style.border = '1px solid #dee2e6';
                input.style.borderRadius = '0.2rem';
                input.style.height = '1.5rem';
                input.style.width = '4rem'; // Width for 5 digits
                input.style.boxSizing = 'border-box';
                input.addEventListener('input', (e) => {
                    onChange(Math.round(parseFloat(e.target.value) || 0));
                    markForRedraw();
                    saveEditorStateToSession();
                });
                input.addEventListener('focus', (e) => {
                    e.stopPropagation();
                });
                input.addEventListener('click', (e) => {
                    e.stopPropagation();
                });
                input.addEventListener('mousedown', (e) => {
                    e.stopPropagation();
                });

                wrapper.appendChild(labelEl);
                wrapper.appendChild(input);
            } else {
                // Standard number input
                const input = document.createElement('input');
                input.type = 'number';
                input.draggable = false;
                input.value = value;
                input.step = '0.1';
                input.style.padding = '0.2rem 0.3rem';
                input.style.fontSize = '0.65rem';
                input.style.border = '1px solid #dee2e6';
                input.style.borderRadius = '0.2rem';
                input.style.height = '1.5rem';
                input.style.width = '4rem'; // Width for 5 digits
                input.style.boxSizing = 'border-box';
                input.addEventListener('input', (e) => {
                    onChange(parseFloat(e.target.value));
                    markForRedraw();
                    saveEditorStateToSession();
                });
                input.addEventListener('focus', (e) => {
                    e.stopPropagation();
                });
                input.addEventListener('click', (e) => {
                    e.stopPropagation();
                });
                input.addEventListener('mousedown', (e) => {
                    e.stopPropagation();
                });

                wrapper.appendChild(labelEl);
                wrapper.appendChild(input);
            }
            return wrapper;
        };

        fieldsContainer.appendChild(createEditField('X', Math.round(s.x), (val) => { s.x = Math.round(val); }, 'integer'));
        fieldsContainer.appendChild(createEditField('Y', Math.round(s.y), (val) => { s.y = Math.round(val); }, 'integer'));
        fieldsContainer.appendChild(createEditField('Size', s.size, (val) => { s.size = Math.max(20, val); }, 'number'));
        
        // Initialize scale linking (default to linked/symmetric)
        if (s.scaleLinked === undefined) s.scaleLinked = true;
        
        // Create compact scale section: ScaleX - 🔗 - ScaleY all in one line
        const scaleContainer = document.createElement('div');
        scaleContainer.style.gridColumn = '1 / -1';
        scaleContainer.style.display = 'flex';
        scaleContainer.style.gap = '0.3rem';
        scaleContainer.style.alignItems = 'flex-end';
        scaleContainer.style.marginTop = '0.15rem';
        scaleContainer.style.marginBottom = '0.15rem';
        
        // ScaleX field
        const scaleXField = createEditField('ScaleX', s.scaleX.toFixed(2), (val) => { 
            const newVal = Math.max(MIN_SCALE, Math.min(MAX_SCALE, val));
            s.scaleX = newVal;
            if (s.scaleLinked) {
                s.scaleY = newVal;
                updateObjectList();
            }
        }, 'number');
        scaleXField.style.flex = '1';
        scaleContainer.appendChild(scaleXField);
        
        // Lock/Unlock button (center)
        const lockButton = document.createElement('button');
        lockButton.draggable = false;
        lockButton.textContent = s.scaleLinked ? '🔗' : '🔓';
        lockButton.title = s.scaleLinked ? 'Linked (symmetric scaling)' : 'Unlinked (independent scaling)';
        lockButton.style.fontSize = '1rem';
        lockButton.style.padding = '0.2rem 0.35rem';
        lockButton.style.border = '1px solid #dee2e6';
        lockButton.style.borderRadius = '0.25rem';
        lockButton.style.background = s.scaleLinked ? '#e3f2fd' : '#f5f5f5';
        lockButton.style.cursor = 'pointer';
        lockButton.style.lineHeight = '1';
        lockButton.style.height = '1.5rem';
        lockButton.style.minWidth = '1.8rem';
        lockButton.style.flexShrink = '0';
        lockButton.onclick = (e) => {
            e.stopPropagation();
            s.scaleLinked = !s.scaleLinked;
            if (s.scaleLinked) {
                s.scaleY = s.scaleX;
            }
            updateObjectList();
            markForRedraw();
            saveEditorStateToSession();
        };
        lockButton.addEventListener('mousedown', (e) => e.stopPropagation());
        scaleContainer.appendChild(lockButton);
        
        // ScaleY field
        const scaleYField = createEditField('ScaleY', s.scaleY.toFixed(2), (val) => { 
            const newVal = Math.max(MIN_SCALE, Math.min(MAX_SCALE, val));
            s.scaleY = newVal;
            if (s.scaleLinked) {
                s.scaleX = newVal;
                updateObjectList();
            }
        }, 'number');
        scaleYField.style.flex = '1';
        scaleContainer.appendChild(scaleYField);
        
        fieldsContainer.appendChild(scaleContainer);
        
        fieldsContainer.appendChild(createEditField('Rot(°)', (s.rotation * 180 / Math.PI).toFixed(1), (val) => { s.rotation = val * Math.PI / 180; }, 'number'));

        contentContainer.appendChild(fieldsContainer);

        if (s.type === 'matrix') {
            const mFieldsContainer = document.createElement('div');
            mFieldsContainer.style.display = 'grid';
            mFieldsContainer.style.gridTemplateColumns = '1fr 1fr';
            mFieldsContainer.style.gap = '0.35rem';
            mFieldsContainer.style.marginBottom = '0.5rem';

            mFieldsContainer.appendChild(createEditField('Rows', s.rows, (val) => { s.rows = Math.max(1, Math.min(64, Math.round(val))); }, 'number'));
            mFieldsContainer.appendChild(createEditField('Cols', s.cols, (val) => { s.cols = Math.max(1, Math.min(64, Math.round(val))); }, 'number'));

            contentContainer.appendChild(mFieldsContainer);
        }

        const pts = (s.type === 'line') ? getLinePoints(s) : (s.type === 'arc') ? getArcPoints(s) : getShapePoints(s);
        const ul = document.createElement('ul');
        ul.className = 'points-list';
        ul.style.marginTop = '0.5rem';
        ul.style.paddingTop = '0.5rem';
        ul.style.borderTop = '1px solid #dee2e6';

        for (let i = 0; i < Math.min(pts.length, 8); i++) {
            const [gx, gy] = localToWorld(s, pts[i][0], pts[i][1]);
            const li = document.createElement('li');
            li.textContent = `P${i + 1}: (${Math.round(gx)}, ${Math.round(gy)})`;
            ul.appendChild(li);
        }
        if (pts.length > 8) {
            const li = document.createElement('li');
            li.textContent = `... +${pts.length - 8} weitere`;
            li.style.fontStyle = 'italic';
            ul.appendChild(li);
        }
        contentContainer.appendChild(ul);

        div.appendChild(contentContainer);
        container.appendChild(div);
    }
    
    // Update project statistics
    updateProjectStats();
}

// Track which shapes start a new 8-universe connection
let shapeUniverseBreaks = new Set();

// Update project statistics
function updateProjectStats() {
    // Count total points across all shapes and track universe boundaries
    let totalPoints = 0;
    let runningChannels = 0;
    const channelsPerUniverse = 510;
    const universesPerConnection = 8; // 8 universes per Art-Net connection
    const newBreaks = new Set();
    
    for (let i = 0; i < shapes.length; i++) {
        const s = shapes[i];
        const pts = (s.type === 'line') ? getLinePoints(s) : 
                    (s.type === 'freehand') ? getFreehandPoints(s) : 
                    getShapePoints(s);
        
        const shapeChannels = pts.length * 3;
        const previousUniverse = Math.floor(runningChannels / channelsPerUniverse);
        const previousConnectionGroup = Math.floor(previousUniverse / universesPerConnection);
        
        runningChannels += shapeChannels;
        
        const currentUniverse = Math.floor((runningChannels - 1) / channelsPerUniverse);
        const currentConnectionGroup = Math.floor(currentUniverse / universesPerConnection);
        
        // Check if this shape crosses into a new 8-universe connection group
        if (i > 0 && previousConnectionGroup < currentConnectionGroup) {
            newBreaks.add(i);
            
            // Show toast only if this is a new break (not previously detected)
            if (!shapeUniverseBreaks.has(i)) {
                const shapeLabel = s.label || `Shape ${i + 1}`;
                showToast(
                    `🔌 Neue Art-Net Verbindung benötigt ab "${shapeLabel}" (Universe ${currentUniverse + 1})`,
                    'warning',
                    5000
                );
            }
        }
        
        totalPoints += pts.length;
    }
    
    // Update global universe breaks
    shapeUniverseBreaks = newBreaks;
    
    // Calculate channels (RGB = 3 channels per pixel)
    const totalChannels = totalPoints * 3;
    
    // Calculate universes needed (510 channels per universe for RGB)
    const universesNeeded = Math.ceil(totalChannels / channelsPerUniverse);
    
    // Update display
    document.getElementById('statsPixels').textContent = totalPoints.toLocaleString();
    document.getElementById('statsChannels').textContent = totalChannels.toLocaleString();
    document.getElementById('statsUniverses').textContent = universesNeeded.toLocaleString();
    
    // Update note - just show channels per universe
    const noteEl = document.getElementById('statsNote');
    if (universesNeeded === 0) {
        noteEl.textContent = '';
        noteEl.className = 'stats-note';
    } else {
        const avgChannelsPerUniverse = Math.round(totalChannels / universesNeeded);
        noteEl.textContent = `⌀ ${avgChannelsPerUniverse} Kanäle/Universum`;
        noteEl.className = 'stats-note success';
    }
}

markForRedraw();
updateObjectList();

// ========================================
// GROUPING FUNCTIONS
// ========================================

function groupSelectedShapes() {
    const shapesToGroup = selectedShapes.length > 0 ? selectedShapes : (selectedShape ? [selectedShape] : []);
    
    if (shapesToGroup.length < 2) {
        showToast('Mindestens 2 Objekte zum Gruppieren erforderlich', 'warning');
        return;
    }
    
    // Create new group
    const groupId = `group-${groupCounter++}`;
    const group = {
        id: groupId,
        shapes: shapesToGroup.map(s => s.id)
    };
    
    // Mark shapes as grouped
    shapesToGroup.forEach(s => {
        s.groupId = groupId;
    });
    
    groups.push(group);
    
    showToast(`Gruppe mit ${shapesToGroup.length} Objekten erstellt`, 'success');
    
    markForRedraw();
    updateObjectList();
}

function ungroupSelectedShapes() {
    const shapesToUngroup = selectedShapes.length > 0 ? selectedShapes : (selectedShape ? [selectedShape] : []);
    
    if (shapesToUngroup.length === 0) {
        showToast('Keine Gruppe zum Auflösen ausgewählt', 'warning');
        return;
    }
    
    let ungroupedCount = 0;
    const groupIdsToRemove = new Set();
    
    // Remove group assignment from shapes
    shapesToUngroup.forEach(s => {
        if (s.groupId) {
            groupIdsToRemove.add(s.groupId);
            delete s.groupId;
            ungroupedCount++;
        }
    });
    
    // Remove groups from list
    groups = groups.filter(g => !groupIdsToRemove.has(g.id));
    
    if (ungroupedCount > 0) {
        showToast(`${ungroupedCount} Objekte aus Gruppe(n) entfernt`, 'success');
        markForRedraw();
        updateObjectList();
    } else {
        showToast('Keine gruppierten Objekte ausgewählt', 'warning');
    }
}

function getShapesInSameGroup(shape) {
    if (!shape.groupId) return [shape];
    
    const group = groups.find(g => g.id === shape.groupId);
    if (!group) return [shape];
    
    return shapes.filter(s => s.groupId === shape.groupId);
}

function selectGroup(shape) {
    if (!shape.groupId) return;
    
    const groupShapes = getShapesInSameGroup(shape);
    selectedShapes = groupShapes;
    selectedShape = groupShapes[0];
    
    markForRedraw();
    updateObjectList();
}

// ========================================
// TEXT TOOL [Stroke Font Text Generation]
// ========================================

function toggleTextTool() {
    const textSection = document.getElementById('textSection');
    const isVisible = textSection.style.display !== 'none';
    textSection.style.display = isVisible ? 'none' : 'block';
    if (!isVisible) {
        document.getElementById('textInput').focus();
    }
}

function addTextToCanvas() {
    const text = document.getElementById('textInput').value.toUpperCase();
    if (!text) {
        showToast('Bitte Text eingeben', 'warning');
        return;
    }

    const letterSize = parseInt(document.getElementById('letterSize').value) || 100;
    const letterSpacing = parseInt(document.getElementById('letterSpacing').value) || 20;
    const pointsPerLetter = parseInt(document.getElementById('letterPoints').value) || 20;

    let currentX = 300; // Start position
    const baseY = 300;
    
    // Create group for entire text
    const textGroupId = `group-${groupCounter++}`;
    const textGroup = {
        id: textGroupId,
        shapes: []
    };

    for (let i = 0; i < text.length; i++) {
        const char = text[i];
        const letterDef = STROKE_FONT[char];
        
        if (!letterDef) {
            debug.warn(`Character '${char}' not found in font`);
            continue;
        }

        // Skip empty letters (space)
        if (letterDef.length === 0) {
            currentX += (LETTER_WIDTHS[char] || DEFAULT_LETTER_WIDTH) * (letterSize / 100) + letterSpacing;
            continue;
        }

        // Create shapes for each stroke in the letter
        for (const stroke of letterDef) {
            const shape = {
                id: `shape-${shapeCounter++}`,
                type: stroke.type,
                x: currentX,
                y: baseY,
                size: letterSize,
                rotation: 0,
                scaleX: 1,
                scaleY: 1,
                color: 'cyan',
                pointCount: pointsPerLetter
            };

            if (stroke.type === 'line') {
                // Polyline - scale and position points
                shape.type = 'line';
                shape.linePoints = stroke.points.map(([x, y]) => ({
                    x: x * (letterSize / 100),
                    y: y * (letterSize / 100)
                }));
            } else if (stroke.type === 'arc') {
                // Convert arc to line with points along the arc path
                shape.type = 'line';
                const [cx, cy] = stroke.center;
                const radius = stroke.radius * (letterSize / 100);
                const startAngle = (stroke.startAngle || 0) * Math.PI / 180;
                const endAngle = (stroke.endAngle || 360) * Math.PI / 180;
                
                // Normalize angles
                let angle1 = startAngle;
                let angle2 = endAngle;
                if (angle2 < angle1) angle2 += Math.PI * 2;
                
                // Generate points along arc
                const arcPoints = [];
                const steps = Math.max(pointsPerLetter, Math.ceil(Math.abs(angle2 - angle1) / (Math.PI / 8)));
                
                for (let j = 0; j <= steps; j++) {
                    const t = j / steps;
                    const angle = angle1 + t * (angle2 - angle1);
                    const x = cx * (letterSize / 100) + Math.cos(angle) * radius;
                    const y = cy * (letterSize / 100) + Math.sin(angle) * radius;
                    arcPoints.push({ x, y });
                }
                
                shape.linePoints = arcPoints;
            }

            // Assign to text group
            shape.groupId = textGroupId;
            textGroup.shapes.push(shape.id);
            
            shapes.push(shape);
        }

        // Move to next letter position
        const letterWidth = (LETTER_WIDTHS[char] || DEFAULT_LETTER_WIDTH) * (letterSize / 100);
        currentX += letterWidth + letterSpacing;
    }

    // Add group to groups list if shapes were created
    if (textGroup.shapes.length > 0) {
        groups.push(textGroup);
        showToast(`Text "${text}" mit ${textGroup.shapes.length} Objekten hinzugefügt`, 'success');
    } else {
        showToast('Keine gültigen Zeichen im Text gefunden', 'warning');
    }

    // Clear input and hide panel
    document.getElementById('textInput').value = '';
    document.getElementById('textSection').style.display = 'none';
    
    markForRedraw();
    updateObjectList();
}

// ========================================
// CANVAS ZOOM & PAN FUNCTIONS
// ========================================

// Convert screen coordinates to canvas coordinates considering zoom (CSS transform handles this automatically)
function screenToCanvas(x, y) {
    // Subtract offset when in overflow mode
    if (allowOutOfBounds) {
        return [x - CANVAS_OVERFLOW, y - CANVAS_OVERFLOW];
    }
    return [x, y];
}

function updateCanvasSize() {
    const container = document.getElementById('canvasContainer');
    const wrapper = document.getElementById('canvasWrapper');
    
    // Set container size based on zoom
    const scaledWidth = canvas.width * canvasZoom;
    const scaledHeight = canvas.height * canvasZoom;
    
    // Make container at least as big as the wrapper or the scaled canvas
    const wrapperWidth = wrapper.clientWidth;
    const wrapperHeight = wrapper.clientHeight;
    
    container.style.width = Math.max(scaledWidth, wrapperWidth) + 'px';
    container.style.height = Math.max(scaledHeight, wrapperHeight) + 'px';
    
    // Center canvas in container when smaller than wrapper
    if (scaledWidth < wrapperWidth) {
        canvas.style.marginLeft = ((wrapperWidth - scaledWidth) / 2) + 'px';
    } else {
        canvas.style.marginLeft = '0';
    }
    
    if (scaledHeight < wrapperHeight) {
        canvas.style.marginTop = ((wrapperHeight - scaledHeight) / 2) + 'px';
    } else {
        canvas.style.marginTop = '0';
    }
    
    // Apply scale transform to canvas
    canvas.style.transform = `scale(${canvasZoom})`;
    canvas.style.transformOrigin = 'top left';
}

function fitCanvasToViewport() {
    const wrapper = document.getElementById('canvasWrapper');
    const wrapperWidth = wrapper.clientWidth;
    const wrapperHeight = wrapper.clientHeight;
    
    // Calculate zoom to fit canvas in viewport with some padding (90% of available space)
    const padding = 0.9; // Use 90% of viewport to leave some margin
    const zoomX = (wrapperWidth * padding) / canvas.width;
    const zoomY = (wrapperHeight * padding) / canvas.height;
    
    // Use the smaller zoom to ensure canvas fits in both dimensions
    canvasZoom = Math.min(zoomX, zoomY, MAX_SCALE);
    canvasZoom = Math.max(canvasZoom, MIN_SCALE);
    
    // Center the canvas
    canvasOffsetX = 0;
    canvasOffsetY = 0;
    
    updateCanvasSize();
    updateZoomDisplay();
    console.debug(`Auto-fit canvas: zoom=${canvasZoom.toFixed(2)}`);
}

function zoomIn() {
    canvasZoom = Math.min(canvasZoom * 1.2, 5.0);
    updateCanvasSize();
    updateZoomDisplay();
    markForRedraw();
}

function zoomOut() {
    canvasZoom = Math.max(canvasZoom / 1.2, 0.1);
    updateCanvasSize();
    updateZoomDisplay();
    markForRedraw();
}

function resetZoom() {
    fitCanvasToViewport();
    markForRedraw();
}

function updateZoomDisplay() {
    document.getElementById('zoomLevel').textContent = Math.round(canvasZoom * 100) + '%';
}

// Mouse wheel zoom with center on cursor
canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    
    const wrapper = document.getElementById('canvasWrapper');
    
    // Get mouse position relative to the wrapper (viewport)
    const wrapperRect = wrapper.getBoundingClientRect();
    const mouseX = e.clientX - wrapperRect.left;
    const mouseY = e.clientY - wrapperRect.top;
    
    // Get current scroll position
    const scrollX = wrapper.scrollLeft;
    const scrollY = wrapper.scrollTop;
    
    // Calculate the point in the canvas that's under the mouse (before zoom)
    const canvasX = (mouseX + scrollX) / canvasZoom;
    const canvasY = (mouseY + scrollY) / canvasZoom;
    
    // Store old zoom
    const oldZoom = canvasZoom;
    
    // Update zoom level
    if (e.deltaY < 0) {
        canvasZoom = Math.min(canvasZoom * 1.1, 5.0);
    } else {
        canvasZoom = Math.max(canvasZoom / 1.1, 0.1);
    }
    
    // Update canvas size first
    updateCanvasSize();
    
    // Calculate new scroll position to keep the same point under the mouse
    const newScrollX = canvasX * canvasZoom - mouseX;
    const newScrollY = canvasY * canvasZoom - mouseY;
    
    // Apply new scroll position
    wrapper.scrollLeft = newScrollX;
    wrapper.scrollTop = newScrollY;
    
    updateZoomDisplay();
    markForRedraw();
}, { passive: false });

// Initialize canvas size on load
updateCanvasSize();

// ========================================
// EXPORT FUNCTIONS TO GLOBAL SCOPE (for inline onclick handlers)
// ========================================
window.addShape = addShape;
window.deleteSelectedShape = deleteSelectedShape;
window.duplicateSelectedShape = duplicateSelectedShape;
window.resetSelectedShape = resetSelectedShape;
window.selectAllShapes = selectAllShapes;
window.groupSelectedShapes = groupSelectedShapes;
window.ungroupSelectedShapes = ungroupSelectedShapes;
window.saveProject = saveProject;
window.saveProjectToServer = saveProjectToServer;
window.showProjectManager = showProjectManager;
window.loadProjectFromServer = loadProjectFromServer;
window.refreshProjectList = refreshProjectList;
window.applyCustomCanvasSize = applyCustomCanvasSize;
window.clearBackgroundImage = clearBackgroundImage;
window.toggleTextTool = toggleTextTool;
window.addTextToCanvas = addTextToCanvas;
window.toggleFreehandDrawing = toggleFreehandDrawing;
window.zoomIn = zoomIn;
window.zoomOut = zoomOut;
window.resetZoom = resetZoom;
window.fitToCanvas = fitToCanvas;

// Export for LED mapper integration
window.markForRedraw = markForRedraw;
window.updateObjectList = updateObjectList;
window.saveEditorStateToSession = saveEditorStateToSession;

// ========================================
// CONTEXT MENU
// ========================================
const contextMenu = document.getElementById('contextMenu');
let contextMenuVisible = false;

// Show context menu
function showContextMenu(x, y) {
    // Update menu items based on selection
    updateContextMenuItems();
    
    // Position menu
    contextMenu.style.left = x + 'px';
    contextMenu.style.top = y + 'px';
    contextMenu.style.display = 'block';
    contextMenuVisible = true;
    
    // Ensure menu stays within viewport
    setTimeout(() => {
        const rect = contextMenu.getBoundingClientRect();
        if (rect.right > window.innerWidth) {
            contextMenu.style.left = (x - rect.width) + 'px';
        }
        if (rect.bottom > window.innerHeight) {
            contextMenu.style.top = (y - rect.height) + 'px';
        }
    }, 0);
}

// Hide context menu
function hideContextMenu() {
    contextMenu.style.display = 'none';
    contextMenuVisible = false;
}

// Update context menu items based on current selection
function updateContextMenuItems() {
    const hasSelection = selectedShape !== null || selectedShapes.length > 0;
    const hasMultipleSelection = selectedShapes.length > 1;
    const isGrouped = selectedShape && groups.some(g => g.shapes.includes(selectedShape));
    
    // Get all menu items
    const items = contextMenu.querySelectorAll('.context-menu-item');
    
    items.forEach(item => {
        const action = item.dataset.action;
        
        // Enable/disable based on context
        switch(action) {
            case 'duplicate':
            case 'delete':
            case 'reset':
            case 'flipHorizontal':
            case 'flipVertical':
                item.classList.toggle('disabled', !hasSelection);
                break;
            case 'group':
                item.classList.toggle('disabled', !hasMultipleSelection);
                break;
            case 'ungroup':
                item.classList.toggle('disabled', !isGrouped);
                break;
            case 'selectAll':
                item.classList.toggle('disabled', shapes.length === 0);
                break;
        }
    });
}

// Handle context menu actions
function handleContextMenuAction(action) {
    hideContextMenu();
    
    switch(action) {
        case 'duplicate':
            duplicateSelectedShape();
            break;
        case 'delete':
            deleteSelectedShape();
            break;
        case 'group':
            groupSelectedShapes();
            break;
        case 'ungroup':
            ungroupSelectedShapes();
            break;
        case 'selectAll':
            selectAllShapes();
            break;
        case 'reset':
            resetSelectedShape();
            break;
        case 'flipHorizontal':
            if (selectedShape) {
                selectedShape.scaleX = -selectedShape.scaleX;
                markForRedraw();
                saveSessionStateDebounced();
            }
            break;
        case 'flipVertical':
            if (selectedShape) {
                selectedShape.scaleY = -selectedShape.scaleY;
                markForRedraw();
                saveSessionStateDebounced();
            }
            break;
    }
}

// Canvas right-click handler
canvas.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    showContextMenu(e.clientX, e.clientY);
});

// Global context menu handler - prevent default except for UI elements
document.addEventListener('contextmenu', (e) => {
    // Allow default context menu for input elements, textareas, and main UI areas
    const allowedElements = ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'];
    const isInUI = e.target.closest('.menu-bar, .toolbar, .sidebar, .canvas-settings-bar, .modal, #objectList, #zoomControls');
    
    if (!allowedElements.includes(e.target.tagName) && !isInUI) {
        e.preventDefault();
    }
});

// Click outside to close
document.addEventListener('click', (e) => {
    if (contextMenuVisible && !contextMenu.contains(e.target)) {
        hideContextMenu();
    }
});

// Context menu item clicks
contextMenu.addEventListener('click', (e) => {
    const item = e.target.closest('.context-menu-item');
    if (item && !item.classList.contains('disabled')) {
        const action = item.dataset.action;
        handleContextMenuAction(action);
    }
});

// Hide on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && contextMenuVisible) {
        hideContextMenu();
    }
});