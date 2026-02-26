# Performance Benchmarking - Integration Guide

Dieses Dokument beschreibt die Schritte zur Integration des Performance-Benchmarking-Systems in das bestehende Py_artnet Backend.

## ✅ Bereits erstellt

Die folgenden Dateien wurden bereits erstellt:

### Backend
- `src/modules/performance/__init__.py` - Package initialization
- `src/modules/performance/monitor.py` - Core performance monitor
- `src/modules/api/performance.py` - API endpoints

### Frontend
- `frontend/css/performance-overlay.css` - Overlay styling
- `frontend/js/performance-overlay.js` - Overlay controller

## 🔧 Integration Steps

### 1. API Routes registrieren

**Datei**: `src/main.py` (oder wo Flask app erstellt wird)

```python
# Import performance routes
from modules.api.performance import register_performance_routes

# Nach Flask app Erstellung:
app = Flask(__name__)

# ... andere routes ...

# Register performance monitoring routes
register_performance_routes(app)
```

### 2. Frontend-Dateien einbinden

**Datei**: `frontend/index.html` (oder main player page)

Im `<head>`:
```html
<!-- Performance Overlay CSS -->
<link rel="stylesheet" href="css/performance-overlay.css">
```

Vor dem schließenden `</body>`:
```html
<!-- Performance Overlay Script -->
<script src="js/performance-overlay.js"></script>
```

### 3. Player Core Integration (OPTIONAL)

**Datei**: `src/modules/player/core.py`

Am Anfang der Datei importieren:
```python
from ..performance.monitor import get_performance_monitor
```

In der `_play_loop()` Methode (ca. Zeile 1000):

```python
def _play_loop(self):
    """Haupt-Wiedergabeschleife (läuft in separatem Thread)."""
    
    # HINZUFÜGEN: Performance Monitor
    perf_monitor = get_performance_monitor()
    
    # ... bestehender Code ...
    
    while self.is_running and self.is_playing:
        # HINZUFÜGEN: Measure total frame time
        with perf_monitor.measure("player.frame_total"):
            
            # ... bestehender Frame-Processing Code ...
            
            # BEISPIEL: Measure specific operations
            with perf_monitor.measure("player.get_frame"):
                if self.layers:
                    frame, source_delay = self.layers[0].source.get_next_frame()
                else:
                    frame, source_delay = self.source.get_next_frame()
            
            # BEISPIEL: Measure effects
            with perf_monitor.measure("player.apply_effects"):
                frame_for_video_preview = self.effect_processor.apply_effects(
                    frame, chain_type='video', player_name=self.player_name
                )
        
        # HINZUFÜGEN: Mark frame complete
        perf_monitor.measure_frame_complete()
```

### 4. Effect Processor Integration (OPTIONAL)

**Datei**: `src/modules/player/effects/processor.py`

```python
from ...performance.monitor import get_performance_monitor

def apply_effects(self, frame, chain_type='video', player_name='Player'):
    """Apply effects to frame with performance tracking"""
    perf_monitor = get_performance_monitor()
    
    chain = self.artnet_effect_chain if chain_type == 'artnet' else self.video_effect_chain
    
    for effect_data in chain:
        if not effect_data.get('enabled', True):
            continue
        
        effect_name = effect_data['id']
        instance = effect_data['instance']
        
        # Measure individual effect
        with perf_monitor.measure(f"effect.{chain_type}.{effect_name}"):
            frame = instance.process_frame(frame, **effect_data.get('config', {}))
    
    return frame
```

### 5. Layer Manager Integration (OPTIONAL)

**Datei**: `src/modules/player/layers/manager.py`

```python
from ...performance.monitor import get_performance_monitor

def apply_layer_effects(self, layer, frame, player_name):
    """Apply layer effects with performance tracking"""
    perf_monitor = get_performance_monitor()
    
    for effect in layer.effects:
        if not effect.get('enabled', True):
            continue
        
        effect_name = effect['id']
        
        with perf_monitor.measure(f"layer.L{layer.layer_id}.effect.{effect_name}"):
            frame = effect['instance'].process_frame(frame, **effect.get('config', {}))
    
    return frame
```

## 🎯 Verwendung

### Via Keyboard (empfohlen)
1. Player starten
2. Taste **B** drücken
3. Overlay erscheint oben rechts
4. Zeigt FPS, Frame-Time, und Performance-Breakdown
5. Erneut **B** drücken zum Ausblenden

### Via API
```bash
# Enable
curl -X POST http://localhost:5000/api/performance/enable \
  -H "Content-Type: application/json" \
  -d '{"enable": true}'

# Get stats
curl http://localhost:5000/api/performance/stats

# Reset
curl -X POST http://localhost:5000/api/performance/reset

# Disable
curl -X POST http://localhost:5000/api/performance/enable \
  -H "Content-Type: application/json" \
  -d '{"enable": false}'
```

## 📊 Beispiel-Ausgabe

```json
{
    "enabled": true,
    "fps": 59.8,
    "frame_count": 1200,
    "uptime": 20.05,
    "total_frame_time_ms": 14.523,
    "target_frame_time_ms": 33.33,
    "metrics": {
        "player.get_frame": {
            "avg_ms": 5.234,
            "min_ms": 3.123,
            "max_ms": 12.456,
            "calls": 1200,
            "percentage": 36.0
        },
        "player.apply_effects": {
            "avg_ms": 3.456,
            "min_ms": 2.234,
            "max_ms": 8.123,
            "calls": 1200,
            "percentage": 23.8
        }
    }
}
```

## 🔍 Measurement Guidelines

### Was messen?
- ✅ Frame generation (`player.get_frame`)
- ✅ Effect application (`player.apply_effects`, `effect.video.*`, `effect.artnet.*`)
- ✅ Layer compositing (`player.layers.L*.blend`)
- ✅ Brightness adjustment (`player.brightness`)
- ✅ DMX extraction (`player.dmx_extraction`)
- ✅ Art-Net send (`player.artnet_send`)

### Naming Convention
- `player.*` - Core player operations
- `player.layers.L{id}.*` - Layer-specific operations
- `effect.{chain}.{name}` - Effect operations
- `layer.L{id}.effect.{name}` - Layer effect operations

### Best Practices
1. **Nur kritische Pfade messen** - Zu viele Messungen = Overhead
2. **Aussagekräftige Namen** - Klar und konsistent
3. **Nested measurements vermeiden** - Kann zu doppelter Zählung führen
4. **Optional halten** - User kann bei Bedarf aktivieren

## ⚠️ Performance Impact

Erwarteter Overhead (bei aktiviertem Monitoring):
- Pro Messung: ~0.13ms
- Pro Frame (15 Messungen): ~0.4ms
- Bei 30 FPS (33.33ms Budget): **1.2% Overhead**

✅ **Akzeptabel für Debug/Profiling**

## 🐛 Troubleshooting

### Overlay erscheint nicht
- Prüfe Browser Console auf Fehler
- Prüfe ob `performance-overlay.js` geladen wurde
- Prüfe ob API-Endpoints registriert sind

### Keine Daten im Overlay
- Prüfe ob Backend Messungen durchführt
- Prüfe API Response: `curl http://localhost:5000/api/performance/stats`
- Prüfe ob `perf_monitor.measure()` aufgerufen wird

### Performance zu langsam
- Reduziere Anzahl der Messungen
- Erhöhe Update-Interval im Frontend (z.B. 1000ms statt 500ms)
- Deaktiviere Monitoring wenn nicht benötigt

## 📝 Nächste Schritte

1. ✅ API Routes registrieren (Schritt 1)
2. ✅ Frontend-Dateien einbinden (Schritt 2)
3. 🔄 Player Core Integration (Schritt 3) - OPTIONAL aber empfohlen
4. 🔄 Effect/Layer Integration (Schritte 4-5) - OPTIONAL
5. 🧪 Testen mit Taste 'B'

## 📚 Weitere Dokumentation

Siehe [PERFORMANCE_BENCHMARKING.md](./PERFORMANCE_BENCHMARKING.md) für:
- Vollständige Architektur
- Implementation Details
- Beispiel-Code
- Future Enhancements
