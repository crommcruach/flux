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
    /**
     * @param {string} containerId - The DOM element id to render into
     * @param {string} initialColor - Initial hex color
     * @param {function|null} onChange - Called with hex color on every change
     * @param {function|null} onPaletteChange - Called with palette colors array when palette changes
     */
    constructor(containerId, initialColor = '#ff0000', onChange = null, onPaletteChange = null, options = {}) {
        this.containerId = containerId;
        this.onChange = onChange;
        this.onPaletteChange = onPaletteChange;
        this._initializing = true;
        this.currentMode = 'hsb';
        // Range handles for sequence cycling
        this.showRangeHandles = options.showRangeHandles || false;
        this._rangeMin = options.rangeMin !== undefined ? options.rangeMin : 0.0;
        this._rangeMax = options.rangeMax !== undefined ? options.rangeMax : 1.0;
        this.onRangeChange = options.onRangeChange || null;
        
        // Color state
        this.hsb = { h: 0, s: 100, b: 100, a: 255 };
        this.rgb = { r: 255, g: 0, b: 0 };
        
        // Palette state
        this.paletteColors = [];
        this.isAddingToPalette = false;
        
        // Set initial color state (DOM doesn't exist yet — updateColor will skip)
        this.setValue(initialColor);
        
        // Render the picker (uses already-set color state, calls updateColor once DOM exists)
        this.render();
        this.attachEventListeners();
        this._initializing = false;
    }

    /** Fire onPaletteChange callback with current palette colors (only in palette mode) */
    _notifyPaletteChange() {
        if (this.onPaletteChange && this.currentMode === 'palette') {
            this.onPaletteChange([...this.paletteColors]);
        }
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
                                <div class="hue-range-track${this.showRangeHandles ? '' : ' hidden'}" id="${this.containerId}_hueRangeTrack">
                                    <div class="hue-range-fill" id="${this.containerId}_hueRangeFill"></div>
                                    <div class="hue-range-handle hue-range-min" id="${this.containerId}_hueRangeMin" title="Drag to set min hue for sequence cycling"></div>
                                    <div class="hue-range-handle hue-range-max" id="${this.containerId}_hueRangeMax" title="Drag to set max hue for sequence cycling"></div>
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
                    <div class="palette-named-row">
                        <select class="palette-named-select" id="${this.containerId}_namedSelect">
                            <option value="">-- Load saved palette --</option>
                        </select>
                        <button class="palette-btn" id="${this.containerId}_saveNamedBtn" title="Save current palette under a name">Save as…</button>
                        <button class="palette-btn palette-btn-delete" id="${this.containerId}_deleteNamedBtn" title="Delete selected palette">🗑</button>
                    </div>
                    <div class="palette-grid" id="${this.containerId}_paletteGrid"></div>
                    <!-- Inline color wheel for adding colors (hidden until + Add Color clicked) -->
                    <div class="palette-wheel-picker" id="${this.containerId}_wheelPicker" style="display:none">
                        <div class="palette-wheel-body">
                            <canvas class="palette-wheel-canvas" id="${this.containerId}_wheelCanvas" width="150" height="150"></canvas>
                            <div class="palette-wheel-right">
                                <div class="palette-wheel-swatch" id="${this.containerId}_wheelSwatch"></div>
                                <div class="palette-wheel-bright-label">V</div>
                                <div class="palette-wheel-bright-track" id="${this.containerId}_brightTrack">
                                    <div class="palette-wheel-bright-thumb" id="${this.containerId}_brightThumb"></div>
                                </div>
                            </div>
                        </div>
                        <div class="palette-wheel-actions">
                            <button class="palette-btn palette-btn-confirm" id="${this.containerId}_wheelAddBtn">✓ Add</button>
                            <button class="palette-btn" id="${this.containerId}_wheelCancelBtn">Cancel</button>
                        </div>
                    </div>
                    <div class="palette-actions" id="${this.containerId}_paletteActions">
                        <button class="palette-btn" id="${this.containerId}_addColorBtn">+ Add Color</button>
                        <button class="palette-btn" id="${this.containerId}_clearPalette">Clear</button>
                    </div>
                </div>
                
                <!-- Alpha (shared across all modes) -->
                <div class="slider-group alpha-slider-group">
                    <div class="slider-row">
                        <span class="slider-label">Alpha</span>
                        <div class="slider-container">
                            <div class="color-slider alpha-slider" data-slider="alpha" id="${this.containerId}_alphaSlider">
                                <div class="slider-thumb" id="${this.containerId}_alphaThumb"></div>
                            </div>
                        </div>
                        <span class="slider-value" id="${this.containerId}_alphaValue">255</span>
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
        
        // Alpha slider (shared)
        this.attachSlider('alpha', (value) => {
            this.hsb.a = Math.round(value * 255);
            this.updateColor();
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
            this._showWheelPicker();
        });
        document.getElementById(`${this.containerId}_clearPalette`)?.addEventListener('click', (e) => {
            const btn = e.currentTarget;
            if (btn.dataset.confirming === '1') return; // second click handled by onclick below
            btn.dataset.confirming = '1';
            const origText = btn.textContent;
            btn.textContent = '✓ Confirm';
            btn.classList.add('palette-btn-confirm');
            const timer = setTimeout(() => {
                btn.textContent = origText;
                btn.classList.remove('palette-btn-confirm');
                delete btn.dataset.confirming;
                btn.onclick = null;
            }, 3000);
            btn.onclick = () => {
                clearTimeout(timer);
                btn.textContent = origText;
                btn.classList.remove('palette-btn-confirm');
                delete btn.dataset.confirming;
                btn.onclick = null;
                this.paletteColors = [];
                this.renderPalette();
                this._notifyPaletteChange();
            };
        });
        
        // Named palette: auto-load on select change
        document.getElementById(`${this.containerId}_namedSelect`)?.addEventListener('change', () => {
            const sel = document.getElementById(`${this.containerId}_namedSelect`);
            const name = sel?.value;
            if (!name) return;
            const colors = (window._colorPalettes || {})[name];
            if (colors) {
                this.paletteColors = [...colors];
                this.renderPalette();
                this._notifyPaletteChange();
            }
        });
        
        // Named palette: save as
        document.getElementById(`${this.containerId}_saveNamedBtn`)?.addEventListener('click', async () => {
            const name = prompt('Palette name:');
            if (!name || !name.trim()) return;
            const trimmed = name.trim();
            if (!window._colorPalettes) window._colorPalettes = {};
            window._colorPalettes[trimmed] = [...this.paletteColors];
            // Persist to localStorage
            try {
                const stored = JSON.parse(localStorage.getItem('colorPalettes') || '{}');
                stored[trimmed] = [...this.paletteColors];
                localStorage.setItem('colorPalettes', JSON.stringify(stored));
            } catch (e) {
                console.warn('ColorPicker: could not save palette to localStorage', e);
            }
            // Best-effort persist to config.json (may fail silently)
            try {
                const cfgResp = await fetch('/api/config');
                if (cfgResp.ok) {
                    const cfg = await cfgResp.json();
                    cfg.color_palettes = { ...(cfg.color_palettes || {}), [trimmed]: [...this.paletteColors] };
                    await fetch('/api/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(cfg)
                    });
                }
            } catch (e) {
                console.warn('ColorPicker: could not persist palette to config.json', e);
            }
            this._refreshNamedSelect();
        });

        // Named palette: delete
        document.getElementById(`${this.containerId}_deleteNamedBtn`)?.addEventListener('click', async () => {
            const sel = document.getElementById(`${this.containerId}_namedSelect`);
            const name = sel?.value;
            if (!name) return;
            if (!confirm(`Delete palette "${name}"?`)) return;
            // Remove from memory
            if (window._colorPalettes) delete window._colorPalettes[name];
            // Remove from localStorage
            try {
                const stored = JSON.parse(localStorage.getItem('colorPalettes') || '{}');
                delete stored[name];
                localStorage.setItem('colorPalettes', JSON.stringify(stored));
            } catch (e) {
                console.warn('ColorPicker: could not update localStorage', e);
            }
            // Best-effort persist to config.json
            try {
                const cfgResp = await fetch('/api/config');
                if (cfgResp.ok) {
                    const cfg = await cfgResp.json();
                    if (cfg.color_palettes) delete cfg.color_palettes[name];
                    await fetch('/api/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(cfg)
                    });
                }
            } catch (e) {
                console.warn('ColorPicker: could not remove palette from config.json', e);
            }
            this._refreshNamedSelect();
        });

        // Populate dropdown with any palettes already in window._colorPalettes
        this._refreshNamedSelect();

        // Wire wheel picker buttons
        document.getElementById(`${this.containerId}_wheelAddBtn`)?.addEventListener('click', () => {
            this._addColorFromWheel();
        });
        document.getElementById(`${this.containerId}_wheelCancelBtn`)?.addEventListener('click', () => {
            this._hideWheelPicker();
        });

        // Range handles for sequence cycling
        if (this.showRangeHandles) {
            this._attachRangeHandles();
        }
    }

    _attachRangeHandles() {
        const track = document.getElementById(`${this.containerId}_hueRangeTrack`);
        const minHandle = document.getElementById(`${this.containerId}_hueRangeMin`);
        const maxHandle = document.getElementById(`${this.containerId}_hueRangeMax`);
        if (!track || !minHandle || !maxHandle) return;

        this._updateRangeHandlePositions();

        const makeHandleDragger = (isMin) => {
            const handle = isMin ? minHandle : maxHandle;
            let dragging = false;

            handle.addEventListener('mousedown', (e) => {
                e.preventDefault();
                e.stopPropagation();
                dragging = true;
            });

            const onMove = (e) => {
                if (!dragging) return;
                const rect = track.getBoundingClientRect();
                let val = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                val = Math.round(val * 100) / 100;
                if (isMin) {
                    this._rangeMin = Math.min(val, this._rangeMax - 0.01);
                } else {
                    this._rangeMax = Math.max(val, this._rangeMin + 0.01);
                }
                this._updateRangeHandlePositions();
                if (this.onRangeChange) this.onRangeChange(this._rangeMin, this._rangeMax);
            };

            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', () => { dragging = false; });
        };

        makeHandleDragger(true);
        makeHandleDragger(false);
    }

    _updateRangeHandlePositions() {
        const minHandle = document.getElementById(`${this.containerId}_hueRangeMin`);
        const maxHandle = document.getElementById(`${this.containerId}_hueRangeMax`);
        const fill = document.getElementById(`${this.containerId}_hueRangeFill`);
        if (!minHandle || !maxHandle) return;
        minHandle.style.left = `${this._rangeMin * 100}%`;
        maxHandle.style.left = `${this._rangeMax * 100}%`;
        if (fill) {
            fill.style.left = `${this._rangeMin * 100}%`;
            fill.style.width = `${(this._rangeMax - this._rangeMin) * 100}%`;
        }
    }
    
    _refreshNamedSelect() {
        const sel = document.getElementById(`${this.containerId}_namedSelect`);
        if (!sel) return;
        const palettes = window._colorPalettes || {};
        const current = sel.value;
        sel.innerHTML = '<option value="">-- Load saved palette --</option>' +
            Object.keys(palettes).map(n =>
                `<option value="${n}" ${n === current ? 'selected' : ''}>${n}</option>`
            ).join('');
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
        const previousMode = this.currentMode;
        this.currentMode = mode;
        
        if (mode === 'palette') {
            this._refreshNamedSelect();
            this.renderPalette();
            this._notifyPaletteChange();
        } else if (previousMode === 'palette') {
            // Leaving palette mode — clear palette cycling on the backend (send empty list)
            if (this.onPaletteChange) this.onPaletteChange([]);
        }

        // Range handles only visible in HSB mode
        if (this.showRangeHandles) {
            const track = document.getElementById(`${this.containerId}_hueRangeTrack`);
            if (track) track.classList.toggle('hidden', mode !== 'hsb');
        }
    }

    /** Returns the currently loaded palette colors (empty array if not in palette mode or no palette loaded) */
    getPaletteColors() {
        return this.paletteColors || [];
    }

    /** Returns the name of the currently selected named palette, or null */
    getActivePaletteName() {
        const sel = document.getElementById(`${this.containerId}_namedSelect`);
        return sel?.value || null;
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
        // Bail out if DOM hasn't been rendered yet
        const swatch = document.getElementById(`${this.containerId}_swatch`);
        if (!swatch) return;
        
        // Swatch shows current color with alpha
        swatch.style.background = `rgba(${this.rgb.r}, ${this.rgb.g}, ${this.rgb.b}, ${(this.hsb.a / 255).toFixed(3)})`;
        
        // Update HSB values
        document.getElementById(`${this.containerId}_hueValue`).textContent = Math.round(this.hsb.h) + '°';
        document.getElementById(`${this.containerId}_saturationValue`).textContent = Math.round(this.hsb.s) + '%';
        document.getElementById(`${this.containerId}_brightnessValue`).textContent = Math.round(this.hsb.b) + '%';
        
        // Update RGB values
        document.getElementById(`${this.containerId}_redValue`).textContent = this.rgb.r;
        document.getElementById(`${this.containerId}_greenValue`).textContent = this.rgb.g;
        document.getElementById(`${this.containerId}_blueValue`).textContent = this.rgb.b;
        
        // Update alpha display
        const alphaValue = document.getElementById(`${this.containerId}_alphaValue`);
        if (alphaValue) alphaValue.textContent = Math.round(this.hsb.a);
        const alphaThumb = document.getElementById(`${this.containerId}_alphaThumb`);
        if (alphaThumb) alphaThumb.style.left = (this.hsb.a / 255 * 100) + '%';
        
        // Update slider positions
        document.getElementById(`${this.containerId}_hueThumb`).style.left = (this.hsb.h / 360 * 100) + '%';
        document.getElementById(`${this.containerId}_saturationThumb`).style.left = (this.hsb.s / 100 * 100) + '%';
        document.getElementById(`${this.containerId}_brightnessThumb`).style.left = (this.hsb.b / 100 * 100) + '%';
        document.getElementById(`${this.containerId}_redThumb`).style.left = (this.rgb.r / 255 * 100) + '%';
        document.getElementById(`${this.containerId}_greenThumb`).style.left = (this.rgb.g / 255 * 100) + '%';
        document.getElementById(`${this.containerId}_blueThumb`).style.left = (this.rgb.b / 255 * 100) + '%';
        
        // Update slider backgrounds
        this.updateSliderBackgrounds();
        
        // Trigger onChange callback (suppressed during initialization)
        if (this.onChange && !this._initializing) {
            this.onChange(this.getValue());
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
        
        const alphaSlider = document.getElementById(`${this.containerId}_alphaSlider`);
        if (alphaSlider) {
            alphaSlider.style.background = `linear-gradient(to right, rgba(${this.rgb.r},${this.rgb.g},${this.rgb.b},0), rgba(${this.rgb.r},${this.rgb.g},${this.rgb.b},1))`;
        }
    }
    
    startAddingToPalette() {
        // Legacy — now uses inline wheel picker
        this._showWheelPicker();
    }

    _showWheelPicker() {
        const wheel = document.getElementById(`${this.containerId}_wheelPicker`);
        const actions = document.getElementById(`${this.containerId}_paletteActions`);
        if (!wheel) return;
        wheel.style.display = 'block';
        if (actions) actions.style.display = 'none';
        // Init wheel state
        this._wheelHsv = { h: 0, s: 1, v: 1 };
        this._drawWheelCanvas();
        this._attachWheelDrag();
        this._updateWheelBrightness();
        this._updateWheelSwatch();
    }

    _hideWheelPicker() {
        const wheel = document.getElementById(`${this.containerId}_wheelPicker`);
        const actions = document.getElementById(`${this.containerId}_paletteActions`);
        if (wheel) wheel.style.display = 'none';
        if (actions) actions.style.display = '';
    }

    _addColorFromWheel() {
        if (!this._wheelHsv) return;
        const { h, s, v } = this._wheelHsv;
        const rgb = this.hsbToRgb(h, s * 100, v * 100);
        const hex = this.rgbToHex(rgb.r, rgb.g, rgb.b);
        this.paletteColors.push(hex + 'ff');
        this.renderPalette();
        this._notifyPaletteChange();
        this._hideWheelPicker();
    }

    _drawWheelCanvas() {
        const canvas = document.getElementById(`${this.containerId}_wheelCanvas`);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const cx = canvas.width / 2;
        const cy = canvas.height / 2;
        const r = Math.min(cx, cy) - 2;
        // Draw hue+saturation wheel
        const imgData = ctx.createImageData(canvas.width, canvas.height);
        const data = imgData.data;
        for (let y = 0; y < canvas.height; y++) {
            for (let x = 0; x < canvas.width; x++) {
                const dx = x - cx;
                const dy = y - cy;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist > r) { data[(y * canvas.width + x) * 4 + 3] = 0; continue; }
                const angle = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
                const sat = dist / r;
                const rgb = this.hsbToRgb(angle, sat * 100, 100);
                const i = (y * canvas.width + x) * 4;
                data[i] = rgb.r; data[i+1] = rgb.g; data[i+2] = rgb.b; data[i+3] = 255;
            }
        }
        ctx.putImageData(imgData, 0, 0);
        // Draw selector dot
        if (this._wheelHsv) {
            const { h, s } = this._wheelHsv;
            const angle = h * Math.PI / 180;
            const dotX = cx + s * r * Math.cos(angle);
            const dotY = cy + s * r * Math.sin(angle);
            ctx.beginPath();
            ctx.arc(dotX, dotY, 5, 0, Math.PI * 2);
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 2;
            ctx.stroke();
            ctx.beginPath();
            ctx.arc(dotX, dotY, 5, 0, Math.PI * 2);
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 1;
            ctx.stroke();
        }
    }

    _attachWheelDrag() {
        const canvas = document.getElementById(`${this.containerId}_wheelCanvas`);
        if (!canvas || canvas._wheelDragAttached) return;
        canvas._wheelDragAttached = true;
        let dragging = false;
        const pick = (e) => {
            const rect = canvas.getBoundingClientRect();
            const cx = canvas.width / 2;
            const cy = canvas.height / 2;
            const r = Math.min(cx, cy) - 2;
            // scale mouse to canvas coords
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            const dx = (e.clientX - rect.left) * scaleX - cx;
            const dy = (e.clientY - rect.top) * scaleY - cy;
            const dist = Math.min(Math.sqrt(dx * dx + dy * dy), r);
            const angle = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
            this._wheelHsv.h = angle;
            this._wheelHsv.s = dist / r;
            this._drawWheelCanvas();
            this._updateWheelSwatch();
        };
        canvas.addEventListener('mousedown', (e) => { dragging = true; pick(e); });
        document.addEventListener('mousemove', (e) => { if (dragging) pick(e); });
        document.addEventListener('mouseup', () => { dragging = false; });
        // Brightness track
        const track = document.getElementById(`${this.containerId}_brightTrack`);
        if (track && !track._wheelDragAttached) {
            track._wheelDragAttached = true;
            let bdrag = false;
            const pickB = (e) => {
                const rect = track.getBoundingClientRect();
                const v = 1 - Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
                this._wheelHsv.v = v;
                this._updateWheelBrightness();
                this._updateWheelSwatch();
            };
            track.addEventListener('mousedown', (e) => { bdrag = true; pickB(e); });
            document.addEventListener('mousemove', (e) => { if (bdrag) pickB(e); });
            document.addEventListener('mouseup', () => { bdrag = false; });
        }
    }

    _updateWheelBrightness() {
        const thumb = document.getElementById(`${this.containerId}_brightThumb`);
        if (thumb && this._wheelHsv) {
            thumb.style.top = `${(1 - this._wheelHsv.v) * 100}%`;
        }
    }

    _updateWheelSwatch() {
        if (!this._wheelHsv) return;
        const { h, s, v } = this._wheelHsv;
        const rgb = this.hsbToRgb(h, s * 100, v * 100);
        const swatch = document.getElementById(`${this.containerId}_wheelSwatch`);
        if (swatch) swatch.style.background = `rgb(${rgb.r},${rgb.g},${rgb.b})`;
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
                 title="${color}">
                <span class="palette-color-delete" data-index="${index}" title="Remove">&times;</span>
            </div>
        `).join('');
        
        // Attach click handlers
        grid.querySelectorAll('.palette-color').forEach(colorDiv => {
            colorDiv.addEventListener('click', () => {
                const index = parseInt(colorDiv.getAttribute('data-index'));
                const color = this.paletteColors[index];
                this.setValue(color);
            });
        });
        
        // Attach delete handlers (stop propagation so click-to-select doesn't fire)
        grid.querySelectorAll('.palette-color-delete').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const index = parseInt(btn.getAttribute('data-index'));
                this.paletteColors.splice(index, 1);
                this.renderPalette();
            });
        });
    }
    
    // Public API
    getValue() {
        const alphaHex = Math.round(this.hsb.a).toString(16).padStart(2, '0');
        return this.rgbToHex(this.rgb.r, this.rgb.g, this.rgb.b) + alphaHex;
    }
    
    setValue(hexColor) {
        const match = String(hexColor).match(/#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})?/i);
        if (match) {
            this.rgb.r = parseInt(match[1], 16);
            this.rgb.g = parseInt(match[2], 16);
            this.rgb.b = parseInt(match[3], 16);
            const alpha = match[4] !== undefined ? parseInt(match[4], 16) : 255;
            const hsb = this.rgbToHsb(this.rgb.r, this.rgb.g, this.rgb.b);
            this.hsb = { ...hsb, a: alpha };
            this.updateColor();
        }
    }
    
    setPalette(colors) {
        this.paletteColors = colors;
        this.renderPalette();
    }

    getRangeMin() { return this._rangeMin; }
    getRangeMax() { return this._rangeMax; }

    setRange(min, max) {
        this._rangeMin = Math.max(0, Math.min(1, min));
        this._rangeMax = Math.max(0, Math.min(1, max));
        this._updateRangeHandlePositions();
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
