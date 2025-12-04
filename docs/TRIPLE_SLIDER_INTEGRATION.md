# Triple-Handle Slider Integration - Implementierungsplan

## Status: VORBEREITET ✅

## Übersicht
Der neue Triple-Handle Slider aus `snippets/SliderNew.html` soll alle bestehenden Range-Slider ersetzen.

### Neue Features:
- **Min/Max Range Handles (▼)**: Dynamische Anpassung der zulässigen Range
- **Value Handle (|)**: Aktueller Parameterwert
- **Drag & Drop**: Alle Handles sind verschiebbar
- **Auto-Clamping**: Value wird automatisch auf Range begrenzt

---

## ✅ Bereits erstellt:

1. **`src/static/js/triple-slider.js`** - Wiederverwendbare Slider-Komponente
   - `TripleSlider` Klasse mit voller API
   - `initTripleSlider(containerId, options)` Funktion
   - `getTripleSlider(containerId)` für Zugriff auf Instanzen
   - Globales Registry in `window.tripleSliders`

2. **`src/static/css/triple-slider.css`** - Styling passend zu bestehendem Design
   - Responsive Design
   - Dark Mode Support
   - Hover-Effekte
   - Bootstrap-Integration

---

## 📋 Nächste Schritte:

### 1. Integration in HTML-Templates (~10min)

#### `src/static/controls.html`:
```html
<!-- Nach bestehenden CSS includes -->
<link rel="stylesheet" href="css/triple-slider.css">

<!-- Nach bestehenden JS includes -->
<script src="js/triple-slider.js"></script>
```

#### `src/static/artnet.html`:
```html
<!-- Nach bestehenden CSS includes -->
<link rel="stylesheet" href="css/triple-slider.css">

<!-- Nach bestehenden JS includes -->
<script src="js/triple-slider.js"></script>
```

#### `src/static/editor.html`:
```html
<!-- Nach bestehenden CSS includes -->
<link rel="stylesheet" href="css/triple-slider.css">

<!-- Nach bestehenden JS includes -->
<script src="js/triple-slider.js"></script>
```

---

### 2. Anpassung `effects.js` (~30min)

**Datei:** `src/static/js/effects.js`

**Zeilen 248-268** - FLOAT/INT Case ersetzen:

```javascript
case 'FLOAT':
case 'INT':
    const step = paramType === 'INT' ? 1 : 0.1;
    const decimals = paramType === 'INT' ? 0 : (step >= 0.1 ? 1 : 2);
    const sliderId = `${controlId}_slider`;
    
    control = `
        <div class="parameter-control">
            <div class="parameter-label">
                <label for="${controlId}">${param.name}</label>
                <span class="parameter-value" id="${controlId}_value">${value}</span>
            </div>
            <div id="${sliderId}"></div>
            ${param.description ? `<div class="parameter-description">${param.description}</div>` : ''}
        </div>
        <script>
            // Initialize triple slider after DOM update
            setTimeout(() => {
                initTripleSlider('${sliderId}', {
                    min: ${param.min || 0},
                    max: ${param.max || 100},
                    value: ${value},
                    step: ${step},
                    decimals: ${decimals},
                    showRangeHandles: true,
                    onChange: (val) => {
                        document.getElementById('${controlId}_value').textContent = val.toFixed(${decimals});
                        updateParameter(${effectIndex}, '${param.name}', val, '${controlId}_value');
                    }
                });
            }, 0);
        </script>
    `;
    break;
```

---

### 3. Anpassung `player.js` (~30min)

**Datei:** `src/static/js/player.js`

**Zeilen 3002-3030** - FLOAT/INT Case ersetzen:

```javascript
case 'FLOAT':
case 'INT':
    const intStep = param.step || 1;
    const intDecimals = intStep >= 1 ? 0 : (intStep >= 0.1 ? 1 : 2);
    const intDefaultValue = param.default || 0;
    const sliderId = `${controlId}_slider`;
    
    control = `
        <div class="parameter-control">
            <div class="parameter-label">
                <label for="${controlId}">${param.name}</label>
                <span class="parameter-value" id="${controlId}_value">${value.toFixed(intDecimals)}</span>
            </div>
            <div id="${sliderId}"></div>
        </div>
        <script>
            setTimeout(() => {
                const slider = initTripleSlider('${sliderId}', {
                    min: ${param.min || 0},
                    max: ${param.max || 100},
                    value: ${value},
                    step: ${intStep},
                    decimals: ${intDecimals},
                    showRangeHandles: true,
                    onChange: (val) => {
                        const formatted = ${intDecimals === 0} ? Math.round(val) : val.toFixed(${intDecimals});
                        document.getElementById('${controlId}_value').textContent = formatted;
                        updateParameter('${player}', ${effectIndex}, '${param.name}', val, '${controlId}_value');
                    }
                });
                
                // Right-click to reset
                document.getElementById('${sliderId}').addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    slider.setValue(${intDefaultValue});
                    slider.config.onChange(${intDefaultValue});
                });
            }, 0);
        </script>
    `;
    break;
```

---

### 4. Generator-Parameter Slider (~20min)

**Datei:** `src/static/js/player.js`

**Zeilen 993-1011** - Generator parameter rendering anpassen:

```javascript
// Render control based on parameter type
if (param.type === 'float' || param.type === 'int') {
    const step = param.step || (param.type === 'int' ? 1 : 0.01);
    const decimals = param.type === 'int' ? 0 : 2;
    const sliderId = `${paramId}_slider`;
    
    paramDiv.innerHTML = `
        <div class="mb-2">
            <label class="form-label d-flex justify-content-between">
                <span>${key}</span>
                <span id="${paramId}_value">${value.toFixed(decimals)}</span>
            </label>
            <div id="${sliderId}"></div>
        </div>
    `;
    
    setTimeout(() => {
        initTripleSlider(sliderId, {
            min: param.min || 0,
            max: param.max || 100,
            value: value,
            step: step,
            decimals: decimals,
            showRangeHandles: true,
            onChange: (val) => {
                document.getElementById('${paramId}_value').textContent = val.toFixed(decimals);
                updateGeneratorParam(key, val);
            }
        });
    }, 0);
} else if (param.type === 'bool') {
    // ... existing code ...
}
```

---

### 5. Optional: Bestehende Range-Inputs entfernen (~10min)

Falls gewünscht, können die alten `<input type="range">` Elemente vollständig entfernt werden:

- `src/static/artnet.html` Zeile 29 - Brightness Slider
- `src/static/editor.html` Zeile 107 - Point Count Slider
- `src/static/index.html` Zeile 107 - Point Count Slider
- `src/static/components/transition-menu.html` Zeile 35 - Duration Slider

**Jeder dieser Slider sollte durch einen Triple-Slider ersetzt werden.**

---

### 6. Testing (~30min)

#### Test-Checkliste:
- [ ] Effects Tab: Parameter-Slider funktionieren
- [ ] Player Tab: Generator-Parameter funktionieren
- [ ] Range Handles: Min/Max sind verschiebbar
- [ ] Value Handle: Bleibt innerhalb Range
- [ ] Right-Click Reset funktioniert
- [ ] Dark Mode: Styling korrekt
- [ ] Mobile/Touch: Drag & Drop funktioniert

---

## 🎯 Vorteile des neuen Sliders:

1. **Bessere UX**: Visuelles Feedback durch Range-Highlight
2. **Mehr Kontrolle**: User können Range dynamisch einschränken
3. **Konsistenz**: Ein Slider-Typ für alle Parameter
4. **Erweiterbar**: Einfach neue Features hinzufügen (z.B. Tooltips, Presets)

---

## 🔧 API-Dokumentation:

### Initialisierung:
```javascript
const slider = initTripleSlider('containerId', {
    min: 0,              // Absolute minimum
    max: 100,            // Absolute maximum
    value: 50,           // Current value
    rangeMin: 0,         // Range minimum (optional)
    rangeMax: 100,       // Range maximum (optional)
    step: 1,             // Value step
    decimals: 0,         // Decimal places for display
    showRangeHandles: true, // Show min/max handles
    readOnly: false,     // Disable dragging
    onChange: (val) => {}, // Value change callback
    onRangeChange: (min, max) => {} // Range change callback
});
```

### Public Methods:
```javascript
slider.setValue(50);           // Set current value
slider.getValue();             // Get current value
slider.setRange(20, 80);       // Set range limits
slider.getRange();             // Get { min, max }
slider.destroy();              // Cleanup
```

---

## 📝 Zusätzliche Optionen (später):

### Feature-Ideen für zukünftige Versionen:
1. **Preset-Buttons**: Quick-Select für häufige Werte
2. **Keyboard-Navigation**: Arrow-Keys für Feinsteuerung
3. **Double-Click Reset**: Doppelklick auf Default zurücksetzen
4. **Value Input Field**: Manuelle Eingabe per Textfeld
5. **Animation**: Smooth transitions bei setValue()
6. **Snap-To-Grid**: Magnetisches Snapping an Intervalle

---

## ⚠️ Breaking Changes:

**Keine!** Der neue Slider ist vollständig abwärtskompatibel.

Alte `<input type="range">` Slider können parallel existieren, bis alle ersetzt sind.

---

## 📚 Referenzen:

- Original Snippet: `snippets/SliderNew.html`
- Neue Komponente: `src/static/js/triple-slider.js`
- Styling: `src/static/css/triple-slider.css`
- Haupt-Integration: `effects.js`, `player.js`

---

## ✅ Status-Tracking:

- [x] Komponente erstellt (`triple-slider.js`)
- [x] Styling erstellt (`triple-slider.css`)
- [x] Dokumentation erstellt (dieses File)
- [ ] Integration in HTML-Templates
- [ ] Anpassung `effects.js`
- [ ] Anpassung `player.js`
- [ ] Generator-Parameter Update
- [ ] Testing
- [ ] Alte Slider entfernen (optional)

---

**Geschätzte Gesamtzeit: 2-3h**

**Nächster Schritt: HTML-Templates updaten (Schritt 1)**
