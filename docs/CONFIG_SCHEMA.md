# Configuration Schema

## Übersicht

Flux nutzt ein JSON-Schema zur automatischen Validierung der `config.json`. Dies stellt sicher, dass die Konfiguration korrekt ist und verhindert Fehler beim Start.

## Features

- ✅ **Automatische Validierung** beim Start und beim Speichern
- ✅ **JSON Schema Draft 7** Standard
- ✅ **Typ-Prüfung** für alle Werte (String, Integer, Boolean, Array)
- ✅ **Range-Validierung** (Min/Max Werte)
- ✅ **Pattern-Matching** für IPs und andere Strings
- ✅ **Custom-Validierung** für spezielle Regeln
- ✅ **Hilfreiche Fehlermeldungen** mit exakter Pfadangabe

## Schema-Module

### ConfigValidator

Hauptklasse für Validierung:

```python
from modules.config_schema import ConfigValidator

validator = ConfigValidator()

# Config validieren
is_valid, errors = validator.validate(config_dict)

if not is_valid:
    for error in errors:
        print(f"Fehler: {error}")

# Schema abrufen
schema = validator.get_schema()

# Default-Config generieren
default = validator.get_default_config()
```

## Validierungs-Regeln

### App Konfiguration (NEU v2.2)

```json
"app": {
  "default_player": "video",          // "video" oder "script"
  "console_log_level": "WARNING"      // DEBUG, INFO, WARNING, ERROR, CRITICAL
}
```

**Validierte Eigenschaften:**
- Log-Level aus erlaubten Werten
- Default-Player aus erlaubten Werten

**Verfügbare Log-Levels:**
- `DEBUG` - Alle Meldungen (sehr detailliert)
- `INFO` - Informationen + Warnungen + Fehler
- `WARNING` - Nur Warnungen und Fehler (Standard)
- `ERROR` - Nur Fehler
- `CRITICAL` - Nur kritische Fehler

### Art-Net Konfiguration

```json
"artnet": {
  "target_ip": "192.168.1.11",        // Muss gültige IPv4-Adresse sein
  "start_universe": 0,                // 0-32767
  "dmx_control_universe": 100,        // 0-32767
  "dmx_listen_port": 6454,            // 1-65535
  "fps": 60,                          // 1-120
  "bit_depth": 8,                     // 8 oder 16 (NEU v2.2)
  "delta_encoding": {                 // NEU v2.2
    "enabled": true,                  // Delta-Encoding aktivieren
    "threshold": 8,                   // Schwellwert für 8-bit (0-255)
    "threshold_16bit": 2048,          // Schwellwert für 16-bit (0-65535)
    "full_frame_interval": 30         // Full-Frame alle N Frames
  },
  "universe_configs": {
    "default": "RGB",                 // RGB, GRB, BGR, RBG, GBR, BRG
    "0": "GRB"                        // Pro Universum konfigurierbar
  }
}
```

**Validierte Eigenschaften:**
- IP-Adresse Format (xxx.xxx.xxx.xxx)
- Universe im gültigen Bereich
- Port im erlaubten Bereich
- Bit-Tiefe: 8 oder 16
- Delta-Encoding Threshold: 0-255 (8-bit) oder 0-65535 (16-bit)
- Full-Frame Intervall: >= 1
- RGB-Reihenfolge aus erlaubten Werten

**Delta-Encoding Details:**
- `enabled`: Aktiviert/deaktiviert Delta-Encoding (50-90% Netzwerk-Reduktion)
- `threshold`: Minimale Farbänderung für Update (höher = mehr gespart)
- `threshold_16bit`: Schwellwert für 16-bit LEDs
- `full_frame_interval`: Anzahl Frames zwischen Full-Frame Sync (verhindert Packet-Loss Artefakte)

### Video Konfiguration

```json
"video": {
  "extensions": [".mp4", ".avi"],    // Array von Strings
  "default_fps": 30,                 // 1-240 oder null
  "default_brightness": 100,         // 0-100
  "default_speed": 1.0,              // 0.1-10.0
  "gif_transparency_bg": [0, 0, 0]   // Array mit 3 Integers (0-255)
}
```

**Validierte Eigenschaften:**
- FPS im gültigen Bereich oder null
- Brightness als Prozent (0-100)
- Speed als Float
- GIF-Hintergrund als RGB-Array

### Pfad Konfiguration

```json
"paths": {
  "video_dir": "video",              // Erforderlich, nicht leer
  "data_dir": "data",                // Erforderlich, nicht leer
  "points_json": "punkte.json",      // Erforderlich
  "scripts_dir": "scripts",          // Optional
  "projects_dir": "PROJECTS"         // Optional
}
```

**Validierte Eigenschaften:**
- Erforderliche Felder vorhanden
- Keine leeren Strings für Pflichtfelder

### API Konfiguration

```json
"api": {
  "port": 5000,                      // 1-65535
  "host": "0.0.0.0",                 // String
  "console_log_maxlen": 500,         // 10-10000
  "status_broadcast_interval": 2     // 0.1-60 Sekunden
}
```

**Validierte Eigenschaften:**
- Port im gültigen Bereich
- Log-Länge sinnvoll begrenzt
- Broadcast-Intervall in vernünftigem Bereich

## API Endpoints

### GET /api/config/schema

Gibt das vollständige JSON-Schema zurück.

```bash
curl http://localhost:5000/api/config/schema
```

**Response:**
```json
{
  "status": "success",
  "schema": {
    "type": "object",
    "properties": { ... }
  }
}
```

### GET /api/config/default

Gibt Standard-Konfiguration zurück.

```bash
curl http://localhost:5000/api/config/default
```

**Response:**
```json
{
  "status": "success",
  "config": {
    "artnet": { ... },
    "video": { ... }
  }
}
```

### POST /api/config/validate

Validiert Konfiguration ohne zu speichern.

```bash
curl -X POST http://localhost:5000/api/config/validate \
  -H "Content-Type: application/json" \
  -d @config.json
```

**Response (Erfolg):**
```json
{
  "status": "success",
  "message": "Konfiguration ist valide",
  "valid": true,
  "errors": []
}
```

**Response (Fehler):**
```json
{
  "status": "error",
  "message": "Validierung fehlgeschlagen",
  "valid": false,
  "errors": [
    "artnet.target_ip: Ungültige IP-Adresse '300.168.1.1'",
    "video.default_brightness: 150 ist größer als maximum 100"
  ]
}
```

### POST /api/config

Speichert Konfiguration (mit automatischer Validierung).

```bash
curl -X POST http://localhost:5000/api/config \
  -H "Content-Type: application/json" \
  -d @config.json
```

Die Config wird vor dem Speichern automatisch validiert. Bei Fehlern wird nicht gespeichert.

## CLI Integration

Beim Start wird die Config automatisch validiert:

```bash
python src/main.py
```

**Erfolgreiche Validierung:**
```
✓ Konfiguration erfolgreich geladen und validiert
```

**Fehlgeschlagene Validierung:**
```
⚠️  Config-Validierung fehlgeschlagen:
    - artnet.target_ip: Ungültige IP-Adresse '999.999.999.999'
    - video.default_fps: 500 ist größer als maximum 240
⚠️  Verwende Standard-Konfiguration
```

Das System startet auch bei ungültiger Config (mit Default-Werten).

## Custom Validierungen

Zusätzlich zum Schema werden Custom-Validierungen durchgeführt:

1. **IP-Adresse Format**
   - Prüft ob xxx.xxx.xxx.xxx Format
   - Jedes Oktett 0-255

2. **Pfad-Validierung**
   - Pflichtfelder nicht leer
   - Pfade existieren (Warning, kein Error)

3. **Channel-Mathematik**
   - `max_per_universe` teilbar durch `channels_per_point`
   - Warning wenn nicht optimal

4. **RGB-Reihenfolge**
   - Nur erlaubte Permutationen
   - Prüfung aller universe_configs Einträge

## Fehlermeldungs-Format

Fehlermeldungen folgen dem Schema: `pfad.zur.property: Fehlerbeschreibung`

**Beispiele:**
```
artnet.target_ip: Ungültige IP-Adresse '300.1.1.1'
video.default_brightness: 150 ist größer als maximum 100
paths.video_dir: Darf nicht leer sein
artnet.universe_configs.0: Ungültige RGB-Reihenfolge 'XYZ'
```

## Migration von alter Config

Falls eine alte config.json nicht validiert:

1. **Backup erstellen:**
   ```bash
   cp config.json config.json.old
   ```

2. **Default generieren:**
   ```bash
   curl http://localhost:5000/api/config/default > config_new.json
   ```

3. **Manuell anpassen:**
   - Alte Werte in neue Config übertragen
   - Neue Felder mit sinnvollen Werten füllen

4. **Validieren:**
   ```bash
   curl -X POST http://localhost:5000/api/config/validate \
     -H "Content-Type: application/json" \
     -d @config_new.json
   ```

5. **Speichern:**
   ```bash
   mv config_new.json config.json
   ```

## Schema erweitern

Neue Properties zum Schema hinzufügen:

```python
# In config_schema.py

CONFIG_SCHEMA = {
    "properties": {
        "neue_sektion": {
            "type": "object",
            "properties": {
                "neue_property": {
                    "type": "string",
                    "description": "Beschreibung"
                }
            }
        }
    }
}
```

**Custom Validierung hinzufügen:**

```python
def _custom_validations(self, config):
    errors = []
    
    # Neue Validierung
    if "neue_sektion" in config:
        wert = config["neue_sektion"].get("neue_property")
        if wert and not wert.startswith("test_"):
            errors.append("neue_sektion.neue_property: Muss mit 'test_' beginnen")
    
    return errors
```

## Best Practices

### 1. Validiere vor dem Deployment

```bash
# Lokale Validierung
python -c "
from src.modules.config_schema import validate_config_file
is_valid, errors, _ = validate_config_file('config.json')
if not is_valid:
    print('FEHLER:', errors)
    exit(1)
print('OK')
"
```

### 2. Nutze Default-Config als Vorlage

```bash
curl http://localhost:5000/api/config/default | jq . > config_template.json
```

### 3. Versioniere Config-Schema

Wenn Breaking Changes am Schema gemacht werden:
- Erhöhe Version in Schema
- Implementiere Migration-Logik
- Dokumentiere Changes

### 4. Teste neue Config-Werte

Nach Änderungen:
1. Validiere (`/api/config/validate`)
2. Speichere (automatisches Backup)
3. Starte neu und prüfe Logs
4. Bei Problemen: Restore von Backup

## Troubleshooting

### jsonschema nicht verfügbar

```
WARNING - jsonschema nicht installiert - Schema-Validierung deaktiviert
```

**Lösung:**
```bash
pip install jsonschema>=4.17.0
```

### Validation wird übersprungen

Wenn jsonschema fehlt, läuft System ohne Validierung weiter (mit Warning).

### Fehlermeldungen zu streng

Schema kann in `config_schema.py` angepasst werden:
- `minimum`/`maximum` Werte ändern
- `required` Felder entfernen
- Neue Patterns erlauben

### Config wird nicht geladen

1. Prüfe Syntax: `python -m json.tool config.json`
2. Prüfe Pfad: `ls -la config.json`
3. Prüfe Encoding: UTF-8 erforderlich
4. Prüfe Logs für Details

## Zusammenfassung

Das Config-Schema:
- ✅ Verhindert ungültige Konfigurationen
- ✅ Gibt hilfreiche Fehlermeldungen
- ✅ Funktioniert auch ohne jsonschema (mit Warning)
- ✅ Ist über API abrufbar
- ✅ Unterstützt Custom-Validierungen
- ✅ Erstellt automatisch Backups
- ✅ Ist einfach erweiterbar
