/**
 * Circular Slider (Knob) Component
 * 
 * A reusable circular slider that can be used for any numeric parameter.
 * Supports 270° (default) or 360° arc modes.
 * 
 * @example
 * const knob = new CircularSlider('myContainer', {
 *     min: 0,
 *     max: 100,
 *     value: 50,
 *     step: 1,
 *     arc: 270, // or 360
 *     size: 'medium', // 'small', 'medium', 'large'
 *     onChange: (value) => console.log(value)
 * });
 */

class CircularSlider {
    constructor(containerId, options = {}) {
        this.container = typeof containerId === 'string' 
            ? document.getElementById(containerId) 
            : containerId;
        
        if (!this.container) {
            console.error('CircularSlider: Container not found');
            return;
        }
        
        // Configuration
        this.config = {
            min: options.min || 0,
            max: options.max || 100,
            value: options.value || 0,
            step: options.step || 1,
            arc: options.arc || 270, // 270° or 360°
            startAngle: options.startAngle !== undefined ? options.startAngle : null, // Custom start angle (null = auto)
            size: options.size || 'medium', // 'small', 'medium', 'large'
            label: options.label || '',
            showValue: options.showValue !== false,
            showTicks: options.showTicks || false,
            tickCount: options.tickCount || 10,
            disabled: options.disabled || false,
            variant: options.variant || 'primary', // 'primary', 'success', 'warning', 'danger'
            decimals: options.decimals || 0,
            unit: options.unit || '',
            onChange: options.onChange || null,
            onDragStart: options.onDragStart || null,
            onDragEnd: options.onDragEnd || null
        };
        
        // State
        this.isDragging = false;
        // Use custom startAngle if provided, otherwise calculate centered arc
        if (this.config.startAngle !== null) {
            this.startAngle = this.config.startAngle;
        } else {
            this.startAngle = this.config.arc === 360 ? 0 : (360 - this.config.arc) / 2;
        }
        this.endAngle = this.startAngle + this.config.arc;
        
        // Create DOM
        this.createElement();
        this.setValue(this.config.value);
        this.attachEvents();
    }
    
    /**
     * Create DOM structure
     */
    createElement() {
        const wrapper = document.createElement('div');
        wrapper.className = 'circular-slider-container';
        
        const slider = document.createElement('div');
        slider.className = `circular-slider ${this.config.size} variant-${this.config.variant}`;
        if (this.config.disabled) slider.classList.add('disabled');
        
        // Get size
        const sizeMap = { tiny: 25, small: 40, medium: 60, large: 80 };
        const size = typeof this.config.size === 'number' ? this.config.size : (sizeMap[this.config.size] || 60);
        const radius = size / 2;
        const strokeWidth = size < 30 ? 3 : 4;
        const normalizedRadius = radius - strokeWidth / 2;
        const circumference = normalizedRadius * 2 * Math.PI;
        const arcLength = (this.config.arc / 360) * circumference;
        
        // Background track (using path for true arc, not full circle)
        const trackSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        trackSvg.setAttribute('class', 'circular-slider-track');
        trackSvg.setAttribute('width', size);
        trackSvg.setAttribute('height', size);
        
        const trackPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        trackPath.setAttribute('d', this.createArcPath(radius, normalizedRadius, 0, this.config.arc));
        trackPath.setAttribute('fill', 'none');
        trackPath.setAttribute('stroke-width', strokeWidth);
        trackSvg.appendChild(trackPath);
        
        // Progress arc (using path for true arc)
        const progressSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        progressSvg.setAttribute('class', 'circular-slider-progress');
        progressSvg.setAttribute('width', size);
        progressSvg.setAttribute('height', size);
        
        const progressPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        progressPath.setAttribute('d', this.createArcPath(radius, normalizedRadius, 0, 0));
        progressPath.setAttribute('fill', 'none');
        progressPath.setAttribute('stroke-width', strokeWidth);
        progressSvg.appendChild(progressPath);
        
        // Handle (indicator dot)
        const handle = document.createElement('div');
        handle.className = 'circular-slider-handle';
        
        // Value display
        const valueDisplay = document.createElement('div');
        valueDisplay.className = 'circular-slider-value';
        valueDisplay.textContent = this.formatValue(this.config.value);
        
        // Ticks (optional)
        if (this.config.showTicks) {
            const ticksContainer = document.createElement('div');
            ticksContainer.className = 'circular-slider-ticks';
            this.createTicks(ticksContainer, size, radius);
            slider.appendChild(ticksContainer);
        }
        
        // Assemble
        slider.appendChild(trackSvg);
        slider.appendChild(progressSvg);
        slider.appendChild(handle);
        if (this.config.showValue) {
            slider.appendChild(valueDisplay);
        }
        
        wrapper.appendChild(slider);
        
        // Label
        if (this.config.label) {
            const label = document.createElement('div');
            label.className = 'circular-slider-label';
            label.textContent = this.config.label;
            wrapper.appendChild(label);
        }
        
        // Store references
        this.wrapper = wrapper;
        this.slider = slider;
        this.progressPath = progressPath;
        this.handle = handle;
        this.valueDisplay = valueDisplay;
        this.arcLength = arcLength;
        this.radius = radius;
        this.normalizedRadius = normalizedRadius;
        
        this.container.appendChild(wrapper);
    }
    
    /**
     * Create SVG arc path
     * SVG coordinate system: 0°=East (3 o'clock), angles increase clockwise
     */
    createArcPath(radius, arcRadius, startPercent, arcDegrees) {
        const startAngle = this.startAngle + (this.config.arc * startPercent / 100);
        const endAngle = startAngle + arcDegrees;
        
        // Convert to radians - no offset needed, angles already aligned correctly
        const startRad = startAngle * Math.PI / 180;
        const endRad = endAngle * Math.PI / 180;
        
        const x1 = radius + arcRadius * Math.cos(startRad);
        const y1 = radius + arcRadius * Math.sin(startRad);
        const x2 = radius + arcRadius * Math.cos(endRad);
        const y2 = radius + arcRadius * Math.sin(endRad);
        
        const largeArc = arcDegrees > 180 ? 1 : 0;
        
        if (arcDegrees === 0) {
            return `M ${x1} ${y1}`;
        }
        
        return `M ${x1} ${y1} A ${arcRadius} ${arcRadius} 0 ${largeArc} 1 ${x2} ${y2}`;
    }
    
    /**
     * Create tick marks
     */
    createTicks(container, size, radius) {
        const tickRadius = radius - 12;
        const angleStep = this.config.arc / (this.config.tickCount - 1);
        
        for (let i = 0; i < this.config.tickCount; i++) {
            const angle = this.startAngle + (i * angleStep);
            const rad = (angle - 90) * Math.PI / 180;
            const x = size / 2 + tickRadius * Math.cos(rad);
            const y = size / 2 + tickRadius * Math.sin(rad);
            
            const tick = document.createElement('div');
            tick.className = 'circular-slider-tick';
            if (i % 5 === 0) tick.classList.add('major');
            tick.style.left = x + 'px';
            tick.style.top = y + 'px';
            tick.style.transform = `rotate(${angle}deg)`;
            
            container.appendChild(tick);
        }
    }
    
    /**
     * Attach event listeners
     */
    attachEvents() {
        if (this.config.disabled) return;
        
        this.slider.addEventListener('mousedown', this.onMouseDown.bind(this));
        document.addEventListener('mousemove', this.onMouseMove.bind(this));
        document.addEventListener('mouseup', this.onMouseUp.bind(this));
        
        // Touch support
        this.slider.addEventListener('touchstart', this.onTouchStart.bind(this));
        document.addEventListener('touchmove', this.onTouchMove.bind(this));
        document.addEventListener('touchend', this.onTouchEnd.bind(this));
        
        // Scroll support
        this.slider.addEventListener('wheel', this.onWheel.bind(this), { passive: false });
    }
    
    /**
     * Mouse down handler
     */
    onMouseDown(e) {
        e.preventDefault();
        this.startDrag();
        this.updateFromMouse(e);
    }
    
    /**
     * Mouse move handler
     */
    onMouseMove(e) {
        if (!this.isDragging) return;
        e.preventDefault();
        this.updateFromMouse(e);
    }
    
    /**
     * Mouse up handler
     */
    onMouseUp(e) {
        if (!this.isDragging) return;
        this.stopDrag();
    }
    
    /**
     * Touch start handler
     */
    onTouchStart(e) {
        e.preventDefault();
        this.startDrag();
        this.updateFromTouch(e);
    }
    
    /**
     * Touch move handler
     */
    onTouchMove(e) {
        if (!this.isDragging) return;
        e.preventDefault();
        this.updateFromTouch(e);
    }
    
    /**
     * Touch end handler
     */
    onTouchEnd(e) {
        if (!this.isDragging) return;
        this.stopDrag();
    }
    
    /**
     * Wheel handler
     */
    onWheel(e) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -this.config.step : this.config.step;
        const newValue = this.clamp(this.config.value + delta);
        this.setValue(newValue);
        if (this.config.onChange) {
            this.config.onChange(newValue);
        }
    }
    
    /**
     * Start dragging
     */
    startDrag() {
        this.isDragging = true;
        this.slider.classList.add('dragging');
        if (this.config.onDragStart) {
            this.config.onDragStart(this.config.value);
        }
    }
    
    /**
     * Stop dragging
     */
    stopDrag() {
        this.isDragging = false;
        this.slider.classList.remove('dragging');
        if (this.config.onDragEnd) {
            this.config.onDragEnd(this.config.value);
        }
    }
    
    /**
     * Update from mouse position
     */
    updateFromMouse(e) {
        const rect = this.slider.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        const angle = this.calculateAngle(e.clientX, e.clientY, centerX, centerY);
        this.updateFromAngle(angle);
    }
    
    /**
     * Update from touch position
     */
    updateFromTouch(e) {
        const touch = e.touches[0];
        const rect = this.slider.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        const angle = this.calculateAngle(touch.clientX, touch.clientY, centerX, centerY);
        this.updateFromAngle(angle);
    }
    
    /**
     * Calculate angle from mouse/touch coordinates
     * Converts screen coordinates to our angle system
     */
    calculateAngle(x, y, centerX, centerY) {
        const dx = x - centerX;
        const dy = y - centerY;
        // atan2 gives angle from positive X-axis (3 o'clock = 0°)
        let angle = Math.atan2(dy, dx) * 180 / Math.PI;
        if (angle < 0) angle += 360;
        return angle;
    }
    
    /**
     * Update value from angle
     */
    updateFromAngle(angle) {
        // Normalize angle to arc range
        let normalizedAngle = angle - this.startAngle;
        if (normalizedAngle < 0) normalizedAngle += 360;
        if (normalizedAngle > this.config.arc) {
            // Choose closest boundary
            if (normalizedAngle > this.config.arc + (360 - this.config.arc) / 2) {
                normalizedAngle = 0;
            } else {
                normalizedAngle = this.config.arc;
            }
        }
        
        // Convert angle to value
        const percent = normalizedAngle / this.config.arc;
        const range = this.config.max - this.config.min;
        const rawValue = this.config.min + (range * percent);
        const steppedValue = Math.round(rawValue / this.config.step) * this.config.step;
        const newValue = this.clamp(steppedValue);
        
        this.setValue(newValue);
        if (this.config.onChange) {
            this.config.onChange(newValue);
        }
    }
    
    /**
     * Set value
     */
    setValue(value) {
        this.config.value = this.clamp(value);
        this.updateUI();
    }
    
    /**
     * Get value
     */
    getValue() {
        return this.config.value;
    }
    
    /**
     * Update UI
     */
    updateUI() {
        const percent = (this.config.value - this.config.min) / (this.config.max - this.config.min);
        const progressDegrees = this.config.arc * percent;
        
        // Update progress arc path
        this.progressPath.setAttribute('d', this.createArcPath(this.radius, this.normalizedRadius, 0, progressDegrees));
        
        // Update handle position (use same angle system as arc path)
        const angle = this.startAngle + progressDegrees;
        const rad = angle * Math.PI / 180;
        const handleRadius = this.normalizedRadius;
        const x = this.radius + handleRadius * Math.cos(rad);
        const y = this.radius + handleRadius * Math.sin(rad);
        
        this.handle.style.left = x + 'px';
        this.handle.style.top = y + 'px';
        
        // Update value display
        if (this.valueDisplay) {
            this.valueDisplay.textContent = this.formatValue(this.config.value);
        }
    }
    
    /**
     * Format value for display
     */
    formatValue(value) {
        const fixed = value.toFixed(this.config.decimals);
        return this.config.unit ? `${fixed}${this.config.unit}` : fixed;
    }
    
    /**
     * Clamp value to min/max
     */
    clamp(value) {
        return Math.max(this.config.min, Math.min(this.config.max, value));
    }
    
    /**
     * Update configuration
     */
    updateConfig(options) {
        Object.assign(this.config, options);
        if (options.disabled !== undefined) {
            this.slider.classList.toggle('disabled', options.disabled);
        }
        if (options.variant) {
            this.slider.className = this.slider.className.replace(/variant-\w+/, `variant-${options.variant}`);
        }
        this.updateUI();
    }
    
    /**
     * Destroy
     */
    destroy() {
        if (this.wrapper && this.wrapper.parentNode) {
            this.wrapper.parentNode.removeChild(this.wrapper);
        }
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CircularSlider;
}
