# Flux Logging System

## Übersicht

Das Logging-System bietet strukturierte, mehrstufige Protokollierung für die gesamte Flux-Anwendung.

## Features

- **Automatische Log-Rotation**: Maximale Dateigröße 10 MB, 5 Backup-Dateien
- **Dual-Output**: Logs sowohl in Datei als auch Konsole
- **Verschiedene Log-Level**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Strukturierte Logs**: Timestamp, Level, Modul, Funktion, Zeilennummer
- **Externe Bibliotheken gedämpft**: Flask/SocketIO Ausgaben reduziert

## Verwendung

### Grundlegende Integration

```python
from modules.logger import get_logger

logger = get_logger(__name__)

# Verschiedene Log-Level
logger.debug("Detaillierte Debug-Information")
logger.info("Normale Information")
logger.warning("Warnung - etwas ist ungewöhnlich")
logger.error("Fehler aufgetreten")
logger.critical("Kritischer Fehler!")
```

### Mit Exception-Info

```python
try:
    # Code der fehlschlagen könnte
    result = risky_operation()
except Exception as e:
    logger.error(f"Operation fehlgeschlagen: {e}", exc_info=True)
    # exc_info=True fügt vollständigen Stack-Trace hinzu
```

### Hilfs-Funktionen

```python
from modules.logger import (
    log_function_call,
    log_performance,
    log_video_info,
    log_cache_operation,
    log_artnet_output
)

# Funktionsaufruf loggen
log_function_call(logger, "load_video", path="/path/to/video.mp4", fps=30)

# Performance messen
import time
start = time.time()
# ... Operation ...
duration_ms = (time.time() - start) * 1000
log_performance(logger, "video_decode", duration_ms)

# Video-Info strukturiert
log_video_info(logger, video_path, frames=1000, fps=30.0, dimensions=(1920, 1080))

# Cache-Operationen
log_cache_operation(logger, "save", video_hash, success=True, details="5.2 MB")

# Art-Net Output
log_artnet_output(logger, universe=1, channel_count=510, first_values=[255, 128, 64])
```

## Log-Dateien

Logs werden gespeichert in: `logs/flux_YYYYMMDD_HHMMSS.log`

### Datei-Format (detailliert)
```
2025-11-16 14:30:45 | INFO     | main | main:78 | Flux startet...
2025-11-16 14:30:45 | INFO     | main | main:82 | Konfiguration geladen
2025-11-16 14:30:46 | INFO     | video_player | __init__:45 | VideoPlayer initialisiert
2025-11-16 14:30:46 | DEBUG    | video_player | _load_cache:310 | Lade RGB-Cache: test_abc123.cache
2025-11-16 14:30:47 | INFO     | video_player | _load_cache:320 | Cache geladen: 900 Frames, 5.2 MB
2025-11-16 14:30:50 | WARNING  | rest_api | start:145 | API-Server läuft bereits
2025-11-16 14:31:05 | ERROR    | video_player | play:550 | Fehler beim Abspielen: Video nicht gefunden
```

### Konsolen-Format (kompakt)
```
INFO     | main | Flux startet...
INFO     | main | Konfiguration geladen
WARNING  | rest_api | API-Server läuft bereits
ERROR    | video_player | Fehler beim Abspielen: Video nicht gefunden
```

## Konfiguration

### Log-Level ändern

```python
from modules.logger import FluxLogger
import logging

# Bei Startup in main.py
flux_logger = FluxLogger()
flux_logger.setup_logging(log_level=logging.DEBUG)  # Alle Details loggen
```

### Log-Verzeichnis ändern

```python
flux_logger.setup_logging(log_dir='custom_logs')
```

## Best Practices

1. **Logger pro Modul**: Jedes Modul sollte seinen eigenen Logger haben
   ```python
   logger = get_logger(__name__)
   ```

2. **Richtige Log-Level wählen**:
   - `DEBUG`: Detaillierte Informationen für Entwicklung
   - `INFO`: Wichtige Ereignisse (Start, Stop, Config-Änderungen)
   - `WARNING`: Unerwartete Situationen, aber weiter lauffähig
   - `ERROR`: Fehler, die eine Operation abbrechen
   - `CRITICAL`: Schwere Fehler, die App-Absturz verursachen könnten

3. **Sensible Daten vermeiden**: Keine Passwörter, API-Keys etc. loggen

4. **Kontext liefern**: Genug Information für Debugging
   ```python
   logger.error(f"Video nicht gefunden: {video_path}")  # Gut
   logger.error("Video nicht gefunden")  # Schlecht - welches Video?
   ```

5. **Exception-Info nutzen**: Immer `exc_info=True` bei Fehler-Handling
   ```python
   except Exception as e:
       logger.error(f"Fehler: {e}", exc_info=True)
   ```

## Integration Status

Logging ist bereits integriert in:
- ✅ `main.py` - Startup und Konfiguration
- ✅ `video_player.py` - Cache-Operationen
- ✅ `rest_api.py` - API-Start
- ✅ `dmx_controller.py` - DMX-Empfang

## Fehlersuche mit Logs

### Cache-Probleme debuggen
```bash
# Suche nach Cache-Fehlern
grep "Cache" logs/flux_*.log
grep "ERROR.*cache" logs/flux_*.log
```

### Performance-Probleme finden
```bash
# Suche nach langsamen Operationen (>1s)
grep "Performance.*>1s" logs/flux_*.log
```

### API-Probleme
```bash
# API-bezogene Logs
grep "rest_api" logs/flux_*.log
```

### Vollständiger Error-Report
```bash
# Alle Fehler und Warnungen
grep -E "ERROR|WARNING|CRITICAL" logs/flux_*.log
```
