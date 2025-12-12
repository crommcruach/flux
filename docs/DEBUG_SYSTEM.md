# Debug-System Dokumentation

## Überblick

Das Debug-System ermöglicht granulare Kontrolle über Log-Ausgaben zur Laufzeit. Anstatt alle Debug-Logs zu entfernen oder auskommentieren zu müssen, können Sie Debug-Kategorien aktivieren/deaktivieren.

## Debug-Kategorien

Verfügbare Kategorien:
- **transport** - Transport Plugin (Position, Loop, Speed, Trim)
- **effects** - Effect Processing
- **layers** - Layer Compositing & Management
- **playback** - Playback Loop, Frame Fetch
- **api** - API Calls & Responses
- **websocket** - WebSocket Communication
- **artnet** - Art-Net Output
- **performance** - Performance Metriken
- **cache** - Cache-Operationen

## Verwendung im Code

### Import
```python
from .logger import get_logger, debug_transport, debug_layers, debug_playback, debug_effects
```

### Bedingte Debug-Logs

Statt:
```python
logger.debug(f"🎯 Transport pre-set frame to {next_frame}")
```

Verwenden:
```python
debug_transport(logger, f"🎯 Transport pre-set frame to {next_frame}")
```

Die Log-Ausgabe erfolgt nur, wenn die Kategorie `transport` aktiviert ist.

### Formatierung

Unterstützt % und .format() Syntax:
```python
debug_transport(logger, "Frame %d, position=%s", frame, position)
debug_layers(logger, "Layer {id} blend={mode}", id=layer_id, mode=blend_mode)
```

## API-Kontrolle

### Alle Kategorien anzeigen
```bash
curl http://localhost:5000/api/debug/categories
```

Response:
```json
{
  "categories": [
    {"name": "transport", "enabled": false},
    {"name": "effects", "enabled": false},
    ...
  ],
  "total": 9,
  "enabled_count": 0
}
```

### Kategorien aktivieren
```bash
curl -X POST http://localhost:5000/api/debug/categories/enable \
  -H "Content-Type: application/json" \
  -d '{"categories": ["transport", "layers"]}'
```

Alle aktivieren:
```bash
curl -X POST http://localhost:5000/api/debug/categories/enable \
  -H "Content-Type: application/json" \
  -d '{"categories": ["all"]}'
```

### Kategorien deaktivieren
```bash
curl -X POST http://localhost:5000/api/debug/categories/disable \
  -H "Content-Type: application/json" \
  -d '{"categories": ["transport"]}'
```

Alle deaktivieren:
```bash
curl -X POST http://localhost:5000/api/debug/categories/disable \
  -H "Content-Type: application/json" \
  -d '{"categories": ["all"]}'
```

### Kategorie umschalten
```bash
curl -X POST http://localhost:5000/api/debug/categories/toggle \
  -H "Content-Type: application/json" \
  -d '{"category": "transport"}'
```

## Programmierung

### Initialisierung (in main.py oder config)
```python
from modules.logger import DebugCategories

# Standard: Alle deaktiviert
DebugCategories.initialize()

# Oder: Bestimmte Kategorien aktivieren
DebugCategories.initialize(['transport', 'layers'])
```

### Zur Laufzeit steuern
```python
from modules.logger import DebugCategories

# Einzelne Kategorien
DebugCategories.enable('transport', 'layers')
DebugCategories.disable('api')

# Alle
DebugCategories.enable_all()
DebugCategories.disable_all()

# Status prüfen
if DebugCategories.is_enabled('transport'):
    # ...
```

## Convenience-Funktionen

```python
debug_transport(logger, msg, *args)  # Transport debugging
debug_effects(logger, msg, *args)    # Effects debugging
debug_layers(logger, msg, *args)     # Layer debugging
debug_playback(logger, msg, *args)   # Playback debugging
```

## Migration bestehender Logs

### Vorher
```python
logger.debug(f"🎬 Transport initialized: out_point={out_point}")
logger.debug(f"🎨 Layer {id} composited with {mode}")
```

### Nachher
```python
debug_transport(logger, f"🎬 Transport initialized: out_point={out_point}")
debug_layers(logger, f"🎨 Layer {id} composited with {mode}")
```

## Best Practices

1. **INFO-Logs bleiben**: Wichtige Status-Meldungen sollten INFO bleiben
2. **DEBUG für Details**: Nur detaillierte Ablauf-Informationen als bedingte Debug-Logs
3. **Kategorien konsistent**: Gleiche Funktionalität = gleiche Kategorie
4. **Performance**: Debug-Logs haben minimal Overhead wenn deaktiviert

## Vorteile

✅ Logs bleiben im Code (keine Kommentare/Entfernen nötig)
✅ Zur Laufzeit steuerbar (keine Code-Änderungen)
✅ API-gesteuert (Frontend-Integration möglich)
✅ Minimal Overhead bei deaktivierten Kategorien
✅ Log-Datei enthält weiterhin alles (Forensik)
✅ Konsole bleibt übersichtlich
