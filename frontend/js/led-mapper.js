/**
 * LED Visual Mapper - 2D Webcam-based LED position detection
 * Maps physical LED positions to canvas coordinates using webcam
 */

import { getSocket, isSocketConnected, showToast } from './common.js';

// ==================== GLOBAL STATE ======================================

let currentMapperStep = 1;
let mapperModal = null;
let ledMapper = null;
let calibrationManager = null;
let ledDetector = null;
let mappingSession = null;

const mapperConfig = {
    artnetIP: null,
    universe: 0,
    colorType: 'rgb',
    ledCount: 0,
    startAddress: 1,
    cameraId: null
};

// ==================== LED MAPPER CLASS ====================

class LEDMapper {
    constructor() {
        this.videoElement = null;
        this.stream = null;
        this.isActive = false;
    }
    
    async initCamera(deviceId = null) {
        try {
            const constraints = {
                video: {
                    deviceId: deviceId ? {exact: deviceId} : undefined,
                    width: {ideal: 1920},
                    height: {ideal: 1080},
                    facingMode: 'environment'
                }
            };
            
            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            this.videoElement = document.createElement('video');
            this.videoElement.srcObject = this.stream;
            await this.videoElement.play();
            
            this.isActive = true;
            return true;
        } catch (error) {
            console.error('Camera access failed:', error);
            showToast('Webcam nicht verfügbar', 'error');
            return false;
        }
    }
    
    async listCameras() {
        const devices = await navigator.mediaDevices.enumerateDevices();
        return devices.filter(device => device.kind === 'videoinput');
    }
    
    attachToVideo(videoElement) {
        if (this.stream && videoElement) {
            videoElement.srcObject = this.stream;
            videoElement.play();
        }
    }
    
    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
            this.isActive = false;
        }
    }
}

// ==================== CALIBRATION MANAGER ====================

class CalibrationManager {
    constructor() {
        this.referencePoints = []; // Canvas coordinates
        this.cameraPoints = [];    // Webcam pixel coordinates
        this.transformMatrix = null;
        this.calibrationRect = null; // {x, y, width, height} in camera pixels
    }
    
    addCalibrationPoint(canvasX, canvasY, cameraX, cameraY) {
        this.referencePoints.push({x: canvasX, y: canvasY});
        this.cameraPoints.push({x: cameraX, y: cameraY});
    }
    
    isComplete() {
        return this.referencePoints.length >= 4;
    }
    
    calculateTransform() {
        if (this.referencePoints.length < 4) {
            throw new Error('Need at least 4 calibration points');
        }
        
        console.log('=== Calculating Calibration Transform ===');
        console.log('Camera points (webcam pixels):');
        this.cameraPoints.forEach((p, i) => 
            console.log(`  ${i+1}. (${p.x.toFixed(1)}, ${p.y.toFixed(1)})`));
        
        // Calculate bounds of calibration region
        const calMinX = Math.min(...this.cameraPoints.map(p => p.x));
        const calMaxX = Math.max(...this.cameraPoints.map(p => p.x));
        const calMinY = Math.min(...this.cameraPoints.map(p => p.y));
        const calMaxY = Math.max(...this.cameraPoints.map(p => p.y));
        console.log(`Camera calibration region: (${calMinX.toFixed(1)}, ${calMinY.toFixed(1)}) to (${calMaxX.toFixed(1)}, ${calMaxY.toFixed(1)})`);
        console.log(`  Width: ${(calMaxX - calMinX).toFixed(1)}px, Height: ${(calMaxY - calMinY).toFixed(1)}px`);
        
        console.log('Canvas points (output coordinates):');
        this.referencePoints.forEach((p, i) => 
            console.log(`  ${i+1}. (${p.x.toFixed(1)}, ${p.y.toFixed(1)})`));
        
        // Compute 2D affine transform using least squares
        // This maps camera coordinates to canvas coordinates
        try {
            this.transformMatrix = this._computeAffineTransform(
                this.cameraPoints,
                this.referencePoints
            );
            
            console.log('Transform matrix:', this.transformMatrix);
            console.log('  x\' = ' + this.transformMatrix.a.toFixed(4) + '*x + ' + 
                                      this.transformMatrix.b.toFixed(4) + '*y + ' + 
                                      this.transformMatrix.c.toFixed(2));
            console.log('  y\' = ' + this.transformMatrix.d.toFixed(4) + '*x + ' + 
                                      this.transformMatrix.e.toFixed(4) + '*y + ' + 
                                      this.transformMatrix.f.toFixed(2));
            
            // Verify transform with all calibration points
            console.log('Verification (camera → canvas):');
            for (let i = 0; i < this.cameraPoints.length; i++) {
                const test = this.mapCameraToCanvas(this.cameraPoints[i].x, this.cameraPoints[i].y);
                const expected = this.referencePoints[i];
                const errorX = Math.abs(test.x - expected.x);
                const errorY = Math.abs(test.y - expected.y);
                console.log(`  ${i+1}. (${this.cameraPoints[i].x.toFixed(1)}, ${this.cameraPoints[i].y.toFixed(1)}) → ` +
                           `(${test.x.toFixed(1)}, ${test.y.toFixed(1)}) ` +
                           `[expected: (${expected.x}, ${expected.y}), error: ${errorX.toFixed(1)}, ${errorY.toFixed(1)}]`);
            }
            console.log('========================================');
            
        } catch (e) {
            console.error('Failed to compute transform:', e);
            throw e;
        }
    }
    
    mapCameraToCanvas(cameraX, cameraY) {
        if (!this.transformMatrix) {
            throw new Error('Calibration not complete');
        }
        
        const m = this.transformMatrix;
        const x = m.a * cameraX + m.b * cameraY + m.c;
        const y = m.d * cameraX + m.e * cameraY + m.f;
        
        // Validate output (detect extreme values)
        if (!isFinite(x) || !isFinite(y)) {
            console.error('Transform produced non-finite coordinates!');
            console.error('  Input: camera(', cameraX, ',', cameraY, ')');
            console.error('  Output: canvas(', x, ',', y, ')');
            console.error('  Transform matrix:', m);
            throw new Error('Transform produced invalid coordinates (non-finite)');
        }
        
        if (Math.abs(x) > 100000 || Math.abs(y) > 100000) {
            console.warn('Transform produced very large coordinates (possible error):');
            console.warn('  Input: camera(', cameraX, ',', cameraY, ')');
            console.warn('  Output: canvas(', x, ',', y, ')');
            console.warn('  Transform matrix:', m);
            // Don't throw, just warn - might be valid in some cases
        }
        
        return {x, y};
    }
    
    _computeAffineTransform(srcPoints, dstPoints) {
        // Solve for 2D affine transform using least squares
        // x' = a*x + b*y + c
        // y' = d*x + e*y + f
        
        const n = srcPoints.length;
        
        // Build matrices for normal equations
        // For X transform: [a b c]^T
        let A11 = 0, A12 = 0, A13 = 0;
        let A21 = 0, A22 = 0, A23 = 0;
        let A31 = 0, A32 = 0, A33 = n;
        let B1 = 0, B2 = 0, B3 = 0;
        
        // For Y transform: [d e f]^T
        let C1 = 0, C2 = 0, C3 = 0;
        
        for (let i = 0; i < n; i++) {
            const x = srcPoints[i].x;
            const y = srcPoints[i].y;
            const xp = dstPoints[i].x;
            const yp = dstPoints[i].y;
            
            // Build A matrix (same for both X and Y)
            A11 += x * x;
            A12 += x * y;
            A13 += x;
            A21 += x * y;
            A22 += y * y;
            A23 += y;
            A31 += x;
            A32 += y;
            
            // Build B vector (for X transform)
            B1 += x * xp;
            B2 += y * xp;
            B3 += xp;
            
            // Build C vector (for Y transform)
            C1 += x * yp;
            C2 += y * yp;
            C3 += yp;
        }
        
        // Solve using Cramer's rule
        // det(A) = A11(A22*A33 - A23*A32) - A12(A21*A33 - A23*A31) + A13(A21*A32 - A22*A31)
        const det = A11 * (A22 * A33 - A23 * A32) -
                    A12 * (A21 * A33 - A23 * A31) +
                    A13 * (A21 * A32 - A22 * A31);
        
        if (Math.abs(det) < 1e-10) {
            console.error('Degenerate calibration points!');
            console.error('Source points:', srcPoints);
            console.error('Dest points:', dstPoints);
            throw new Error('Cannot compute transform - points are degenerate');
        }
        
        // Solve for [a, b, c] using Cramer's rule
        const det_a = B1 * (A22 * A33 - A23 * A32) -
                      A12 * (B2 * A33 - A23 * B3) +
                      A13 * (B2 * A32 - A22 * B3);
        const a = det_a / det;
        
        const det_b = A11 * (B2 * A33 - A23 * B3) -
                      B1 * (A21 * A33 - A23 * A31) +
                      A13 * (A21 * B3 - B2 * A31);
        const b = det_b / det;
        
        const det_c = A11 * (A22 * B3 - B2 * A32) -
                      A12 * (A21 * B3 - B2 * A31) +
                      B1 * (A21 * A32 - A22 * A31);
        const c = det_c / det;
        
        // Solve for [d, e, f] using Cramer's rule (same A matrix, different RHS)
        const det_d = C1 * (A22 * A33 - A23 * A32) -
                      A12 * (C2 * A33 - A23 * C3) +
                      A13 * (C2 * A32 - A22 * C3);
        const d = det_d / det;
        
        const det_e = A11 * (C2 * A33 - A23 * C3) -
                      C1 * (A21 * A33 - A23 * A31) +
                      A13 * (A21 * C3 - C2 * A31);
        const e = det_e / det;
        
        const det_f = A11 * (A22 * C3 - C2 * A32) -
                      A12 * (A21 * C3 - C2 * A31) +
                      C1 * (A21 * A32 - A22 * A31);
        const f = det_f / det;
        
        return {a, b, c, d, e, f};
    }
    
    reset() {
        this.referencePoints = [];
        this.cameraPoints = [];
        this.transformMatrix = null;
        this.calibrationRect = null; // Also clear calibration rectangle
    }
}

// ==================== LED DETECTOR ====================

class LEDDetector {
    constructor() {
        this.detectionCanvas = document.createElement('canvas');
        this.ctx = this.detectionCanvas.getContext('2d', {willReadFrequently: true});
        this.detectionThreshold = 60; // Brightness CHANGE threshold (0-255)
        this.minBlobSize = 3;
        this.regionOfInterest = null; // {x, y, width, height} - restrict detection to this area
        this.baselineFrame = null; // Store baseline (LED off) for differential detection
        this.useDifferentialDetection = true; // Enable differential mode by default
        this.useGrayscale = true; // Convert to grayscale for cleaner detection
        this.averageFrames = 3; // Average multiple frames to reduce noise
        
        // Temporal filtering - smooth positions across detections
        this.temporalFilterSize = 5; // Number of positions to track
        this.positionHistory = []; // Recent position detections
        
        // ROI Auto-Refinement - shrink search area after first LED detected
        this.useAutoRefinement = true; // Enable dynamic ROI shrinking
        this.refinedROISize = 150; // Size of refined search window (pixels)
        this.initialROI = null; // Store original calibration ROI
        this.lastDetectedPosition = null; // Last successful detection position
    }
    
    resetTemporalFilter() {
        // Clear position history when starting new LED detection
        this.positionHistory = [];
    }
    
    resetROIRefinement() {
        // Reset to initial calibration ROI (call when starting new mapping sequence)
        if (this.initialROI) {
            this.regionOfInterest = {...this.initialROI};
            console.log('🔄 ROI reset to initial calibration area');
        }
        this.lastDetectedPosition = null;
    }
    
    setVideoSource(videoElement) {
        this.detectionCanvas.width = videoElement.videoWidth || 1920;
        this.detectionCanvas.height = videoElement.videoHeight || 1080;
    }
    
    setRegionOfInterest(rect) {
        // Only search for LEDs in this rectangle
        this.regionOfInterest = rect ? {...rect} : null;
        this.initialROI = rect ? {...rect} : null; // Store for auto-refinement reset
        console.log('🔍 LED detection ROI set:', this.regionOfInterest);
    }
    
    async captureBaseline(videoElement) {
        // Capture current frame as baseline (LEDs should be OFF)
        console.log('📸 Capturing baseline frame (LEDs OFF)...');
        
        // Capture multiple frames and average them
        const frames = [];
        for (let i = 0; i < this.averageFrames; i++) {
            await this._waitFrame();
            this.ctx.drawImage(videoElement, 0, 0, this.detectionCanvas.width, this.detectionCanvas.height);
            const frameData = this.ctx.getImageData(0, 0, this.detectionCanvas.width, this.detectionCanvas.height);
            frames.push(this._toGrayscale(frameData.data));
            if (i < this.averageFrames - 1) await this._sleep(30);
        }
        
        // Average frames to reduce noise
        this.baselineFrame = this._averageGrayscaleFrames(frames);
        
        // ========== ADAPTIVE THRESHOLD ==========
        // Measure ambient brightness and adjust detection threshold
        const avgBrightness = this._calculateAverageBrightness(this.baselineFrame);
        
        // Adjust threshold based on lighting conditions
        let oldThreshold = this.detectionThreshold;
        if (avgBrightness < 30) {
            // Dark room - lower threshold (more sensitive)
            this.detectionThreshold = 30;
            console.log('🌙 Dark environment detected - using sensitive threshold');
        } else if (avgBrightness > 150) {
            // Bright room - higher threshold (less sensitive to noise)
            this.detectionThreshold = 100;
            console.log('☀️ Bright environment detected - using robust threshold');
        } else {
            // Normal lighting
            this.detectionThreshold = 60;
            console.log('💡 Normal lighting detected - using standard threshold');
        }
        
        console.log(`✅ Baseline captured | Ambient: ${avgBrightness.toFixed(1)} | Threshold: ${oldThreshold} → ${this.detectionThreshold}`);
    }
    
    _calculateAverageBrightness(grayscalePixels) {
        // Calculate average brightness of entire frame (or ROI if set)
        let sum = 0;
        let count = 0;
        
        if (this.regionOfInterest) {
            // Only sample within ROI
            const roi = this.regionOfInterest;
            const startX = Math.max(0, Math.floor(roi.x));
            const startY = Math.max(0, Math.floor(roi.y));
            const endX = Math.min(this.detectionCanvas.width, Math.floor(roi.x + roi.width));
            const endY = Math.min(this.detectionCanvas.height, Math.floor(roi.y + roi.height));
            
            for (let y = startY; y < endY; y++) {
                for (let x = startX; x < endX; x++) {
                    const i = y * this.detectionCanvas.width + x;
                    sum += grayscalePixels[i];
                    count++;
                }
            }
        } else {
            // Entire frame
            for (let i = 0; i < grayscalePixels.length; i++) {
                sum += grayscalePixels[i];
            }
            count = grayscalePixels.length;
        }
        
        return sum / count;
    }
    
    _toGrayscale(rgbaPixels) {
        // Convert RGBA to single-channel grayscale
        const len = rgbaPixels.length / 4;
        const gray = new Uint8ClampedArray(len);
        for (let i = 0; i < len; i++) {
            const idx = i * 4;
            // Simple average: (R+G+B)/3
            gray[i] = (rgbaPixels[idx] + rgbaPixels[idx+1] + rgbaPixels[idx+2]) / 3;
        }
        return gray;
    }
    
    _averageGrayscaleFrames(frames) {
        // Average multiple grayscale frames
        const len = frames[0].length;
        const averaged = new Uint8ClampedArray(len);
        for (let i = 0; i < len; i++) {
            let sum = 0;
            for (let f = 0; f < frames.length; f++) {
                sum += frames[f][i];
            }
            averaged[i] = sum / frames.length;
        }
        return averaged;
    }
    
    _sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    _waitFrame() {
        return new Promise(resolve => requestAnimationFrame(resolve));
    }
    
    async detectLED(videoElement, timeout = 2000) {
        const startTime = Date.now();
        
        // Reset temporal filter for new LED
        this.resetTemporalFilter();
        
        // Use differential detection if baseline is available
        const useDiff = this.useDifferentialDetection && this.baselineFrame;
        
        if (useDiff) {
            console.log('🔍 Using DIFFERENTIAL detection (comparing to baseline)');
        } else {
            console.log('⚠️ Using ABSOLUTE detection (no baseline)');
        }
        
        // Capture and average frames for noise reduction
        const frames = [];
        while (Date.now() - startTime < timeout) {
            await this._waitFrame();
            this.ctx.drawImage(videoElement, 0, 0, this.detectionCanvas.width, this.detectionCanvas.height);
            const frameData = this.ctx.getImageData(0, 0, this.detectionCanvas.width, this.detectionCanvas.height);
            frames.push(this._toGrayscale(frameData.data));
            
            // Keep only last N frames
            if (frames.length > this.averageFrames) frames.shift();
            
            // Only try detection once we have enough frames
            if (frames.length >= this.averageFrames) {
                const avgGray = this._averageGrayscaleFrames(frames);
                
                const position = useDiff ? 
                    this._analyzeDifferential(avgGray) : 
                    this._analyzeAbsolute(avgGray);
                
                if (position) {
                    // Success! Apply ROI auto-refinement for next LED
                    if (this.useAutoRefinement) {
                        this._refineROIAroundPosition(position.x, position.y);
                    }
                    this.lastDetectedPosition = {x: position.x, y: position.y};
                    return position; // {x, y, confidence}
                }
            }
            
            await this._sleep(30); // Small delay
        }
        
        return null; // Detection failed
    }
    
    _analyzeDifferential(currentGray) {
        // DIFFERENTIAL with GRAYSCALE: Find what CHANGED compared to baseline
        const baselineGray = this.baselineFrame;
        
        // Determine search region
        let searchX = 0, searchY = 0;
        let searchWidth = this.detectionCanvas.width;
        let searchHeight = this.detectionCanvas.height;
        
        if (this.regionOfInterest) {
            searchX = Math.max(0, Math.floor(this.regionOfInterest.x));
            searchY = Math.max(0, Math.floor(this.regionOfInterest.y));
            searchWidth = Math.min(this.detectionCanvas.width - searchX, Math.ceil(this.regionOfInterest.width));
            searchHeight = Math.min(this.detectionCanvas.height - searchY, Math.ceil(this.regionOfInterest.height));
        }
        
        let maxChangeX = -1;
        let maxChangeY = -1;
        let maxChange = 0;
        
        // Find pixel with BIGGEST BRIGHTNESS INCREASE (grayscale)
        const endY = searchY + searchHeight;
        const endX = searchX + searchWidth;
        
        for (let y = searchY; y < endY; y++) {
            for (let x = searchX; x < endX; x++) {
                const i = y * this.detectionCanvas.width + x;
                const change = currentGray[i] - baselineGray[i];
                
                if (change > maxChange && change > this.detectionThreshold) {
                    maxChange = change;
                    maxChangeX = x;
                    maxChangeY = y;
                }
            }
        }
        
        if (maxChange > this.detectionThreshold) {
            if (window.DEBUG) {
                console.log(`  💡 Brightest change at (${maxChangeX}, ${maxChangeY}) = +${maxChange.toFixed(1)}`);
                if (this.regionOfInterest) {
                    console.log(`  📐 ROI: x=${this.regionOfInterest.x}, y=${this.regionOfInterest.y}, w=${this.regionOfInterest.width}, h=${this.regionOfInterest.height}`);
                    console.log(`  📍 Brightest pixel offset from ROI origin: (${(maxChangeX - this.regionOfInterest.x).toFixed(1)}, ${(maxChangeY - this.regionOfInterest.y).toFixed(1)})`);
                }
            }
            const position = this._refineGrayBlobCenter(currentGray, baselineGray, maxChangeX, maxChangeY, true);
            
            // Apply temporal filtering for smoother results
            const filteredPosition = this._applyTemporalFilter(position.x, position.y);
            
            if (window.DEBUG) {
                console.log(`  📊 After temporal filter: (${position.x.toFixed(1)}, ${position.y.toFixed(1)}) → (${filteredPosition.x.toFixed(1)}, ${filteredPosition.y.toFixed(1)})`);
            }
            
            return {
                x: filteredPosition.x,
                y: filteredPosition.y,
                confidence: Math.min(maxChange / 200, 1.0)
            };
        }
        
        return null;
    }
    
    _analyzeAbsolute(grayscalePixels) {
        // ABSOLUTE with GRAYSCALE: Find brightest spot
        // Determine search region
        let searchX = 0, searchY = 0;
        let searchWidth = this.detectionCanvas.width;
        let searchHeight = this.detectionCanvas.height;
        
        if (this.regionOfInterest) {
            searchX = Math.max(0, Math.floor(this.regionOfInterest.x));
            searchY = Math.max(0, Math.floor(this.regionOfInterest.y));
            searchWidth = Math.min(this.detectionCanvas.width - searchX, Math.ceil(this.regionOfInterest.width));
            searchHeight = Math.min(this.detectionCanvas.height - searchY, Math.ceil(this.regionOfInterest.height));
        }
        
        let brightestX = -1;
        let brightestY = -1;
        let maxBrightness = 0;
        
        // Find brightest pixel
        const endY = searchY + searchHeight;
        const endX = searchX + searchWidth;
        
        for (let y = searchY; y < endY; y++) {
            for (let x = searchX; x < endX; x++) {
                const i = y * this.detectionCanvas.width + x;
                const brightness = grayscalePixels[i];
                
                if (brightness > maxBrightness && brightness > 200) {
                    maxBrightness = brightness;
                    brightestX = x;
                    brightestY = y;
                }
            }
        }
        
        if (maxBrightness > 200) {
            const position = this._refineGrayBlobCenter(grayscalePixels, null, brightestX, brightestY, false);
            
            // Apply temporal filtering for smoother results
            const filteredPosition = this._applyTemporalFilter(position.x, position.y);
            
            return {
                x: filteredPosition.x,
                y: filteredPosition.y,
                confidence: maxBrightness / 255
            };
        }
        
        return null;
    }
    
    _refineGrayBlobCenter(currentGray, baselineGray, seedX, seedY, useDifferential) {
        // ========== IMPROVED: WINDOW-BASED WEIGHTED CENTROID ==========
        // Instead of flood-fill (which can expand asymmetrically),
        // scan a fixed window and calculate weighted average
        
        const windowSize = 20; // Scan 20x20 pixel window around seed
        const halfWindow = Math.floor(windowSize / 2);
        
        let sumX = 0, sumY = 0, totalWeight = 0;
        let minX = Math.max(0, seedX - halfWindow);
        let maxX = Math.min(this.detectionCanvas.width - 1, seedX + halfWindow);
        let minY = Math.max(0, seedY - halfWindow);
        let maxY = Math.min(this.detectionCanvas.height - 1, seedY + halfWindow);
        
        // Scan window and calculate weighted centroid
        for (let y = minY; y <= maxY; y++) {
            for (let x = minX; x <= maxX; x++) {
                const i = y * this.detectionCanvas.width + x;
                
                let weight = 0;
                
                if (useDifferential && baselineGray) {
                    const change = currentGray[i] - baselineGray[i];
                    if (change > this.detectionThreshold) {
                        weight = change; // Use brightness change as weight
                    }
                } else {
                    const brightness = currentGray[i];
                    if (brightness > 200) {
                        weight = brightness; // Use absolute brightness as weight
                    }
                }
                
                if (weight > 0) {
                    sumX += x * weight;
                    sumY += y * weight;
                    totalWeight += weight;
                }
            }
        }
        
        if (totalWeight === 0) {
            // No valid pixels found, return seed position
            return {x: seedX, y: seedY};
        }
        
        // Weighted centroid (center of mass)
        const centerX = sumX / totalWeight;
        const centerY = sumY / totalWeight;
        
        if (window.DEBUG) {
            console.log(`  🎯 Window-based centroid: seed(${seedX}, ${seedY}) → center(${centerX.toFixed(1)}, ${centerY.toFixed(1)})`);
            console.log(`  📦 Window bounds: x=[${minX},${maxX}], y=[${minY},${maxY}], pixels=${totalWeight > 0 ? 'found' : 'NONE'}`);
            console.log(`  ⬅️➡️ Shift from seed: dx=${(centerX - seedX).toFixed(1)}, dy=${(centerY - seedY).toFixed(1)}`);
        }
        
        return {
            x: centerX,
            y: centerY
        };
    }
    
    _applyTemporalFilter(x, y) {
        // ========== TEMPORAL FILTERING ==========
        // Smooth position across multiple detections using median filter
        // This reduces jitter caused by webcam noise
        
        // Add new position to history
        this.positionHistory.push({x, y});
        
        // Keep only last N positions
        if (this.positionHistory.length > this.temporalFilterSize) {
            this.positionHistory.shift();
        }
        
        // Need at least 3 samples for median
        if (this.positionHistory.length < 3) {
            return {x, y}; // Not enough data yet, return raw position
        }
        
        // Calculate median X and Y separately
        const xValues = this.positionHistory.map(p => p.x).sort((a, b) => a - b);
        const yValues = this.positionHistory.map(p => p.y).sort((a, b) => a - b);
        
        const medianX = this._median(xValues);
        const medianY = this._median(yValues);
        
        // Optional: Calculate jitter for debugging
        const jitterX = Math.abs(x - medianX);
        const jitterY = Math.abs(y - medianY);
        const totalJitter = Math.sqrt(jitterX * jitterX + jitterY * jitterY);
        
        if (totalJitter > 2) {
            console.log(`  🎯 Temporal filter: jitter ${totalJitter.toFixed(1)}px reduced`);
        }
        
        return {
            x: medianX,
            y: medianY
        };
    }
    
    _median(values) {
        // Calculate median of sorted array
        const mid = Math.floor(values.length / 2);
        if (values.length % 2 === 0) {
            return (values[mid - 1] + values[mid]) / 2;
        } else {
            return values[mid];
        }
    }
    
    _refineROIAroundPosition(x, y) {
        // ========== ROI AUTO-REFINEMENT ==========
        // Create smaller search window around detected LED for faster next detection
        
        if (!this.initialROI) {
            return; // No initial ROI set, can't refine
        }
        
        const halfSize = this.refinedROISize / 2;
        
        // Create refined ROI centered on detected position
        let refinedROI = {
            x: x - halfSize,
            y: y - halfSize,
            width: this.refinedROISize,
            height: this.refinedROISize
        };
        
        // Clamp to initial calibration ROI boundaries
        const initialROI = this.initialROI;
        refinedROI.x = Math.max(initialROI.x, refinedROI.x);
        refinedROI.y = Math.max(initialROI.y, refinedROI.y);
        
        const maxX = initialROI.x + initialROI.width;
        const maxY = initialROI.y + initialROI.height;
        
        if (refinedROI.x + refinedROI.width > maxX) {
            refinedROI.width = maxX - refinedROI.x;
        }
        if (refinedROI.y + refinedROI.height > maxY) {
            refinedROI.height = maxY - refinedROI.y;
        }
        
        // Calculate area reduction
        const initialArea = initialROI.width * initialROI.height;
        const refinedArea = refinedROI.width * refinedROI.height;
        const speedup = (initialArea / refinedArea).toFixed(1);
        
        this.regionOfInterest = refinedROI;
        
        console.log(`  🎯 ROI refined: ${Math.round(refinedROI.width)}×${Math.round(refinedROI.height)}px (${speedup}x faster search)`);
    }
}

// ==================== GEOMETRY UTILITIES ====================

/**
 * Normalize LED positions to smooth path and equalize spacing
 * Useful for LEDs on PCB strips with consistent physical spacing
 */
function normalizeGeometry(positions, options = {}) {
    const {
        smoothingWindow = 5,      // Moving average window size
        equalizeSpacing = true,   // Make distances between LEDs consistent
        targetSpacing = null      // Target spacing (null = auto-calculate from average)
    } = options;
    
    if (positions.length < 3) {
        return positions; // Need at least 3 points
    }
    
    console.log(`📐 Normalizing ${positions.length} LED positions...`);
    
    // Step 1: Smooth positions using moving average
    const smoothed = smoothPath(positions, smoothingWindow);
    
    // Step 2: Optionally equalize spacing
    let normalized = smoothed;
    if (equalizeSpacing) {
        normalized = equalizePointSpacing(smoothed, targetSpacing);
    }
    
    // Calculate improvement metrics
    const originalSpacing = calculateSpacingVariance(positions);
    const normalizedSpacing = calculateSpacingVariance(normalized);
    const improvement = ((originalSpacing - normalizedSpacing) / originalSpacing * 100).toFixed(1);
    
    console.log(`✅ Geometry normalized | Spacing variance: ${originalSpacing.toFixed(2)} → ${normalizedSpacing.toFixed(2)} (${improvement}% better)`);
    
    return normalized;
}

/**
 * Smooth path using moving average filter
 */
function smoothPath(positions, windowSize) {
    if (windowSize < 2) return positions;
    
    const smoothed = [];
    const halfWindow = Math.floor(windowSize / 2);
    
    for (let i = 0; i < positions.length; i++) {
        let sumX = 0, sumY = 0, count = 0;
        
        // Average within window
        for (let j = Math.max(0, i - halfWindow); j <= Math.min(positions.length - 1, i + halfWindow); j++) {
            sumX += positions[j].x;
            sumY += positions[j].y;
            count++;
        }
        
        smoothed.push({
            x: sumX / count,
            y: sumY / count
        });
    }
    
    return smoothed;
}

/**
 * Redistribute points along path with equal spacing
 */
function equalizePointSpacing(positions, targetSpacing = null) {
    if (positions.length < 2) return positions;
    
    // Calculate cumulative distances along path
    const distances = [0];
    for (let i = 1; i < positions.length; i++) {
        const dx = positions[i].x - positions[i-1].x;
        const dy = positions[i].y - positions[i-1].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        distances.push(distances[i-1] + dist);
    }
    
    const totalLength = distances[distances.length - 1];
    
    // Calculate target spacing
    if (targetSpacing === null) {
        targetSpacing = totalLength / (positions.length - 1);
    }
    
    // Redistribute points with equal spacing
    const equalized = [positions[0]]; // Keep first point
    
    for (let i = 1; i < positions.length - 1; i++) {
        const targetDist = i * targetSpacing;
        
        // Find segment containing this distance
        let segmentIdx = 0;
        for (let j = 0; j < distances.length - 1; j++) {
            if (distances[j] <= targetDist && targetDist <= distances[j + 1]) {
                segmentIdx = j;
                break;
            }
        }
        
        // Interpolate position within segment
        const t = (targetDist - distances[segmentIdx]) / (distances[segmentIdx + 1] - distances[segmentIdx]);
        const p1 = positions[segmentIdx];
        const p2 = positions[segmentIdx + 1];
        
        equalized.push({
            x: p1.x + t * (p2.x - p1.x),
            y: p1.y + t * (p2.y - p1.y)
        });
    }
    
    equalized.push(positions[positions.length - 1]); // Keep last point
    
    return equalized;
}

/**
 * Calculate variance in spacing between consecutive points
 * Lower = more consistent spacing
 */
function calculateSpacingVariance(positions) {
    if (positions.length < 2) return 0;
    
    const spacings = [];
    for (let i = 1; i < positions.length; i++) {
        const dx = positions[i].x - positions[i-1].x;
        const dy = positions[i].y - positions[i-1].y;
        spacings.push(Math.sqrt(dx * dx + dy * dy));
    }
    
    const avgSpacing = spacings.reduce((a, b) => a + b, 0) / spacings.length;
    const variance = spacings.reduce((sum, s) => sum + Math.pow(s - avgSpacing, 2), 0) / spacings.length;
    
    return Math.sqrt(variance); // Return standard deviation
}

// ==================== LED DETECTOR (LEGACY) ====================

class LEDDetectorOld {
    // OLD METHODS - kept for reference/fallback (NOT USED)
    _analyzeDifferentialFrame(videoElement) {
        // DIFFERENTIAL DETECTION: Find what CHANGED compared to baseline
        this.ctx.drawImage(videoElement, 0, 0, this.detectionCanvas.width, this.detectionCanvas.height);
        
        const currentFrame = this.ctx.getImageData(0, 0, this.detectionCanvas.width, this.detectionCanvas.height);
        const currentPixels = currentFrame.data;
        const baselinePixels = this.baselineFrame.data;
        
        // Determine search region
        let searchX = 0, searchY = 0;
        let searchWidth = this.detectionCanvas.width;
        let searchHeight = this.detectionCanvas.height;
        
        if (this.regionOfInterest) {
            searchX = Math.max(0, Math.floor(this.regionOfInterest.x));
            searchY = Math.max(0, Math.floor(this.regionOfInterest.y));
            searchWidth = Math.min(this.detectionCanvas.width - searchX, Math.ceil(this.regionOfInterest.width));
            searchHeight = Math.min(this.detectionCanvas.height - searchY, Math.ceil(this.regionOfInterest.height));
        }
        
        let maxChangeX = -1;
        let maxChangeY = -1;
        let maxChange = 0;
        
        // Find pixel with BIGGEST BRIGHTNESS INCREASE
        const endY = searchY + searchHeight;
        const endX = searchX + searchWidth;
        
        for (let y = searchY; y < endY; y++) {
            for (let x = searchX; x < endX; x++) {
                const i = (y * this.detectionCanvas.width + x) * 4;
                
                const currentBrightness = (currentPixels[i] + currentPixels[i+1] + currentPixels[i+2]) / 3;
                const baselineBrightness = (baselinePixels[i] + baselinePixels[i+1] + baselinePixels[i+2]) / 3;
                
                const brightnessChange = currentBrightness - baselineBrightness;
                
                if (brightnessChange > maxChange && brightnessChange > this.detectionThreshold) {
                    maxChange = brightnessChange;
                    maxChangeX = x;
                    maxChangeY = y;
                }
            }
        }
        
        if (maxChange > this.detectionThreshold) {
            if (window.DEBUG) console.log(`  💡 Detected brightness change: +${maxChange.toFixed(1)} at (${maxChangeX}, ${maxChangeY})`);
            const position = this._refineBlobCenter(currentPixels, baselinePixels, maxChangeX, maxChangeY);
            return {
                x: position.x,
                y: position.y,
                confidence: Math.min(maxChange / 200, 1.0) // Normalize to 0-1
            };
        }
        
        return null;
    }
    
    _analyzeAbsoluteFrame(videoElement) {
        // ABSOLUTE DETECTION: Find brightest spot (old method, fallback)
        this.ctx.drawImage(videoElement, 0, 0, this.detectionCanvas.width, this.detectionCanvas.height);
        
        // Determine search region (use ROI if set, otherwise entire frame)
        let searchX = 0;
        let searchY = 0;
        let searchWidth = this.detectionCanvas.width;
        let searchHeight = this.detectionCanvas.height;
        
        if (this.regionOfInterest) {
            searchX = Math.max(0, Math.floor(this.regionOfInterest.x));
            searchY = Math.max(0, Math.floor(this.regionOfInterest.y));
            searchWidth = Math.min(this.detectionCanvas.width - searchX, Math.ceil(this.regionOfInterest.width));
            searchHeight = Math.min(this.detectionCanvas.height - searchY, Math.ceil(this.regionOfInterest.height));
        }
        
        // Get pixel data
        const imageData = this.ctx.getImageData(
            0, 0, this.detectionCanvas.width, this.detectionCanvas.height
        );
        const pixels = imageData.data;
        
        let brightestX = -1;
        let brightestY = -1;
        let maxBrightness = 0;
        
        // Find brightest pixel WITHIN SEARCH REGION ONLY
        const endY = searchY + searchHeight;
        const endX = searchX + searchWidth;
        
        for (let y = searchY; y < endY; y++) {
            for (let x = searchX; x < endX; x++) {
                const i = (y * this.detectionCanvas.width + x) * 4;
                const brightness = (pixels[i] + pixels[i+1] + pixels[i+2]) / 3;
                
                if (brightness > maxBrightness && brightness > 200) {
                    maxBrightness = brightness;
                    brightestX = x;
                    brightestY = y;
                }
            }
        }
        
        if (maxBrightness > 200) {
            // Refine position using centroid of bright region
            const position = this._refineAbsoluteBlobCenter(pixels, brightestX, brightestY);
            return {
                x: position.x,
                y: position.y,
                confidence: maxBrightness / 255
            };
        }
        
        return null;
    }
    
    _refineBlobCenter(currentPixels, baselinePixels, seedX, seedY) {
        // Refine center using WEIGHTED DIFFERENTIAL method (legacy, fallback only)
        const visited = new Set();
        const queue = [{x: seedX, y: seedY}];
        let sumX = 0, sumY = 0, totalWeight = 0;
        
        while (queue.length > 0) {
            const {x, y} = queue.shift();
            const key = `${x},${y}`;
            
            if (visited.has(key)) continue;
            visited.add(key);
            
            if (x < 0 || x >= this.detectionCanvas.width || 
                y < 0 || y >= this.detectionCanvas.height) continue;
            
            const i = (y * this.detectionCanvas.width + x) * 4;
            const currentBrightness = (currentPixels[i] + currentPixels[i+1] + currentPixels[i+2]) / 3;
            const baselineBrightness = (baselinePixels[i] + baselinePixels[i+1] + baselinePixels[i+2]) / 3;
            const change = currentBrightness - baselineBrightness;
            
            if (change > this.detectionThreshold) {
                // Brightness-weighted position
                sumX += x * change;
                sumY += y * change;
                totalWeight += change;
                
                // Add neighbors (limit blob size)
                if (totalWeight < 20000) {
                    queue.push({x: x+1, y});
                    queue.push({x: x-1, y});
                    queue.push({x, y: y+1});
                    queue.push({x, y: y-1});
                }
            }
        }
        
        if (totalWeight === 0) {
            return {x: seedX, y: seedY};
        }
        
        return {
            x: sumX / totalWeight,
            y: sumY / totalWeight
        };
    }
    
    _refineAbsoluteBlobCenter(pixels, seedX, seedY) {
        // Refine center using WEIGHTED centroid (old RGBA approach, fallback only)
        const visited = new Set();
        const queue = [{x: seedX, y: seedY}];
        let sumX = 0, sumY = 0, totalWeight = 0;
        
        while (queue.length > 0) {
            const {x, y} = queue.shift();
            const key = `${x},${y}`;
            
            if (visited.has(key)) continue;
            visited.add(key);
            
            if (x < 0 || x >= this.detectionCanvas.width || 
                y < 0 || y >= this.detectionCanvas.height) continue;
            
            const i = (y * this.detectionCanvas.width + x) * 4;
            const brightness = (pixels[i] + pixels[i+1] + pixels[i+2]) / 3;
            
            if (brightness > 200) {
                // Brightness-weighted position (center of mass)
                sumX += x * brightness;
                sumY += y * brightness;
                totalWeight += brightness;
                
                // Add neighbors (limit blob size)
                if (totalWeight < 20000) { // Use weight as limiter
                    queue.push({x: x+1, y});
                    queue.push({x: x-1, y});
                    queue.push({x, y: y+1});
                    queue.push({x, y: y-1});
                }
            }
        }
        
        if (totalWeight === 0) {
            return {x: seedX, y: seedY};
        }
        
        return {
            x: sumX / totalWeight,
            y: sumY / totalWeight
        };
    }
    
    _waitFrame() {
        return new Promise(resolve => requestAnimationFrame(resolve));
    }
}

// ==================== MAPPING SESSION ====================

class MappingSession {
    constructor(config, calibration, detector, videoElement) {
        this.config = config;
        this.calibration = calibration;
        this.detector = detector;
        this.videoElement = videoElement;
        this.mappedPositions = new Map();
        this.failedLEDs = [];
        this.isPaused = false;
        this.taskId = null;
        this.socket = null;
        
        // Bind event handlers
        this.handleLedActive = this.handleLedActive.bind(this);
        this.handleSequenceComplete = this.handleSequenceComplete.bind(this);
        this.handleError = this.handleError.bind(this);
    }
    
    async startMappingSequence() {
        try {
            showToast(`Starting mapping of ${this.config.ledCount} LEDs...`, 'info');
            
            // Reset ROI refinement to start fresh
            if (window.DEBUG) console.log('Resetting ROI refinement...');
            this.detector.resetROIRefinement();
            
            // Set detection region to calibration rectangle (CRITICAL FIX!)
            if (this.calibration.calibrationRect) {
                this.detector.setRegionOfInterest(this.calibration.calibrationRect);
                if (window.DEBUG) console.log('🎯 LED detection restricted to calibration rectangle:', this.calibration.calibrationRect);
            } else {
                console.warn('⚠️ No calibration rectangle set - will search entire camera view!');
            }
            
            // CAPTURE BASELINE FRAME (LEDs OFF) for differential detection
            console.log('Starting baseline capture...');
            showToast('📸 Capturing baseline (LEDs OFF)...', 'info', 2000);
            await this._sleep(500); // Wait for video to stabilize
            
            if (window.DEBUG) console.log('Calling captureBaseline...');
            await this.detector.captureBaseline(this.videoElement);
            if (window.DEBUG) console.log('Baseline captured successfully');
            
            await this._sleep(500); // Extra pause to ensure baseline is clean
            
            // Get socket from common.js and verify it's connected
            if (window.DEBUG) console.log('Getting WebSocket...');
            this.socket = getSocket();
            if (!this.socket || !isSocketConnected()) {
                showToast('WebSocket not connected. Please wait for connection...', 'error');
                return;
            }
            if (window.DEBUG) console.log('WebSocket connected');
            
            // Start backend sequence
            if (window.DEBUG) console.log('Starting backend sequence...');
            const response = await fetch('/api/mapper/start-sequence', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                artnet_ip: this.config.artnetIP,
                universe: this.config.universe,
                color_type: this.config.colorType,
                led_count: this.config.ledCount,
                start_address: this.config.startAddress,
                delay_ms: 800,
                use_broadcast: this.config.useBroadcast || false
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            showToast('Failed to start mapping: ' + data.error, 'error');
            return;
        }
        
        this.taskId = data.task_id;
        
        // Listen for LED activation events
        this.socket.on('mapper:led_active', this.handleLedActive);
        this.socket.on('mapper:sequence_complete', this.handleSequenceComplete);
        this.socket.on('mapper:error', this.handleError);
        
        console.log('✅ Mapping sequence started successfully!');
        
        } catch (error) {
            console.error('❌ Error starting mapping sequence:', error);
            showToast('Error starting mapping: ' + error.message, 'error');
        }
    }
    
    async handleLedActive(eventData) {
        if (!this.isPaused) {
            await this.captureLEDPosition(eventData.led_index, eventData.total);
        }
    }
    
    handleSequenceComplete() {
        this.finishMapping();
    }
    
    handleError(eventData) {
        showToast('Mapping error: ' + eventData.error, 'error');
    }
    
    cleanup() {
        // Remove event listeners
        if (this.socket) {
            this.socket.off('mapper:led_active', this.handleLedActive);
            this.socket.off('mapper:sequence_complete', this.handleSequenceComplete);
            this.socket.off('mapper:error', this.handleError);
        }
    }
    
    async captureLEDPosition(ledIndex, total) {
        // Update progress UI
        const progress = ((ledIndex + 1) / total) * 100;
        const progressBar = document.getElementById('mappingProgressBar');
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
            progressBar.innerHTML = `<strong>${ledIndex + 1} / ${total}</strong>`;
        }
        
        // Wait for LED to be fully lit (longer wait for differential detection)
        await this._sleep(300);
        
        // Detect LED in camera view
        const cameraPos = await this.detector.detectLED(this.videoElement, 1500);
        
        if (!cameraPos) {
            console.warn(`Failed to detect LED #${ledIndex + 1}`);
            this.failedLEDs.push(ledIndex);
            this._drawDetectionMarker(null, ledIndex, false);
            return;
        }
        
        if (window.DEBUG) {
            console.log(`📍 LED #${ledIndex + 1} FINAL camera position: (${cameraPos.x.toFixed(1)}, ${cameraPos.y.toFixed(1)}) confidence=${cameraPos.confidence.toFixed(2)}`);
        } else {
            console.log(`LED #${ledIndex + 1}: Camera pos (${cameraPos.x.toFixed(1)}, ${cameraPos.y.toFixed(1)})`);
        }
        
        // Draw visual marker showing where LED was detected
        this._drawDetectionMarker(cameraPos, ledIndex, true);
        
        // Check if LED is within calibration region
        const calPoints = this.calibration.cameraPoints;
        const calMinX = Math.min(...calPoints.map(p => p.x));
        const calMaxX = Math.max(...calPoints.map(p => p.x));
        const calMinY = Math.min(...calPoints.map(p => p.y));
        const calMaxY = Math.max(...calPoints.map(p => p.y));
        
        if (ledIndex === 0 && (cameraPos.x < calMinX || cameraPos.x > calMaxX || 
                                cameraPos.y < calMinY || cameraPos.y > calMaxY)) {
            console.warn(`⚠️ WARNING: First LED is OUTSIDE calibration region!`);
            console.warn(`   LED at (${cameraPos.x.toFixed(1)}, ${cameraPos.y.toFixed(1)})`);
            console.warn(`   Calibration region: (${calMinX.toFixed(1)}, ${calMinY.toFixed(1)}) to (${calMaxX.toFixed(1)}, ${calMaxY.toFixed(1)})`);
            console.warn(`   You probably calibrated the WRONG area of the camera view!`);
        }
        
        // Transform to canvas coordinates
        const canvasPos = this.calibration.mapCameraToCanvas(
            cameraPos.x,
            cameraPos.y
        );
        
        console.log(`LED #${ledIndex + 1}: Canvas pos (${canvasPos.x.toFixed(1)}, ${canvasPos.y.toFixed(1)})`);
        
        // Store position
        this.mappedPositions.set(ledIndex, {
            x: canvasPos.x,
            y: canvasPos.y,
            confidence: cameraPos.confidence
        });
        
        // Update success rate
        const successRate = ((this.mappedPositions.size / (ledIndex + 1)) * 100).toFixed(1);
        const successEl = document.getElementById('successRate');
        if (successEl) successEl.textContent = `${successRate}%`;
        
        const failedEl = document.getElementById('failedLEDs');
        if (failedEl) failedEl.textContent = this.failedLEDs.length;
    }
    
    finishMapping() {
        showToast('Mapping sequence complete!', 'success');
        
        // Calculate statistics
        const totalLEDs = this.config.ledCount;
        const successCount = this.mappedPositions.size;
        const failedCount = this.failedLEDs.length;
        const successRate = ((successCount / totalLEDs) * 100).toFixed(1);
        
        // Update review UI
        document.getElementById('reviewTotalLEDs').textContent = totalLEDs;
        document.getElementById('reviewSuccessCount').textContent = successCount;
        document.getElementById('reviewFailedCount').textContent = failedCount;
        document.getElementById('reviewSuccessRate').textContent = `${successRate}%`;
        
        // Move to review step
        mapperNextStep();
    }
    
    _drawDetectionMarker(cameraPos, ledIndex, success) {
        const video = document.getElementById('mappingVideo');
        const overlay = document.getElementById('mappingOverlay');
        
        if (!video || !overlay || !video.videoWidth) return;
        
        const rect = video.getBoundingClientRect();
        const parent = video.parentElement.getBoundingClientRect();
        
        // Set overlay to match parent size
        overlay.width = parent.width;
        overlay.height = parent.height;
        
        // Calculate video offset within parent (when centered)
        const videoOffsetX = rect.left - parent.left;
        const videoOffsetY = rect.top - parent.top;
        
        const ctx = overlay.getContext('2d');
        
        let displayX, displayY;
        
        if (cameraPos) {
            // Scale from camera pixels to display pixels and add offset
            const scaleX = rect.width / video.videoWidth;
            const scaleY = rect.height / video.videoHeight;
            displayX = cameraPos.x * scaleX + videoOffsetX;
            displayY = cameraPos.y * scaleY + videoOffsetY;
            
            if (window.DEBUG) {
                console.log(`  📺 Drawing marker: camera(${cameraPos.x.toFixed(1)}, ${cameraPos.y.toFixed(1)}) → display(${displayX.toFixed(1)}, ${displayY.toFixed(1)})`);
                console.log(`  🗔️ Video: ${video.videoWidth}x${video.videoHeight} | Display: ${rect.width.toFixed(0)}x${rect.height.toFixed(0)} | Scale: ${scaleX.toFixed(3)}x${scaleY.toFixed(3)}`);
            }
            
            // Draw marker at detected position
            ctx.fillStyle = success ? '#00ff00' : '#ff0000';
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(displayX, displayY, 10, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();
            
            // Draw LED index
            ctx.fillStyle = '#000000';
            ctx.font = 'bold 12px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText((ledIndex + 1).toString(), displayX, displayY);
        }
        
        // Draw calibration rectangle outline for reference (only in DEBUG mode)
        if (window.DEBUG && this.calibration.calibrationRect) {
            const r = this.calibration.calibrationRect;
            const scaleX = rect.width / video.videoWidth;
            const scaleY = rect.height / video.videoHeight;
            
            const rectX = r.x * scaleX;
            const rectY = r.y * scaleY;
            const rectW = r.width * scaleX;
            const rectH = r.height * scaleY;
            
            if (cameraPos) {
                console.log(`  📐 Calibration rect on display: x=${rectX.toFixed(1)}, y=${rectY.toFixed(1)}, w=${rectW.toFixed(1)}, h=${rectH.toFixed(1)}`);
                console.log(`  🎯 Marker position relative to rect: dx=${(displayX - rectX).toFixed(1)}px (${((displayX - rectX) / rectW * 100).toFixed(1)}% from left edge)`);
            }
            
            ctx.strokeStyle = 'rgba(0, 255, 0, 0.5)';
            ctx.lineWidth = 2;
            ctx.setLineDash([5, 5]);
            ctx.strokeRect(rectX, rectY, rectW, rectH);
            ctx.setLineDash([]);
            
            // Draw crosshair at center of rectangle for reference
            const centerX = rectX + rectW / 2;
            const centerY = rectY + rectH / 2;
            ctx.strokeStyle = 'rgba(255, 0, 0, 0.8)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(centerX - 20, centerY);
            ctx.lineTo(centerX + 20, centerY);
            ctx.moveTo(centerX, centerY - 20);
            ctx.lineTo(centerX, centerY + 20);
            ctx.stroke();
            
            // Label rectangle corners
            ctx.fillStyle = 'rgba(255, 255, 0, 0.9)';
            ctx.font = 'bold 14px Arial';
            ctx.fillText('1:TL', rectX + 5, rectY + 15);
            ctx.fillText('2:TR', rectX + rectW - 40, rectY + 15);
            ctx.fillText('3:BR', rectX + rectW - 40, rectY + rectH - 5);
            ctx.fillText('4:BL', rectX + 5, rectY + rectH - 5);
            
            // Draw vertical line showing LED X position
            if (cameraPos) {
                ctx.strokeStyle = 'rgba(255, 165, 0, 0.8)';
                ctx.lineWidth = 2;
                ctx.setLineDash([3, 3]);
                ctx.beginPath();
                ctx.moveTo(displayX, rectY);
                ctx.lineTo(displayX, rectY + rectH);
                ctx.stroke();
                ctx.setLineDash([]);
            }
        }
        
        // Draw refined ROI (dynamic search area) if active (only in DEBUG mode)
        if (window.DEBUG && this.detector.useAutoRefinement && this.detector.regionOfInterest && 
            this.detector.initialROI && this.detector.regionOfInterest !== this.detector.initialROI) {
            const roi = this.detector.regionOfInterest;
            const scaleX = rect.width / video.videoWidth;
            const scaleY = rect.height / video.videoHeight;
            
            ctx.strokeStyle = 'rgba(0, 255, 255, 0.8)'; // Cyan for refined ROI
            ctx.lineWidth = 2;
            ctx.setLineDash([3, 3]);
            ctx.strokeRect(roi.x * scaleX, roi.y * scaleY, roi.width * scaleX, roi.height * scaleY);
            ctx.setLineDash([]);
            
            // Add label
            ctx.fillStyle = 'rgba(0, 255, 255, 0.9)';
            ctx.font = 'bold 10px Arial';
            ctx.textAlign = 'left';
            ctx.fillText('Refined ROI', roi.x * scaleX + 5, roi.y * scaleY + 15);
        }
    }
    
    _sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// ==================== UI CONTROL FUNCTIONS ====================

window.showLEDMapper = function() {
    // Initialize modal
    const modalElement = document.getElementById('ledMapperModal');
    mapperModal = new bootstrap.Modal(modalElement);
    
    // Add cleanup on modal close
    modalElement. addEventListener('hidden.bs.modal', function() {
        if (mappingSession) {
            mappingSession.cleanup();
        }
        if (ledMapper) {
            ledMapper.stopCamera();
        }
    }, { once: true });
    
    mapperModal.show();
    
    // Initialize managers
    ledMapper = new LEDMapper();
    calibrationManager = new CalibrationManager();
    ledDetector = new LEDDetector();
    
    // Reset state
    currentMapperStep = 1;
    
    // Build UI
    buildMapperUI();
    
    // Load saved config from session state and populate form
    loadMapperConfig();
    
    // Populate camera list
    populateCameraList();
    
    showMapperStep(1);
};

function buildMapperUI() {
    const container = document.getElementById('mapperStepsContainer');
    
    // Get canvas dimensions for calibration
    const canvas = document.getElementById('canvas');
    const canvasWidth = canvas ? canvas.width : 1920;
    const canvasHeight = canvas ? canvas.height : 1080;
    
    container.innerHTML = `
        <!-- STEP 1: Configuration -->
        <div id="mapperStep1" class="mapper-step">
            <div class="container" style="max-width: 600px; margin-top: 2rem;">
                <h4 class="mb-4">LED Configuration</h4>
                
                <div class="mb-3">
                    <label class="form-label">Art-Net IP Address</label>
                    <div class="input-group">
                        <input type="text" class="form-control" id="mapperArtnetIP" 
                               placeholder="192.168.1.100" value="192.168.1.100">
                        <button class="btn btn-outline-secondary" type="button" onclick="testNetworkDiagnostics()">
                            🔍 Test Network
                        </button>
                    </div>
                    <div id="networkDiagResult" class="form-text mt-2" style="display: none;"></div>
                </div>
                
                <div class="mb-3">
                    <label class="form-label">Universe</label>
                    <input type="number" class="form-control" id="mapperUniverse" 
                           min="0" max="32767" value="0">
                </div>
                
                <div class="mb-3">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="mapperUseBroadcast">
                        <label class="form-check-label" for="mapperUseBroadcast">
                            Use Broadcast Mode (Multi-NIC Fix)
                        </label>
                        <div class="form-text">Enable if you have multiple network adapters and direct mode doesn't work</div>
                    </div>
                </div>
                
                <div class="mb-3">
                    <label class="form-label">LED Color Type</label>
                    <select class="form-select" id="mapperColorType">
                        <option value="rgb">RGB (3 channels)</option>
                        <option value="rgbw">RGBW (4 channels)</option>
                        <option value="rgbww">RGB+WW (4 channels)</option>
                        <option value="rgbwwcw">RGB+WW+CW (5 channels)</option>
                    </select>
                </div>
                
                <div class="mb-3">
                    <label class="form-label">Number of LEDs</label>
                    <input type="number" class="form-control" id="mapperLEDCount" 
                           min="1" max="500" value="50">
                </div>
                
                <div class="mb-3">
                    <label class="form-label">Starting DMX Address</label>
                    <input type="number" class="form-control" id="mapperStartAddress" 
                           min="1" max="512" value="1">
                </div>
                
                <div class="mb-3">
                    <label class="form-label">Webcam</label>
                    <select class="form-select" id="mapperCamera">
                        <option value="">Auto-detect</option>
                    </select>
                </div>
                
                <div class="mb-4">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="mapperNormalizeGeometry" checked 
                            title="When checked: Smooths LED positions and equalizes spacing for uniform distribution. When unchecked: Uses raw detected positions without adjustment.">
                        <label class="form-check-label" for="mapperNormalizeGeometry" 
                            title="When checked: Smooths LED positions and equalizes spacing for uniform distribution. When unchecked: Uses raw detected positions without adjustment.">
                            Normalize Geometry
                        </label>
                        <div class="form-text">Smooth LED positions and equalize spacing (recommended for LED strips)</div>
                    </div>
                </div>
                
                <button class="btn btn-primary btn-lg w-100" onclick="mapperNextStep()">
                    Next: Calibration →
                </button>
            </div>
        </div>
        
        <!-- STEP 2: Calibration -->
        <div id="mapperStep2" class="mapper-step" style="display: none;">
            <div class="text-center mb-3">
                <h4>Camera Calibration</h4>
                <p class="mb-2"><strong>Draw a rectangle around ALL visible LEDs</strong></p>
                <div class="alert alert-warning">
                    <strong>Click and drag</strong> on the camera preview to draw a rectangle that contains ALL LEDs<br>
                    <small>💡 The rectangle shows exactly what area will be calibrated</small>
                </div>
                <div class="alert alert-secondary">
                    Status: <span id="calibrationStatus">Rectangle not drawn</span> | 
                    Canvas: ${canvasWidth}×${canvasHeight}px
                </div>
                
                <!-- Manual Coordinate Input for Debugging -->
                <details class="mb-2" style="max-width: 600px; margin: 0 auto;">
                    <summary class="btn btn-sm btn-outline-secondary mb-2">🔧 Manual Input (for debugging)</summary>
                    <div class="alert alert-info p-2">
                        <small>Enter rectangle in camera pixel coordinates:</small>
                        <div class="row g-2 mt-1">
                            <div class="col-3">
                                <label class="form-label-sm">X:</label>
                                <input type="number" id="calibRectX" class="form-control form-control-sm" placeholder="e.g. 100">
                            </div>
                            <div class="col-3">
                                <label class="form-label-sm">Y:</label>
                                <input type="number" id="calibRectY" class="form-control form-control-sm" placeholder="e.g. 50">
                            </div>
                            <div class="col-3">
                                <label class="form-label-sm">Width:</label>
                                <input type="number" id="calibRectW" class="form-control form-control-sm" placeholder="e.g. 1000">
                            </div>
                            <div class="col-3">
                                <label class="form-label-sm">Height:</label>
                                <input type="number" id="calibRectH" class="form-control form-control-sm" placeholder="e.g. 700">
                            </div>
                        </div>
                        <button class="btn btn-sm btn-primary mt-2" onclick="applyManualCalibration()">Apply Manual Coordinates</button>
                    </div>
                </details>
            </div>
            
            <div class="position-relative" style="max-width: 100%; margin: 0 auto;">
                <video id="calibrationVideo" autoplay muted playsinline 
                       style="width: 100%; max-width: 1280px; height: auto; border: 3px solid #007bff; border-radius: 8px; cursor: crosshair;">
                </video>
                <canvas id="calibrationOverlay" 
                        style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none;">
                </canvas>
            </div>
            
            <div class="mt-3 d-flex gap-2 justify-content-center">
                <button class="btn btn-secondary" onclick="resetCalibration()">🔄 Reset Points</button>
                <button class="btn btn-secondary" onclick="mapperPrevStep()">← Back</button>
                <button class="btn btn-primary" id="calibrationNextBtn" disabled onclick="completeCalibration()">
                    Next: Start Mapping →
                </button>
            </div>
        </div>
        
        <!-- STEP 3: Mapping -->
        <div id="mapperStep3" class="mapper-step" style="display: none;">
            <div class="text-center mb-4">
                <h4>🔍 Detecting LED Positions...</h4>
                <p class="text-muted">Keep the camera steady while LEDs light up one by one</p>
            </div>
            
            <div class="progress mb-3" style="height: 30px;">
                <div id="mappingProgressBar" class="progress-bar progress-bar-striped progress-bar-animated" 
                     style="width: 0%; font-size: 1.1rem;">0 / 0</div>
            </div>
            
            <div class="row text-center mb-3">
                <div class="col-6">
                    <h5 class="text-success">✓ Success Rate</h5>
                    <h3 id="successRate">-</h3>
                </div>
                <div class="col-6">
                    <h5 class="text-danger">✗ Failed LEDs</h5>
                    <h3 id="failedLEDs">0</h3>
                </div>
            </div>
            
            <div class="position-relative" style="max-width: 100%; margin: 0 auto;">
                <video id="mappingVideo" autoplay muted playsinline 
                       style="width: 100%; max-width: 1280px; height: auto; border: 2px solid #28a745; border-radius: 8px;">
                </video>
                <canvas id="mappingOverlay" 
                        style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none;">
                </canvas>
            </div>
        </div>
        
        <!-- STEP 4: Review -->
        <div id="mapperStep4" class="mapper-step" style="display: none;">
            <div class="text-center">
                <h2 class="mb-4">✅ Mapping Complete!</h2>
                
                <div class="alert alert-success" style="max-width: 500px; margin: 0 auto;">
                    <h5>Results Summary</h5>
                    <p class="mb-1"><strong>Total LEDs:</strong> <span id="reviewTotalLEDs">-</span></p>
                    <p class="mb-1"><strong>Successfully Mapped:</strong> <span id="reviewSuccessCount">-</span></p>
                    <p class="mb-1"><strong>Failed:</strong> <span id="reviewFailedCount">-</span></p>
                    <p class="mb-0"><strong>Success Rate:</strong> <span id="reviewSuccessRate">-</span></p>
                </div>
                
                <div class="mt-4">
                    <button class="btn btn-success btn-lg" onclick="saveMappingToEditor()">
                        💾 Save to Editor as Freehand Shape
                    </button>
                </div>
                
                <div class="mt-3 d-flex gap-2 justify-content-center">
                    <button class="btn btn-warning" onclick="redetectFromCalibration()">
                        ↩️ Back to Re-Detect
                    </button>
                    <button class="btn btn-secondary" onclick="closeMapperModal()">
                        ✕ Close Without Saving
                    </button>
                </div>
            </div>
        </div>
    `;
}

function showMapperStep(step) {
    document.querySelectorAll('.mapper-step').forEach(el => {
        el.style.display = 'none';
    });
    
    document.getElementById(`mapperStep${step}`).style.display = 'block';
    
    const stepNames = ['Configuration', 'Calibration', 'Mapping', 'Review'];
    document.getElementById('mapperStepIndicator').textContent = 
        `Step ${step}/4: ${stepNames[step - 1]}`;
    
    // Step-specific cleanup when LEAVING a step
    if (currentMapperStep === 2 && step !== 2) {
        stopCalibrationOverlayLoop();
    }
    
    // Step-specific initialization
    if (step === 2) {
        initCalibrationUI();
    } else if (step === 3) {
        initMappingUI();
    }
}

window.mapperNextStep = function() {
    if (currentMapperStep === 1) {
        if (!validateMapperConfig()) return;
        saveMapperConfig();
    }
    
    currentMapperStep++;
    showMapperStep(currentMapperStep);
};

// Separate function for completing calibration
window.completeCalibration = function() {
    calibrationManager.calculateTransform();
    showToast('✅ Calibration complete!', 'success');
    currentMapperStep++;
    showMapperStep(currentMapperStep);
    startMappingSequence();
};

window.mapperPrevStep = function() {
    currentMapperStep--;
    showMapperStep(currentMapperStep);
};

function validateMapperConfig() {
    const ip = document.getElementById('mapperArtnetIP').value;
    const ledCount = parseInt(document.getElementById('mapperLEDCount').value);
    
    if (!ip || !/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(ip)) {
        showToast('Invalid Art-Net IP address', 'error');
        return false;
    }
    
    if (ledCount < 1 || ledCount > 500) {
        showToast('LED count must be between 1 and 500', 'error');
        return false;
    }
    
    return true;
}

function saveMapperConfig() {
    mapperConfig.artnetIP = document.getElementById('mapperArtnetIP').value;
    mapperConfig.universe = parseInt(document.getElementById('mapperUniverse').value);
    mapperConfig.colorType = document.getElementById('mapperColorType').value;
    mapperConfig.ledCount = parseInt(document.getElementById('mapperLEDCount').value);
    mapperConfig.startAddress = parseInt(document.getElementById('mapperStartAddress').value);
    mapperConfig.cameraId = document.getElementById('mapperCamera').value || null;
    mapperConfig.useBroadcast = document.getElementById('mapperUseBroadcast').checked;
    mapperConfig.normalizeGeometry = document.getElementById('mapperNormalizeGeometry').checked;
    
    // Save to session state asynchronously
    saveMapperConfigToSession();
}

async function loadMapperConfig() {
    try {
        const response = await fetch('/api/session/mapper');
        const data = await response.json();
        
        if (data.success && data.config && Object.keys(data.config).length > 0) {
            // Populate form fields from saved config
            if (data.config.artnetIP) document.getElementById('mapperArtnetIP').value = data.config.artnetIP;
            if (data.config.universe !== undefined) document.getElementById('mapperUniverse').value = data.config.universe;
            if (data.config.colorType) document.getElementById('mapperColorType').value = data.config.colorType;
            if (data.config.ledCount) document.getElementById('mapperLEDCount').value = data.config.ledCount;
            if (data.config.startAddress) document.getElementById('mapperStartAddress').value = data.config.startAddress;
            if (data.config.useBroadcast !== undefined) document.getElementById('mapperUseBroadcast').checked = data.config.useBroadcast;
            if (data.config.normalizeGeometry !== undefined) document.getElementById('mapperNormalizeGeometry').checked = data.config.normalizeGeometry;
            // Camera ID will be populated after camera list loads
            if (data.config.cameraId) {
                setTimeout(() => {
                    const cameraSelect = document.getElementById('mapperCamera');
                    if (cameraSelect) cameraSelect.value = data.config.cameraId;
                }, 100);
            }
            
            // Update mapperConfig object
            Object.assign(mapperConfig, data.config);
            
            if (window.DEBUG) console.log('💾 Loaded mapper config from session:', data.config);
        }
    } catch (error) {
        console.error('Error loading mapper config:', error);
    }
    
    // Add auto-save listeners to all input fields
    ['mapperArtnetIP', 'mapperUniverse', 'mapperColorType', 'mapperLEDCount', 
     'mapperStartAddress', 'mapperCamera', 'mapperUseBroadcast', 'mapperNormalizeGeometry'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', () => {
                saveMapperConfig();
            });
        }
    });
}

async function saveMapperConfigToSession() {
    try {
        await fetch('/api/session/mapper', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(mapperConfig)
        });
        if (window.DEBUG) console.log('💾 Saved mapper config to session');
    } catch (error) {
        console.error('Error saving mapper config:', error);
    }
}

async function populateCameraList() {
    const select = document.getElementById('mapperCamera');
    const cameras = await ledMapper.listCameras();
    
    select.innerHTML = '<option value="">Auto-detect</option>';
    cameras.forEach((device, idx) => {
        const option = document.createElement('option');
        option.value = device.deviceId;
        option.textContent = device.label || `Camera ${idx + 1}`;
        select.appendChild(option);
    });
}

let calibrationDragState = {
    isDragging: false,
    startX: 0,
    startY: 0,
    dragMode: null // 'draw' or 'resize-tl', 'resize-tr', 'resize-br', 'resize-bl', 'move'
};

let calibrationOverlayAnimationId = null;

async function initCalibrationUI() {
    // Initialize camera for calibration
    const success = await ledMapper.initCamera(mapperConfig.cameraId);
    if (!success) return;
    
    // Attach video to calibration preview
    const videoEl = document.getElementById('calibrationVideo');
    ledMapper.attachToVideo(videoEl);
    
    // Set up drag handlers for rectangle drawing
    videoEl.onmousedown = handleCalibrationMouseDown;
    videoEl.onmousemove = handleCalibrationMouseMove;
    videoEl.onmouseup = handleCalibrationMouseUp;
    videoEl.onmouseleave = handleCalibrationMouseUp;
    
    // Reset calibration state
    calibrationManager.reset();
    updateCalibrationStatus();
    
    // Start continuous overlay redraw
    startCalibrationOverlayLoop();
}

function startCalibrationOverlayLoop() {
    function redraw() {
        drawCalibrationOverlay();
        calibrationOverlayAnimationId = requestAnimationFrame(redraw);
    }
    redraw();
}

function stopCalibrationOverlayLoop() {
    if (calibrationOverlayAnimationId) {
        cancelAnimationFrame(calibrationOverlayAnimationId);
        calibrationOverlayAnimationId = null;
    }
}

function handleCalibrationMouseDown(event) {
    const video = event.target;
    const rect = video.getBoundingClientRect();
    
    const clickX = event.clientX - rect.left;
    const clickY = event.clientY - rect.top;
    
    // Convert to video pixel coordinates
    const scaleX = video.videoWidth / rect.width;
    const scaleY = video.videoHeight / rect.height;
    const cameraX = clickX * scaleX;
    const cameraY = clickY * scaleY;
    
    // Check if clicking on a resize handle
    if (calibrationManager.calibrationRect) {
        const handle = getResizeHandle(cameraX, cameraY, video.videoWidth, video.videoHeight);
        if (handle) {
            calibrationDragState = {
                isDragging: true,
                startX: cameraX,
                startY: cameraY,
                dragMode: handle,
                originalRect: {...calibrationManager.calibrationRect}
            };
            return;
        }
    }
    
    // Start drawing new rectangle
    calibrationDragState = {
        isDragging: true,
        startX: cameraX,
        startY: cameraY,
        dragMode: 'draw'
    };
}

function handleCalibrationMouseMove(event) {
    const video = event.target;
    const rect = video.getBoundingClientRect();
    
    const currentX = (event.clientX - rect.left) * (video.videoWidth / rect.width);
    const currentY = (event.clientY - rect.top) * (video.videoHeight / rect.height);
    
    // Update cursor based on what's under mouse
    if (!calibrationDragState.isDragging && calibrationManager.calibrationRect) {
        const handle = getResizeHandle(currentX, currentY, video.videoWidth, video.videoHeight);
        if (handle) {
            const cursorMap = {
                'resize-tl': 'nwse-resize',
                'resize-tr': 'nesw-resize',
                'resize-br': 'nwse-resize',
                'resize-bl': 'nesw-resize'
            };
            video.style.cursor = cursorMap[handle];
        } else {
            video.style.cursor = 'crosshair';
        }
    } else if (!calibrationDragState.isDragging) {
        video.style.cursor = 'crosshair';
    }
    
    if (!calibrationDragState.isDragging) return;
    
    if (calibrationDragState.dragMode === 'draw') {
        // Drawing new rectangle
        const x = Math.min(calibrationDragState.startX, currentX);
        const y = Math.min(calibrationDragState.startY, currentY);
        const width = Math.abs(currentX - calibrationDragState.startX);
        const height = Math.abs(currentY - calibrationDragState.startY);
        
        calibrationManager.calibrationRect = {x, y, width, height};
    } else if (calibrationDragState.dragMode.startsWith('resize-')) {
        // Resizing rectangle
        resizeCalibrationRect(currentX, currentY);
    }
}

function handleCalibrationMouseUp(event) {
    if (calibrationDragState.isDragging && calibrationManager.calibrationRect) {
        // Finalize rectangle and convert to 4 corner points
        const r = calibrationManager.calibrationRect;
        
        // Validate minimum size
        if (r.width < 50 || r.height < 50) {
            showToast('Rectangle too small! Draw a larger area.', 'warning');
            calibrationManager.calibrationRect = null;
            drawCalibrationOverlay();
            calibrationDragState.isDragging = false;
            return;
        }
        
        // Update status and enable next button
        updateCalibrationStatus();
        setCalibrationPointsFromRect();
        document.getElementById('calibrationNextBtn').disabled = false;
    }
    
    calibrationDragState.isDragging = false;
}

function setCalibrationPointsFromRect() {
    if (!calibrationManager.calibrationRect) return;
    
    const r = calibrationManager.calibrationRect;
    const canvas = document.getElementById('canvas');
    const canvasWidth = canvas ? canvas.width : 1920;
    const canvasHeight = canvas ? canvas.height : 1080;
    
    // Clear previous points
    calibrationManager.referencePoints = [];
    calibrationManager.cameraPoints = [];
    
    // Map rectangle corners to canvas corners
    // Order: TL, TR, BR, BL
    const corners = [
        {cam: {x: r.x, y: r.y}, canvas: {x: 0, y: 0}},                                // Top-Left
        {cam: {x: r.x + r.width, y: r.y}, canvas: {x: canvasWidth, y: 0}},           // Top-Right
        {cam: {x: r.x + r.width, y: r.y + r.height}, canvas: {x: canvasWidth, y: canvasHeight}}, // Bottom-Right
        {cam: {x: r.x, y: r.y + r.height}, canvas: {x: 0, y: canvasHeight}}          // Bottom-Left
    ];
    
    corners.forEach(corner => {
        calibrationManager.addCalibrationPoint(
            corner.canvas.x, corner.canvas.y,
            corner.cam.x, corner.cam.y
        );
    });
    
    // Update manual input fields
    document.getElementById('calibRectX').value = Math.round(r.x);
    document.getElementById('calibRectY').value = Math.round(r.y);
    document.getElementById('calibRectW').value = Math.round(r.width);
    document.getElementById('calibRectH').value = Math.round(r.height);
}

function getResizeHandle(x, y, videoWidth, videoHeight) {
    if (!calibrationManager.calibrationRect) return null;
    
    const r = calibrationManager.calibrationRect;
    const handleSize = Math.max(20, videoWidth * 0.02); // 2% of video width or 20px min
    
    const handles = {
        'resize-tl': {x: r.x, y: r.y},
        'resize-tr': {x: r.x + r.width, y: r.y},
        'resize-br': {x: r.x + r.width, y: r.y + r.height},
        'resize-bl': {x: r.x, y: r.y + r.height}
    };
    
    for (const [name, pos] of Object.entries(handles)) {
        const dist = Math.sqrt((x - pos.x)**2 + (y - pos.y)**2);
        if (dist < handleSize) return name;
    }
    
    return null;
}

function resizeCalibrationRect(currentX, currentY) {
    const orig = calibrationDragState.originalRect;
    const mode = calibrationDragState.dragMode;
    
    let newRect = {...orig};
    
    if (mode === 'resize-tl') {
        newRect.width = orig.width + (orig.x - currentX);
        newRect.height = orig.height + (orig.y - currentY);
        newRect.x = currentX;
        newRect.y = currentY;
    } else if (mode === 'resize-tr') {
        newRect.width = currentX - orig.x;
        newRect.height = orig.height + (orig.y - currentY);
        newRect.y = currentY;
    } else if (mode === 'resize-br') {
        newRect.width = currentX - orig.x;
        newRect.height = currentY - orig.y;
    } else if (mode === 'resize-bl') {
        newRect.width = orig.width + (orig.x - currentX);
        newRect.height = currentY - orig.y;
        newRect.x = currentX;
    }
    
    // Prevent negative dimensions
    if (newRect.width < 0) {
        newRect.x += newRect.width;
        newRect.width = Math.abs(newRect.width);
    }
    if (newRect.height < 0) {
        newRect.y += newRect.height;
        newRect.height = Math.abs(newRect.height);
    }
    
    calibrationManager.calibrationRect = newRect;
}

function drawCalibrationOverlay() {
    const video = document.getElementById('calibrationVideo');
    const overlay = document.getElementById('calibrationOverlay');
    const rect = video.getBoundingClientRect();
    const parent = video.parentElement.getBoundingClientRect();
    
    if (!video.videoWidth || !video.videoHeight) return;
    
    // Set overlay to match parent size
    overlay.width = parent.width;
    overlay.height = parent.height;
    
    // Calculate video offset within parent (when centered)
    const videoOffsetX = rect.left - parent.left;
    const videoOffsetY = rect.top - parent.top;
    
    const ctx = overlay.getContext('2d');
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    
    if (!calibrationManager.calibrationRect) return;
    
    const r = calibrationManager.calibrationRect;
    
    // Scale from camera pixels to display pixels
    const scaleX = rect.width / video.videoWidth;
    const scaleY = rect.height / video.videoHeight;
    
    const displayX = r.x * scaleX + videoOffsetX;
    const displayY = r.y * scaleY + videoOffsetY;
    const displayW = r.width * scaleX;
    const displayH = r.height * scaleY;
    
    // Draw semi-transparent overlay outside rectangle (darken non-calibrated area)
    ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
    ctx.fillRect(0, 0, overlay.width, displayY); // Top
    ctx.fillRect(0, displayY, displayX, displayH); // Left
    ctx.fillRect(displayX + displayW, displayY, overlay.width - (displayX + displayW), displayH); // Right
    ctx.fillRect(0, displayY + displayH, overlay.width, overlay.height - (displayY + displayH)); // Bottom
    
    // Draw calibration rectangle
    ctx.strokeStyle = '#00ff00';
    ctx.lineWidth = 3;
    ctx.strokeRect(displayX, displayY, displayW, displayH);
    
    // Draw corner handles
    const handleSize = 12;
    const handles = [
        {x: displayX, y: displayY},                           // TL
        {x: displayX + displayW, y: displayY},                // TR
        {x: displayX + displayW, y: displayY + displayH},     // BR
        {x: displayX, y: displayY + displayH}                 // BL
    ];
    
    handles.forEach(h => {
        ctx.fillStyle = '#00ff00';
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.fillRect(h.x - handleSize/2, h.y - handleSize/2, handleSize, handleSize);
        ctx.strokeRect(h.x - handleSize/2, h.y - handleSize/2, handleSize, handleSize);
    });
    
    // Draw dimensions text
    ctx.fillStyle = '#00ff00';
    ctx.font = 'bold 16px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(`${Math.round(r.width)}×${Math.round(r.height)}px`, displayX + displayW/2, displayY - 10);
}

function updateCalibrationStatus() {
    const statusEl = document.getElementById('calibrationStatus');
    if (!calibrationManager.calibrationRect) {
        statusEl.textContent = 'Rectangle not drawn';
        statusEl.className = 'text-warning';
    } else {
        const r = calibrationManager.calibrationRect;
        statusEl.textContent = `✓ Rectangle: ${Math.round(r.width)}×${Math.round(r.height)}px at (${Math.round(r.x)}, ${Math.round(r.y)})`;
        statusEl.className = 'text-success fw-bold';
    }
}

window.resetCalibration = function() {
    calibrationManager.reset();
    calibrationManager.calibrationRect = null;
    updateCalibrationStatus();
    drawCalibrationOverlay();
    
    // Clear manual input
    document.getElementById('calibRectX').value = '';
    document.getElementById('calibRectY').value = '';
    document.getElementById('calibRectW').value = '';
    document.getElementById('calibRectH').value = '';
    
    // Disable next button
    document.getElementById('calibrationNextBtn').disabled = true;
    
    showToast('Calibration reset', 'info');
};

window.applyManualCalibration = function() {
    const x = parseFloat(document.getElementById('calibRectX').value);
    const y = parseFloat(document.getElementById('calibRectY').value);
    const width = parseFloat(document.getElementById('calibRectW').value);
    const height = parseFloat(document.getElementById('calibRectH').value);
    
    if (isNaN(x) || isNaN(y) || isNaN(width) || isNaN(height)) {
        showToast('Invalid coordinates! Enter numbers only.', 'error');
        return;
    }
    
    if (width < 50 || height < 50) {
        showToast('Rectangle too small! Minimum 50×50px.', 'error');
        return;
    }
    
    calibrationManager.calibrationRect = {x, y, width, height};
    setCalibrationPointsFromRect();
    drawCalibrationOverlay();
    updateCalibrationStatus();
    document.getElementById('calibrationNextBtn').disabled = false;
    
    showToast(`Manual calibration applied: ${Math.round(width)}×${Math.round(height)}px`, 'success');
};

function initMappingUI() {
    // Attach video to mapping preview
    const videoEl = document.getElementById('mappingVideo');
    if (ledMapper.videoElement) {
        ledMapper.attachToVideo(videoEl);
    }
    
    // Set up detector
    ledDetector.setVideoSource(ledMapper.videoElement);
}

async function startMappingSequence() {
    // Create mapping session
    mappingSession = new MappingSession(
        mapperConfig,
        calibrationManager,
        ledDetector,
        ledMapper.videoElement
    );
    
    await mappingSession.startMappingSequence();
}

window.saveMappingToEditor = function() {
    // Debug logging
    console.log('saveMappingToEditor called');
    console.log('mappingSession:', mappingSession);
    console.log('window.shapes:', window.shapes);
    console.log('window.shapeCounter:', window.shapeCounter);
    
    if (!mappingSession) {
        showToast('No mapping session found', 'error');
        return;
    }
    
    if (!window.shapes) {
        showToast('Editor shapes array not available', 'error');
        return;
    }
    
    // Get mapped positions sorted by LED index
    const positions = Array.from(mappingSession.mappedPositions.entries())
        .sort((a, b) => a[0] - b[0])
        .map(([idx, pos]) => ({x: pos.x, y: pos.y}));
    
    if (positions.length === 0) {
        showToast('No positions to save', 'error');
        return;
    }
    
    console.log('Raw detected positions:', positions.length);
    
    // ========== GEOMETRIC NORMALIZATION (OPTIONAL) ==========
    // Smooth path and equalize spacing (if enabled in config)
    let normalizedPositions;
    if (mapperConfig.normalizeGeometry) {
        normalizedPositions = normalizeGeometry(positions, {
            smoothingWindow: 5,        // Smooth over 5 neighbors
            equalizeSpacing: true,     // Make distances consistent
            targetSpacing: null        // Auto-calculate from average
        });
        if (window.DEBUG) console.log('Geometry normalization applied');
    } else {
        normalizedPositions = positions;
        if (window.DEBUG) console.log('Geometry normalization skipped');
    }
    
    // Calculate bounding box using normalized positions
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    normalizedPositions.forEach(p => {
        minX = Math.min(minX, p.x);
        minY = Math.min(minY, p.y);
        maxX = Math.max(maxX, p.x);
        maxY = Math.max(maxY, p.y);
    });
    
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    const width = maxX - minX;
    const height = maxY - minY;
    
    console.log('Bounding box:', {minX, minY, maxX, maxY, centerX, centerY, width, height});
    
    // Get canvas dimensions for validation
    const canvas = document.getElementById('canvas');
    const canvasWidth = canvas ? canvas.width : 1920;
    const canvasHeight = canvas ? canvas.height : 1080;
    
    // Validate coordinates - warn if mostly outside canvas
    const outsideCount = normalizedPositions.filter(p => 
        p.x < 0 || p.x > canvasWidth || p.y < 0 || p.y > canvasHeight
    ).length;
    const outsidePercent = (outsideCount / normalizedPositions.length) * 100;
    
    if (outsidePercent > 50) {
        console.error('❌ CALIBRATION ERROR: Most LEDs are outside canvas bounds!');
        console.error(`   ${outsideCount}/${normalizedPositions.length} LEDs (${outsidePercent.toFixed(1)}%) are outside canvas`);
        console.error(`   Canvas: ${canvasWidth}×${canvasHeight}`);
        console.error(`   LED range: (${minX.toFixed(1)}, ${minY.toFixed(1)}) to (${maxX.toFixed(1)}, ${maxY.toFixed(1)})`);
        
        showToast(`❌ Calibration Error: ${outsidePercent.toFixed(0)}% of LEDs are outside canvas. Did you calibrate the correct camera region?`, 'error', 8000);
        
        // Ask user if they want to continue anyway
        if (!confirm(`WARNING: ${outsideCount} out of ${normalizedPositions.length} LEDs are outside the canvas bounds!\n\n` +
                     `This usually means you calibrated the wrong area of the camera view.\n\n` +
                     `The LEDs should be INSIDE the 4 corners you clicked during calibration.\n\n` +
                     `Do you want to save anyway (not recommended)?`)) {
            return;
        }
    }
    
    // Convert to relative coordinates (relative to center) - using NORMALIZED positions
    const relativePoints = normalizedPositions.map(p => ({
        x: p.x - centerX,
        y: p.y - centerY
    }));
    
    // Create freehand shape
    // Get current counter value or default to 1
    const currentCounter = (typeof window.shapeCounter === 'number') ? window.shapeCounter : 1;
    const newShapeId = `shape-${currentCounter}`;
    
    const mappedShape = {
        id: newShapeId,
        type: 'freehand',
        name: `Mapped LEDs (${normalizedPositions.length})`,
        x: centerX,
        y: centerY,
        size: Math.max(width, height),
        rotation: 0,
        scaleX: 1,
        scaleY: 1,
        color: 'cyan',
        pointCount: normalizedPositions.length,
        freehandPoints: relativePoints
    };
    
    // Increment counter for next shape
    window.shapeCounter = currentCounter + 1;
    
    console.log('Created shape:', mappedShape);
    
    // Add to shapes array
    window.shapes.push(mappedShape);
    console.log('Shapes array after push:', window.shapes.length, 'shapes');
    
    // Set as selected shape
    window.selectedShape = mappedShape;
    
    // Update editor UI
    if (window.markForRedraw) window.markForRedraw();
    if (window.updateObjectList) window.updateObjectList();
    if (window.saveEditorStateToSession) window.saveEditorStateToSession();
    
    showToast(`✅ ${normalizedPositions.length} LEDs added (path smoothed & spacing equalized)`, 'success');
    
    // Cleanup event listeners
    if (mappingSession) {
        mappingSession.cleanup();
    }
    
    // Close modal and cleanup
    mapperModal.hide();
    ledMapper.stopCamera();
};

window.closeMapperModal = function() {
    // Cleanup event listeners
    if (mappingSession) {
        mappingSession.cleanup();
    }
    
    // Close modal and stop camera
    if (mapperModal) {
        mapperModal.hide();
    }
    if (ledMapper) {
        ledMapper.stopCamera();
    }
};

window.redetectFromCalibration = function() {
    // Go back to step 1 (configuration) for clean restart
    currentMapperStep = 1;
    
    // Clear calibration rectangle
    if (calibrationManager) {
        calibrationManager.calibrationRect = null;
        calibrationManager.reset(); // Clear reference and camera points
    }
    
    // Clear mapping session if it exists
    if (mappingSession) {
        mappingSession.mappedPositions.clear();
        mappingSession.failedLEDs = [];
        mappingSession = null;
    }
    
    // Clear overlay canvas
    const overlay = document.getElementById('mappingOverlay');
    if (overlay) {
        const ctx = overlay.getContext('2d');
        ctx.clearRect(0, 0, overlay.width, overlay.height);
    }
    
    showMapperStep(1);
    showToast('Returned to configuration - ready for clean restart', 'info');
};

// Network Diagnostics Test
window.testNetworkDiagnostics = async function() {
    const targetIP = document.getElementById('mapperArtnetIP').value;
    const resultDiv = document.getElementById('networkDiagResult');
    
    if (!targetIP || !/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(targetIP)) {
        resultDiv.innerHTML = '<span class="text-danger">⚠️ Please enter a valid IP address first</span>';
        resultDiv.style.display = 'block';
        return;
    }
    
    resultDiv.innerHTML = '<span class="text-info">🔄 Testing network connection...</span>';
    resultDiv.style.display = 'block';
    
    try {
        const response = await fetch('/api/mapper/network-diagnostics', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ target_ip: targetIP })
        });
        
        const data = await response.json();
        
        if (data.success) {
            let html = '<div class="alert alert-sm mb-0 ' + (data.target_reachable ? 'alert-success' : 'alert-warning') + '">';
            html += '<strong>Network Diagnostics:</strong><br>';
            html += `📍 Target: ${data.target_ip} - ${data.target_reachable ? '✅ Reachable' : '❌ Not reachable'}<br>`;
            html += `🖥️ Hostname: ${data.hostname}<br>`;
            html += `📤 Source IP: ${data.source_ip || 'Unknown'}<br>`;
            html += `🌐 All Local IPs: ${data.local_ips.join(', ')}<br>`;
            html += `💻 Platform: ${data.platform}`;
            html += '</div>';
            resultDiv.innerHTML = html;
        } else {
            resultDiv.innerHTML = `<span class="text-danger">⚠️ Test failed: ${data.error}</span>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<span class="text-danger">⚠️ Network test error: ${error.message}</span>`;
    }
};

console.log('✅ LED Mapper module loaded');
