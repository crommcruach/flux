/**
 * ColorPicker Component
 * Reusable color picker with HSB, RGB, and Palette modes
 * 
 * Usage:
 *   const picker = new ColorPicker(containerId, initialColor, callback);
 *   picker.getValue() // returns hex color like "#ff0000"
 *   picker.setValue("#00ff00") // sets color programmatically
 */

class ColorPicker {
    constructor(containerId, initialColor = '#ff0000', onChange = null) {
        this.containerId = containerId;
        this.onChange = onChange;
        
        // Color state
        this.hsb = { h: 0, s: 100, b: 100, a: 255 };
        this.rgb = { r: 255, g: 0, b: 0 };
        
        // Palette state
        this.paletteColors = [];
        this.isAddingToPalette = false;
        
        // Set initial color
        this.setValue(initialColor);
        
        // Render the picker
        this.render();
        this.attachEventListeners();
    }
    
    render() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`ColorPicker: Container ${this.containerId} not found`);
            return;
        }
        
        container.innerHTML = `
            <div class="color-picker-container">
                <div class="color-header">
                    <div class="color-swatch" id="${this.containerId}_swatch"></div>
                    <div class="mode-tabs">
                        <button class="mode-tab active" data-mode="hsb">HSB</button>
                        <button class="mode-tab" data-mode="rgb">RGB</button>
                        <button class="mode-tab" data-mode="palette">Palette</button>
                    </div>
                </div>
                
                <!-- HSB Mode -->
                <div class="mode-content active" id="${this.containerId}_hsbMode">
                    <div class="slider-group">
                        <div class="slider-row">
                            <span class="slider-label">Hue</span>
                            <div class="slider-container">
                                <div class="color-slider hue-slider" data-slider="hue">
                                    <div class="slider-thumb" id="${this.containerId}_hueThumb"></div>
                                </div>
                            </div>
                            <span class="slider-value" id="${this.containerId}_hueValue">0°</span>
                        </div>
                        <div class="slider-row">
                            <span class="slider-label">Saturation</span>
                            <div class="slider-container">
                                <div class="color-slider" data-slider="saturation" id="${this.containerId}_saturationSlider">
                                    <div class="slider-thumb" id="${this.containerId}_saturationThumb"></div>
                                </div>
                            </div>
                            <span class="slider-value" id="${this.containerId}_saturationValue">100%</span>
                        </div>
                        <div class="slider-row">
                            <span class="slider-label">Brightness</span>
                            <div class="slider-container">
                                <div class="color-slider" data-slider="brightness" id="${this.containerId}_brightnessSlider">
                                    <div class="slider-thumb" id="${this.containerId}_brightnessThumb"></div>
                                </div>
                            </div>
                            <span class="slider-value" id="${this.containerId}_brightnessValue">100%</span>
                        </div>
                    </div>
                    <button class="add-to-palette-btn hidden" id="${this.containerId}_addToPaletteBtn">Add to Palette</button>
                </div>
                
                <!-- RGB Mode -->
                <div class="mode-content" id="${this.containerId}_rgbMode">
                    <div class="slider-group">
                        <div class="slider-row">
                            <span class="slider-label">Red</span>
                            <div class="slider-container">
                                <div class="color-slider" data-slider="red" id="${this.containerId}_redSlider">
                                    <div class="slider-thumb" id="${this.containerId}_redThumb"></div>
                                </div>
                            </div>
                            <span class="slider-value" id="${this.containerId}_redValue">255</span>
                        </div>
                        <div class="slider-row">
                            <span class="slider-label">Green</span>
                            <div class="slider-container">
                                <div class="color-slider" data-slider="green" id="${this.containerId}_greenSlider">
                                    <div class="slider-thumb" id="${this.containerId}_greenThumb"></div>
                                </div>
                            </div>
                            <span class="slider-value" id="${this.containerId}_greenValue">0</span>
                        </div>
                        <div class="slider-row">
                            <span class="slider-label">Blue</span>
                            <div class="slider-container">
                                <div class="color-slider" data-slider="blue" id="${this.containerId}_blueSlider">
                                    <div class="slider-thumb" id="${this.containerId}_blueThumb"></div>
                                </div>
                            </div>
                            <span class="slider-value" id="${this.containerId}_blueValue">0</span>
                        </div>
                    </div>
                    <button class="add-to-palette-btn hidden" id="${this.containerId}_addToPaletteRgbBtn">Add to Palette</button>
                </div>
                
                <!-- Palette Mode -->
                <div class="mode-content" id="${this.containerId}_paletteMode">
                    <div class="palette-grid" id="${this.containerId}_paletteGrid"></div>
                    <div class="palette-actions">
                        <button class="palette-btn" id="${this.containerId}_addColorBtn">+ Add Color</button>
                        <button class="palette-btn" id="${this.containerId}_clearPalette">Clear</button>
                    </div>
                </div>
            </div>
        `;
        
        this.updateColor();
    }
    
    attachEventListeners() {
        const container = document.getElementById(this.containerId);
        
        // Mode tabs
        container.querySelectorAll('.mode-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const mode = tab.getAttribute('data-mode');
                this.switchMode(mode);
            });
        });
        
        // HSB sliders
        this.attachSlider('hue', (value) => {
            this.hsb.h = value * 360;
            this.updateFromHsb();
        });
        this.attachSlider('saturation', (value) => {
            this.hsb.s = value * 100;
            this.updateFromHsb();
        });
        this.attachSlider('brightness', (value) => {
            this.hsb.b = value * 100;
            this.updateFromHsb();
        });
        
        // RGB sliders
        this.attachSlider('red', (value) => {
            this.rgb.r = Math.round(value * 255);
            this.updateFromRgb();
        });
        this.attachSlider('green', (value) => {
            this.rgb.g = Math.round(value * 255);
            this.updateFromRgb();
        });
        this.attachSlider('blue', (value) => {
            this.rgb.b = Math.round(value * 255);
            this.updateFromRgb();
        });
        
        // Add to palette buttons
        document.getElementById(`${this.containerId}_addToPaletteBtn`)?.addEventListener('click', () => {
            this.addToPalette();
        });
        document.getElementById(`${this.containerId}_addToPaletteRgbBtn`)?.addEventListener('click', () => {
            this.addToPalette();
        });
        
        // Palette actions
        document.getElementById(`${this.containerId}_addColorBtn`)?.addEventListener('click', () => {
            this.startAddingToPalette();
        });
        document.getElementById(`${this.containerId}_clearPalette`)?.addEventListener('click', () => {
            if (confirm('Clear all colors?')) {
                this.paletteColors = [];
                this.renderPalette();
            }
        });
    }
    
    attachSlider(name, callback) {
        const slider = document.querySelector(`#${this.containerId} [data-slider="${name}"]`);
        if (!slider) return;
        
        let isDragging = false;
        
        const updateSlider = (e) => {
            const rect = slider.getBoundingClientRect();
            const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
            const value = x / rect.width;
            callback(value);
        };
        
        slider.addEventListener('mousedown', (e) => {
            isDragging = true;
            updateSlider(e);
        });
        
        document.addEventListener('mousemove', (e) => {
            if (isDragging) updateSlider(e);
        });
        
        document.addEventListener('mouseup', () => {
            isDragging = false;
        });
    }
    
    switchMode(mode) {
        const container = document.getElementById(this.containerId);
        container.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
        container.querySelector(`[data-mode="${mode}"]`)?.classList.add('active');
        container.querySelectorAll('.mode-content').forEach(c => c.classList.remove('active'));
        document.getElementById(`${this.containerId}_${mode}Mode`)?.classList.add('active');
        
        if (mode === 'palette') {
            this.renderPalette();
        }
    }
    
    updateFromHsb() {
        const rgb = this.hsbToRgb(this.hsb.h, this.hsb.s, this.hsb.b);
        this.rgb = rgb;
        this.updateColor();
    }
    
    updateFromRgb() {
        const hsb = this.rgbToHsb(this.rgb.r, this.rgb.g, this.rgb.b);
        this.hsb = { ...hsb, a: this.hsb.a };
        this.updateColor();
    }
    
    updateColor() {
        const hex = this.rgbToHex(this.rgb.r, this.rgb.g, this.rgb.b);
        
        // Update swatch
        const swatch = document.getElementById(`${this.containerId}_swatch`);
        if (swatch) swatch.style.background = hex;
        
        // Update HSB values
        document.getElementById(`${this.containerId}_hueValue`).textContent = Math.round(this.hsb.h) + '°';
        document.getElementById(`${this.containerId}_saturationValue`).textContent = Math.round(this.hsb.s) + '%';
        document.getElementById(`${this.containerId}_brightnessValue`).textContent = Math.round(this.hsb.b) + '%';
        
        // Update RGB values
        document.getElementById(`${this.containerId}_redValue`).textContent = this.rgb.r;
        document.getElementById(`${this.containerId}_greenValue`).textContent = this.rgb.g;
        document.getElementById(`${this.containerId}_blueValue`).textContent = this.rgb.b;
        
        // Update slider positions
        document.getElementById(`${this.containerId}_hueThumb`).style.left = (this.hsb.h / 360 * 100) + '%';
        document.getElementById(`${this.containerId}_saturationThumb`).style.left = (this.hsb.s / 100 * 100) + '%';
        document.getElementById(`${this.containerId}_brightnessThumb`).style.left = (this.hsb.b / 100 * 100) + '%';
        document.getElementById(`${this.containerId}_redThumb`).style.left = (this.rgb.r / 255 * 100) + '%';
        document.getElementById(`${this.containerId}_greenThumb`).style.left = (this.rgb.g / 255 * 100) + '%';
        document.getElementById(`${this.containerId}_blueThumb`).style.left = (this.rgb.b / 255 * 100) + '%';
        
        // Update slider backgrounds
        this.updateSliderBackgrounds();
        
        // Trigger onChange callback
        if (this.onChange) {
            this.onChange(hex);
        }
    }
    
    updateSliderBackgrounds() {
        const currentHue = this.hsbToRgb(this.hsb.h, 100, 100);
        const satSlider = document.getElementById(`${this.containerId}_saturationSlider`);
        if (satSlider) {
            const hueHex = this.rgbToHex(currentHue.r, currentHue.g, currentHue.b);
            satSlider.style.background = `linear-gradient(to right, #808080, ${hueHex})`;
        }
        
        const brightSlider = document.getElementById(`${this.containerId}_brightnessSlider`);
        if (brightSlider) {
            const currentColor = this.hsbToRgb(this.hsb.h, this.hsb.s, 100);
            const colorHex = this.rgbToHex(currentColor.r, currentColor.g, currentColor.b);
            brightSlider.style.background = `linear-gradient(to right, #000000, ${colorHex})`;
        }
        
        const redSlider = document.getElementById(`${this.containerId}_redSlider`);
        if (redSlider) {
            const startColor = this.rgbToHex(0, this.rgb.g, this.rgb.b);
            const endColor = this.rgbToHex(255, this.rgb.g, this.rgb.b);
            redSlider.style.background = `linear-gradient(to right, ${startColor}, ${endColor})`;
        }
        
        const greenSlider = document.getElementById(`${this.containerId}_greenSlider`);
        if (greenSlider) {
            const startColor = this.rgbToHex(this.rgb.r, 0, this.rgb.b);
            const endColor = this.rgbToHex(this.rgb.r, 255, this.rgb.b);
            greenSlider.style.background = `linear-gradient(to right, ${startColor}, ${endColor})`;
        }
        
        const blueSlider = document.getElementById(`${this.containerId}_blueSlider`);
        if (blueSlider) {
            const startColor = this.rgbToHex(this.rgb.r, this.rgb.g, 0);
            const endColor = this.rgbToHex(this.rgb.r, this.rgb.g, 255);
            blueSlider.style.background = `linear-gradient(to right, ${startColor}, ${endColor})`;
        }
    }
    
    startAddingToPalette() {
        this.isAddingToPalette = true;
        document.getElementById(`${this.containerId}_addToPaletteBtn`)?.classList.remove('hidden');
        document.getElementById(`${this.containerId}_addToPaletteRgbBtn`)?.classList.remove('hidden');
        this.switchMode('hsb');
    }
    
    addToPalette() {
        const hex = this.rgbToHex(this.rgb.r, this.rgb.g, this.rgb.b);
        this.paletteColors.push(hex);
        
        this.isAddingToPalette = false;
        document.getElementById(`${this.containerId}_addToPaletteBtn`)?.classList.add('hidden');
        document.getElementById(`${this.containerId}_addToPaletteRgbBtn`)?.classList.add('hidden');
        
        this.switchMode('palette');
    }
    
    renderPalette() {
        const grid = document.getElementById(`${this.containerId}_paletteGrid`);
        if (!grid) return;
        
        if (this.paletteColors.length === 0) {
            grid.innerHTML = '<div class="palette-empty">No colors in palette. Click "+ Add Color" to start.</div>';
            return;
        }
        
        grid.innerHTML = this.paletteColors.map((color, index) => `
            <div class="palette-color" style="background: ${color}" 
                 data-index="${index}" 
                 title="${color}"></div>
        `).join('');
        
        // Attach click handlers
        grid.querySelectorAll('.palette-color').forEach(colorDiv => {
            colorDiv.addEventListener('click', () => {
                const index = parseInt(colorDiv.getAttribute('data-index'));
                const color = this.paletteColors[index];
                this.setValue(color);
            });
        });
    }
    
    // Public API
    getValue() {
        return this.rgbToHex(this.rgb.r, this.rgb.g, this.rgb.b);
    }
    
    setValue(hexColor) {
        const match = hexColor.match(/#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i);
        if (match) {
            this.rgb.r = parseInt(match[1], 16);
            this.rgb.g = parseInt(match[2], 16);
            this.rgb.b = parseInt(match[3], 16);
            const hsb = this.rgbToHsb(this.rgb.r, this.rgb.g, this.rgb.b);
            this.hsb = { ...hsb, a: this.hsb.a };
            this.updateColor();
        }
    }
    
    setPalette(colors) {
        this.paletteColors = colors;
        this.renderPalette();
    }
    
    getPalette() {
        return this.paletteColors;
    }
    
    // Color conversion utilities
    hsbToRgb(h, s, b) {
        s /= 100;
        b /= 100;
        const k = (n) => (n + h / 60) % 6;
        const f = (n) => b * (1 - s * Math.max(0, Math.min(k(n), 4 - k(n), 1)));
        return {
            r: Math.round(255 * f(5)),
            g: Math.round(255 * f(3)),
            b: Math.round(255 * f(1))
        };
    }
    
    rgbToHsb(r, g, b) {
        r /= 255;
        g /= 255;
        b /= 255;
        const max = Math.max(r, g, b);
        const min = Math.min(r, g, b);
        const d = max - min;
        let h = 0;
        const s = max === 0 ? 0 : d / max;
        const v = max;
        
        if (d !== 0) {
            switch (max) {
                case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
                case g: h = ((b - r) / d + 2) / 6; break;
                case b: h = ((r - g) / d + 4) / 6; break;
            }
        }
        
        return {
            h: h * 360,
            s: s * 100,
            b: v * 100
        };
    }
    
    rgbToHex(r, g, b) {
        return '#' + [r, g, b].map(x => {
            const hex = x.toString(16);
            return hex.length === 1 ? '0' + hex : hex;
        }).join('');
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ColorPicker;
}
