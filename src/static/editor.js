// ========================================
// TASTATUR-SHORTCUTS
// ========================================
// Entf/Backspace: Ausgewählte Form(en) löschen
// Strg+D: Ausgewählte Form(en) duplizieren
// Strg+S: Projekt speichern (lokal)

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

// Scale limits
const MIN_SCALE = 0.3;
const MAX_SCALE = 10;

// Handle configuration
const HANDLE = {
    SIZE: 7,
    DISTANCE: 26,
    DISTANCE_Y: 50,
    DISTANCE_SCALE_Y: 50,
    HIT_RADIUS: 12,
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

// Toast notification system
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast-message ${type}`;
    
    const icons = {
        success: '✓',
        error: '✗',
        info: 'ℹ',
        warning: '⚠'
    };
    
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-content">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    container.appendChild(toast);
    
    // Auto remove after duration
    setTimeout(() => {
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

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
let scaleHandleIndex = null;
let showConnectionLines = true; // Toggle for connection lines between objects
let dragStartX = 0, dragStartY = 0;
let dragStartRotation = 0;
let dragStartScaleX = 0, dragStartScaleY = 0;
let selectionBox = null; // For marquee selection: {startX, startY, endX, endY}
let backgroundImage = null;
let flipIconImage = null; // Bootstrap icon for flip handle
let rotateIconImage = null; // Bootstrap icon for rotate handle
let scaleYIconImage = null; // Bootstrap icon for Y-axis scale handle
let scaleXIconImage = null; // Bootstrap icon for X-axis scale handle

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
        canvas.width = w; 
        canvas.height = h;
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
    
    canvas.width = width;
    canvas.height = height;
    markForRedraw();
    updateObjectList();
    
    showToast(`Canvas-Größe: ${width} × ${height}`, 'success');
}

// ========================================
// EVENT LISTENERS - UI Controls [Lines 311-415]
// ========================================

// Theme Toggle
const themeToggle = document.getElementById('themeToggle');
const themeLabel = document.getElementById('themeLabel');


// Load saved theme preference or default to dark
const savedTheme = localStorage.getItem('theme') || 'dark';
if (savedTheme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
    themeToggle.checked = true;
    themeLabel.textContent = 'Dunkel';
} else {
    themeLabel.textContent = 'Hell';
}

themeToggle.addEventListener('change', () => {
    if (themeToggle.checked) {
        document.documentElement.setAttribute('data-theme', 'dark');
        themeLabel.textContent = 'Dunkel';
        localStorage.setItem('theme', 'dark');
    } else {
        document.documentElement.removeAttribute('data-theme');
        themeLabel.textContent = 'Hell';
        localStorage.setItem('theme', 'light');
    }
});

// Connection lines toggle
document.getElementById('showConnectionLines').addEventListener('change', e => {
    showConnectionLines = e.target.checked;
    markForRedraw();
});

// Project file input handler
document.getElementById('projectFileInput').addEventListener('change', e => {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (event) => {
            try {
                const projectData = JSON.parse(event.target.result);
                loadProject(projectData);
            } catch (error) {
                showToast('Ungültige Projektdatei!', 'error');
                console.error(error);
            }
        };
        reader.readAsText(file);
        // Reset input so same file can be loaded again
        e.target.value = '';
    }
});

document.getElementById('bgImageInput').addEventListener('change', e => {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (event) => {
            const img = new Image();
            img.onload = () => {
                backgroundImage = img;
                markForRedraw();
            };
            img.src = event.target.result;
        };
        reader.readAsDataURL(file);
    }
});

function clearBackgroundImage() {
    backgroundImage = null;
    document.getElementById('bgImageInput').value = '';
    markForRedraw();
}

const pointCountInput = document.getElementById('pointCount');
const pointCountNumber = document.getElementById('pointCountNumber');

pointCountInput.addEventListener('input', e => {
    const value = parseInt(e.target.value, 10);
    pointCountNumber.value = value;
    if (selectedShape && selectedShape.type !== 'matrix') {
        selectedShape.pointCount = value;
        // Für Freihand-Formen: Punkte neu samplen
        if (selectedShape.type === 'freehand' && selectedShape.freehandPoints) {
            selectedShape.freehandPoints = resampleFreehandPoints(selectedShape.freehandPoints, value);
        }
        markForRedraw(); updateObjectList();
    }
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
    const base = {
        id: `shape-${shapeCounter++}`,
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

        // Offset the position slightly so it's visible
        duplicate.x += 30;
        duplicate.y += 30;

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

// Show project manager modal
async function showProjectManager() {
    const modal = new bootstrap.Modal(document.getElementById('projectManagerModal'));
    modal.show();
    await refreshProjectList();
}

// Refresh project list
async function refreshProjectList() {
    const container = document.getElementById('projectListContainer');
    container.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Lädt...</span></div></div>';

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
            container.innerHTML = html;
        } else {
            container.innerHTML = '<div class="alert alert-info">Keine gespeicherten Projekte gefunden.</div>';
        }
    } catch (error) {
        console.error('Error loading projects:', error);
        container.innerHTML = `<div class="alert alert-danger">Fehler beim Laden: ${error.message}</div>`;
    }
}

// Load project from server
async function loadProjectFromServer(filename) {
    try {
        const response = await fetch(`/api/projects/load/${filename}`);
        const result = await response.json();

        if (result.success) {
            loadProject(result.data);
            bootstrap.Modal.getInstance(document.getElementById('projectManagerModal')).hide();
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
            canvas.width = projectData.canvas.width;
            canvas.height = projectData.canvas.height;

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
                    pointCount: shapeData.pointCount || 20
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
            width: canvas.width,
            height: canvas.height
        },
        objects: []
    };

    for (let i = 0; i < shapes.length; i++) {
        const s = shapes[i];
        const pts = (s.type === 'line') ? getLinePoints(s) : 
                    (s.type === 'arc') ? getArcPoints(s) : 
                    (s.type === 'freehand') ? getFreehandPoints(s) : 
                    getShapePoints(s);

        const points = pts.map((pt, j) => {
            const [gx, gy] = localToWorld(s, pt[0], pt[1]);
            return {
                id: j + 1,
                x: Math.round(gx),
                y: Math.round(gy)
            };
        });

        exportData.objects.push({
            id: s.id,
            points: points
        });
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
// DRAWING FUNCTIONS [Lines 544-640]
// ========================================
function draw() {
    if (!needsRedraw) return;
    needsRedraw = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw background image if present
    if (backgroundImage) {
        ctx.save();
        ctx.drawImage(backgroundImage, 0, 0, canvas.width, canvas.height);
        ctx.restore();
    }

    for (const s of shapes) {
        ctx.save();
        ctx.translate(s.x, s.y);
        ctx.rotate(s.rotation);
        ctx.scale(s.scaleX, s.scaleY);
        ctx.strokeStyle = s.color;
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

                // Draw connection line
                ctx.beginPath();
                ctx.moveTo(lastX, lastY);
                ctx.lineTo(firstX, firstY);
                ctx.strokeStyle = COLORS.CONNECTION_LINE;
                ctx.lineWidth = 1;
                ctx.stroke();
            }
        }
        ctx.restore();
    }

    // Draw tooltip for hovered point (in world coordinates, not transformed)
    if (hoveredPoint) {
        const pointLabel = `P${hoveredPoint.pointIndex + 1}`;

        ctx.save();
        ctx.font = `${TOOLTIP.FONT_SIZE}px Arial`;
        ctx.textBaseline = 'top';

        const textWidth = ctx.measureText(pointLabel).width;
        const boxWidth = textWidth + TOOLTIP.PADDING * 2;
        const boxHeight = TOOLTIP.FONT_SIZE + TOOLTIP.PADDING * 2;

        // Position tooltip above the point
        let tooltipX = hoveredPoint.x - boxWidth / 2;
        let tooltipY = hoveredPoint.y - boxHeight - TOOLTIP.OFFSET_Y;

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

    // Draw selection box (marquee)
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
    for (const [x, y] of corners) {
        // Draw corner handles with inverse scale to keep them constant size
        ctx.save();
        ctx.translate(x, y);
        ctx.scale(1 / s.scaleX, 1 / s.scaleY);
        
        // Fill with 30% alpha cyan
        ctx.fillStyle = COLORS.HANDLE_CORNER_FILL;
        ctx.beginPath();
        ctx.arc(0, 0, baseHandleSize, 0, Math.PI * 2);
        ctx.fill();

        // Outline with 1pt cyan
        ctx.strokeStyle = COLORS.HANDLE_CORNER_STROKE;
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.restore();
    }
    // Rotation handle (SVG icon) - top center
    if (rotateIconImage) {
        const iconX = 0;
        const iconY = (s.type === 'line' || s.type === 'arc') ? -20 - HANDLE.DISTANCE / s.scaleY : -s.size / 2 - HANDLE.DISTANCE / s.scaleY;

        // Draw icon with cyan tint, compensating for scale distortion
        ctx.save();
        ctx.translate(iconX, iconY);
        ctx.scale(1 / s.scaleX, 1 / s.scaleY);
        
        // Use filter to colorize the icon to cyan
        ctx.filter = 'brightness(0) saturate(100%) invert(70%) sepia(100%) saturate(2000%) hue-rotate(160deg)';
               ctx.drawImage(rotateIconImage, -iconSize / 2, -iconSize / 2, iconSize, iconSize);
        ctx.restore();
    } else {
        // Fallback to orange circle if icon not loaded
        const fallbackY = (s.type === 'line' || s.type === 'arc') ? -20 - HANDLE.DISTANCE / s.scaleY : -s.size / 2 - HANDLE.DISTANCE / s.scaleY;
        ctx.save();
        ctx.translate(0, fallbackY);
        ctx.scale(1 / s.scaleX, 1 / s.scaleY);
        ctx.fillStyle = 'orange';
        ctx.beginPath();
        ctx.arc(0, 0, baseHandleSize, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }
    // X-axis scale handle (cyan) - right middle
    if (scaleXIconImage) {
        const iconX = s.size / 2 + HANDLE.DISTANCE / s.scaleX;
        const iconY = 0;

        // Draw icon with cyan tint, compensating for scale distortion
        ctx.save();
        ctx.translate(iconX, iconY);
        ctx.scale(1 / s.scaleX, 1 / s.scaleY);
        
        // Use filter to colorize the icon to cyan
        ctx.filter = 'brightness(0) saturate(100%) invert(70%) sepia(100%) saturate(2000%) hue-rotate(160deg)';
        ctx.drawImage(scaleXIconImage, -iconSize / 2, -iconSize / 2, iconSize, iconSize);
        ctx.restore();
    } else {
        // Fallback to cyan circle if icon not loaded
        ctx.save();
        ctx.translate(s.size / 2 + HANDLE.DISTANCE / s.scaleX, 0);
        ctx.scale(1 / s.scaleX, 1 / s.scaleY);
        ctx.fillStyle = COLORS.HANDLE_ICON_TINT;
        ctx.beginPath();
        ctx.arc(0, 0, baseHandleSize, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }
    // Y-axis scale handle (SVG icon) - top middle
    if (scaleYIconImage) {
        const iconX = 0;
        const iconY = (s.type === 'line' || s.type === 'arc') ? -20 - HANDLE.DISTANCE_Y / s.scaleY : -s.size / 2 - HANDLE.DISTANCE_Y / s.scaleY;

        // Draw icon with cyan tint, compensating for scale distortion
        ctx.save();
        ctx.translate(iconX, iconY);
        ctx.scale(1 / s.scaleX, 1 / s.scaleY);
        
        // Use filter to colorize the icon to cyan
        ctx.filter = 'brightness(0) saturate(100%) invert(70%) sepia(100%) saturate(2000%) hue-rotate(160deg)';
        ctx.drawImage(scaleYIconImage, -iconSize / 2, -iconSize / 2, iconSize, iconSize);
        ctx.restore();
    } else {
        // Fallback to lime circle if icon not loaded
        const fallbackY = (s.type === 'line' || s.type === 'arc') ? -20 - HANDLE.DISTANCE_Y / s.scaleY : -s.size / 2 - HANDLE.DISTANCE_Y / s.scaleY;
        ctx.save();
        ctx.translate(0, fallbackY);
        ctx.scale(1 / s.scaleX, 1 / s.scaleY);
        ctx.fillStyle = 'lime';
        ctx.beginPath();
        ctx.arc(0, 0, baseHandleSize, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }
    // Flip handle (SVG icon) - bottom left
    if (flipIconImage) {
        const iconX = -s.size / 2 - HANDLE.DISTANCE / s.scaleX;
        const iconY = (s.type === 'line' || s.type === 'arc') ? 20 : s.size / 2;

        // Draw icon with cyan tint, compensating for scale distortion
        ctx.save();
        ctx.translate(iconX, iconY);
        ctx.scale(1 / s.scaleX, 1 / s.scaleY);
        
        // Use filter to colorize the icon to cyan
        ctx.filter = 'brightness(0) saturate(100%) invert(70%) sepia(100%) saturate(2000%) hue-rotate(160deg)';
        ctx.drawImage(flipIconImage, -iconSize / 2, -iconSize / 2, iconSize, iconSize);
        ctx.restore();
    } else {
        // Fallback to purple circle if icon not loaded
        const fallbackX = -s.size / 2 - HANDLE.DISTANCE / s.scaleX;
        const fallbackY = (s.type === 'line' || s.type === 'arc') ? 20 : s.size / 2;
        ctx.save();
        ctx.translate(fallbackX, fallbackY);
        ctx.scale(1 / s.scaleX, 1 / s.scaleY);
        ctx.fillStyle = COLORS.HANDLE_FLIP_FALLBACK;
        ctx.beginPath();
        ctx.arc(0, 0, baseHandleSize, 0, Math.PI * 2);
        ctx.fill();
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
        if (handle === 'rotate') {
            dragMode = 'rotate';
            dragStartRotation = selectedShape.rotation;
        } else if (handle === 'flip') {
            dragMode = 'flip';
            dragStartX = mx; dragStartY = my;
        } else if (handle === 'scaleX') {
            dragMode = 'scaleX';
            dragStartScaleX = selectedShape.scaleX;
        } else if (handle === 'scaleY') {
            dragMode = 'scaleY';
            dragStartScaleY = selectedShape.scaleY;
        } else if (handle && handle.startsWith('scale')) {
            dragMode = 'scale';
            scaleHandleIndex = parseInt(handle.split('-')[1], 10);
            dragStartScaleX = selectedShape.scaleX;
            dragStartScaleY = selectedShape.scaleY;
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
        canvas.style.cursor = 'crosshair';
        return;
    }

    const handle = findHandle(selectedShape, mx, my);

    // Cursor je nach Handle-Typ ändern
    if (handle === 'rotate') {
        canvas.style.cursor = 'grabbing';
    } else if (handle === 'flip') {
        canvas.style.cursor = 'pointer';
    } else if (handle === 'scaleX') {
        canvas.style.cursor = 'ew-resize';
    } else if (handle === 'scaleY') {
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
        const nx = mx - offsetX;
        const ny = my - offsetY;
        const dx = nx - selectedShape.x;
        const dy = ny - selectedShape.y;
        
        // Move all selected shapes (for grouped movement)
        const shapesToMove = selectedShapes.length > 0 ? selectedShapes : [selectedShape];
        
        shapesToMove.forEach(shape => {
            const newX = shape.x + dx;
            const newY = shape.y + dy;
            const halfW = (shape.size * Math.abs(shape.scaleX)) / 2;
            const halfH = (shape.size * Math.abs(shape.scaleY)) / 2;
            shape.x = Math.max(halfW, Math.min(canvas.width - halfW, newX));
            shape.y = Math.max(halfH, Math.min(canvas.height - halfH, newY));
        });
        
        markForRedraw();
    } else if (dragMode === 'rotate') {
        const dx = mx - selectedShape.x, dy = my - selectedShape.y;
        const currentAngle = Math.atan2(dy, dx);
        const initialAngle = Math.atan2(dragStartY - selectedShape.y, dragStartX - selectedShape.x);
        const angleDelta = currentAngle - initialAngle;
        selectedShape.rotation = dragStartRotation + angleDelta;
        markForRedraw();
    } else if (dragMode === 'scale') {
        const half = selectedShape.size / 2;
        const corners = [[-half, -half], [half, -half], [half, half], [-half, half]];
        const [cx, cy] = corners[scaleHandleIndex];

        // Vector from center to mouse
        const toMouseX = mx - selectedShape.x;
        const toMouseY = my - selectedShape.y;

        // Vector from center to corner (in local space, unscaled)
        const toCornerX = cx;
        const toCornerY = cy;

        // Calculate scale factors
        if (Math.abs(toCornerX) > 0.1 || Math.abs(toCornerY) > 0.1) {
            // Get world direction to corner before scale
            const cosA = Math.cos(selectedShape.rotation), sinA = Math.sin(selectedShape.rotation);
            const worldCornerDirX = (toCornerX * cosA - toCornerY * sinA);
            const worldCornerDirY = (toCornerX * sinA + toCornerY * cosA);

            // Distance scaling factor
            const originalDist = Math.hypot(worldCornerDirX, worldCornerDirY);
            const newDist = Math.hypot(toMouseX, toMouseY);

            if (originalDist > 0.1) {
                const scaleFactor = newDist / originalDist;

                if (selectedShape.type === 'matrix') {
                    // Uniform scaling for matrix
                    selectedShape.scaleX = selectedShape.scaleY = Math.max(MIN_SCALE, Math.min(MAX_SCALE, dragStartScaleX * scaleFactor));
                } else {
                    // Independent scaling for other shapes
                    const newScaleX = Math.max(MIN_SCALE, Math.min(MAX_SCALE, dragStartScaleX * scaleFactor));
                    const newScaleY = Math.max(MIN_SCALE, Math.min(MAX_SCALE, dragStartScaleY * scaleFactor));
                    selectedShape.scaleX = newScaleX;
                    selectedShape.scaleY = newScaleY;
                }
            }
        }
        markForRedraw();
    } else if (dragMode === 'scaleX') {
        // Scale only on X-axis
        const toMouseX = mx - selectedShape.x;
        const toMouseY = my - selectedShape.y;
        const cosA = Math.cos(selectedShape.rotation);
        const sinA = Math.sin(selectedShape.rotation);
        // Project mouse position onto rotated X-axis
        const projX = (toMouseX * cosA + toMouseY * sinA) / (selectedShape.size / 2);
        const newScaleX = Math.max(MIN_SCALE, Math.min(MAX_SCALE, dragStartScaleX * Math.abs(projX)));
        selectedShape.scaleX = newScaleX;
        markForRedraw();
    } else if (dragMode === 'scaleY') {
        // Scale only on Y-axis
        const toMouseX = mx - selectedShape.x;
        const toMouseY = my - selectedShape.y;
        const cosA = Math.cos(selectedShape.rotation);
        const sinA = Math.sin(selectedShape.rotation);
        // Project mouse position onto rotated Y-axis
        const projY = (-toMouseX * sinA + toMouseY * cosA) / (selectedShape.size / 2);
        const newScaleY = Math.max(MIN_SCALE, Math.min(MAX_SCALE, dragStartScaleY * Math.abs(projY)));
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

    dragMode = null; scaleHandleIndex = null; updateObjectList();
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
    
    // Rotation handle - position in world space (top center above shape)
    // Die Hitbox muss unabhängig von der Skalierung gleich groß bleiben:
    const rotHandleLocalX = 0;
    const rotHandleLocalY = (s.type === 'line' || s.type === 'arc') ? -20 - HANDLE.DISTANCE / s.scaleY : -s.size / 2 - HANDLE.DISTANCE / s.scaleY;
    const [rotWorldX, rotWorldY] = handleToWorld(s, rotHandleLocalX, rotHandleLocalY);
    // Korrigiere die Hitbox: Abstand im lokalen System berechnen und dann auf die Welt skalieren
    // Die Hitbox soll auf dem Bildschirm immer gleich groß sein, unabhängig von s.scaleX/s.scaleY
    // Daher: Maus in lokale Koordinaten transformieren
    const [localMx, localMy] = worldToLocal(s, mx, my);
    const distLocal = Math.hypot(localMx - rotHandleLocalX, localMy - rotHandleLocalY);
    if (distLocal < HANDLE.HIT_RADIUS) return 'rotate';

    // Flip handle - position in world space (bottom left)
    const flipHandleLocalX = -(s.size / 2) * s.scaleX - HANDLE.DISTANCE;
    const flipHandleLocalY = (s.type === 'line' || s.type === 'arc') ? 20 * s.scaleY : (s.size / 2) * s.scaleY;
    const [flipWorldX, flipWorldY] = handleToWorld(s, flipHandleLocalX, flipHandleLocalY);
    if (Math.hypot(mx - flipWorldX, my - flipWorldY) < HANDLE.HIT_RADIUS) return 'flip';

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

    // X-axis scale handle (cyan) - right middle
    const [scaleXWorldX, scaleXWorldY] = handleToWorld(s, (s.size / 2) * s.scaleX + HANDLE.DISTANCE, 0);
    if (Math.hypot(mx - scaleXWorldX, my - scaleXWorldY) < HANDLE.HIT_RADIUS) return 'scaleX';

    // Y-axis scale handle (lime) - top middle
    const scaleYLocalY = -((s.type === 'line' || s.type === 'arc') ? 20 : s.size / 2) * s.scaleY - HANDLE.DISTANCE_Y;
    const [scaleYWorldX, scaleYWorldY] = handleToWorld(s, 0, scaleYLocalY);
    if (Math.hypot(mx - scaleYWorldX, my - scaleYWorldY) < HANDLE.HIT_RADIUS) return 'scaleY';

    // Scale handles at corners - use UNSCALED local coordinates, let localToWorld apply scaling
    const corners = [[-halfSize, -halfH], [halfSize, -halfH], [halfSize, halfH], [-halfSize, halfH]];
    for (let i = 0; i < corners.length; i++) {
        const [cx, cy] = corners[i];
        const [worldX, worldY] = localToWorld(s, cx, cy);
        if (Math.hypot(mx - worldX, my - worldY) < HANDLE.HIT_RADIUS) return `scale-${i}`;
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
        div.draggable = true;
        div.dataset.shapeIndex = i;
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

        const title = document.createElement('div');
        title.className = 'shape-item-title';
        title.textContent = `${s.id} — ${s.type}`;

        const toggleBtn = document.createElement('button');
        toggleBtn.textContent = s.collapsed ? '▼' : '▲';
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
                });

                sliderContainer.appendChild(input);
                sliderContainer.appendChild(valueDisplay);
                wrapper.appendChild(labelEl);
                wrapper.appendChild(sliderContainer);
            } else {
                // Standard number input
                const input = document.createElement('input');
                input.type = 'number';
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
                });
                input.addEventListener('focus', (e) => {
                    e.stopPropagation();
                });
                input.addEventListener('click', (e) => {
                    e.stopPropagation();
                });

                wrapper.appendChild(labelEl);
                wrapper.appendChild(input);
            }
            return wrapper;
        };

        fieldsContainer.appendChild(createEditField('X', s.x.toFixed(1), (val) => { s.x = val; }, 'number'));
        fieldsContainer.appendChild(createEditField('Y', s.y.toFixed(1), (val) => { s.y = val; }, 'number'));
        fieldsContainer.appendChild(createEditField('Size', s.size, (val) => { s.size = Math.max(20, val); }, 'number'));
        fieldsContainer.appendChild(createEditField('ScaleX', s.scaleX.toFixed(2), (val) => { s.scaleX = Math.max(MIN_SCALE, Math.min(MAX_SCALE, val)); }, 'number'));
        fieldsContainer.appendChild(createEditField('ScaleY', s.scaleY.toFixed(2), (val) => { s.scaleY = Math.max(MIN_SCALE, Math.min(MAX_SCALE, val)); }, 'number'));
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
            console.warn(`Character '${char}' not found in font`);
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
    canvasZoom = 1.0;
    canvasOffsetX = 0;
    canvasOffsetY = 0;
    updateCanvasSize();
    updateZoomDisplay();
    markForRedraw();
}

function updateZoomDisplay() {
    document.getElementById('zoomLevel').textContent = Math.round(canvasZoom * 100) + '%';
}

// Mouse wheel zoom
canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    
    if (e.deltaY < 0) {
        canvasZoom = Math.min(canvasZoom * 1.1, 5.0);
    } else {
        canvasZoom = Math.max(canvasZoom / 1.1, 0.1);
    }
    
    updateCanvasSize();
    updateZoomDisplay();
    markForRedraw();
}, { passive: false });

// Initialize canvas size on load
updateCanvasSize();