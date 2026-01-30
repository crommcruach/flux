/**
 * Output Settings - Slice & Mask Editor
 * Multi-projector output configuration with transform, rotation, and soft edge blending
 * 
 * FEATURES:
 * - Multi-slice output mapping (slices = output regions)
 * - Mask system (per-slice masks for complex shapes)
 * - 4-corner perspective transform
 * - Rotation with snapping (15° increments)
 * - Soft edge blending with automatic overlap detection
 * - Per-edge soft edge control (top, bottom, left, right)
 * - Fade curves (linear, smooth, exponential)
 * - Gamma correction (overall + RGB channels)
 * - Context menu with positioning shortcuts
 * - Export/Import JSON configuration
 * - Backend session state persistence (no localStorage)
 * 
 * SECTIONS:
 * - Application State
 * - Initialization
 * - Type & Shape Selection
 * - Drawing Mode
 * - Mouse Event Handlers
 * - Rendering
 * - Transform & Rotation
 * - Soft Edge & Overlap Detection
 * - Screen Assignment & Output Management
 * - Export / Import / Storage
 * - UI Updates & List Rendering
 * - Utility Methods
 * - Toast & Context Menu
 */

// ========================================
// APPLICATION STATE
// ========================================
const app = {
    // Canvas
    canvas: null,
    ctx: null,
    videoCanvas: null,
    videoCtx: null,
    canvasWidth: 1920,
    canvasHeight: 1080,
    canvasZoom: 1.0,
    scale: 1,
    
    // Slices & Selection
    slices: [],
    selectedSlice: null,
    
    // Interaction State
    isDragging: false,
    isResizing: false,
    isRotating: false,
    isTransforming: false,
    transformMode: false,
    draggingCorner: null,
    dragStart: null,
    resizeHandle: null,
    
    // Grid & Snapping
    snapToGrid: false,
    gridSize: 10,
    
    // Outputs (dynamically loaded from backend)
    screens: [],
    customScreens: [],
    
    // Colors
    colors: ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#00BCD4', '#FFEB3B', '#E91E63', '#8BC34A'],
    colorIndex: 0,
    
    // Shape Drawing
    currentShape: 'rectangle',
    currentType: 'slice',
    drawingMode: false,
    drawingPoints: [],
    tempShape: null,
    contextMenuTarget: null,

    // ========================================
    // INITIALIZATION
    // ========================================
    async init() {
        this.canvas = document.getElementById('sliceCanvas');
        this.ctx = this.canvas.getContext('2d');
        this.videoCanvas = document.getElementById('videoCanvas');
        this.videoCtx = this.videoCanvas.getContext('2d');
        
        // Initialize compositions object
        this.compositions = this.compositions || {};

        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.onMouseUp(e));
        this.canvas.addEventListener('contextmenu', (e) => this.onContextMenu(e));
        
        // Close context menu on click outside
        document.addEventListener('click', (e) => {
    if (!e.target.closest('#contextMenu')) {
        this.closeContextMenu();
    }
        });
        
        // Mouse wheel zoom
        const wrapper = document.getElementById('canvasWrapper');
        wrapper.addEventListener('wheel', (e) => {
    if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -1 : 1;
        if (delta > 0) {
    this.zoomIn();
        } else {
    this.zoomOut();
        }
    }
        }, { passive: false });
        
        document.addEventListener('keydown', (e) => {
    if (e.key === 'Delete') this.deleteSelected();
    if (e.key === 'Escape') this.cancelDrawing();
    if (e.ctrlKey && e.key === 'd') {
        e.preventDefault();
        this.duplicateSelected();
    }
        });

        this.updateCanvasSize();
        this.loadVideoPlayerSettings();
        
        // Load outputs first (to get compositions and output configs)
        await this.loadExistingOutputs();
        
        // Then load slices (which will restore output assignments)
        await this.loadFromBackend();
        
        this.setType('slice'); // Set default to slice mode with correct UI state
        this.updateScreenButtons();
        this.updateUI();
        this.render();
    },

    async loadVideoPlayerSettings() {
        try {
            const response = await fetch('/api/player/video/settings');
            const data = await response.json();
            
            if (data.success && data.settings) {
                const settings = data.settings;
                
                // Calculate resolution from preset or custom
                let width, height;
                if (settings.preset === 'custom') {
                    width = settings.custom_width || 1920;
                    height = settings.custom_height || 1080;
                } else {
                    const presets = {
                        '720p': [1280, 720],
                        '1080p': [1920, 1080],
                        '1440p': [2560, 1440],
                        '2160p': [3840, 2160]
                    };
                    [width, height] = presets[settings.preset] || [1920, 1080];
                }
                
                // Update canvas dimensions
                this.canvasWidth = width;
                this.canvasHeight = height;
                document.getElementById('canvasWidth').value = width;
                document.getElementById('canvasHeight').value = height;
                
                console.log('✅ Canvas resolution loaded from player settings:', width, 'x', height);
                
                // Update canvas after loading settings
                this.updateCanvasSize();
            }
        } catch (error) {
            console.error('❌ Failed to load video player settings for canvas:', error);
        }
    },

    // ========================================
    // TYPE & SHAPE SELECTION
    // ========================================
    setType(type) {
        this.currentType = type;
        document.getElementById('typeSliceBtn').classList.toggle('active', type === 'slice');
        document.getElementById('typeMaskBtn').classList.toggle('active', type === 'mask');
        
        // Force rectangle for slices, show shape selector only for masks
        const shapeSection = document.getElementById('shapeTypeSection');
        if (type === 'slice') {
    this.currentShape = 'rectangle';
    shapeSection.style.display = 'none';
        } else {
    shapeSection.style.display = 'block';
        }
        
        // Show warning if trying to add mask without selected slice
        const warning = document.getElementById('maskWarning');
        if (type === 'mask' && (!this.selectedSlice || this.selectedSlice.type === 'mask')) {
    warning.style.display = 'block';
        } else {
    warning.style.display = 'none';
        }
        
        this.updateAddButton();
    },

    setShape(shape) {
        this.currentShape = shape;
        ['Rectangle', 'Circle', 'Triangle', 'Polygon', 'Freehand'].forEach(s => {
    const btn = document.getElementById(`shape${s}Btn`);
    if (btn) btn.classList.toggle('active', s.toLowerCase() === shape);
        });
        this.updateAddButton();
    },

    updateAddButton() {
        const btn = document.getElementById('addShapeBtn');
        if (btn) {
    if (this.currentType === 'slice') {
        btn.textContent = `➕ Add Slice`;
    } else {
        const shape = this.currentShape || 'rectangle';
        const shapeLabel = shape.charAt(0).toUpperCase() + shape.slice(1);
        btn.textContent = `➕ Add Mask (${shapeLabel})`;
    }
        }
    },

    // ========================================
    // DRAWING MODE
    // ========================================
    startDrawing() {
        // Don't allow adding mask without a selected slice
        if (this.currentType === 'mask' && (!this.selectedSlice || this.selectedSlice.type === 'mask')) {
    this.showToast('Select a slice first to add masks', 'error');
    return;
        }
        
        this.drawingMode = true;
        this.drawingPoints = [];
        this.tempShape = null;
        const needsFinish = ['polygon', 'freehand'].includes(this.currentShape);
        document.getElementById('finishDrawBtn').style.display = needsFinish ? 'block' : 'none';
        document.getElementById('cancelDrawBtn').style.display = 'block';
        this.canvas.style.cursor = 'crosshair';
        this.showToast(`Draw ${this.currentShape}`);
    },

    finishDrawing() {
        if (this.drawingPoints.length < 3 && ['polygon', 'triangle'].includes(this.currentShape)) {
    this.showToast('Need at least 3 points', 'error');
    return;
        }
        this.createShapeFromDrawing();
        this.cancelDrawing();
    },

    cancelDrawing() {
        this.drawingMode = false;
        this.drawingPoints = [];
        this.tempShape = null;
        document.getElementById('finishDrawBtn').style.display = 'none';
        document.getElementById('cancelDrawBtn').style.display = 'none';
        this.canvas.style.cursor = 'default';
        this.render();
    },

    createShapeFromDrawing() {
        const id = crypto.randomUUID();
        const color = this.colors[this.colorIndex % this.colors.length];
        this.colorIndex++;
        
        let shape = {
    id: id,
    type: this.currentType,
    shape: this.currentShape,
    color: color,
    label: `${this.currentType === 'mask' ? 'Mask' : 'Slice'} ${this.slices.filter(s => s.type === this.currentType).length + 1}`,
    visible: true
        };

        // Only slices have screens and masks
        if (this.currentType === 'slice') {
    shape.screens = [];
    shape.outputs = []; // Initialize outputs array for slice-to-output assignment
    shape.name = shape.label; // Also set name for backend consistency
    shape.masks = [];
    shape.brightness = 0;
    shape.contrast = 0;
    shape.red = 0;
    shape.green = 0;
    shape.blue = 0;
    shape.softEdge = {
        enabled: false,
        autoDetect: true,
        width: { top: 50, bottom: 50, left: 50, right: 50 },
        curve: 'smooth', // linear, smooth, exponential
        strength: 1.0,
        gamma: 1.0,
        gammaR: 1.0,
        gammaG: 1.0,
        gammaB: 1.0
    };
    shape.mirror = 'none'; // none, horizontal, vertical, both
        }

        if (this.currentShape === 'rectangle' && this.tempShape) {
    let x = Math.min(this.tempShape.x, this.tempShape.x + this.tempShape.width);
    let y = Math.min(this.tempShape.y, this.tempShape.y + this.tempShape.height);
    let w = Math.abs(this.tempShape.width);
    let h = Math.abs(this.tempShape.height);
    if (w < 10 || h < 10) return;
    shape.x = x;
    shape.y = y;
    shape.width = w;
    shape.height = h;
        } else if (this.currentShape === 'circle' && this.tempShape) {
    if (this.tempShape.radius < 5) return;
    shape.centerX = this.tempShape.centerX;
    shape.centerY = this.tempShape.centerY;
    shape.radius = this.tempShape.radius;
        } else if (['triangle', 'polygon', 'freehand'].includes(this.currentShape)) {
    if (this.drawingPoints.length < 2) return;
    shape.points = [...this.drawingPoints];
        }

        if (this.currentType === 'slice') {
    // Add as new slice
    this.slices.push(shape);
    this.selectedSlice = shape;
        } else {
    // Add as mask to selected slice
    if (this.selectedSlice && this.selectedSlice.type === 'slice') {
        if (!this.selectedSlice.masks) this.selectedSlice.masks = [];
        console.log('Adding mask to slice:', shape);
        this.selectedSlice.masks.push(shape);
        // Keep the parent slice selected
    }
        }

        this.updateUI();
        this.render();
        this.saveToBackend(); // Auto-save to backend
        this.showToast(`${shape.label} created`);
    },

    // ========================================
    // MOUSE EVENT HANDLERS
    // ========================================
    onMouseDown(e) {
        const pos = this.getMousePos(e);

        if (this.drawingMode) {
    if (this.currentShape === 'rectangle') {
        this.tempShape = { x: pos.x, y: pos.y, width: 0, height: 0 };
        this.isDragging = true;
    } else if (this.currentShape === 'circle') {
        if (!this.tempShape) {
    this.tempShape = { centerX: pos.x, centerY: pos.y, radius: 0 };
    this.isDragging = true;
        }
    } else if (this.currentShape === 'triangle') {
        this.drawingPoints.push({x: pos.x, y: pos.y});
        if (this.drawingPoints.length === 3) {
    this.createShapeFromDrawing();
    this.cancelDrawing();
        }
        this.render();
    } else if (this.currentShape === 'polygon') {
        this.drawingPoints.push({x: pos.x, y: pos.y});
        this.render();
    } else if (this.currentShape === 'freehand') {
        this.drawingPoints = [{x: pos.x, y: pos.y}];
        this.isDragging = true;
    }
    return;
        }

        // Check if clicking on transform corner
        if (this.transformMode && this.selectedSlice && this.selectedSlice.shape === 'rectangle') {
    const corner = this.getTransformCorner(pos, this.selectedSlice);
    if (corner !== null) {
        this.isTransforming = true;
        this.draggingCorner = corner;
        return;
    }
        }

        // Check rotation handle (rectangles only) - but not if transformed
        if (this.selectedSlice && this.selectedSlice.shape === 'rectangle' && !this.isTransformed(this.selectedSlice) && this.isOnRotationHandle(pos, this.selectedSlice)) {
    this.isRotating = true;
    this.dragStart = pos;
    return;
        }

        // Check resize handle (rectangles only) - but not if transformed
        if (this.selectedSlice && this.selectedSlice.shape === 'rectangle' && !this.isTransformed(this.selectedSlice)) {
    const handle = this.getResizeHandle(pos, this.selectedSlice);
    if (handle) {
        this.isResizing = true;
        this.resizeHandle = handle;
        this.dragStart = pos;
        return;
    }
        }

        // Check click on shape
        const clickedSlice = this.getSliceAt(pos);
        if (clickedSlice) {
    this.selectedSlice = clickedSlice;
    this.isDragging = true;
    this.dragStart = pos;
        } else {
    this.selectedSlice = null;
        }

        this.updateUI();
        this.render();
    },

    onMouseMove(e) {
        const pos = this.getMousePos(e);
        document.getElementById('mousePosition').textContent = `${Math.round(pos.x)}, ${Math.round(pos.y)}`;

        if (this.isTransforming && this.draggingCorner !== null && this.selectedSlice) {
    this.moveTransformCorner(pos);
    this.render();
    return;
        }

        if (this.drawingMode && this.isDragging) {
    if (this.currentShape === 'rectangle' && this.tempShape) {
        this.tempShape.width = pos.x - this.tempShape.x;
        this.tempShape.height = pos.y - this.tempShape.y;
        this.render();
    } else if (this.currentShape === 'circle' && this.tempShape) {
        const dx = pos.x - this.tempShape.centerX;
        const dy = pos.y - this.tempShape.centerY;
        this.tempShape.radius = Math.sqrt(dx * dx + dy * dy);
        this.render();
    } else if (this.currentShape === 'freehand') {
        this.drawingPoints.push({x: pos.x, y: pos.y});
        this.render();
    }
    return;
        }

        if (this.isRotating && this.selectedSlice) {
    this.rotateSlice(pos);
    this.render();
        } else if (this.isDragging && this.selectedSlice) {
    const dx = pos.x - this.dragStart.x;
    const dy = pos.y - this.dragStart.y;
    this.moveShape(this.selectedSlice, dx, dy);
    this.dragStart = pos;
    this.render();
        } else if (this.isResizing && this.selectedSlice) {
    this.resizeSlice(pos);
    this.render();
        }
    },

    onMouseUp(e) {
        if (this.drawingMode && this.isDragging) {
    if (['rectangle', 'circle'].includes(this.currentShape)) {
        this.createShapeFromDrawing();
        this.cancelDrawing();
    } else if (this.currentShape === 'freehand' && this.drawingPoints.length > 5) {
        this.createShapeFromDrawing();
        this.cancelDrawing();
    }
        }

        this.isDragging = false;
        this.isResizing = false;
        this.isRotating = false;
        this.isTransforming = false;
        this.draggingCorner = null;
        this.resizeHandle = null;

        if (!this.drawingMode) {
            this.saveToBackend(); // Auto-save to backend
        }
        this.updateUI();
        this.render();
    },

    snapToGridPos(pos) {
        if (!this.snapToGrid) return pos;
        return {
    x: Math.round(pos.x / this.gridSize) * this.gridSize,
    y: Math.round(pos.y / this.gridSize) * this.gridSize
        };
    },

    moveShape(shape, dx, dy) {
        if (shape.shape === 'rectangle') {
    let newX = shape.x + dx;
    let newY = shape.y + dy;
    
    if (this.snapToGrid) {
        const snapped = this.snapToGridPos({ x: newX, y: newY });
        newX = snapped.x;
        newY = snapped.y;
    }
    
    // Check for center alignment and snap
    const centerX = newX + shape.width / 2;
    const centerY = newY + shape.height / 2;
    const canvasCenterX = this.canvasWidth / 2;
    const canvasCenterY = this.canvasHeight / 2;
    const snapThreshold = 10;
    
    if (Math.abs(centerX - canvasCenterX) < snapThreshold) {
        newX = canvasCenterX - shape.width / 2;
    }
    if (Math.abs(centerY - canvasCenterY) < snapThreshold) {
        newY = canvasCenterY - shape.height / 2;
    }
    
    // Bounds checking
    newX = Math.max(0, Math.min(newX, this.canvasWidth - shape.width));
    newY = Math.max(0, Math.min(newY, this.canvasHeight - shape.height));
    
    // Calculate actual movement after snapping and bounds
    const actualDx = newX - shape.x;
    const actualDy = newY - shape.y;
    
    shape.x = newX;
    shape.y = newY;
    
    // Move masks with the slice if this is a slice with masks
    if (shape.type === 'slice' && shape.masks && shape.masks.length > 0) {
        shape.masks.forEach(mask => {
    if (mask.shape === 'rectangle') {
        mask.x += actualDx;
        mask.y += actualDy;
    } else if (mask.shape === 'circle') {
        mask.centerX += actualDx;
        mask.centerY += actualDy;
    } else if (mask.points) {
        mask.points.forEach(p => {
                    p.x += actualDx;
                    p.y += actualDy;
        });
    }
        });
    }
        } else if (shape.shape === 'circle') {
    shape.centerX = Math.max(shape.radius, Math.min(shape.centerX + dx, this.canvasWidth - shape.radius));
    shape.centerY = Math.max(shape.radius, Math.min(shape.centerY + dy, this.canvasHeight - shape.radius));
        } else if (shape.points) {
    shape.points.forEach(p => {
        p.x += dx;
        p.y += dy;
    });
        }
    },

    isOnRotationHandle(pos, slice) {
        if (slice.shape !== 'rectangle') return false;
        const centerX = slice.x + slice.width / 2;
        const centerY = slice.y + slice.height / 2;
        const rotation = (slice.rotation || 0) * Math.PI / 180;
        
        // Rotation handle position (unrotated)
        const handleX = centerX;
        const handleY = slice.y - 30;
        
        // Rotate the handle position around center
        const dx = handleX - centerX;
        const dy = handleY - centerY;
        const rotHandleX = centerX + dx * Math.cos(rotation) - dy * Math.sin(rotation);
        const rotHandleY = centerY + dx * Math.sin(rotation) + dy * Math.cos(rotation);
        
        const distance = Math.sqrt(Math.pow(pos.x - rotHandleX, 2) + Math.pow(pos.y - rotHandleY, 2));
        return distance <= 15;
    },

    getTransformCorner(pos, slice) {
        if (!slice.transformCorners) {
    // Initialize transform corners as regular rectangle corners
    slice.transformCorners = [
        {x: 0, y: 0}, // top-left
        {x: slice.width, y: 0}, // top-right
        {x: slice.width, y: slice.height}, // bottom-right
        {x: 0, y: slice.height} // bottom-left
    ];
        }

        const handleSize = 12;
        for (let i = 0; i < slice.transformCorners.length; i++) {
    const corner = slice.transformCorners[i];
    const cornerX = slice.x + corner.x;
    const cornerY = slice.y + corner.y;
    
    if (Math.abs(pos.x - cornerX) < handleSize && Math.abs(pos.y - cornerY) < handleSize) {
        return i;
    }
        }
        return null;
    },

    moveTransformCorner(pos) {
        const slice = this.selectedSlice;
        if (!slice || !slice.transformCorners) return;

        // Update corner position relative to slice origin (no constraints)
        const corner = slice.transformCorners[this.draggingCorner];
        corner.x = pos.x - slice.x;
        corner.y = pos.y - slice.y;
        
        // Recalculate slice dimensions based on bounding box of transform corners
        this.updateSliceDimensionsFromTransform(slice);
    },

    updateSliceDimensionsFromTransform(slice) {
        if (!slice.transformCorners) return;
        
        // Find bounding box of all corners
        let minX = Infinity, minY = Infinity;
        let maxX = -Infinity, maxY = -Infinity;
        
        slice.transformCorners.forEach(corner => {
    const absX = slice.x + corner.x;
    const absY = slice.y + corner.y;
    minX = Math.min(minX, absX);
    minY = Math.min(minY, absY);
    maxX = Math.max(maxX, absX);
    maxY = Math.max(maxY, absY);
        });
        
        // Update slice position and size to match bounding box
        const oldX = slice.x;
        const oldY = slice.y;
        
        slice.x = minX;
        slice.y = minY;
        slice.width = maxX - minX;
        slice.height = maxY - minY;
        
        // Adjust corner positions relative to new origin
        const deltaX = oldX - slice.x;
        const deltaY = oldY - slice.y;
        slice.transformCorners.forEach(corner => {
    corner.x += deltaX;
    corner.y += deltaY;
        });
    },

    isTransformed(slice) {
        if (!slice.transformCorners) return false;
        
        // Check if corners differ from default rectangle corners
        const defaultCorners = [
    {x: 0, y: 0},
    {x: slice.width, y: 0},
    {x: slice.width, y: slice.height},
    {x: 0, y: slice.height}
        ];
        
        for (let i = 0; i < 4; i++) {
    const c = slice.transformCorners[i];
    const d = defaultCorners[i];
    if (Math.abs(c.x - d.x) > 1 || Math.abs(c.y - d.y) > 1) {
        return true;
    }
        }
        return false;
    },

    drawTransformHandles(slice) {
        if (!slice.transformCorners) {
    slice.transformCorners = [
        {x: 0, y: 0},
        {x: slice.width, y: 0},
        {x: slice.width, y: slice.height},
        {x: 0, y: slice.height}
    ];
        }

        // Draw lines connecting corners
        this.ctx.strokeStyle = '#FFA500';
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        for (let i = 0; i < slice.transformCorners.length; i++) {
    const corner = slice.transformCorners[i];
    const x = slice.x + corner.x;
    const y = slice.y + corner.y;
    if (i === 0) {
        this.ctx.moveTo(x, y);
    } else {
        this.ctx.lineTo(x, y);
    }
        }
        this.ctx.closePath();
        this.ctx.stroke();

        // Draw corner handles
        this.ctx.fillStyle = '#FFA500';
        slice.transformCorners.forEach((corner, i) => {
    const x = slice.x + corner.x;
    const y = slice.y + corner.y;
    this.ctx.fillRect(x - 8, y - 8, 16, 16);
    
    // Draw corner number
    this.ctx.fillStyle = '#000';
    this.ctx.font = 'bold 10px Arial';
    this.ctx.textAlign = 'center';
    this.ctx.textBaseline = 'middle';
    this.ctx.fillText(i + 1, x, y);
    this.ctx.fillStyle = '#FFA500';
        });
    },

    rotateSlice(pos) {
        const slice = this.selectedSlice;
        if (slice.shape !== 'rectangle') return;
        
        const centerX = slice.x + slice.width / 2;
        const centerY = slice.y + slice.height / 2;
        let angle = Math.atan2(pos.y - centerY, pos.x - centerX) * 180 / Math.PI + 90;
        angle = angle % 360;
        
        // Snap to 0, 90, 180, 270 degrees if within 3 degrees
        const snapAngles = [0, 90, 180, 270, 360];
        for (let snapAngle of snapAngles) {
    if (Math.abs(angle - snapAngle) < 3) {
        angle = snapAngle % 360;
        break;
    }
        }
        
        // Calculate rotation delta
        const oldRotation = slice.rotation || 0;
        const newRotation = Math.round(angle * 10) / 10;
        const deltaRotation = (newRotation - oldRotation) * Math.PI / 180;
        
        slice.rotation = newRotation;
        
        // Rotate transform corners if they exist
        if (slice.transformCorners && Math.abs(deltaRotation) > 0.001) {
    const cx = slice.width / 2;
    const cy = slice.height / 2;
    
    slice.transformCorners = slice.transformCorners.map(corner => {
        // Translate to center
        const x = corner.x - cx;
        const y = corner.y - cy;
        
        // Rotate
        const cos = Math.cos(deltaRotation);
        const sin = Math.sin(deltaRotation);
        const newX = x * cos - y * sin;
        const newY = x * sin + y * cos;
        
        // Translate back
        return {
    x: newX + cx,
    y: newY + cy
        };
    });
        }
    },

    resizeSlice(pos) {
        const slice = this.selectedSlice;
        const h = this.resizeHandle;

        switch (h) {
    case 'se':
        slice.width = Math.max(10, pos.x - slice.x);
        slice.height = Math.max(10, pos.y - slice.y);
        break;
    case 'sw':
        const newW = slice.width + (slice.x - pos.x);
        if (newW >= 10) {
    slice.x = pos.x;
    slice.width = newW;
        }
        slice.height = Math.max(10, pos.y - slice.y);
        break;
    case 'ne':
        slice.width = Math.max(10, pos.x - slice.x);
        const newH = slice.height + (slice.y - pos.y);
        if (newH >= 10) {
    slice.y = pos.y;
    slice.height = newH;
        }
        break;
    case 'nw':
        const nw = slice.width + (slice.x - pos.x);
        const nh = slice.height + (slice.y - pos.y);
        if (nw >= 10 && nh >= 10) {
    slice.x = pos.x;
    slice.y = pos.y;
    slice.width = nw;
    slice.height = nh;
        }
        break;
    case 'e': // East - change width only
        slice.width = Math.max(10, pos.x - slice.x);
        break;
    case 'w': // West - change width only
        const newWest = slice.width + (slice.x - pos.x);
        if (newWest >= 10) {
    slice.x = pos.x;
    slice.width = newWest;
        }
        break;
    case 's': // South - change height only
        slice.height = Math.max(10, pos.y - slice.y);
        break;
    case 'n': // North - change height only
        const newNorth = slice.height + (slice.y - pos.y);
        if (newNorth >= 10) {
    slice.y = pos.y;
    slice.height = newNorth;
        }
        break;
        }
    },

    getResizeHandle(pos, slice) {
        if (slice.shape !== 'rectangle') return null;
        const handleSize = 10;
        const centerX = slice.x + slice.width / 2;
        const centerY = slice.y + slice.height / 2;
        const rotation = (slice.rotation || 0) * Math.PI / 180;
        
        // Helper function to rotate a point around center
        const rotatePoint = (x, y) => {
    const dx = x - centerX;
    const dy = y - centerY;
    return {
        x: centerX + dx * Math.cos(rotation) - dy * Math.sin(rotation),
        y: centerY + dx * Math.sin(rotation) + dy * Math.cos(rotation)
    };
        };
        
        // Corner handles (unrotated positions)
        const corners = {
    'nw': { x: slice.x, y: slice.y },
    'ne': { x: slice.x + slice.width, y: slice.y },
    'sw': { x: slice.x, y: slice.y + slice.height },
    'se': { x: slice.x + slice.width, y: slice.y + slice.height }
        };

        // Check corners first (priority)
        for (let [handle, hPos] of Object.entries(corners)) {
    const rotPos = rotatePoint(hPos.x, hPos.y);
    if (Math.abs(pos.x - rotPos.x) < handleSize && Math.abs(pos.y - rotPos.y) < handleSize) {
        return handle;
    }
        }
        
        // Edge handles (middle of each side)
        const edges = {
    'n': { x: slice.x + slice.width / 2, y: slice.y },
    's': { x: slice.x + slice.width / 2, y: slice.y + slice.height },
    'e': { x: slice.x + slice.width, y: slice.y + slice.height / 2 },
    'w': { x: slice.x, y: slice.y + slice.height / 2 }
        };
        
        for (let [handle, hPos] of Object.entries(edges)) {
    const rotPos = rotatePoint(hPos.x, hPos.y);
    if (Math.abs(pos.x - rotPos.x) < handleSize && Math.abs(pos.y - rotPos.y) < handleSize) {
        return handle;
    }
        }
        
        return null;
    },

    getSliceAt(pos) {
        // Check masks first (they're on top)
        for (let i = this.slices.length - 1; i >= 0; i--) {
    const slice = this.slices[i];
    if (slice.type === 'slice' && slice.masks && slice.masks.length > 0) {
        for (let j = slice.masks.length - 1; j >= 0; j--) {
    if (this.isPointInShape(pos, slice.masks[j])) {
        return slice.masks[j];
    }
        }
    }
        }
        // Then check slices
        for (let i = this.slices.length - 1; i >= 0; i--) {
    if (this.isPointInShape(pos, this.slices[i])) {
        return this.slices[i];
    }
        }
        return null;
    },

    isPointInShape(pos, shape) {
        if (shape.shape === 'rectangle') {
    return pos.x >= shape.x && pos.x <= shape.x + shape.width &&
           pos.y >= shape.y && pos.y <= shape.y + shape.height;
        } else if (shape.shape === 'circle') {
    const dx = pos.x - shape.centerX;
    const dy = pos.y - shape.centerY;
    return (dx * dx + dy * dy) <= (shape.radius * shape.radius);
        } else if (shape.points && shape.points.length > 0) {
    // Point in polygon
    let inside = false;
    for (let i = 0, j = shape.points.length - 1; i < shape.points.length; j = i++) {
        const xi = shape.points[i].x, yi = shape.points[i].y;
        const xj = shape.points[j].x, yj = shape.points[j].y;
        const intersect = ((yi > pos.y) !== (yj > pos.y)) &&
    (pos.x < (xj - xi) * (pos.y - yi) / (yj - yi) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
        }
        return false;
    },

    // ========================================
    // RENDERING
    // ========================================
    render() {
        this.ctx.clearRect(0, 0, this.canvasWidth, this.canvasHeight);

        // Draw alignment guides if dragging or resizing
        if ((this.isDragging || this.isResizing) && this.selectedSlice && this.selectedSlice.shape === 'rectangle') {
    const slice = this.selectedSlice;
    const centerX = slice.x + slice.width / 2;
    const centerY = slice.y + slice.height / 2;
    const snapThreshold = 10;
    
    // Quarter points
    const quarterX = this.canvasWidth / 4;
    const halfX = this.canvasWidth / 2;
    const threeQuarterX = this.canvasWidth * 3 / 4;
    const quarterY = this.canvasHeight / 4;
    const halfY = this.canvasHeight / 2;
    const threeQuarterY = this.canvasHeight * 3 / 4;
    
    const verticalGuides = [];
    const horizontalGuides = [];
    
    // Check center alignment
    if (Math.abs(centerX - quarterX) < snapThreshold) verticalGuides.push(quarterX);
    if (Math.abs(centerX - halfX) < snapThreshold) verticalGuides.push(halfX);
    if (Math.abs(centerX - threeQuarterX) < snapThreshold) verticalGuides.push(threeQuarterX);
    
    if (Math.abs(centerY - quarterY) < snapThreshold) horizontalGuides.push(quarterY);
    if (Math.abs(centerY - halfY) < snapThreshold) horizontalGuides.push(halfY);
    if (Math.abs(centerY - threeQuarterY) < snapThreshold) horizontalGuides.push(threeQuarterY);
    
    // Check edge alignment when resizing
    if (this.isResizing) {
        // Check left and right edges
        [quarterX, halfX, threeQuarterX].forEach(guide => {
    if (Math.abs(slice.x - guide) < snapThreshold || 
        Math.abs(slice.x + slice.width - guide) < snapThreshold) {
        if (!verticalGuides.includes(guide)) verticalGuides.push(guide);
    }
        });
        // Check top and bottom edges
        [quarterY, halfY, threeQuarterY].forEach(guide => {
    if (Math.abs(slice.y - guide) < snapThreshold || 
        Math.abs(slice.y + slice.height - guide) < snapThreshold) {
        if (!horizontalGuides.includes(guide)) horizontalGuides.push(guide);
    }
        });
    }
    
    // Draw guides
    if (verticalGuides.length > 0 || horizontalGuides.length > 0) {
        this.ctx.save();
        this.ctx.strokeStyle = '#FFC107';
        this.ctx.lineWidth = 1;
        this.ctx.setLineDash([5, 5]);
        
        verticalGuides.forEach(x => {
    this.ctx.beginPath();
    this.ctx.moveTo(x, 0);
    this.ctx.lineTo(x, this.canvasHeight);
    this.ctx.stroke();
        });
        
        horizontalGuides.forEach(y => {
    this.ctx.beginPath();
    this.ctx.moveTo(0, y);
    this.ctx.lineTo(this.canvasWidth, y);
    this.ctx.stroke();
        });
        
        this.ctx.restore();
    }
        }

        // Draw temp shape
        if (this.drawingMode && this.tempShape) {
    this.ctx.save();
    this.ctx.strokeStyle = '#4CAF50';
    this.ctx.lineWidth = 2;
    this.ctx.setLineDash([5, 5]);
    this.drawShapePath(this.tempShape, this.currentShape);
    this.ctx.stroke();
    this.ctx.restore();
        }

        // Draw points
        if (this.drawingMode && this.drawingPoints.length > 0) {
    this.ctx.save();
    this.ctx.strokeStyle = '#4CAF50';
    this.ctx.fillStyle = '#4CAF50';
    this.ctx.lineWidth = 2;
    
    this.drawingPoints.forEach((p, i) => {
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
        this.ctx.fill();
        
        if (i > 0) {
    this.ctx.beginPath();
    this.ctx.moveTo(this.drawingPoints[i-1].x, this.drawingPoints[i-1].y);
    this.ctx.lineTo(p.x, p.y);
    this.ctx.stroke();
        }
    });
    this.ctx.restore();
        }

        // Draw all slices and their masks
        this.slices.forEach(slice => {
    if (slice.type !== 'slice') return; // Only draw slices (masks are children)
    if (slice.visible === false) return; // Skip hidden slices
    
    const isSelected = slice === this.selectedSlice;

    this.ctx.save();

    // Apply rotation for rectangles
    if (slice.shape === 'rectangle' && slice.rotation) {
        const centerX = slice.x + slice.width / 2;
        const centerY = slice.y + slice.height / 2;
        this.ctx.translate(centerX, centerY);
        this.ctx.rotate(slice.rotation * Math.PI / 180);
        this.ctx.translate(-centerX, -centerY);
    }

    // Draw slice fill
    this.ctx.fillStyle = slice.color + '11';
    this.drawShapePath(slice, slice.shape);
    this.ctx.fill();

    // Draw slice outline
    this.ctx.strokeStyle = isSelected ? '#ffffff' : slice.color;
    this.ctx.lineWidth = isSelected ? 3 : 2;
    this.drawShapePath(slice, slice.shape);
    this.ctx.stroke();

    // Draw label
    const labelPos = this.getShapeLabelPosition(slice);
    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = 'bold 18px Arial';
    this.ctx.textAlign = 'left';
    this.ctx.textBaseline = 'top';
    this.ctx.fillText(slice.label, labelPos.x, labelPos.y);

    this.ctx.restore();

    // Draw masks for this slice
    if (slice.masks && slice.masks.length > 0) {
        slice.masks.forEach(mask => {
    if (mask.visible === false) return; // Skip hidden masks
    const isMaskSelected = mask === this.selectedSlice;
    this.ctx.save();
            
    // Apply rotation for rectangles
    if (mask.shape === 'rectangle' && mask.rotation) {
        const centerX = mask.x + mask.width / 2;
        const centerY = mask.y + mask.height / 2;
        this.ctx.translate(centerX, centerY);
        this.ctx.rotate(mask.rotation * Math.PI / 180);
        this.ctx.translate(-centerX, -centerY);
    }
            
    // Draw mask fill
    this.ctx.fillStyle = '#ff000022';
    this.drawShapePath(mask, mask.shape);
    this.ctx.fill();
            
    // Hatch pattern
    this.ctx.strokeStyle = '#ff0000';
    this.ctx.lineWidth = 1;
    this.ctx.save();
    this.drawShapePath(mask, mask.shape);
    this.ctx.clip();
            
    const bounds = this.getShapeBounds(mask);
    for (let i = -bounds.width; i < bounds.width + bounds.height; i += 10) {
        this.ctx.beginPath();
        this.ctx.moveTo(bounds.x + i, bounds.y);
        this.ctx.lineTo(bounds.x + i + bounds.height, bounds.y + bounds.height);
        this.ctx.stroke();
    }
    this.ctx.restore();
            
    // Draw mask outline (thicker if selected)
    this.ctx.strokeStyle = isMaskSelected ? '#ffffff' : '#ff0000';
    this.ctx.lineWidth = isMaskSelected ? 3 : 2;
    this.drawShapePath(mask, mask.shape);
    this.ctx.stroke();
            
    // Draw mask label
    const maskLabelPos = this.getShapeLabelPosition(mask);
    this.ctx.fillStyle = isMaskSelected ? '#ffffff' : '#ff0000';
    this.ctx.font = 'bold 16px Arial';
    this.ctx.textAlign = 'left';
    this.ctx.textBaseline = 'top';
    this.ctx.fillText(mask.label, maskLabelPos.x, maskLabelPos.y);
            
    // Draw handles for selected mask (rectangles only)
    if (isMaskSelected && mask.shape === 'rectangle') {
        this.drawResizeHandles(mask);
    }
            
    this.ctx.restore();
        });
    }

    // Draw handles for selected slice
    if (isSelected && slice.shape === 'rectangle') {
        if (this.transformMode || this.isTransformed(slice)) {
    // Show transform handles if in transform mode OR if slice has been transformed
    this.drawTransformHandles(slice);
        } else {
    this.drawResizeHandles(slice);
    this.drawRotationHandle(slice);
        }
    }
    
    // Draw transform indicator for non-selected transformed slices
    if (!isSelected && slice.shape === 'rectangle' && this.isTransformed(slice)) {
        this.drawTransformIndicator(slice);
    }
        });
    },

    drawShapePath(shape, shapeType) {
        const type = shapeType || shape.shape;
        this.ctx.beginPath();
        
        if (type === 'rectangle') {
    const x = shape.x || 0;
    const y = shape.y || 0;
    const w = shape.width || 0;
    const h = shape.height || 0;
    if (w === 0 || h === 0) {
        console.warn('Rectangle with zero dimensions:', shape);
        return;
    }
    this.ctx.rect(x, y, w, h);
        } else if (type === 'circle') {
    const cx = shape.centerX || 0;
    const cy = shape.centerY || 0;
    const r = shape.radius || 0;
    if (r === 0) {
        console.warn('Circle with zero radius:', shape);
        return;
    }
    this.ctx.arc(cx, cy, r, 0, Math.PI * 2);
        } else if (shape.points && shape.points.length > 0) {
    this.ctx.moveTo(shape.points[0].x, shape.points[0].y);
    for (let i = 1; i < shape.points.length; i++) {
        this.ctx.lineTo(shape.points[i].x, shape.points[i].y);
    }
    this.ctx.closePath();
        } else {
    console.warn('No valid shape data:', shape);
        }
    },

    getShapeBounds(shape) {
        if (shape.shape === 'rectangle') {
    return { 
        x: shape.x || 0, 
        y: shape.y || 0, 
        width: shape.width || 0, 
        height: shape.height || 0 
    };
        } else if (shape.shape === 'circle') {
    const cx = shape.centerX || 0;
    const cy = shape.centerY || 0;
    const r = shape.radius || 0;
    return {
        x: cx - r,
        y: cy - r,
        width: r * 2,
        height: r * 2
    };
        } else if (shape.points && shape.points.length > 0) {
    const xs = shape.points.map(p => p.x);
    const ys = shape.points.map(p => p.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
        }
        console.warn('Shape bounds not found for:', shape);
        return { x: 0, y: 0, width: 0, height: 0 };
    },

    getShapeLabelPosition(shape) {
        const bounds = this.getShapeBounds(shape);
        return { x: bounds.x + 5, y: bounds.y + 5 };
    },

    drawResizeHandles(slice) {
        const centerX = slice.x + slice.width / 2;
        const centerY = slice.y + slice.height / 2;
        const rotation = (slice.rotation || 0) * Math.PI / 180;
        
        // Helper function to rotate a point around center
        const rotatePoint = (x, y) => {
    const dx = x - centerX;
    const dy = y - centerY;
    return [
        centerX + dx * Math.cos(rotation) - dy * Math.sin(rotation),
        centerY + dx * Math.sin(rotation) + dy * Math.cos(rotation)
    ];
        };
        
        // Corner handles (unrotated positions)
        const corners = [
    [slice.x, slice.y],
    [slice.x + slice.width, slice.y],
    [slice.x, slice.y + slice.height],
    [slice.x + slice.width, slice.y + slice.height]
        ];
        
        // Edge handles (middle of each side)
        const edges = [
    [slice.x + slice.width / 2, slice.y], // North
    [slice.x + slice.width / 2, slice.y + slice.height], // South
    [slice.x + slice.width, slice.y + slice.height / 2], // East
    [slice.x, slice.y + slice.height / 2] // West
        ];
        
        // Draw corner handles (larger, white)
        this.ctx.fillStyle = '#ffffff';
        corners.forEach(([x, y]) => {
    const [rx, ry] = rotatePoint(x, y);
    this.ctx.fillRect(rx - 6, ry - 6, 12, 12);
        });
        
        // Draw edge handles (smaller, blue)
        this.ctx.fillStyle = '#2196F3';
        edges.forEach(([x, y]) => {
    const [rx, ry] = rotatePoint(x, y);
    this.ctx.fillRect(rx - 5, ry - 5, 10, 10);
        });
    },

    drawRotationHandle(slice) {
        const centerX = slice.x + slice.width / 2;
        const centerY = slice.y + slice.height / 2;
        const rotation = (slice.rotation || 0) * Math.PI / 180;
        
        // Rotation handle position (unrotated)
        const handleX = centerX;
        const handleY = slice.y - 30;
        
        // Rotate the handle position around center
        const dx = handleX - centerX;
        const dy = handleY - centerY;
        const rotHandleX = centerX + dx * Math.cos(rotation) - dy * Math.sin(rotation);
        const rotHandleY = centerY + dx * Math.sin(rotation) + dy * Math.cos(rotation);
        
        // Top edge center (rotated)
        const topX = centerX;
        const topY = slice.y;
        const topDx = topX - centerX;
        const topDy = topY - centerY;
        const rotTopX = centerX + topDx * Math.cos(rotation) - topDy * Math.sin(rotation);
        const rotTopY = centerY + topDx * Math.sin(rotation) + topDy * Math.cos(rotation);
        
        // Draw line from top center to rotation handle
        this.ctx.beginPath();
        this.ctx.strokeStyle = '#4CAF50';
        this.ctx.lineWidth = 2;
        this.ctx.moveTo(rotTopX, rotTopY);
        this.ctx.lineTo(rotHandleX, rotHandleY);
        this.ctx.stroke();
        
        // Draw rotation handle circle
        this.ctx.beginPath();
        this.ctx.arc(rotHandleX, rotHandleY, 12, 0, Math.PI * 2);
        this.ctx.fillStyle = '#4CAF50';
        this.ctx.fill();
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 3;
        this.ctx.stroke();
        
        // Draw rotation icon
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 1.5;
        this.ctx.beginPath();
        this.ctx.arc(rotHandleX, rotHandleY, 4, 0.5, Math.PI * 1.5);
        this.ctx.stroke();
    },

    drawTransformIndicator(slice) {
        if (!slice.transformCorners) return;
        
        // Draw dashed lines connecting corners
        this.ctx.strokeStyle = '#FFA500';
        this.ctx.lineWidth = 2;
        this.ctx.setLineDash([5, 5]); // Dashed line pattern
        this.ctx.beginPath();
        for (let i = 0; i < slice.transformCorners.length; i++) {
    const corner = slice.transformCorners[i];
    const x = slice.x + corner.x;
    const y = slice.y + corner.y;
    if (i === 0) {
        this.ctx.moveTo(x, y);
    } else {
        this.ctx.lineTo(x, y);
    }
        }
        this.ctx.closePath();
        this.ctx.stroke();
        this.ctx.setLineDash([]); // Reset to solid line
        
        // Draw corner dots
        this.ctx.fillStyle = '#FFA500';
        slice.transformCorners.forEach(corner => {
    const x = slice.x + corner.x;
    const y = slice.y + corner.y;
    this.ctx.beginPath();
    this.ctx.arc(x, y, 4, 0, Math.PI * 2);
    this.ctx.fill();
        });
    },

    // ========================================
    // UTILITY METHODS
    // ========================================
    getMousePos(e) {
        const rect = this.canvas.getBoundingClientRect();
        return {
    x: (e.clientX - rect.left) / (this.scale * this.canvasZoom),
    y: (e.clientY - rect.top) / (this.scale * this.canvasZoom)
        };
    },

    updateCanvasSize() {
        // Get current values (readonly, but can be updated programmatically)
        const widthInput = document.getElementById('canvasWidth');
        const heightInput = document.getElementById('canvasHeight');
        
        if (widthInput && heightInput) {
            this.canvasWidth = parseInt(widthInput.value) || this.canvasWidth;
            this.canvasHeight = parseInt(heightInput.value) || this.canvasHeight;
        }

        const container = document.getElementById('canvasContainer');
        const maxWidth = container.parentElement.clientWidth - 40;
        const maxHeight = container.parentElement.clientHeight - 40;
        
        const scaleX = maxWidth / this.canvasWidth;
        const scaleY = maxHeight / this.canvasHeight;
        this.scale = Math.min(scaleX, scaleY, 1);

        const displayWidth = this.canvasWidth * this.scale;
        const displayHeight = this.canvasHeight * this.scale;

        this.canvas.width = this.canvasWidth;
        this.canvas.height = this.canvasHeight;
        this.canvas.style.width = displayWidth + 'px';
        this.canvas.style.height = displayHeight + 'px';

        this.videoCanvas.width = this.canvasWidth;
        this.videoCanvas.height = this.canvasHeight;
        this.videoCanvas.style.width = displayWidth + 'px';
        this.videoCanvas.style.height = displayHeight + 'px';

        container.style.width = displayWidth + 'px';
        container.style.height = displayHeight + 'px';

        document.getElementById('canvasDimensions').textContent = `${this.canvasWidth}x${this.canvasHeight}`;

        this.drawTestPattern();
        this.render();
    },

    drawTestPattern() {
        const ctx = this.videoCtx;
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, this.canvasWidth, this.canvasHeight);

        ctx.strokeStyle = '#2a2a2a';
        ctx.lineWidth = 1;
        const gridSize = 100;
        
        for (let x = 0; x <= this.canvasWidth; x += gridSize) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, this.canvasHeight);
    ctx.stroke();
        }
        
        for (let y = 0; y <= this.canvasHeight; y += gridSize) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(this.canvasWidth, y);
    ctx.stroke();
        }

        ctx.fillStyle = '#444';
        ctx.font = '48px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('VIDEO CANVAS', this.canvasWidth / 2, this.canvasHeight / 2);
    },

    deleteSelected() {
        if (this.selectedSlice) {
    // Check if selected item is a mask
    let isMask = false;
    for (let slice of this.slices) {
        if (slice.masks && slice.masks.includes(this.selectedSlice)) {
    slice.masks = slice.masks.filter(m => m !== this.selectedSlice);
    isMask = true;
    this.showToast('Mask deleted');
    break;
        }
    }
    
    // If not a mask, delete slice
    if (!isMask) {
        this.slices = this.slices.filter(s => s !== this.selectedSlice);
        this.showToast('Shape deleted');
    }
    
    this.selectedSlice = null;
    this.updateUI();
    this.render();
        }
    },

    duplicateSelected() {
        if (!this.selectedSlice) return;
        
        // Check if selected item is a mask
        let isMask = false;
        let parentSlice = null;
        for (let slice of this.slices) {
    if (slice.masks && slice.masks.includes(this.selectedSlice)) {
        isMask = true;
        parentSlice = slice;
        break;
    }
        }
        
        if (isMask && parentSlice) {
    // Duplicate mask
    const mask = this.selectedSlice;
    const duplicate = JSON.parse(JSON.stringify(mask));
	duplicate.id = crypto.randomUUID();
	duplicate.label = mask.label + ' Copy';
	
	// Offset position
	if (duplicate.shape === 'rectangle') {
	    duplicate.x += 20;
	    duplicate.y += 20;
	} else if (duplicate.shape === 'circle') {
	    duplicate.centerX += 20;
	    duplicate.centerY += 20;
	} else if (duplicate.points) {
	    duplicate.points = duplicate.points.map(p => ({x: p.x + 20, y: p.y + 20}));
	}
	
	parentSlice.masks.push(duplicate);
	this.selectedSlice = duplicate;
	this.showToast('Mask duplicated');
        } else if (this.selectedSlice.type === 'slice') {
	// Duplicate slice
	const slice = this.selectedSlice;
	const duplicate = JSON.parse(JSON.stringify(slice));
	duplicate.id = crypto.randomUUID();
	duplicate.label = slice.label + ' Copy';
	
	// Offset position
	if (duplicate.shape === 'rectangle') {
	    duplicate.x += 20;
	    duplicate.y += 20;
	} else if (duplicate.shape === 'circle') {
	    duplicate.centerX += 20;
	    duplicate.centerY += 20;
	} else if (duplicate.points) {
	    duplicate.points = duplicate.points.map(p => ({x: p.x + 20, y: p.y + 20}));
	}
	
	// Duplicate masks with new IDs
	if (duplicate.masks && duplicate.masks.length > 0) {
	    duplicate.masks = duplicate.masks.map(m => {
		const newMask = JSON.parse(JSON.stringify(m));
		newMask.id = crypto.randomUUID();
    this.slices.push(duplicate);
    this.selectedSlice = duplicate;
    this.showToast('Slice duplicated');
        }
        
        this.updateUI();
        this.render();
        
        // Save duplicated slice to backend
        if (duplicate && duplicate.id) {
            this.saveSliceToBackend(duplicate);
        }
    },

    toggleSnap() {
        this.snapToGrid = !this.snapToGrid;
        document.getElementById('snapBtn').textContent = `📐 Snap: ${this.snapToGrid ? 'ON' : 'OFF'}`;
    },

    // ========================================
    // SOFT EDGE & OVERLAP DETECTION
    // ========================================
    detectSliceOverlaps(slice) {
        if (!slice || slice.type !== 'slice') return null;
        
        const overlaps = { top: 0, bottom: 0, left: 0, right: 0 };
        
        // Check against all other slices with soft edge enabled
        for (const other of this.slices) {
    if (other === slice || other.type !== 'slice') continue;
    if (!other.softEdge || !other.softEdge.enabled) continue;
    if (!slice.softEdge || !slice.softEdge.enabled) continue;
    
    // Check for left/right overlap (vertical alignment must be 100%)
    const verticalOverlap = Math.min(slice.y + slice.height, other.y + other.height) - Math.max(slice.y, other.y);
    const minHeight = Math.min(slice.height, other.height);
    
    if (verticalOverlap >= minHeight * 0.99) { // 99% to account for rounding
        // Check right edge overlap (slice on left, other on right)
        if (slice.x + slice.width > other.x && slice.x + slice.width < other.x + other.width) {
    const overlapWidth = slice.x + slice.width - other.x;
    overlaps.right = Math.max(overlaps.right, overlapWidth);
        }
        // Check left edge overlap (slice on right, other on left)
        if (slice.x < other.x + other.width && slice.x > other.x) {
    const overlapWidth = other.x + other.width - slice.x;
    overlaps.left = Math.max(overlaps.left, overlapWidth);
        }
    }
    
    // Check for top/bottom overlap (horizontal alignment must be 100%)
    const horizontalOverlap = Math.min(slice.x + slice.width, other.x + other.width) - Math.max(slice.x, other.x);
    const minWidth = Math.min(slice.width, other.width);
    
    if (horizontalOverlap >= minWidth * 0.99) { // 99% to account for rounding
        // Check bottom edge overlap (slice on top, other on bottom)
        if (slice.y + slice.height > other.y && slice.y + slice.height < other.y + other.height) {
    const overlapHeight = slice.y + slice.height - other.y;
    overlaps.bottom = Math.max(overlaps.bottom, overlapHeight);
        }
        // Check top edge overlap (slice on bottom, other on top)
        if (slice.y < other.y + other.height && slice.y > other.y) {
    const overlapHeight = other.y + other.height - slice.y;
    overlaps.top = Math.max(overlaps.top, overlapHeight);
        }
    }
        }
        
        return overlaps;
    },

    updateSoftEdgeFromOverlap(slice) {
        if (!slice || !slice.softEdge || !slice.softEdge.autoDetect || !slice.softEdge.enabled) return;
        
        const overlaps = this.detectSliceOverlaps(slice);
        if (overlaps) {
    if (overlaps.top > 0) slice.softEdge.width.top = Math.round(overlaps.top);
    if (overlaps.bottom > 0) slice.softEdge.width.bottom = Math.round(overlaps.bottom);
    if (overlaps.left > 0) slice.softEdge.width.left = Math.round(overlaps.left);
    if (overlaps.right > 0) slice.softEdge.width.right = Math.round(overlaps.right);
        }
    },

    toggleSoftEdge(sliceId, enabled) {
        const slice = this.slices.find(s => s.id === sliceId);
        if (!slice) return;
        
        if (!slice.softEdge || typeof slice.softEdge !== 'object') {
    slice.softEdge = {
        enabled: false,
        autoDetect: true,
        width: { top: 50, bottom: 50, left: 50, right: 50 },
        curve: 'smooth',
        strength: 1.0,
        gamma: 1.0,
        gammaR: 1.0,
        gammaG: 1.0,
        gammaB: 1.0
    };
        }
        
        slice.softEdge.enabled = enabled;
        
        // Auto-detect overlaps if enabled
        if (enabled && slice.softEdge.autoDetect) {
    this.updateSoftEdgeFromOverlap(slice);
    // Update all other slices with soft edge enabled
    for (const other of this.slices) {
        if (other !== slice && other.type === 'slice' && other.softEdge?.enabled && other.softEdge?.autoDetect) {
    this.updateSoftEdgeFromOverlap(other);
        }
    }
        }
        
        this.saveState();
        this.updateSliceList();
        this.render();
    },

    updateSoftEdgeProperty(sliceId, property, value) {
        const slice = this.slices.find(s => s.id === sliceId);
        if (!slice || !slice.softEdge) return;
        
        slice.softEdge[property] = value;
        
        // If auto-detect was toggled, recalculate
        if (property === 'autoDetect' && value === true) {
    this.updateSoftEdgeFromOverlap(slice);
        }
        
        this.saveState();
        this.updateSliceList();
        this.render();
    },

    updateSoftEdgeWidth(sliceId, edge, value) {
        const slice = this.slices.find(s => s.id === sliceId);
        if (!slice || !slice.softEdge || !slice.softEdge.width) return;
        
        slice.softEdge.width[edge] = value;
        
        // Disable auto-detect when manually changing values
        if (slice.softEdge.autoDetect) {
    slice.softEdge.autoDetect = false;
        }
        
        this.saveState();
        this.updateSliceList();
        this.render();
    },

    // ========================================
    // TRANSFORM & ROTATION
    // ========================================
    toggleTransformMode() {
        this.transformMode = !this.transformMode;
        const btn = document.getElementById('transformBtn');
        if (this.transformMode) {
    // Reset rotation to 0° when entering transform mode
    if (this.selectedSlice && this.selectedSlice.rotation) {
        this.selectedSlice.rotation = 0;
        this.saveState();
    }
    btn.style.background = '#2a4a2a';
    btn.style.borderColor = '#4CAF50';
    this.showToast('Transform mode active (rotation disabled). Drag corners to move them independently.');
        } else {
    btn.style.background = '';
    btn.style.borderColor = '';
        }
        this.render();
    },

    deleteTransform() {
        if (!this.selectedSlice) {
    this.showToast('Select a slice first', 'error');
    return;
        }
        
        if (this.selectedSlice.type !== 'slice') {
    this.showToast('Transform only available for slices', 'error');
    return;
        }
        
        // Reset transform corners to default rectangle
        this.selectedSlice.transformCorners = [
    {x: 0, y: 0}, // top-left
    {x: this.selectedSlice.width, y: 0}, // top-right
    {x: this.selectedSlice.width, y: this.selectedSlice.height}, // bottom-right
    {x: 0, y: this.selectedSlice.height} // bottom-left
        ];
        
        // Update dimensions
        this.updateSliceDimensionsFromTransform(this.selectedSlice);
        
        // Turn off transform mode
        if (this.transformMode) {
    this.toggleTransformMode();
        }
        
        this.showToast('Transform reset to default rectangle');
        this.saveState();
        this.render();
    },

    showPreview() {
        if (!this.selectedSlice) {
    this.showToast('Select a slice first', 'error');
    return;
        }

        const modal = document.getElementById('previewModal');
        const canvas = document.getElementById('previewCanvas');
        const ctx = canvas.getContext('2d');
        const infoDiv = document.getElementById('previewInfo');

        const slice = this.selectedSlice;
        
        // Update modal title with slice name
        const modalTitle = modal.querySelector('.preview-header h3');
        modalTitle.textContent = `Slice Preview - ${slice.label}`;
        
        // Determine slice bounds
        let bounds;
        if (slice.shape === 'rectangle') {
    bounds = { x: slice.x, y: slice.y, width: slice.width, height: slice.height };
        } else {
    bounds = this.getShapeBounds(slice);
        }

        // Scale to fit max 800x600
        const maxWidth = 800;
        const maxHeight = 600;
        const scale = Math.min(maxWidth / bounds.width, maxHeight / bounds.height, 1);
        
        canvas.width = bounds.width * scale;
        canvas.height = bounds.height * scale;
        canvas.style.width = canvas.width + 'px';
        canvas.style.height = canvas.height + 'px';

        // Draw scaled slice preview
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.save();
        ctx.scale(scale, scale);
        ctx.translate(-bounds.x, -bounds.y);

        // Apply rotation if rectangle
        if (slice.shape === 'rectangle' && slice.rotation) {
    const centerX = slice.x + slice.width / 2;
    const centerY = slice.y + slice.height / 2;
    ctx.translate(centerX, centerY);
    ctx.rotate(slice.rotation * Math.PI / 180);
    ctx.translate(-centerX, -centerY);
        }

        // Draw slice shape
        ctx.fillStyle = slice.color + '44';
        this.drawShapePath(slice, slice.shape);
        ctx.fill();

        ctx.strokeStyle = slice.color;
        ctx.lineWidth = 3;
        this.drawShapePath(slice, slice.shape);
        ctx.stroke();

        // Draw masks
        if (slice.masks && slice.masks.length > 0) {
    slice.masks.forEach(mask => {
        // Apply rotation if rectangle mask
        if (mask.shape === 'rectangle' && mask.rotation) {
    const centerX = mask.x + mask.width / 2;
    const centerY = mask.y + mask.height / 2;
    ctx.translate(centerX, centerY);
    ctx.rotate(mask.rotation * Math.PI / 180);
    ctx.translate(-centerX, -centerY);
        }

        ctx.fillStyle = '#ff000044';
        this.drawShapePath(mask, mask.shape);
        ctx.fill();

        ctx.strokeStyle = '#ff0000';
        ctx.lineWidth = 2;
        this.drawShapePath(mask, mask.shape);
        ctx.stroke();
    });
        }

        ctx.restore();

        // Update info
        const isMask = slice.type === 'mask';
        infoDiv.innerHTML = `
    <div class="preview-info-row">
        <span class="preview-info-label">Type:</span>
        <span>${isMask ? 'Mask' : 'Slice'}</span>
    </div>
    <div class="preview-info-row">
        <span class="preview-info-label">Label:</span>
        <span>${slice.label}</span>
    </div>
    <div class="preview-info-row">
        <span class="preview-info-label">Shape:</span>
        <span>${slice.shape}</span>
    </div>
    <div class="preview-info-row">
        <span class="preview-info-label">Position:</span>
        <span>${Math.round(bounds.x)}, ${Math.round(bounds.y)}</span>
    </div>
    <div class="preview-info-row">
        <span class="preview-info-label">Size:</span>
        <span>${Math.round(bounds.width)} x ${Math.round(bounds.height)}</span>
    </div>
    ${slice.rotation ? `
    <div class="preview-info-row">
        <span class="preview-info-label">Rotation:</span>
        <span>${Math.round(slice.rotation)}°</span>
    </div>` : ''}
    ${slice.screens ? `
    <div class="preview-info-row">
        <span class="preview-info-label">Outputs:</span>
        <span>${slice.screens.join(', ')}</span>
    </div>` : ''}
    ${slice.masks && slice.masks.length > 0 ? `
    <div class="preview-info-row">
        <span class="preview-info-label">Masks:</span>
        <span>${slice.masks.length}</span>
    </div>` : ''}
    <div class="preview-info-row">
        <span class="preview-info-label">Scale:</span>
        <span>${Math.round(scale * 100)}%</span>
    </div>
        `;

        modal.classList.add('active');
    },

    closePreview() {
        const modal = document.getElementById('previewModal');
        modal.classList.remove('active');
    },

    zoomIn() {
        this.canvasZoom = Math.min(this.canvasZoom * 1.2, 5.0);
        this.updateCanvasZoom();
    },

    zoomOut() {
        this.canvasZoom = Math.max(this.canvasZoom / 1.2, 0.2);
        this.updateCanvasZoom();
    },

    resetZoom() {
        this.canvasZoom = 1.0;
        this.updateCanvasZoom();
    },

    updateCanvasZoom() {
        const container = document.getElementById('canvasContainer');
        
        // Calculate display size considering both scale and zoom
        const displayWidth = this.canvasWidth * this.scale;
        const displayHeight = this.canvasHeight * this.scale;
        
        // Apply zoom transform to both canvases
        this.canvas.style.transform = `scale(${this.canvasZoom})`;
        this.canvas.style.transformOrigin = 'top left';
        this.videoCanvas.style.transform = `scale(${this.canvasZoom})`;
        this.videoCanvas.style.transformOrigin = 'top left';
        
        // Update container size to accommodate zoomed canvas
        const scaledWidth = displayWidth * this.canvasZoom;
        const scaledHeight = displayHeight * this.canvasZoom;
        container.style.width = scaledWidth + 'px';
        container.style.height = scaledHeight + 'px';
        
        // Update zoom display
        document.getElementById('zoomLevel').textContent = Math.round(this.canvasZoom * 100) + '%';
    },

    // ========================================
    // SCREEN ASSIGNMENT & OUTPUT MANAGEMENT
    // ========================================
    toggleScreen(screen) {
        if (this.selectedSlice && this.selectedSlice.type === 'slice') {
    const screens = this.selectedSlice.screens || [];
    const index = screens.indexOf(screen);
    if (index > -1) {
        screens.splice(index, 1);
        this.showToast(`Removed from ${screen}`);
    } else {
        screens.push(screen);
        this.showToast(`Assigned to ${screen}`);
    }
    this.selectedSlice.screens = screens;
    this.updateUI();
        } else {
    this.showToast('Select a slice (not mask) to assign outputs', 'error');
        }
    },

    async addOutput() {
        try {
            // Fetch available output types from backend
            const response = await fetch('/api/outputs/types');
            if (!response.ok) throw new Error('Failed to fetch output types');
            
            const data = await response.json();
            if (!data.success) throw new Error(data.error || 'Failed to get output types');
            
            const outputTypes = data.types || {};
            if (Object.keys(outputTypes).length === 0) {
                throw new Error('No output types available');
            }
            
            // Fetch existing outputs to check for monitor usage
            const existingResponse = await fetch('/api/outputs/video');
            let usedMonitors = new Set();
            if (existingResponse.ok) {
                const existingData = await existingResponse.json();
                if (existingData.success && existingData.outputs) {
                    // Track which monitors are already in use
                    Object.values(existingData.outputs).forEach(output => {
                        if (output.type === 'display' && output.monitor_index !== undefined) {
                            usedMonitors.add(output.monitor_index);
                        }
                    });
                }
            }
            
            // Store used monitors for validation
            this.usedMonitors = usedMonitors;
            
            // Create modal content
            let modalContent = `
                <div style="margin-bottom: 20px;">
                    <label style="font-weight: bold; margin-bottom: 10px; display: block;">Select Output Type:</label>
                    <select id="outputTypeSelect" class="form-select" onchange="app.updateOutputTypeForm()">
                        <option value="">-- Choose Type --</option>
            `;
            
            // Add available output types
            for (const [type, info] of Object.entries(outputTypes)) {
                const disabled = info.available === false ? 'disabled' : '';
                const suffix = info.available === false ? ` (${info.reason || 'Not available'})` : '';
                modalContent += `<option value="${type}" ${disabled}>${info.icon || ''} ${info.name}${suffix}</option>`;
            }
            
            modalContent += `
                    </select>
                    <p id="outputTypeDescription" style="font-size: 12px; color: #888; margin-top: 8px;"></p>
                </div>
                <div id="outputConfigForm" style="display: none;"></div>
            `;
            
            // Store output types data for form generation
            this.availableOutputTypes = outputTypes;
            
            // Create modal
            const modal = ModalManager.create({
                id: 'addOutputModal',
                title: '➕ Add Output',
                content: modalContent,
                size: 'lg',
                buttons: [
                    {
                        label: 'Cancel',
                        class: 'btn-secondary',
                        callback: (modalInstance) => modalInstance.hide()
                    },
                    {
                        label: 'Create Output',
                        class: 'btn-primary',
                        callback: () => this.createOutputFromModal()
                    }
                ]
            });
            
            modal.show();
            
        } catch (error) {
            console.error('Failed to show add output modal:', error);
            this.showToast(`Error: ${error.message}`, 'error');
        }
    },
    
    updateOutputTypeForm() {
        const select = document.getElementById('outputTypeSelect');
        const description = document.getElementById('outputTypeDescription');
        const form = document.getElementById('outputConfigForm');
        const selectedType = select.value;
        
        if (!selectedType) {
            description.textContent = '';
            form.style.display = 'none';
            return;
        }
        
        const typeInfo = this.availableOutputTypes[selectedType];
        description.textContent = typeInfo.description || '';
        
        // Build configuration form
        let formHtml = '<div style="background: #1a1a1a; padding: 15px; border-radius: 8px; margin-top: 15px;">';
        formHtml += '<h6 style="margin-bottom: 15px;">Configuration:</h6>';
        
        // Output name/ID
        formHtml += `
            <div class="mb-3">
                <label for="outputName" class="form-label">Output Name:</label>
                <input type="text" class="form-control" id="outputName" placeholder="e.g. main_display, preview_1" required>
            </div>
        `;
        
        // Type-specific fields
        const fields = typeInfo.configurable_fields || {};
        
        for (const [fieldName, fieldConfig] of Object.entries(fields)) {
            formHtml += this.buildFormField(fieldName, fieldConfig, typeInfo);
        }
        
        formHtml += '</div>';
        form.innerHTML = formHtml;
        form.style.display = 'block';
    },
    
    buildFormField(fieldName, fieldConfig, typeInfo) {
        let html = '<div class="mb-3">';
        html += `<label for="output_${fieldName}" class="form-label">${fieldConfig.label}:</label>`;
        
        switch (fieldConfig.type) {
            case 'select':
                html += `<select id="output_${fieldName}" class="form-select" ${fieldConfig.required ? 'required' : ''}>`;
                if (!fieldConfig.required) {
                    html += '<option value="">-- Select --</option>';
                }
                fieldConfig.options.forEach(opt => {
                    // Check if this monitor is already in use
                    const isMonitorField = fieldName === 'monitor_index';
                    const monitorInUse = isMonitorField && this.usedMonitors && this.usedMonitors.has(opt.value);
                    const disabledAttr = monitorInUse ? 'disabled' : '';
                    const usedSuffix = monitorInUse ? ' ⚠️ (In Use)' : '';
                    html += `<option value="${opt.value}" ${disabledAttr}>${opt.label}${usedSuffix}</option>`;
                });
                html += '</select>';
                
                // Add warning for monitor field
                if (fieldName === 'monitor_index' && this.usedMonitors && this.usedMonitors.size > 0) {
                    html += '<small style="color: #ff9800; display: block; margin-top: 5px;">⚠️ Some monitors are already in use by other outputs</small>';
                }
                break;
                
            case 'resolution':
                if (fieldConfig.from_monitor) {
                    html += '<p style="font-size: 12px; color: #888;">Resolution will be set from selected monitor</p>';
                } else {
                    // Resolution presets for virtual outputs
                    html += '<select id="output_resolution_preset" class="form-select" onchange="app.updateResolutionFields()">';
                    html += '<option value="custom">Custom</option>';
                    
                    // Get presets from field config
                    const presets = fieldConfig.presets || [];
                    presets.forEach(preset => {
                        const [width, height] = preset.value;
                        html += `<option value="${width}x${height}">${preset.label}</option>`;
                    });
                    html += '</select>';
                    
                    html += '<div id="customResolutionFields" style="display: flex; gap: 10px; margin-top: 10px;">';
                    html += '<input type="number" id="output_resolution_width" class="form-control" placeholder="Width" value="1920">';
                    html += '<input type="number" id="output_resolution_height" class="form-control" placeholder="Height" value="1080">';
                    html += '</div>';
                }
                break;
                
            case 'checkbox':
                html += `
                    <div class="form-check">
                        <input type="checkbox" class="form-check-input" id="output_${fieldName}" ${fieldConfig.default ? 'checked' : ''}>
                        <label class="form-check-label" for="output_${fieldName}">${fieldConfig.label}</label>
                    </div>
                `;
                break;
                
            case 'text':
                html += `<input type="text" id="output_${fieldName}" class="form-control" placeholder="${fieldConfig.default || ''}" ${fieldConfig.required ? 'required' : ''}>`;
                break;
                
            case 'number':
                html += `<input type="number" id="output_${fieldName}" class="form-control" value="${fieldConfig.default || ''}" ${fieldConfig.required ? 'required' : ''}>`;
                break;
        }
        
        html += '</div>';
        return html;
    },
    
    updateResolutionFields() {
        const preset = document.getElementById('output_resolution_preset').value;
        const customFields = document.getElementById('customResolutionFields');
        const widthInput = document.getElementById('output_resolution_width');
        const heightInput = document.getElementById('output_resolution_height');
        
        if (preset === 'custom') {
            customFields.style.display = 'flex';
        } else {
            customFields.style.display = 'none';
            
            // Parse preset value (format: "1920x1080")
            const [width, height] = preset.split('x').map(Number);
            if (width && height) {
                widthInput.value = width;
                heightInput.value = height;
            }
        }
    },
    
    async createOutputFromModal() {
        try {
            const outputType = document.getElementById('outputTypeSelect').value;
            const outputName = document.getElementById('outputName').value.trim();
            
            if (!outputType) {
                this.showToast('Please select an output type', 'error');
                return;
            }
            
            if (!outputName) {
                this.showToast('Please enter an output name', 'error');
                return;
            }
            
            // Build output configuration
            const config = {
                type: outputType,
                enabled: true,
                source: 'canvas',
                slice: 'full'
            };
            
            // Collect field values
            const typeInfo = this.availableOutputTypes[outputType];
            const fields = typeInfo.configurable_fields || {};
            
            for (const [fieldName, fieldConfig] of Object.entries(fields)) {
                const fieldId = `output_${fieldName}`;
                const element = document.getElementById(fieldId);
                
                if (fieldConfig.type === 'checkbox') {
                    config[fieldName] = element.checked;
                } else if (fieldConfig.type === 'resolution' && !fieldConfig.from_monitor) {
                    const width = parseInt(document.getElementById('output_resolution_width').value);
                    const height = parseInt(document.getElementById('output_resolution_height').value);
                    config.resolution = [width, height];
                } else if (fieldConfig.type === 'select') {
                    config[fieldName] = parseInt(element.value) || element.value;
                } else if (element) {
                    config[fieldName] = element.value;
                }
            }
            
            // VALIDATION: Check for duplicate monitor usage
            if (config.type === 'display' && config.monitor_index !== undefined) {
                if (this.usedMonitors && this.usedMonitors.has(config.monitor_index)) {
                    this.showToast('⚠️ This monitor is already in use by another output. Please select a different monitor.', 'error');
                    return;
                }
            }
            
            // Add default values from type
            Object.assign(config, typeInfo.default_config);
            config.type = outputType; // Ensure type is correct
            config.enabled = true; // Enable by default
            
            // Create output via API
            const response = await fetch('/api/outputs/video', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    output_id: outputName,
                    config: config
                })
            });
            
            const data = await response.json();
            
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to create output');
            }
            
            this.showToast(`✅ Output "${outputName}" created successfully`);
            
            // Reload outputs list
            await this.loadExistingOutputs();
            
            // Close modal
            const modal = ModalManager.get('addOutputModal');
            if (modal) modal.hide();
            
        } catch (error) {
            console.error('Failed to create output:', error);
            this.showToast(`Error: ${error.message}`, 'error');
        }
    },

    updateScreenButtons() {
        const container = document.getElementById('screenButtonsContainer');
        
        // Check if we have loaded outputs from backend
        if (!this.existingOutputs) {
            container.innerHTML = '<div style="color: #888; font-size: 12px;">Loading outputs...</div>';
            return;
        }
        
        const selectedSlice = this.selectedSlice && this.selectedSlice.type === 'slice' ? this.selectedSlice : null;
        const disabled = !selectedSlice ? 'disabled' : '';
        
        let html = '';
        
        // Display existing outputs from backend as simple checkboxes
        if (Object.keys(this.existingOutputs).length > 0) {
            Object.entries(this.existingOutputs).forEach(([outputId, output]) => {
                const typeIcon = output.type === 'display' ? '🖥️' : 
                               output.type === 'virtual' ? '💾' : 
                               output.type === 'ndi' ? '📡' : '🎨';
                
                const monitorInfo = output.type === 'display' && output.monitor_index !== undefined 
                    ? `Monitor ${output.monitor_index}` 
                    : output.type === 'virtual' 
                    ? `${output.resolution[0]}x${output.resolution[1]}`
                    : 'Network';
                
                // Check if this output is assigned to selected slice
                const isChecked = selectedSlice && output.slice === (selectedSlice.id || selectedSlice.label);
                
                html += `
                    <div style="display: flex; align-items: center; gap: 4px; margin-bottom: 4px;">
                        <div class="screen-checkbox-item ${disabled}" style="flex: 1;">
                            <input type="checkbox" 
                                   id="output_${outputId}" 
                                   ${isChecked ? 'checked' : ''} 
                                   ${disabled ? 'disabled' : ''}
                                   onchange="app.toggleOutputForSlice('${outputId}')">
                            <label for="output_${outputId}">
                                ${typeIcon} ${outputId} <span style="color: #666; font-size: 10px;">(${monitorInfo})</span>
                            </label>
                        </div>
                        <button class="small" onclick="app.openOutputComposer('${outputId}'); event.stopPropagation();" 
                                style="padding: 4px 8px; font-size: 10px; background: #2a5a8a; border: 1px solid #3a7aaa; flex-shrink: 0;" 
                                title="Compose multiple slices for this output">
                            🎨
                        </button>
                    </div>
                `;
            });
        } else {
            html += '<div style="color: #888; font-size: 11px;">No outputs configured</div>';
        }
        
        container.innerHTML = html;
    },
    
    async toggleOutputForSlice(outputId) {
        if (!this.selectedSlice || this.selectedSlice.type !== 'slice') {
            return;
        }
        
        const checkbox = document.getElementById(`output_${outputId}`);
        
        if (checkbox.checked) {
            // First, ensure the slice exists in the backend
            await this.saveSliceToBackend(this.selectedSlice);
            
            // Then assign this slice to the output
            const sliceId = this.selectedSlice.id || this.selectedSlice.label;
            const sliceName = this.selectedSlice.name || this.selectedSlice.label;
            await this.updateOutputSlice(outputId, sliceId);
            this.showToast(`${outputId} ← ${sliceName}`, 'success');
        } else {
            // Unassign (set to full)
            await this.updateOutputSlice(outputId, 'full');
            this.showToast(`${outputId} ← Full Canvas`, 'info');
        }
    },
    
    async updateOutputSource(outputId, newSource) {
        try {
            const response = await fetch(`/api/outputs/video/${outputId}/source`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source: newSource })
            });
            
            const data = await response.json();
            if (data.success) {
                this.showToast(`${outputId}: Source → ${newSource}`, 'success');
                await this.loadExistingOutputs(); // Reload to update display
            } else {
                this.showToast(`Failed: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Failed to update source:', error);
            this.showToast('Failed to update source', 'error');
        }
    },
    
    async updateOutputSlice(outputId, newSlice) {
        try {
            console.log(`Updating output ${outputId} slice to:`, newSlice);
            const response = await fetch(`/api/outputs/video/${outputId}/slice`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ slice_id: newSlice })
            });
            
            const data = await response.json();
            if (data.success) {
                this.showToast(`${outputId}: Slice → ${newSlice}`, 'success');
                await this.loadExistingOutputs(); // Reload to update display
                this.updateUI(); // Refresh right sidebar to show new assignments
            } else {
                console.error('API error:', data.error);
                this.showToast(`Failed: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Failed to update slice:', error);
            this.showToast('Failed to update slice', 'error');
        }
    },

    removeOutput(screen) {
        if (confirm(`Remove "${screen}"?`)) {
    this.slices.forEach(s => {
        const screens = s.screens || [];
        const index = screens.indexOf(screen);
        if (index > -1) screens.splice(index, 1);
        s.screens = screens;
    });
    this.customScreens = this.customScreens.filter(s => s !== screen);
    this.updateScreenButtons();
    this.updateUI();
    this.saveToBackend();
        }
    },
    
    async loadExistingOutputs() {
        try {
            const response = await fetch('/api/outputs/video');
            
            if (!response.ok) {
                console.warn('Failed to load existing outputs:', response.statusText);
                this.existingOutputs = {};
                this.updateScreenButtons();
                return;
            }
            
            const data = await response.json();
            
            if (data.success && data.outputs) {
                // Filter out internal outputs like preview_virtual
                this.existingOutputs = {};
                
                // Initialize compositions object if not exists
                if (!this.compositions) this.compositions = {};
                
                for (const [outputId, config] of Object.entries(data.outputs)) {
                    if (outputId !== 'preview_virtual') {
                        this.existingOutputs[outputId] = config;
                        
                        // Extract and restore composition data from output config
                        if (config.composition && config.composition.slices && config.composition.slices.length > 0) {
                            this.compositions[outputId] = {
                                width: config.composition.width,
                                height: config.composition.height,
                                slices: config.composition.slices.map(s => ({
                                    sliceId: s.sliceId,
                                    x: s.x,
                                    y: s.y,
                                    width: s.width,
                                    height: s.height,
                                    scale: s.scale || 1.0
                                }))
                            };
                            console.log(`✅ Restored composition for ${outputId}:`, this.compositions[outputId]);
                        }
                    }
                }
                console.log('✅ Loaded existing outputs:', Object.keys(this.existingOutputs).length);
                console.log('✅ Loaded compositions:', Object.keys(this.compositions).length, this.compositions);
            } else {
                this.existingOutputs = {};
            }
            
            this.updateScreenButtons();
            
        } catch (error) {
            console.error('Failed to load existing outputs:', error);
            this.existingOutputs = {};
            this.updateScreenButtons();
        }
    },
    
    async toggleOutputEnabled(outputId, enable) {
        try {
            const action = enable ? 'enable' : 'disable';
            const response = await fetch(`/api/outputs/video/${outputId}/${action}`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (!data.success) {
                this.showToast(`❌ Failed to ${action} output: ${data.error}`, 'error');
                return;
            }
            
            this.showToast(`✅ Output ${enable ? 'enabled' : 'disabled'}`, 'success');
            
            // Reload outputs
            await this.loadExistingOutputs();
            
        } catch (error) {
            console.error('Failed to toggle output:', error);
            this.showToast('❌ Failed to toggle output', 'error');
        }
    },
    
    async deleteOutput(outputId) {
        if (!confirm(`Delete output "${outputId}"?\n\nThis will remove the output configuration.`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/outputs/video/${outputId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (!data.success) {
                this.showToast(`❌ Failed to delete output: ${data.error}`, 'error');
                return;
            }
            
            this.showToast('✅ Output deleted', 'success');
            
            // Reload outputs
            await this.loadExistingOutputs();
            
        } catch (error) {
            console.error('Failed to delete output:', error);
            this.showToast('❌ Failed to delete output', 'error');
        }
    },

    updateUI() {
        const sliceCount = this.slices.filter(s => s.type === 'slice').length;
        document.getElementById('sliceCount').textContent = sliceCount;
        document.getElementById('selectedSlice').textContent = 
    this.selectedSlice ? this.selectedSlice.label : 'None';

        this.updateScreenButtons();

        // Build grouped slices list (by outputs and compositions)
        let listHtml = '';
        
        const sliceList = this.slices.filter(s => s.type === 'slice');
        
        if (sliceList.length === 0) {
            listHtml = '<div style="color: #666; font-size: 12px; padding: 8px; text-align: center;">No slices created. Draw a shape to get started.</div>';
        } else {
            // Track which slices are assigned
            const assignedSlices = new Set();
            
            // Group by outputs
            if (this.existingOutputs && Object.keys(this.existingOutputs).length > 0) {
                Object.entries(this.existingOutputs).forEach(([outputId, output]) => {
                    // Check if output has a composition
                    const composition = this.compositions && this.compositions[outputId];
                    const hasComposition = composition && composition.slices && composition.slices.length > 0;
                    
                    // Check if output has a single slice assigned
                    const singleSlice = output.slice && output.slice !== 'full' ? 
                        sliceList.find(s => (s.id || s.label) === output.slice) : null;
                    
                    if (hasComposition || singleSlice) {
                        // Output header
                        listHtml += `
                            <div style="background: #2a5a8a; padding: 6px 10px; margin-bottom: 4px; border-radius: 4px; font-size: 12px; font-weight: bold;">
                                📺 ${outputId}
                            </div>
                        `;
                        
                        if (hasComposition) {
                            // Show composition with remove button
                            listHtml += `
                                <div style="padding-left: 15px; margin-bottom: 8px;">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                                        <div style="color: #aaa; font-size: 11px;">🎨 Composition (${composition.slices.length} slices):</div>
                                        <button class="small danger" onclick="app.removeComposition('${outputId}'); event.stopPropagation();" 
                                                style="padding: 2px 6px; font-size: 10px;" title="Remove composition">✕</button>
                                    </div>
                            `;
                            
                            composition.slices.forEach(compSlice => {
                                const slice = sliceList.find(s => s.id === compSlice.sliceId);
                                if (slice) {
                                    assignedSlices.add(slice.id);
                                    const isActive = slice === this.selectedSlice ? 'active' : '';
                                    listHtml += this.renderSliceItem(slice, isActive, true);
                                }
                            });
                            
                            listHtml += `</div>`;
                        } else if (singleSlice) {
                            // Show single slice
                            assignedSlices.add(singleSlice.id);
                            const isActive = singleSlice === this.selectedSlice ? 'active' : '';
                            listHtml += `<div style="padding-left: 15px; margin-bottom: 8px;">`;
                            listHtml += this.renderSliceItem(singleSlice, isActive, true);
                            listHtml += `</div>`;
                        }
                    }
                });
            }
            
            // Show unassigned slices
            const unassignedSlices = sliceList.filter(s => !assignedSlices.has(s.id));
            if (unassignedSlices.length > 0) {
                listHtml += `
                    <div style="background: #444; padding: 6px 10px; margin-top: 12px; margin-bottom: 4px; border-radius: 4px; font-size: 12px; font-weight: bold;">
                        📦 Unassigned (${unassignedSlices.length})
                    </div>
                `;
                
                unassignedSlices.forEach(slice => {
                    const isActive = slice === this.selectedSlice ? 'active' : '';
                    listHtml += this.renderSliceItem(slice, isActive, false);
                });
            }
        }
        
        // Insert dummy slice item for property editor reference
        sliceList.forEach(slice => {
            const isActive = slice === this.selectedSlice ? 'active' : '';
            
    // Show property editor for selected slice
    if (isActive && slice.shape === 'rectangle') {
        listHtml += `
                    <div style="padding: 10px; background: #1a1a1a; border-radius: 4px; margin-top: 8px;">
                        <div style="font-size: 11px; color: #888; margin-bottom: 8px;">Properties:</div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px;">
                            <div>
                                <label style="font-size: 10px; color: #666;">X</label>
                                <input type="number" value="${Math.round(slice.x)}" onchange="app.updateProperty('${slice.id}', 'x', parseFloat(this.value))" style="width: 100%; padding: 4px; background: #2a2a2a; border: 1px solid #444; color: #fff; border-radius: 3px;">
                            </div>
                            <div>
                                <label style="font-size: 10px; color: #666;">Y</label>
                                <input type="number" value="${Math.round(slice.y)}" onchange="app.updateProperty('${slice.id}', 'y', parseFloat(this.value))" style="width: 100%; padding: 4px; background: #2a2a2a; border: 1px solid #444; color: #fff; border-radius: 3px;">
                            </div>
                            <div>
                                <label style="font-size: 10px; color: #666;">Width</label>
                                <input type="number" value="${Math.round(slice.width)}" onchange="app.updateProperty('${slice.id}', 'width', parseFloat(this.value))" style="width: 100%; padding: 4px; background: #2a2a2a; border: 1px solid #444; color: #fff; border-radius: 3px;">
                            </div>
                            <div>
                                <label style="font-size: 10px; color: #666;">Height</label>
                                <input type="number" value="${Math.round(slice.height)}" onchange="app.updateProperty('${slice.id}', 'height', parseFloat(this.value))" style="width: 100%; padding: 4px; background: #2a2a2a; border: 1px solid #444; color: #fff; border-radius: 3px;">
                            </div>
                            <div style="grid-column: 1 / -1;">
                                <label style="font-size: 10px; color: #666;">Rotation (°)</label>
                                <input type="number" value="${Math.round(slice.rotation || 0)}" onchange="app.updateProperty('${slice.id}', 'rotation', parseFloat(this.value))" style="width: 100%; padding: 4px; background: #2a2a2a; border: 1px solid #444; color: #fff; border-radius: 3px;">
                            </div>
                            <div>
                                <label style="font-size: 10px; color: #666;">Brightness (-100-100)</label>
                                <input type="number" min="-100" max="100" value="${slice.brightness || 0}" onchange="app.updateProperty('${slice.id}', 'brightness', parseInt(this.value))" style="width: 100%; padding: 4px; background: #2a2a2a; border: 1px solid #444; color: #fff; border-radius: 3px;">
                            </div>
                            <div>
                                <label style="font-size: 10px; color: #666;">Contrast (-100-100)</label>
                                <input type="number" min="-100" max="100" value="${slice.contrast || 0}" onchange="app.updateProperty('${slice.id}', 'contrast', parseInt(this.value))" style="width: 100%; padding: 4px; background: #2a2a2a; border: 1px solid #444; color: #fff; border-radius: 3px;">
                            </div>
                            <div>
                                <label style="font-size: 10px; color: #666;">Red (-255-255)</label>
                                <input type="number" min="-255" max="255" value="${slice.red || 0}" onchange="app.updateProperty('${slice.id}', 'red', parseInt(this.value))" style="width: 100%; padding: 4px; background: #2a2a2a; border: 1px solid #444; color: #fff; border-radius: 3px;">
                            </div>
                            <div>
                                <label style="font-size: 10px; color: #666;">Green (-255-255)</label>
                                <input type="number" min="-255" max="255" value="${slice.green || 0}" onchange="app.updateProperty('${slice.id}', 'green', parseInt(this.value))" style="width: 100%; padding: 4px; background: #2a2a2a; border: 1px solid #444; color: #fff; border-radius: 3px;">
                            </div>
                            <div>
                                <label style="font-size: 10px; color: #666;">Blue (-255-255)</label>
                                <input type="number" min="-255" max="255" value="${slice.blue || 0}" onchange="app.updateProperty('${slice.id}', 'blue', parseInt(this.value))" style="width: 100%; padding: 4px; background: #2a2a2a; border: 1px solid #444; color: #fff; border-radius: 3px;">
                            </div>
                            <div>
                                <label style="font-size: 10px; color: #666;">Mirror/Flip</label>
                                <select value="${slice.mirror || 'none'}" onchange="app.updateProperty('${slice.id}', 'mirror', this.value)" style="width: 100%; padding: 4px; background: #2a2a2a; border: 1px solid #444; color: #fff; border-radius: 3px;">
                                    <option value="none" ${(slice.mirror || 'none') === 'none' ? 'selected' : ''}>None</option>
                                    <option value="horizontal" ${slice.mirror === 'horizontal' ? 'selected' : ''}>Horizontal</option>
                                    <option value="vertical" ${slice.mirror === 'vertical' ? 'selected' : ''}>Vertical</option>
                                    <option value="both" ${slice.mirror === 'both' ? 'selected' : ''}>Both</option>
                                </select>
                            </div>
                            <div style="grid-column: 1 / -1; border-top: 1px solid #333; padding-top: 8px; margin-top: 8px;">
                                <label style="font-size: 10px; color: #666; display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                                    <input type="checkbox" ${slice.softEdge?.enabled ? 'checked' : ''} onchange="app.toggleSoftEdge('${slice.id}', this.checked)" style="width: auto;">
                                    <strong>Soft Edge (Blending)</strong>
                                </label>
                                ${slice.softEdge?.enabled ? `
                                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-left: 20px;">
                                        <div style="grid-column: 1 / -1;">
                                            <label style="font-size: 9px; color: #666; display: flex; align-items: center; gap: 8px;">
                                                <input type="checkbox" ${slice.softEdge.autoDetect ? 'checked' : ''} onchange="app.updateSoftEdgeProperty('${slice.id}', 'autoDetect', this.checked)" style="width: auto;">
                                                Auto-detect overlaps
                                            </label>
                                        </div>
                                        <div>
                                            <label style="font-size: 9px; color: #888;">Top (px)</label>
                                            <input type="number" min="0" max="500" value="${slice.softEdge.width?.top || 50}" onchange="app.updateSoftEdgeWidth('${slice.id}', 'top', parseInt(this.value))" style="width: 100%; padding: 2px; background: #1a1a1a; border: 1px solid #444; color: #fff; border-radius: 3px; font-size: 10px;">
                                        </div>
                                        <div>
                                            <label style="font-size: 9px; color: #888;">Bottom (px)</label>
                                            <input type="number" min="0" max="500" value="${slice.softEdge.width?.bottom || 50}" onchange="app.updateSoftEdgeWidth('${slice.id}', 'bottom', parseInt(this.value))" style="width: 100%; padding: 2px; background: #1a1a1a; border: 1px solid #444; color: #fff; border-radius: 3px; font-size: 10px;">
                                        </div>
                                        <div>
                                            <label style="font-size: 9px; color: #888;">Left (px)</label>
                                            <input type="number" min="0" max="500" value="${slice.softEdge.width?.left || 50}" onchange="app.updateSoftEdgeWidth('${slice.id}', 'left', parseInt(this.value))" style="width: 100%; padding: 2px; background: #1a1a1a; border: 1px solid #444; color: #fff; border-radius: 3px; font-size: 10px;">
                                        </div>
                                        <div>
                                            <label style="font-size: 9px; color: #888;">Right (px)</label>
                                            <input type="number" min="0" max="500" value="${slice.softEdge.width?.right || 50}" onchange="app.updateSoftEdgeWidth('${slice.id}', 'right', parseInt(this.value))" style="width: 100%; padding: 2px; background: #1a1a1a; border: 1px solid #444; color: #fff; border-radius: 3px; font-size: 10px;">
                                        </div>
                                        <div style="grid-column: 1 / -1;">
                                            <label style="font-size: 9px; color: #888;">Fade Curve</label>
                                            <select value="${slice.softEdge.curve || 'smooth'}" onchange="app.updateSoftEdgeProperty('${slice.id}', 'curve', this.value)" style="width: 100%; padding: 2px; background: #1a1a1a; border: 1px solid #444; color: #fff; border-radius: 3px; font-size: 10px;">
                                                <option value="linear" ${slice.softEdge.curve === 'linear' ? 'selected' : ''}>Linear</option>
                                                <option value="smooth" ${(slice.softEdge.curve || 'smooth') === 'smooth' ? 'selected' : ''}>Smooth (S-curve)</option>
                                                <option value="exponential" ${slice.softEdge.curve === 'exponential' ? 'selected' : ''}>Exponential</option>
                                            </select>
                                        </div>
                                        <div style="grid-column: 1 / -1;">
                                            <label style="font-size: 9px; color: #888;">Strength (0.0-1.0)</label>
                                            <input type="number" min="0" max="1" step="0.1" value="${slice.softEdge.strength || 1.0}" onchange="app.updateSoftEdgeProperty('${slice.id}', 'strength', parseFloat(this.value))" style="width: 100%; padding: 2px; background: #1a1a1a; border: 1px solid #444; color: #fff; border-radius: 3px; font-size: 10px;">
                                        </div>
                                        <div style="grid-column: 1 / -1;">
                                            <label style="font-size: 9px; color: #888;">Gamma (Overall)</label>
                                            <input type="number" min="0.1" max="5" step="0.1" value="${slice.softEdge.gamma || 1.0}" onchange="app.updateSoftEdgeProperty('${slice.id}', 'gamma', parseFloat(this.value))" style="width: 100%; padding: 2px; background: #1a1a1a; border: 1px solid #444; color: #fff; border-radius: 3px; font-size: 10px;">
                                        </div>
                                        <div>
                                            <label style="font-size: 9px; color: #888;">Gamma R</label>
                                            <input type="number" min="0.1" max="5" step="0.1" value="${slice.softEdge.gammaR || 1.0}" onchange="app.updateSoftEdgeProperty('${slice.id}', 'gammaR', parseFloat(this.value))" style="width: 100%; padding: 2px; background: #1a1a1a; border: 1px solid #444; color: #fff; border-radius: 3px; font-size: 10px;">
                                        </div>
                                        <div>
                                            <label style="font-size: 9px; color: #888;">Gamma G</label>
                                            <input type="number" min="0.1" max="5" step="0.1" value="${slice.softEdge.gammaG || 1.0}" onchange="app.updateSoftEdgeProperty('${slice.id}', 'gammaG', parseFloat(this.value))" style="width: 100%; padding: 2px; background: #1a1a1a; border: 1px solid #444; color: #fff; border-radius: 3px; font-size: 10px;">
                                        </div>
                                        <div>
                                            <label style="font-size: 9px; color: #888;">Gamma B</label>
                                            <input type="number" min="0.1" max="5" step="0.1" value="${slice.softEdge.gammaB || 1.0}" onchange="app.updateSoftEdgeProperty('${slice.id}', 'gammaB', parseFloat(this.value))" style="width: 100%; padding: 2px; background: #1a1a1a; border: 1px solid #444; color: #fff; border-radius: 3px; font-size: 10px;">
                                        </div>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    </div>
        `;
    }

    // Show masks under the slice
    if (slice.masks && slice.masks.length > 0) {
        slice.masks.forEach(mask => {
                    const isMaskActive = mask === this.selectedSlice ? 'active' : '';
                    listHtml += `
                        <div style="padding-left: 20px; margin-top: 4px;">
                            <div class="slice-item ${isMaskActive}" style="background: #1a1a1a; border-color: #f44336;" onclick="app.selectMask('${slice.id}', '${mask.id}'); event.stopPropagation();">
                                <div class="slice-item-header">
                                    <div style="display: flex; align-items: center; gap: 5px;">
                                        <span style="color: #f44336">↳ ✕</span>
                                        <input type="text" value="${mask.label}" onchange="app.updateMaskProperty('${slice.id}', '${mask.id}', 'label', this.value); event.stopPropagation();" onclick="event.stopPropagation();" style="background: transparent; border: none; color: #fff; font-size: 12px; padding: 2px 4px; width: 120px; border-bottom: 1px solid transparent;" onfocus="this.style.borderBottomColor='#f44336'" onblur="this.style.borderBottomColor='transparent'">
                                    </div>
                                    <div class="slice-item-actions">
                                        <button class="small" onclick="app.toggleMaskVisibility('${slice.id}', '${mask.id}'); event.stopPropagation();" style="padding: 4px 8px; font-size: 12px;">${mask.visible !== false ? '👁️' : '🚫'}</button>
                                        <button class="small danger" onclick="app.deleteMask('${slice.id}', '${mask.id}'); event.stopPropagation();" style="padding: 4px 8px; font-size: 10px;">Del</button>
                                    </div>
                                </div>
                                <div class="slice-item-info">
                                    <span style="font-size: 10px;">${mask.shape}</span>
                                </div>
                            </div>
                        </div>
                    `;
        });
    }
        });

        document.getElementById('slicesList').innerHTML = listHtml;
    },

    renderSliceItem(slice, isActive, isAssigned = false) {
        const maskCount = slice.masks ? slice.masks.length : 0;
        const maskBadge = maskCount > 0 ? 
            `<span style="background: #f44336; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px;">${maskCount} masks</span>` : '';
        
        // Unassign button (only show if slice is assigned to outputs)
        const unassignBtn = isAssigned ? 
            `<button class="small" onclick="app.unassignSlice('${slice.id}'); event.stopPropagation();" style="padding: 4px 8px; font-size: 10px; background: #FF9800; border-color: #F57C00;" title="Unassign from all outputs">⊗</button>` : '';
        
        return `
            <div class="slice-item ${isActive}" onclick="app.selectSlice('${slice.id}')" style="margin-bottom: 4px;">
                <div class="slice-item-header">
                    <div style="display: flex; align-items: center; gap: 5px; flex-wrap: wrap;">
                        <span class="slice-color-indicator" style="background: ${slice.color}"></span>
                        <span style="font-size: 12px; color: #fff;">${slice.label || slice.name}</span>
                        ${maskBadge}
                    </div>
                    <div class="slice-item-actions">
                        <button class="small" onclick="app.toggleVisibility('${slice.id}'); event.stopPropagation();" style="padding: 4px 8px; font-size: 12px;">${slice.visible !== false ? '👁️' : '🚫'}</button>
                        ${unassignBtn}
                        <button class="small danger" onclick="app.deleteSliceById('${slice.id}'); event.stopPropagation();" style="padding: 4px 8px; font-size: 10px;">Del</button>
                    </div>
                </div>
                <div class="slice-item-info">
                    <span>${slice.shape} - ${Math.round(slice.width)}×${Math.round(slice.height)}</span>
                </div>
            </div>
        `;
    },

    async unassignSlice(sliceId) {
        if (!confirm('Unassign this slice from all outputs?')) {
            return;
        }

        // Find all outputs using this slice and set them to 'full'
        const promises = [];
        if (this.existingOutputs) {
            Object.entries(this.existingOutputs).forEach(([outputId, output]) => {
                if (output.slice === sliceId) {
                    promises.push(this.updateOutputSlice(outputId, 'full'));
                }
            });
        }

        // Wait for all unassignments to complete
        await Promise.all(promises);
        
        this.showToast('✅ Slice unassigned from all outputs', 'success');
        this.updateUI();
    },

    selectSlice(id) {
        const slice = this.slices.find(s => s.id === id);
        // Toggle selection if clicking the same slice
        if (this.selectedSlice === slice) {
            this.selectedSlice = null;
        } else {
            this.selectedSlice = slice || null;
        }
        this.updateUI();
        this.render();
    },

    selectMask(sliceId, maskId) {
        const slice = this.slices.find(s => s.id === sliceId);
        if (slice && slice.masks) {
    this.selectedSlice = slice.masks.find(m => m.id === maskId) || null;
    this.updateUI();
    this.render();
        }
    },

    deleteMask(sliceId, maskId) {
        const slice = this.slices.find(s => s.id === sliceId);
        if (slice && slice.masks) {
    slice.masks = slice.masks.filter(m => m.id !== maskId);
    if (this.selectedSlice && this.selectedSlice.id === maskId) {
        this.selectedSlice = null;
    }
    this.updateUI();
    this.render();
    this.showToast('Mask deleted');
        }
    },

    async deleteSliceById(id) {
        // Remove from frontend
        this.slices = this.slices.filter(s => s.id !== id);
        if (this.selectedSlice && this.selectedSlice.id === id) {
            this.selectedSlice = null;
        }
        this.updateUI();
        this.render();
        
        // Delete from backend
        try {
            const response = await fetch(`/api/slices/${id}`, {
                method: 'DELETE'
            });
            const data = await response.json();
            
            if (data.success) {
                this.showToast('✅ Slice deleted from backend');
            } else {
                this.showToast('⚠️ Slice removed locally but backend delete failed', 'warning');
            }
        } catch (error) {
            console.error('Failed to delete slice from backend:', error);
            this.showToast('⚠️ Slice removed locally but backend delete failed', 'warning');
        }
    },

    toggleVisibility(id) {
        const slice = this.slices.find(s => s.id === id);
        if (slice) {
    slice.visible = slice.visible === false ? true : false;
    this.updateUI();
    this.render();
    
    // Save to backend
    if (slice.id) {
        this.saveSliceToBackend(slice);
    }
        }
    },

    toggleMaskVisibility(sliceId, maskId) {
        const slice = this.slices.find(s => s.id === sliceId);
        if (slice && slice.masks) {
    const mask = slice.masks.find(m => m.id === maskId);
    if (mask) {
        mask.visible = mask.visible === false ? true : false;
        this.updateUI();
        this.render();
	    
	    // Save to backend (masks are part of slice data)
	    if (slice.id) {
		this.saveSliceToBackend(slice);
	    }
    } else if (!isNaN(value)) {
        slice[property] = value;
    }
    this.updateUI();
    this.render();
    
    // Save to backend
    if (slice.id) {
        this.saveSliceToBackend(slice);
    }
        }
    },

    updateMaskProperty(sliceId, maskId, property, value) {
        const slice = this.slices.find(s => s.id === sliceId);
        if (slice && slice.masks) {
	const mask = slice.masks.find(m => m.id === maskId);
	if (mask) {
	    if (property === 'label') {
		mask[property] = value;
	    } else if (!isNaN(value)) {
		mask[property] = value;
	    }
	    this.updateUI();
	    this.render();
	    
	    // Save to backend (masks are part of slice data)
	    if (slice.id) {
		this.saveSliceToBackend(slice);
	    }
	}
        }
    },

    // ========================================
    // EXPORT / IMPORT
    // ========================================
    
    exportJSON() {
        const data = {
    canvas: {
        width: this.canvasWidth,
        height: this.canvasHeight
    },
    slices: this.slices.map(s => {
        const sliceData = {
	id: s.id,
	label: s.label,
	type: s.type,
	shape: s.shape,
	screens: s.screens || [],
	color: s.color,
	visible: s.visible !== false,
	rotation: s.rotation || 0,
	brightness: s.brightness || 0,
	contrast: s.contrast || 0,
	red: s.red || 0,
	green: s.green || 0,
	blue: s.blue || 0,
	softEdge: s.softEdge && typeof s.softEdge === 'object' ? s.softEdge : { enabled: false, autoDetect: true, width: { top: 50, bottom: 50, left: 50, right: 50 }, curve: 'smooth', strength: 1.0, gamma: 1.0, gammaR: 1.0, gammaG: 1.0, gammaB: 1.0 },
	mirror: s.mirror || 'none',
	...this.getShapeData(s),
	transformCorners: s.transformCorners || null
        };
        
        // Add masks if any
        if (s.masks && s.masks.length > 0) {
    sliceData.masks = s.masks.map(m => ({
        id: m.id,
        label: m.label,
        type: m.type,
        shape: m.shape,
        color: m.color,
        visible: m.visible !== false,
        rotation: m.rotation || 0,
        geometry: m.geometry || null,
        ...this.getShapeData(m)
    }));
        } else {
    sliceData.masks = [];
        }
        
        return sliceData;
    }),
    timestamp: new Date().toISOString()
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `slices_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
        this.showToast('Exported!');
    },

    saveAndApply() {
        // For now, use the export function
        this.exportJSON();
        this.showToast('Saved & Applied!', 'success');
    },

    getShapeData(shape) {
        if (shape.shape === 'rectangle') {
    return { x: shape.x, y: shape.y, width: shape.width, height: shape.height };
        } else if (shape.shape === 'circle') {
    return { centerX: shape.centerX, centerY: shape.centerY, radius: shape.radius };
        } else {
    return { points: shape.points || [] };
        }
    },

    importJSON(event) {
        const file = event.target.files[0];
        if (file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        try {
    const data = JSON.parse(e.target.result);
    if (data.canvas) {
        this.canvasWidth = data.canvas.width;
        this.canvasHeight = data.canvas.height;
        document.getElementById('canvasWidth').value = this.canvasWidth;
        document.getElementById('canvasHeight').value = this.canvasHeight;
    }
    if (data.customScreens) {
        this.customScreens = data.customScreens;
    }
    if (data.slices) {
        this.slices = data.slices;
    }
    this.selectedSlice = null;
    this.updateCanvasSize();
    this.updateScreenButtons();
    this.updateUI();
    this.render();
    this.showToast('Imported!');
        } catch (err) {
    this.showToast('Import failed', 'error');
        }
    };
    reader.readAsText(file);
        }
        event.target.value = '';
    },

    clearAll() {
        if (confirm('Clear all shapes?')) {
    this.slices = [];
    this.selectedSlice = null;
    this.updateUI();
    this.render();
    this.showToast('Cleared');
        }
    },

    // ========================================
    // BACKEND PERSISTENCE (Session State)
    // ========================================
    
    async saveToBackend() {
        // Auto-save to backend session state (debounced)
        if (this._saveTimeout) {
            clearTimeout(this._saveTimeout);
        }
        
        this._saveTimeout = setTimeout(async () => {
            try {
                // Prepare slice data for backend
                const slicesData = {};
                
                this.slices.forEach(slice => {
                    const sliceId = slice.id || crypto.randomUUID();
                    
                    // Store ID back on object if new
                    if (!slice.id) {
                        slice.id = sliceId;
                    }
                    
                    slicesData[sliceId] = {
                        x: Math.round(slice.x),
                        y: Math.round(slice.y),
                        width: Math.round(slice.width),
                        height: Math.round(slice.height),
                        rotation: slice.rotation || 0,
                        shape: slice.shape || 'rectangle',
                        soft_edge: slice.softEdge || null,
                        description: slice.name || '',
                        points: slice.points || null,
                        outputs: slice.outputs || [],
                        source: slice.source || 'canvas'
                    };
                });
                
                // Send to backend using import endpoint
                const response = await fetch('/api/slices/import', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        slices: slicesData,
                        canvas: {
                            width: this.canvasWidth,
                            height: this.canvasHeight
                        },
                        customScreens: this.customScreens,
                        compositions: this.compositions || {}
                    })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    if (data.success) {
                        this.updateBackendStatus(true, `Auto-saved ${Object.keys(slicesData).length} slices`);
                    }
                }
                
            } catch (error) {
                console.error('Auto-save to backend failed:', error);
            }
        }, 1000); // Debounce 1 second
    },
    
    async saveSliceToBackend(slice) {
        try {
            // Generate ID if not present
            if (!slice.id) {
                slice.id = crypto.randomUUID();
            }
            
            const sliceData = {
                [slice.id]: {
                    x: Math.round(slice.x),
                    y: Math.round(slice.y),
                    width: Math.round(slice.width),
                    height: Math.round(slice.height),
                    rotation: slice.rotation || 0,
                    shape: slice.shape || 'rectangle',
                    soft_edge: slice.softEdge || null,
                    description: slice.name || slice.label || '',
                    points: slice.points || null,
                    outputs: slice.outputs || [],
                    source: slice.source || 'canvas'
                }
            };
            
            const response = await fetch('/api/slices/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    slices: sliceData,
                    canvas: { width: this.canvasWidth, height: this.canvasHeight }
                })
            });
            
            const data = await response.json();
            if (!data.success) {
                console.error('Failed to save slice to backend:', data.error);
                return false;
            }
            
            console.log(`✅ Saved slice ${slice.id} to backend`);
            return true;
            
        } catch (error) {
            console.error('Error saving slice to backend:', error);
            return false;
        }
    },
    
    async loadFromBackend() {
        try {
            // Load slices from backend session state
            const response = await fetch('/api/slices/export');
            const data = await response.json();
            
            if (data.success) {
                // Restore canvas dimensions
                if (data.canvas) {
                    this.canvasWidth = data.canvas.width;
                    this.canvasHeight = data.canvas.height;
                }
                
                // Restore slices
                if (data.slices) {
                    this.slices = [];
                    Object.entries(data.slices).forEach(([sliceId, sliceData]) => {
                        if (sliceId === 'full') return; // Skip default full slice
                        
                        this.slices.push({
                            id: sliceId,
                            x: sliceData.x,
                            y: sliceData.y,
                            width: sliceData.width,
                            height: sliceData.height,
                            rotation: sliceData.rotation || 0,
                            shape: sliceData.shape || 'rectangle',
                            softEdge: sliceData.soft_edge || null,
                            name: sliceData.description || sliceId,
                            label: sliceData.description || sliceId,
                            points: sliceData.points || null,
                            outputs: sliceData.outputs || [],
                            source: sliceData.source || 'canvas',
                            color: this.colors[this.colorIndex % this.colors.length],
                            masks: [],
                            type: 'slice'
                        });
                        this.colorIndex++;
                    });
                    
                    // Restore output assignments from backend output configs
                    // This ensures slice.outputs array reflects actual backend state
                    this.restoreSliceOutputAssignments();
                }
                
                this.updateBackendStatus(true, `Loaded ${this.slices.length} slices`);
                console.log('✅ Loaded from backend session state:', this.slices.length, 'slices');
                
                // Render after loading
                this.updateUI();
                this.render();
                
            } else {
                // No backend data - start with empty state
                console.log('No backend data, starting with empty state');
                this.slices = [];
                this.updateUI();
                this.render();
            }
            
        } catch (error) {
            console.error('Failed to load from backend:', error);
            this.updateBackendStatus(false, 'Backend connection failed');
            this.slices = [];
            this.updateUI();
            this.render();
        }
    },
    
    updateBackendStatus(connected, message) {
        const statusEl = document.getElementById('backendStatusText');
        if (statusEl) {
            statusEl.textContent = message;
            statusEl.style.color = connected ? '#4CAF50' : '#f44336';
        }
    },
    
    restoreSliceOutputAssignments() {
        // Restore slice.outputs array based on backend output configurations
        // This ensures the UI shows correct assignments after reload
        
        if (!this.existingOutputs) return;
        
        // First, clear all existing output assignments
        this.slices.forEach(slice => {
            slice.outputs = [];
        });
        
        // Then restore from backend output configs
        Object.entries(this.existingOutputs).forEach(([outputId, config]) => {
            // Check if output has a single slice assigned
            if (config.slice && config.slice !== 'full') {
                const slice = this.slices.find(s => s.id === config.slice);
                if (slice && !slice.outputs.includes(outputId)) {
                    slice.outputs.push(outputId);
                }
            }
            
            // Check if output has a composition with multiple slices
            if (config.composition && config.composition.slices) {
                config.composition.slices.forEach(compSlice => {
                    const slice = this.slices.find(s => s.id === compSlice.sliceId);
                    if (slice && !slice.outputs.includes(outputId)) {
                        slice.outputs.push(outputId);
                    }
                });
            }
        });
        
        console.log('✅ Restored slice output assignments from backend');
    },

    togglePanel(side) {
        const panel = document.getElementById(side === 'left' ? 'rightPanel' : 'leftPanel');
        const toggle = panel.querySelector('.panel-toggle');
        panel.classList.toggle('collapsed');
        
        if (side === 'left') {
    toggle.textContent = panel.classList.contains('collapsed') ? '▶' : '◀';
        } else {
    toggle.textContent = panel.classList.contains('collapsed') ? '◀' : '▶';
        }
    },

    // ========================================
    // TOAST & CONTEXT MENU
    // ========================================
    showToast(message, type = 'success', duration = 3000) {
        // Use shared toast module
        const container = document.getElementById('toastContainer');
        if (!container) {
    console.warn('Toast container not found');
    return;
        }
        
        const toastId = 'toast-' + Date.now();
        const icons = {
    success: '✓',
    error: '✗',
    info: 'ℹ',
    warning: '⚠'
        };
        
        const toastElement = document.createElement('div');
        toastElement.id = toastId;
        toastElement.className = `toast-message ${type}`;
        toastElement.innerHTML = `
    <span class="toast-icon">${icons[type] || icons.info}</span>
    <span class="toast-content">${message}</span>
    <button class="toast-close" onclick="this.parentElement.remove()">×</button>
        `;
        
        container.appendChild(toastElement);
        
        // Auto remove after duration
        setTimeout(() => {
    toastElement.classList.add('removing');
    setTimeout(() => toastElement.remove(), 300);
        }, duration);
    },

    onContextMenu(e) {
        e.preventDefault();
        
        const pos = this.getMousePos(e);
        const slice = this.getSliceAt(pos);
        
        // Only show context menu for slices (not masks)
        if (!slice || slice.type !== 'slice') {
    this.closeContextMenu();
    return;
        }
        
        this.contextMenuTarget = slice;
        this.selectedSlice = slice;
        
        const menu = document.getElementById('contextMenu');
        
        // Position menu initially to measure size
        menu.style.left = e.clientX + 'px';
        menu.style.top = e.clientY + 'px';
        menu.classList.add('active');
        
        // Adjust position if menu would overflow viewport
        const menuRect = menu.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        
        // Adjust horizontal position
        let left = e.clientX;
        if (left + menuRect.width > viewportWidth) {
            left = viewportWidth - menuRect.width - 10; // 10px padding from edge
        }
        
        // Adjust vertical position
        let top = e.clientY;
        if (top + menuRect.height > viewportHeight) {
            top = viewportHeight - menuRect.height - 10; // 10px padding from edge
        }
        
        menu.style.left = left + 'px';
        menu.style.top = top + 'px';
        
        this.render();
    },

    closeContextMenu() {
        const menu = document.getElementById('contextMenu');
        menu.classList.remove('active');
    },

    contextMenuAction(action, event) {
        // Stop event propagation to prevent document click handler from interfering
        if (event) {
            event.stopPropagation();
            event.preventDefault();
        }
        
        this.closeContextMenu();
        
        if (!this.contextMenuTarget) return;
        
        const slice = this.contextMenuTarget;
        
        switch(action) {
    case 'centerX':
        slice.x = (this.canvasWidth - slice.width) / 2;
        this.showToast('Slice centered horizontally');
        break;
        
    case 'centerY':
        slice.y = (this.canvasHeight - slice.height) / 2;
        this.showToast('Slice centered vertically');
        break;
        
    case 'alignCenter':
        slice.x = (this.canvasWidth - slice.width) / 2;
        slice.y = (this.canvasHeight - slice.height) / 2;
        this.showToast('Slice aligned to center');
        break;
        
    case 'alignLeft':
        slice.x = 0;
        this.showToast('Slice aligned to left');
        break;
        
    case 'alignRight':
        slice.x = this.canvasWidth - slice.width;
        this.showToast('Slice aligned to right');
        break;
        
    case 'alignTop':
        slice.y = 0;
        this.showToast('Slice aligned to top');
        break;
        
    case 'alignBottom':
        slice.y = this.canvasHeight - slice.height;
        this.showToast('Slice aligned to bottom');
        break;
        
    case 'leftHalf':
        slice.x = 0;
        slice.y = 0;
        slice.width = this.canvasWidth / 2;
        slice.height = this.canvasHeight;
        this.showToast('Slice set to left half');
        break;
        
    case 'rightHalf':
        slice.x = this.canvasWidth / 2;
        slice.y = 0;
        slice.width = this.canvasWidth / 2;
        slice.height = this.canvasHeight;
        this.showToast('Slice set to right half');
        break;
        
    case 'topHalf':
        slice.x = 0;
        slice.y = 0;
        slice.width = this.canvasWidth;
        slice.height = this.canvasHeight / 2;
        this.showToast('Slice set to top half');
        break;
        
    case 'bottomHalf':
        slice.x = 0;
        slice.y = this.canvasHeight / 2;
        slice.width = this.canvasWidth;
        slice.height = this.canvasHeight / 2;
        this.showToast('Slice set to bottom half');
        break;
        
    case 'wholeArea':
        slice.x = 0;
        slice.y = 0;
        slice.width = this.canvasWidth;
        slice.height = this.canvasHeight;
        this.showToast('Slice set to whole area');
        break;
        
    case 'ratio16_9':
        // Calculate width based on current height (16:9 aspect ratio)
        slice.width = Math.round(slice.height * (16 / 9));
        this.showToast(`Slice resized to 16:9 (${slice.width}×${slice.height})`);
        break;
        
    case 'preview':
        this.selectedSlice = slice;
        this.showRealtimeSlicePreview();
        break;
        
    case 'duplicate':
        this.selectedSlice = slice;
        this.duplicateSelected();
        break;
        
    case 'delete':
        this.deleteSliceById(slice.id);
        this.contextMenuTarget = null;
        this.selectedSlice = null;
        break;
        }
        
        // Force immediate update and save to backend
        // Save the modified slice to backend to ensure composition uses updated dimensions
        if (slice && slice.id) {
            this.saveSliceToBackend(slice);
        }
        
        this.updateUI();
        
        // Use requestAnimationFrame to ensure render happens after DOM updates
        requestAnimationFrame(() => {
            this.render();
        });
    },

    showRealtimeSlicePreview() {
        if (!this.selectedSlice) {
            this.showToast('Select a slice first', 'error');
            return;
        }

        const slice = this.selectedSlice;
        
        // Build slice configuration for URL parameter
        const sliceConfig = {
            x: Math.round(slice.x),
            y: Math.round(slice.y),
            width: Math.round(slice.width),
            height: Math.round(slice.height),
            shape: slice.shape || 'rectangle',
            rotation: slice.rotation || 0
        };
        
        // Add transform corners if slice has perspective transform
        if (slice.transformCorners) {
            sliceConfig.transformCorners = slice.transformCorners.map(c => ({
                x: Math.round(c.x),
                y: Math.round(c.y)
            }));
            console.log('Transform corners detected:', sliceConfig.transformCorners);
        } else {
            console.log('No transform corners on slice');
        }
        
        // Add masks if present - need to adjust coordinates to be relative to slice
        if (slice.masks && slice.masks.length > 0) {
            sliceConfig.masks = slice.masks.map(mask => {
                const maskConfig = {
                    shape: mask.shape,
                    visible: mask.visible !== false
                };
                
                if (mask.shape === 'rectangle') {
                    // Convert canvas coordinates to slice-relative coordinates
                    maskConfig.x = Math.round(mask.x - slice.x);
                    maskConfig.y = Math.round(mask.y - slice.y);
                    maskConfig.width = Math.round(mask.width);
                    maskConfig.height = Math.round(mask.height);
                } else if (mask.shape === 'circle') {
                    // Convert canvas coordinates to slice-relative coordinates
                    maskConfig.centerX = Math.round(mask.centerX - slice.x);
                    maskConfig.centerY = Math.round(mask.centerY - slice.y);
                    maskConfig.radius = Math.round(mask.radius);
                } else if (mask.points) {
                    // Convert canvas coordinates to slice-relative coordinates
                    maskConfig.points = mask.points.map(p => ({
                        x: Math.round(p.x - slice.x),
                        y: Math.round(p.y - slice.y)
                    }));
                }
                
                return maskConfig;
            });
            console.log('Masks included:', sliceConfig.masks);
        }
        
        // Debug log
        console.log('Slice preview config:', sliceConfig);
        console.log('Canvas size:', this.canvasWidth, 'x', this.canvasHeight);
        
        // Add shape-specific data
        if (slice.shape === 'circle') {
            sliceConfig.radius = slice.radius;
            sliceConfig.cx = slice.cx;
            sliceConfig.cy = slice.cy;
        } else if (slice.shape === 'polygon' || slice.shape === 'triangle') {
            sliceConfig.points = slice.points;
        } else if (slice.shape === 'freehand') {
            sliceConfig.points = slice.points;
        }
        
        // URL-encode the slice config
        const sliceParam = encodeURIComponent(JSON.stringify(sliceConfig));
        
        // Create modal content with MJPEG stream
        const modalContent = `
            <div style="position: relative; width: 100%; max-height: 70vh; display: flex; align-items: center; justify-content: center; background: #000;">
                <img id="slicePreviewStream" 
                     style="max-width: 100%; max-height: 70vh; object-fit: contain; image-rendering: auto;" 
                     src="/api/preview/stream?slice=${sliceParam}"
                     alt="Slice Preview">
            </div>
            <div style="margin-top: 15px; padding: 10px; background: #1a1a1a; border-radius: 4px; font-size: 12px;">
                <strong>${slice.label}</strong><br>
                Position: ${Math.round(slice.x)}, ${Math.round(slice.y)}<br>
                Size: ${Math.round(slice.width)} × ${Math.round(slice.height)}<br>
                Shape: ${slice.shape || 'rectangle'}${slice.rotation ? ` (${slice.rotation}°)` : ''}
            </div>
        `;
        
        // Create modal (destroy existing one first if it exists)
        const existingModal = ModalManager.get('slicePreviewModal');
        if (existingModal) {
            existingModal.destroy();
        }
        
        const modal = ModalManager.create({
            id: 'slicePreviewModal',
            title: `🔍 Real-time Preview - ${slice.label}`,
            content: modalContent,
            size: 'xl',
            buttons: [
                {
                    label: 'Close',
                    class: 'btn-secondary',
                    callback: (modalInstance) => {
                        // Stop stream by clearing img src
                        const img = document.getElementById('slicePreviewStream');
                        if (img) img.src = '';
                        
                        // Just hide - let Bootstrap handle cleanup naturally
                        modalInstance.hide();
                    }
                }
            ]
        });
        
        modal.show();
    },

    openOutputComposer(outputId) {
        console.log('Opening output composer for:', outputId);
        console.log('Current compositions:', this.compositions);
        console.log('Composition for this output:', this.compositions?.[outputId]);
        
        // Get ALL slices (not just assigned ones - user can add any slice)
        const availableSlices = this.slices.filter(s => s.type !== 'mask');
        
        // Get output info to determine resolution
        const output = this.existingOutputs[outputId];
        const outputWidth = output?.resolution?.[0] || output?.resolution?.width || 1920;
        const outputHeight = output?.resolution?.[1] || output?.resolution?.height || 1080;
        
        // Get or initialize composition for this output
        if (!this.compositions) this.compositions = {};
        if (!this.compositions[outputId]) {
            console.log(`Creating new empty composition for ${outputId}`);
            this.compositions[outputId] = {
                width: outputWidth,
                height: outputHeight,
                slices: []
            };
        } else {
            console.log(`Using existing composition for ${outputId} with ${this.compositions[outputId].slices.length} slices`);
        }
        
        const composition = this.compositions[outputId];
        
        // Create modal content
        const modalContent = `
            <div style="display: flex; gap: 15px; height: 70vh;">
                <!-- Left sidebar with available slices -->
                <div style="width: 250px; background: #1a1a1a; border-radius: 6px; padding: 15px; overflow-y: auto;">
                    <h6 style="margin-bottom: 15px; color: #aaa;">Available Slices</h6>
                    <div id="composerSliceList">
                        ${availableSlices.length === 0 ? 
                            '<div style="color: #666; font-size: 12px;">No slices created yet. Create slices first!</div>' :
                            availableSlices.map(s => `
                                <div class="composer-slice-item" data-slice-id="${s.id}" draggable="true"
                                     style="padding: 8px; margin-bottom: 8px; background: #2a2a2a; border-radius: 4px; cursor: grab; border-left: 3px solid ${s.color};">
                                    <div style="font-size: 12px; font-weight: bold;">${s.label}</div>
                                    <div style="font-size: 10px; color: #888;">${Math.round(s.width)}×${Math.round(s.height)}</div>
                                </div>
                            `).join('')
                        }
                    </div>
                    
                    <hr style="border-color: #333; margin: 15px 0;">
                    
                    <h6 style="margin-bottom: 10px; color: #aaa;">Composition</h6>
                    <div id="compositionList" style="font-size: 12px;">
                        <!-- Will be populated dynamically -->
                    </div>
                </div>
                
                <!-- Center canvas area -->
                <div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; background: #0a0a0a; border-radius: 6px; position: relative; overflow: hidden;">
                    <div id="composerCanvasContainer" style="position: relative; background: repeating-conic-gradient(#1a1a1a 0% 25%, #0a0a0a 0% 50%) 50% / 20px 20px;">
                        <canvas id="composerCanvas" width="${outputWidth}" height="${outputHeight}" 
                                style="border: 1px solid #444; cursor: crosshair; display: block; max-width: 100%; max-height: 100%; width: auto; height: auto;">
                        </canvas>
                    </div>
                    <div style="position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.7); padding: 8px; border-radius: 4px; font-size: 11px;">
                        <strong>${outputId}</strong> - ${outputWidth}×${outputHeight}
                    </div>
                    <div id="composerHint" style="position: absolute; bottom: 10px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.7); padding: 8px 12px; border-radius: 4px; font-size: 11px;">
                        Drag slices onto canvas to add them to composition
                    </div>
                </div>
            </div>
        `;
        
        // Create modal
        const modal = ModalManager.create({
            id: 'outputComposerModal',
            title: `🎨 Output Composer - ${outputId}`,
            content: modalContent,
            size: 'xl',
            buttons: [
                {
                    label: '📐 Auto-Arrange',
                    class: 'btn-info',
                    callback: () => {
                        this.autoArrangeComposition(outputId);
                    }
                },
                {
                    label: 'Clear All',
                    class: 'btn-warning',
                    callback: () => {
                        if (confirm('Clear all slices from composition?')) {
                            composition.slices = [];
                            this.renderComposition(outputId);
                        }
                    }
                },
                {
                    label: 'Save',
                    class: 'btn-primary',
                    callback: (modalInstance) => {
                        this.saveComposition(outputId);
                        modalInstance.hide();
                    }
                },
                {
                    label: 'Cancel',
                    class: 'btn-secondary',
                    callback: (modalInstance) => {
                        modalInstance.hide();
                    }
                }
            ]
        });
        
        modal.show();
        
        // Initialize composer after modal is shown
        setTimeout(() => {
            this.initComposer(outputId);
        }, 100);
    },

    initComposer(outputId) {
        const canvas = document.getElementById('composerCanvas');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        const composition = this.compositions[outputId];
        
        console.log(`initComposer for ${outputId}, composition:`, composition);
        
        // Initialize composer state for dragging
        if (!this.composerState) {
            this.composerState = {};
        }
        this.composerState[outputId] = {
            isDragging: false,
            dragIndex: -1,
            dragOffset: { x: 0, y: 0 }
        };
        
        // Setup drag and drop from sidebar
        const sliceItems = document.querySelectorAll('.composer-slice-item');
        sliceItems.forEach(item => {
            item.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('sliceId', item.dataset.sliceId);
            });
        });
        
        canvas.addEventListener('dragover', (e) => {
            e.preventDefault();
        });
        
        canvas.addEventListener('drop', (e) => {
            e.preventDefault();
            const sliceId = e.dataTransfer.getData('sliceId');
            if (!sliceId) return;
            
            const slice = this.slices.find(s => s.id === sliceId);
            if (!slice) return;
            
            // Get drop position relative to canvas
            const rect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            const x = (e.clientX - rect.left) * scaleX;
            const y = (e.clientY - rect.top) * scaleY;
            
            // Add slice to composition
            composition.slices.push({
                sliceId: slice.id,
                x: Math.round(x - slice.width / 2),
                y: Math.round(y - slice.height / 2),
                width: Math.round(slice.width),
                height: Math.round(slice.height),
                scale: 1.0
            });
            
            this.renderComposition(outputId);
        });
        
        // Mouse events for moving slices on canvas
        canvas.addEventListener('mousedown', (e) => {
            const rect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            const x = (e.clientX - rect.left) * scaleX;
            const y = (e.clientY - rect.top) * scaleY;
            
            // Find clicked slice (iterate backwards for top-most)
            for (let i = composition.slices.length - 1; i >= 0; i--) {
                const cs = composition.slices[i];
                if (x >= cs.x && x <= cs.x + cs.width && 
                    y >= cs.y && y <= cs.y + cs.height) {
                    this.composerState[outputId].isDragging = true;
                    this.composerState[outputId].dragIndex = i;
                    this.composerState[outputId].dragOffset = {
                        x: x - cs.x,
                        y: y - cs.y
                    };
                    break;
                }
            }
        });
        
        canvas.addEventListener('mousemove', (e) => {
            const state = this.composerState[outputId];
            if (!state.isDragging) return;
            
            const rect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            const x = (e.clientX - rect.left) * scaleX;
            const y = (e.clientY - rect.top) * scaleY;
            
            const compSlice = composition.slices[state.dragIndex];
            compSlice.x = Math.round(x - state.dragOffset.x);
            compSlice.y = Math.round(y - state.dragOffset.y);
            
            this.renderComposition(outputId);
        });
        
        canvas.addEventListener('mouseup', () => {
            this.composerState[outputId].isDragging = false;
            this.composerState[outputId].dragIndex = -1;
        });
        
        canvas.addEventListener('mouseleave', () => {
            this.composerState[outputId].isDragging = false;
            this.composerState[outputId].dragIndex = -1;
        });
        
        // Initial render
        this.renderComposition(outputId);
    },

    renderComposition(outputId) {
        const canvas = document.getElementById('composerCanvas');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        const composition = this.compositions[outputId];
        
        // Clear canvas
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Draw each slice in composition
        composition.slices.forEach((compSlice, index) => {
            const slice = this.slices.find(s => s.id === compSlice.sliceId);
            if (!slice) return;
            
            const isSelected = index === this.composerState?.selectedIndex;
            
            // Draw rectangle representing the slice
            ctx.fillStyle = slice.color + '40';  // Semi-transparent
            ctx.fillRect(compSlice.x, compSlice.y, compSlice.width, compSlice.height);
            
            ctx.strokeStyle = isSelected ? '#fff' : slice.color;
            ctx.lineWidth = isSelected ? 3 : 2;
            ctx.strokeRect(compSlice.x, compSlice.y, compSlice.width, compSlice.height);
            
            // Draw label
            ctx.fillStyle = '#fff';
            ctx.font = '12px Arial';
            const scaleText = compSlice.scale !== 1.0 ? ` (${(compSlice.scale * 100).toFixed(0)}%)` : '';
            ctx.fillText(slice.label + scaleText, compSlice.x + 5, compSlice.y + 15);
            
            // Draw resize handle if selected
            if (isSelected) {
                const handleSize = 8;
                const handleX = compSlice.x + compSlice.width;
                const handleY = compSlice.y + compSlice.height;
                
                ctx.fillStyle = '#fff';
                ctx.fillRect(handleX - handleSize, handleY - handleSize, handleSize * 2, handleSize * 2);
                ctx.strokeStyle = '#000';
                ctx.lineWidth = 1;
                ctx.strokeRect(handleX - handleSize, handleY - handleSize, handleSize * 2, handleSize * 2);
            }
        });
        
        // Update composition list
        this.updateCompositionList(outputId);
    },

    updateCompositionList(outputId) {
        const listContainer = document.getElementById('compositionList');
        if (!listContainer) return;
        
        const composition = this.compositions[outputId];
        
        if (composition.slices.length === 0) {
            listContainer.innerHTML = '<div style="color: #666;">No slices in composition</div>';
            return;
        }
        
        let html = '';
        composition.slices.forEach((compSlice, index) => {
            const slice = this.slices.find(s => s.id === compSlice.sliceId);
            if (!slice) return;
            
            html += `
                <div style="padding: 6px; margin-bottom: 6px; background: #2a2a2a; border-radius: 3px; border-left: 3px solid ${slice.color};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <div>
                            <div style="font-weight: bold; font-size: 11px;">${slice.label}</div>
                            <div style="font-size: 9px; color: #888;">
                                Pos: ${compSlice.x},${compSlice.y} Size: ${compSlice.width}×${compSlice.height}
                            </div>
                        </div>
                        <button onclick="app.removeFromComposition('${outputId}', ${index}); event.stopPropagation();" 
                                style="padding: 2px 6px; font-size: 10px; background: #d32f2f; border: none; color: white; border-radius: 3px; cursor: pointer;">×</button>
                    </div>
                    <div style="display: flex; align-items: center; gap: 5px; font-size: 10px;">
                        <label style="color: #aaa;">Scale:</label>
                        <input type="range" min="0.1" max="3" step="0.1" value="${compSlice.scale || 1.0}" 
                               onchange="app.updateCompositionScale('${outputId}', ${index}, parseFloat(this.value))"
                               style="flex: 1; height: 4px;">
                        <input type="number" min="0.1" max="3" step="0.1" value="${compSlice.scale || 1.0}" 
                               onchange="app.updateCompositionScale('${outputId}', ${index}, parseFloat(this.value))"
                               style="width: 50px; padding: 2px; background: #1a1a1a; border: 1px solid #444; color: #fff; border-radius: 2px; font-size: 9px;">
                    </div>
                </div>
            `;
        });
        
        listContainer.innerHTML = html;
    },

    removeFromComposition(outputId, index) {
        const composition = this.compositions[outputId];
        composition.slices.splice(index, 1);
        this.renderComposition(outputId);
    },

    updateCompositionScale(outputId, index, scale) {
        const composition = this.compositions[outputId];
        const compSlice = composition.slices[index];
        const slice = this.slices.find(s => s.id === compSlice.sliceId);
        if (!slice) return;
        
        compSlice.scale = scale;
        compSlice.width = Math.round(slice.width * scale);
        compSlice.height = Math.round(slice.height * scale);
        
        this.renderComposition(outputId);
    },

    autoArrangeComposition(outputId) {
        const composition = this.compositions[outputId];
        if (!composition || composition.slices.length === 0) {
            this.showToast('Add some slices first!', 'warning');
            return;
        }

        const sliceCount = composition.slices.length;
        const outputWidth = composition.width;
        const outputHeight = composition.height;

        // Smart grid calculation
        let cols, rows;
        if (sliceCount === 1) {
            cols = 1; rows = 1;
        } else if (sliceCount === 2) {
            cols = 2; rows = 1; // Horizontal split
        } else if (sliceCount === 3) {
            cols = 3; rows = 1; // Three columns
        } else if (sliceCount === 4) {
            cols = 2; rows = 2; // 2x2 grid
        } else {
            // For 5+, calculate optimal grid (roughly square)
            cols = Math.ceil(Math.sqrt(sliceCount));
            rows = Math.ceil(sliceCount / cols);
        }

        // Calculate cell dimensions
        const cellWidth = Math.floor(outputWidth / cols);
        const cellHeight = Math.floor(outputHeight / rows);

        // Arrange slices in grid
        composition.slices.forEach((compSlice, index) => {
            const slice = this.slices.find(s => s.id === compSlice.sliceId);
            if (!slice) return;

            const col = index % cols;
            const row = Math.floor(index / cols);

            // Position in grid
            compSlice.x = col * cellWidth;
            compSlice.y = row * cellHeight;

            // Scale to fit cell while maintaining aspect ratio
            const originalAspect = slice.width / slice.height;
            const cellAspect = cellWidth / cellHeight;

            if (originalAspect > cellAspect) {
                // Wider than cell - fit to width
                compSlice.width = cellWidth;
                compSlice.height = Math.round(cellWidth / originalAspect);
                compSlice.scale = cellWidth / slice.width;
            } else {
                // Taller than cell - fit to height
                compSlice.height = cellHeight;
                compSlice.width = Math.round(cellHeight * originalAspect);
                compSlice.scale = cellHeight / slice.height;
            }

            // Center in cell
            if (compSlice.width < cellWidth) {
                compSlice.x += Math.floor((cellWidth - compSlice.width) / 2);
            }
            if (compSlice.height < cellHeight) {
                compSlice.y += Math.floor((cellHeight - compSlice.height) / 2);
            }
        });

        this.renderComposition(outputId);
        this.showToast(`✅ Arranged ${sliceCount} slices in ${cols}×${rows} grid`, 'success');
    },

    async saveComposition(outputId) {
        const composition = this.compositions[outputId];
        
        if (!composition || !composition.slices || composition.slices.length === 0) {
            this.showToast('⚠️ No slices in composition', 'warning');
            return;
        }
        
        try {
            console.log('Saving composition for', outputId, composition);
            
            // Send composition to backend
            const response = await fetch(`/api/outputs/video/${outputId}/composition`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ composition: composition })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showToast(`✅ Composition saved with ${composition.slices.length} slices`, 'success');
                await this.loadExistingOutputs(); // Reload to update display
                this.updateUI();
            } else {
                this.showToast(`❌ Failed: ${data.error}`, 'error');
            }
            
        } catch (error) {
            console.error('Failed to save composition:', error);
            this.showToast('❌ Failed to save composition', 'error');
        }
    },

    async removeComposition(outputId) {
        if (!confirm(`Remove composition from ${outputId}? Slices will be unassigned.`)) {
            return;
        }

        // Clear composition data
        if (this.compositions && this.compositions[outputId]) {
            delete this.compositions[outputId];
        }

        // Set output back to full canvas
        await this.updateOutputSlice(outputId, 'full');

        // Update UI to show slices as unassigned
        this.updateUI();
        this.showToast(`✅ Composition removed from ${outputId}`, 'success');
    }
};


// ========================================
// INITIALIZATION
// ========================================

// Make app globally accessible
window.app = app;

// ========================================
// GLOBAL FUNCTIONS (called from HTML)
// ========================================

async function loadMonitors() {
    try {
        const response = await fetch('/api/monitors');
        const data = await response.json();
        
        if (!data.success) {
            app.showToast('❌ Failed to load monitors: ' + data.error, 'error');
            app.updateBackendStatus(false, 'API error');
            return;
        }
        
        // Update backend status
        app.updateBackendStatus(true, `Connected (${data.count} monitors)`);
        
        // Update monitor count display
        const monitorCountEl = document.getElementById('monitorCount');
        const monitorCountNumEl = document.getElementById('monitorCountNum');
        if (monitorCountEl && monitorCountNumEl) {
            monitorCountEl.style.display = 'block';
            monitorCountNumEl.textContent = data.count;
        }
        
        // Update outputs list with monitors
        app.screens = data.monitors.map((monitor, index) => ({
            id: `monitor_${index}`,
            name: monitor.name,
            width: monitor.width,
            height: monitor.height,
            x: monitor.x,
            y: monitor.y,
            type: 'monitor',
            monitor_index: index
        }));
        
        // Update UI
        app.updateScreenButtons();
        
        app.showToast(`✅ Loaded ${data.count} monitor(s)`, 'success');
        
    } catch (error) {
        console.error('Failed to load monitors:', error);
        app.showToast('❌ Backend connection failed', 'error');
        app.updateBackendStatus(false, 'Connection error');
    }
}

async function saveSlicesToBackend() {
    try {
        // Prepare slice data
        const slicesData = {};
        
        app.slices.forEach(slice => {
            const sliceId = slice.id || crypto.randomUUID();
            
            slicesData[sliceId] = {
                x: Math.round(slice.x),
                y: Math.round(slice.y),
                width: Math.round(slice.width),
                height: Math.round(slice.height),
                rotation: slice.rotation || 0,
                shape: slice.shape || 'rectangle',
                soft_edge: slice.softEdge || null,
                description: slice.name || '',
                points: slice.points || null,
                outputs: slice.outputs || [],
                source: slice.source || 'canvas'
            };
            
            // Store slice ID back on object
            if (!slice.id) {
                slice.id = sliceId;
            }
        });
        
        // Send to backend
        const response = await fetch('/api/slices/import', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                slices: slicesData,
                canvas: {
                    width: app.canvasWidth,
                    height: app.canvasHeight
                }
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            app.showToast('❌ Failed to save slices: ' + data.error, 'error');
            return;
        }
        
        app.showToast(`✅ Saved ${Object.keys(slicesData).length} slice(s) to backend`, 'success');
        app.updateBackendStatus(true, `Saved ${Object.keys(slicesData).length} slices`);
        
    } catch (error) {
        console.error('Failed to save slices:', error);
        app.showToast('❌ Backend save failed', 'error');
    }
}

async function loadSlicesFromBackend() {
    try {
        const response = await fetch('/api/slices/export');
        const data = await response.json();
        
        if (!data.success) {
            app.showToast('❌ Failed to load slices: ' + data.error, 'error');
            return;
        }
        
        // Clear current slices
        app.slices = [];
        
        // Load slices from backend
        Object.entries(data.slices || {}).forEach(([sliceId, sliceData]) => {
            if (sliceId === 'full') return; // Skip default full slice
            
            app.slices.push({
                id: sliceId,
                x: sliceData.x,
                y: sliceData.y,
                width: sliceData.width,
                height: sliceData.height,
                rotation: sliceData.rotation || 0,
                shape: sliceData.shape || 'rectangle',
                softEdge: sliceData.soft_edge || null,
                name: sliceData.description || sliceId,
                points: sliceData.points || null,
                outputs: sliceData.outputs || [],
                source: sliceData.source || 'canvas',
                color: app.colors[app.colorIndex % app.colors.length],
                masks: [],
                type: 'slice'
            });
            app.colorIndex++;
        });
        
        // Update UI
        app.updateSlicesList();
        app.render();
        
        app.showToast(`✅ Loaded ${app.slices.length} slice(s) from backend`, 'success');
        app.updateBackendStatus(true, `Loaded ${app.slices.length} slices`);
        
    } catch (error) {
        console.error('Failed to load slices:', error);
        app.showToast('❌ Backend load failed', 'error');
    }
}

// Initialize on page load
window.addEventListener('load', () => {
    app.init();
});
