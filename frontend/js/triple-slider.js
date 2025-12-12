/**
 * Triple-Handle Slider Component
 * Features:
 * - Min/Max range handles (▼)
 * - Current value handle (|)
 * - Drag & drop for all handles
 * - Automatic value clamping
 * - Customizable callbacks
 */

// Simple debug helper (respects window.DEBUG)
const debugLog = (...args) => {
    if (window.DEBUG === true) {
        console.log(...args);
    }
};

class TripleSlider {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`TripleSlider: Container ${containerId} not found`);
            return;
        }

        // Configuration
        this.config = {
            min: options.min || 0,
            max: options.max || 100,
            value: options.value !== undefined ? options.value : 50,
            rangeMin: options.rangeMin !== undefined ? options.rangeMin : options.min || 0,
            rangeMax: options.rangeMax !== undefined ? options.rangeMax : options.max || 100,
            step: options.step || 1,
            decimals: options.decimals !== undefined ? options.decimals : (options.step < 1 ? 2 : 0),
            onChange: options.onChange || (() => {}),
            onRangeChange: options.onRangeChange || null,
            onDragStart: options.onDragStart || null,
            onDragEnd: options.onDragEnd || null,
            showRangeHandles: options.showRangeHandles !== false, // Default: true
            readOnly: options.readOnly || false,
            displayFormat: options.displayFormat || 'number', // 'number' or 'time'
            fps: options.fps || 30 // For time format conversion
        };
        
        // DEBUG: Log triple-slider configuration
        if (containerId && containerId.includes('transport_position')) {
            debugLog('🎯 TRIPLE-SLIDER CREATED:', containerId, {
                'options.min': options.min,
                'options.max': options.max,
                'options.rangeMin': options.rangeMin,
                'options.rangeMax': options.rangeMax,
                'options.value': options.value,
                'final config.min': this.config.min,
                'final config.max': this.config.max,
                'final config.rangeMin': this.config.rangeMin,
                'final config.rangeMax': this.config.rangeMax,
                'final config.value': this.config.value
            });
        }
        
        // Track the actual content boundary (for dynamic scaling detection)
        // This stays fixed unless content size actually changes
        this.contentMax = this.config.max;

        this.isDragging = false;
        this.activeHandle = null;
        this.isHovering = false; // Track hover state

        this.init();
    }

    init() {
        // Create slider HTML structure
        this.container.innerHTML = `
            <div class="triple-slider">
                <div class="slider-track">
                    <div class="range-highlight"></div>
                    ${this.config.showRangeHandles ? `
                        <div class="handle handle-min" data-type="min" title="Min: ${this.config.rangeMin}">▼</div>
                        <div class="handle handle-max" data-type="max" title="Max: ${this.config.rangeMax}">▼</div>
                    ` : ''}
                    <div class="handle handle-value" data-type="value" title="Value: ${this.config.value}">|</div>
                </div>
            </div>
        `;

        // Get elements
        this.track = this.container.querySelector('.slider-track');
        this.highlight = this.container.querySelector('.range-highlight');
        this.minHandle = this.container.querySelector('.handle-min');
        this.maxHandle = this.container.querySelector('.handle-max');
        this.valueHandle = this.container.querySelector('.handle-value');

        // Bind events
        if (!this.config.readOnly) {
            if (this.minHandle) this.bindDrag(this.minHandle, 'min');
            if (this.maxHandle) this.bindDrag(this.maxHandle, 'max');
            this.bindDrag(this.valueHandle, 'value');
        }

        // Bind hover events to pause auto-updates
        this.track.addEventListener('mouseenter', () => {
            this.isHovering = true;
        });
        this.track.addEventListener('mouseleave', () => {
            this.isHovering = false;
        });

        // Initial render
        this.updateUI();
    }

    bindDrag(handle, type) {
        const mouseDown = (e) => {
            if (this.config.readOnly) return;
            e.preventDefault();
            this.isDragging = true;
            this.activeHandle = type;
            document.body.style.cursor = 'ew-resize';

            // Call onDragStart callback
            if (this.config.onDragStart) {
                this.config.onDragStart(type);
            }

            const mouseMove = (e) => this.onDrag(e.clientX);
            const mouseUp = () => {
                this.isDragging = false;
                this.activeHandle = null;
                document.body.style.cursor = '';
                document.removeEventListener('mousemove', mouseMove);
                document.removeEventListener('mouseup', mouseUp);
                
                // Call onDragEnd callback
                if (this.config.onDragEnd) {
                    this.config.onDragEnd(type);
                }
            };

            document.addEventListener('mousemove', mouseMove);
            document.addEventListener('mouseup', mouseUp);
        };

        handle.addEventListener('mousedown', mouseDown);
    }

    onDrag(clientX) {
        const rect = this.track.getBoundingClientRect();
        const rawPercent = ((clientX - rect.left) / rect.width) * 100;
        const percent = Math.max(0, Math.min(100, rawPercent));

        // Convert percent to actual value
        const range = this.config.max - this.config.min;
        let rawValue = this.config.min + (percent / 100) * range;

        // Apply step
        if (this.config.step) {
            rawValue = Math.round(rawValue / this.config.step) * this.config.step;
        }

        // Apply decimals
        const value = parseFloat(rawValue.toFixed(this.config.decimals));

        // Update based on handle type
        switch (this.activeHandle) {
            case 'min':
                if (value < this.config.rangeMax) {
                    this.config.rangeMin = value;
                    if (this.config.value < value) {
                        this.config.value = value;
                    }
                    if (this.config.onRangeChange) {
                        this.config.onRangeChange(this.config.rangeMin, this.config.rangeMax);
                    }
                }
                break;

            case 'max':
                if (value > this.config.rangeMin) {
                    this.config.rangeMax = value;
                    if (this.config.value > value) {
                        this.config.value = value;
                    }
                    if (this.config.onRangeChange) {
                        this.config.onRangeChange(this.config.rangeMin, this.config.rangeMax);
                    }
                }
                break;

            case 'value':
                // Clamp value between rangeMin and rangeMax
                const clampedValue = Math.max(this.config.rangeMin, Math.min(this.config.rangeMax, value));
                if (clampedValue !== this.config.value) {
                    this.config.value = clampedValue;
                    this.config.onChange(this.config.value);
                }
                break;
        }

        this.updateUI();
    }

    updateUI() {
        const percentValue = (val) => ((val - this.config.min) / (this.config.max - this.config.min)) * 100;

        const minPercent = percentValue(this.config.rangeMin);
        const maxPercent = percentValue(this.config.rangeMax);
        const valuePercent = percentValue(this.config.value);

        // Position handles
        if (this.minHandle) {
            this.minHandle.style.left = `${minPercent}%`;
            this.minHandle.title = `Min: ${this.formatValue(this.config.rangeMin)}`;
        }
        if (this.maxHandle) {
            this.maxHandle.style.left = `${maxPercent}%`;
            this.maxHandle.title = `Max: ${this.formatValue(this.config.rangeMax)}`;
        }
        this.valueHandle.style.left = `${valuePercent}%`;
        this.valueHandle.title = `Value: ${this.formatValue(this.config.value)}`;

        // Update range highlight
        if (this.config.showRangeHandles) {
            this.highlight.style.left = `${minPercent}%`;
            this.highlight.style.width = `${maxPercent - minPercent}%`;
        } else {
            this.highlight.style.display = 'none';
        }
    }

    formatValue(val) {
        if (this.config.displayFormat === 'time') {
            // Convert frames to time format (mm:ss or hh:mm:ss)
            const totalSeconds = Math.floor(val / this.config.fps);
            const hours = Math.floor(totalSeconds / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            const seconds = totalSeconds % 60;
            
            if (hours > 0) {
                return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            } else {
                return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            }
        }
        return this.config.decimals === 0 ? Math.round(val) : val.toFixed(this.config.decimals);
    }

    // Public API
    setValue(value) {
        const clamped = Math.max(this.config.rangeMin, Math.min(this.config.rangeMax, value));
        if (clamped !== this.config.value) {
            this.config.value = clamped;
            this.updateUI();
        }
    }

    getValue() {
        return this.config.value;
    }

    setRange(min, max) {
        this.config.rangeMin = Math.max(this.config.min, min);
        this.config.rangeMax = Math.min(this.config.max, max);
        
        // Clamp value to new range
        if (this.config.value < this.config.rangeMin) {
            this.config.value = this.config.rangeMin;
        }
        if (this.config.value > this.config.rangeMax) {
            this.config.value = this.config.rangeMax;
        }
        
        this.updateUI();
    }

    getRange() {
        return {
            min: this.config.rangeMin,
            max: this.config.rangeMax
        };
    }

    // Update all values at once (for real-time updates without triggering onChange)
    updateValues(value, rangeMin, rangeMax, autoScale = false) {
        // DEBUG: Log all updateValues calls for transport
        if (this.containerId && this.containerId.includes('transport_position')) {
            debugLog('🔧 updateValues called:', {
                containerId: this.containerId,
                value, rangeMin, rangeMax, autoScale,
                isHovering: this.isHovering,
                isDragging: this.isDragging,
                'current config.value': this.config.value
            });
        }
        
        let updated = false;
        
        // Always update position value (even during hover/drag) so transport position moves
        if (value !== undefined) {
            this.config.value = value;
            updated = true;
        }
        
        // Don't update range handles if user is hovering or dragging (easier to grab)
        if (this.isHovering || this.isDragging) {
            if (updated) {
                if (this.containerId && this.containerId.includes('transport_position')) {
                    debugLog('🎨 Rendering slider (hover/drag mode, only value updated)');
                }
                this.render();
            }
            return;
        }
        
        if (rangeMin !== undefined) {
            this.config.rangeMin = rangeMin;
            updated = true;
        }
        if (rangeMax !== undefined) {
            this.config.rangeMax = rangeMax;
            updated = true;
            
            // Scale slider max only when explicitly requested AND rangeMax >= current contentMax
            // This allows scaling UP when content grows, but prevents scaling DOWN during trim
            if (autoScale && rangeMax >= this.contentMax) {
                this.config.max = rangeMax;
                this.contentMax = rangeMax;
            } else if (autoScale && rangeMax < this.contentMax) {
                // Content shrunk (e.g., generator duration decreased) - allow scaling down
                // BUT only if rangeMax is close to a "round" frame count (likely from backend)
                // Check if rangeMax is at max position (full content, not trimmed)
                const epsilon = 5; // Allow small differences
                if (Math.abs(rangeMax - this.contentMax) > epsilon) {
                    // Likely a real content change, not a trim
                    this.config.max = rangeMax;
                    this.contentMax = rangeMax;
                }
            }
        }
        
        // Always update UI if any parameter was provided
        if (updated) {
            this.updateUI();
        }
    }

    destroy() {
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Global registry for slider instances
window.tripleSliders = window.tripleSliders || {};

/**
 * Initialize a triple slider
 * @param {string} containerId - ID of container element
 * @param {object} options - Configuration options
 * @returns {TripleSlider} Slider instance
 */
function initTripleSlider(containerId, options = {}) {
    // Destroy existing instance
    if (window.tripleSliders[containerId]) {
        window.tripleSliders[containerId].destroy();
    }

    // Create new instance
    const slider = new TripleSlider(containerId, options);
    window.tripleSliders[containerId] = slider;
    return slider;
}

/**
 * Get existing slider instance
 * @param {string} containerId - ID of container element
 * @returns {TripleSlider|null} Slider instance or null
 */
function getTripleSlider(containerId) {
    return window.tripleSliders[containerId] || null;
}
