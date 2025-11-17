/**
 * State Management
 * Globaler Zustand des Editors
 */

import { markForRedraw } from './utils.js';

// Shape management
export let shapes = [];
export let selectedShape = null;
export let selectedShapes = []; // Multiple selection support
export let groups = []; // Groups of shapes
export let groupCounter = 1;
export let shapeCounter = 1;

// Drag state
export let dragMode = null;
export let offsetX = 0, offsetY = 0;
export let dragStartX = 0, dragStartY = 0;
export let dragStartRotation = 0;
export let dragStartScaleX = 0, dragStartScaleY = 0;
export let scaleHandleIndex = null;

// Selection
export let selectionBox = null; // For marquee selection: {startX, startY, endX, endY}

// Rendering state
export let needsRedraw = true;
export let hoveredPoint = null; // For tooltip: {shape, pointIndex, x, y}
export let showConnectionLines = true; // Toggle for connection lines between objects
export let backgroundImage = null;

// Icon images
export let flipIconImage = null;
export let rotateIconImage = null;
export let scaleYIconImage = null;
export let scaleXIconImage = null;

// State setters
export function setShapes(newShapes) { shapes = newShapes; }
export function setSelectedShape(shape) { selectedShape = shape; }
export function setSelectedShapes(shapesArray) { selectedShapes = shapesArray; }
export function setGroups(newGroups) { groups = newGroups; }
export function setGroupCounter(count) { groupCounter = count; }
export function setShapeCounter(count) { shapeCounter = count; }
export function incrementShapeCounter() { return shapeCounter++; }
export function incrementGroupCounter() { return groupCounter++; }
export function setDragMode(mode) { dragMode = mode; }
export function setOffsetX(x) { offsetX = x; }
export function setOffsetY(y) { offsetY = y; }
export function setDragStartX(x) { dragStartX = x; }
export function setDragStartY(y) { dragStartY = y; }
export function setDragStartRotation(rot) { dragStartRotation = rot; }
export function setDragStartScaleX(scale) { dragStartScaleX = scale; }
export function setDragStartScaleY(scale) { dragStartScaleY = scale; }
export function setScaleHandleIndex(index) { scaleHandleIndex = index; }
export function setSelectionBox(box) { selectionBox = box; }
export function setNeedsRedraw(value) { needsRedraw = value; }
export function setHoveredPoint(point) { hoveredPoint = point; }
export function setShowConnectionLines(value) { showConnectionLines = value; }
export function setBackgroundImage(img) { backgroundImage = img; }
export function setFlipIconImage(img) { flipIconImage = img; }
export function setRotateIconImage(img) { rotateIconImage = img; }
export function setScaleYIconImage(img) { scaleYIconImage = img; }
export function setScaleXIconImage(img) { scaleXIconImage = img; }

// Load icon images
export function loadIcons() {
    const flipIcon = new Image();
    flipIcon.src = 'bootstrap-icons/symmetry-vertical.svg';
    flipIcon.onload = function () {
        flipIconImage = flipIcon;
        markForRedraw();
    };

    const rotateIcon = new Image();
    rotateIcon.src = 'bootstrap-icons/arrow-clockwise.svg';
    rotateIcon.onload = function () {
        rotateIconImage = rotateIcon;
        markForRedraw();
    };

    const scaleYIcon = new Image();
    scaleYIcon.src = 'bootstrap-icons/arrows-vertical.svg';
    scaleYIcon.onload = function () {
        scaleYIconImage = scaleYIcon;
        markForRedraw();
    };

    const scaleXIcon = new Image();
    scaleXIcon.src = 'bootstrap-icons/arrows.svg';
    scaleXIcon.onload = function () {
        scaleXIconImage = scaleXIcon;
        markForRedraw();
    };
}
