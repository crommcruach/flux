# Reusable UI Components

Dieses Verzeichnis enthält wiederverwendbare UI-Komponenten, die in mehreren Seiten verwendet werden können.

## Toast Notifications

### Verwendung

**Automatisches Laden (empfohlen):**
```html
<!-- Im HTML Head oder vor dem schließenden </body> Tag -->
<script src="js/toast-loader.js"></script>
```

**Manuelles Einbinden:**
```html
<!-- Alternative: Direktes Include (wenn unterstützt) -->
<div id="toast-container-wrapper"></div>
<script>
    fetch('/static/components/toast.html')
        .then(r => r.text())
        .then(html => {
            document.getElementById('toast-container-wrapper').innerHTML = html;
        });
</script>
```

### JavaScript API

Die Toast-Funktionalität wird über `common.js` bereitgestellt:

```javascript
import { showToast } from './common.js';

// Erfolg (grün)
showToast('Operation erfolgreich!', 'success', 3000);

// Fehler (rot)
showToast('Ein Fehler ist aufgetreten', 'error', 5000);

// Info (blau)
showToast('Informative Nachricht', 'info', 3000);

// Warnung (gelb)
showToast('Achtung!', 'warning', 4000);
```

### Styling anpassen

Alle Toast-Styles befinden sich in `components/toast.html`. Änderungen dort werden automatisch auf alle Seiten angewendet.

**CSS-Variablen für Theme-Anpassung:**
- `--bg-secondary`: Hintergrundfarbe
- `--border-color`: Rahmenfarbe
- `--text-primary`: Textfarbe
- `--text-secondary`: Sekundäre Textfarbe

### Vorteile der zentralisierten Komponente

✅ **Single Source of Truth**: Alle Änderungen an einem Ort  
✅ **Konsistentes Design**: Gleiche Toast-Darstellung auf allen Seiten  
✅ **Wartbarkeit**: Keine Code-Duplikation mehr  
✅ **Einfache Updates**: Nur eine Datei ändern statt 5+  

## Weitere Komponenten

Weitere wiederverwendbare Komponenten können hier nach dem gleichen Muster hinzugefügt werden:

- Modals
- Loading Spinner
- Alert Boxes
- Navigation Bars
