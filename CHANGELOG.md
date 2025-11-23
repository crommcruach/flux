# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

---

## [2.2.0] - 2025-11-23

### 🚀 Performance-Optimierungen (55-75% CPU-Reduktion)

#### Hinzugefügt
- **NumPy-Vektorisierung Stream-Loops** - 40-60% CPU-Reduktion durch fancy indexing
- **Zero-Copy Frames** - 15-20% CPU-Reduktion durch Entfernung redundanter Frame-Kopien
- **Hardware Channel-Reordering** - 5-10% CPU-Reduktion durch NumPy statt Python-Loops
- **Lock-Free Statistics** - 2-5% CPU-Reduktion durch atomic Counters
- **Event-basierte Synchronisation** - <1ms Pause-Latenz (vorher 100ms)
- **Gradient Pattern Cache** - 1-3ms pro Generation gespart
- **Memory-Safe Recording** - Deque-basierte Recording verhindert 195MB Memory-Leak nach 1h

### 🌐 Art-Net Delta-Encoding (50-90% Netzwerk-Reduktion)

#### Hinzugefügt
- **Delta-Encoding System** - Intelligente Differenz-Übertragung für Art-Net
  - Threshold-basierte Pixel-Änderungserkennung
  - NumPy-optimierte Differenz-Berechnung
  - 50-90% Netzwerk-Traffic Reduktion bei statischen Szenen
  - 20-40% Reduktion bei langsamen Videos
- **8-bit und 16-bit LED Support**
  - `bit_depth` Config: 8 (Standard) oder 16 (High-End)
  - Separate Threshold-Werte für beide Modi
- **Full-Frame Sync** - Periodisches Full-Frame senden verhindert Packet-Loss Artefakte
- **Runtime-Steuerung**
  - CLI-Befehle: `delta on/off/status/threshold/interval`
  - REST API: `POST /api/artnet/delta-encoding`
  - Info Endpoint: `GET /api/artnet/info` zeigt delta_encoding Status
- **Config-Parameter**
  - `delta_encoding.enabled` - Aktivieren/Deaktivieren
  - `delta_encoding.threshold` - Schwellwert für 8-bit LEDs (Standard: 8)
  - `delta_encoding.threshold_16bit` - Schwellwert für 16-bit LEDs (Standard: 2048)
  - `delta_encoding.full_frame_interval` - Full-Frame alle N Frames (Standard: 30)

### 🐛 Bugfixes

#### Behoben
- **Art-Net Reaktivierung** - `is_active` Flag wird jetzt korrekt in `start()` gesetzt
  - Problem: Art-Net blieb inaktiv nach Player stop/start
  - Lösung: `artnet_manager.is_active = True` in player.py Zeile 186

### 🔧 CLI Debug-Modus

#### Hinzugefügt
- **Console-Log-Level Steuerung**
  - Config: `app.console_log_level` (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  - Standard: `WARNING` (nur Warnungen und Fehler auf Console)
  - CLI-Befehle: `debug on/off/verbose/status`
  - Runtime-Umschaltung ohne Restart
  - Log-Datei enthält immer alle Meldungen

#### CLI-Befehle
```bash
debug                     # Status anzeigen
debug off                 # Nur Warnings & Errors (Standard)
debug on                  # INFO + Warnings + Errors
debug verbose             # Alle Meldungen inkl. DEBUG
```

### 📚 Dokumentation

#### Hinzugefügt
- **docs/PERFORMANCE.md** - Detaillierte Performance-Optimierungs-Dokumentation
  - Benchmarks mit Messwerten
  - Vor/Nachher-Vergleiche
  - A/B Testing Guide
- **docs/DELTA_ENCODING.md** - Technische Delta-Encoding Dokumentation
  - Funktionsweise und Algorithmus
  - Konfiguration und Runtime-Steuerung
  - Empfohlene Einstellungen nach Szenario
  - Troubleshooting Guide
  - Performance-Messungen
- **docs/USAGE.md** - Aktualisiert mit:
  - Art-Net Delta-Encoding Sektion
  - CLI Debug-Modus Anleitung
- **docs/CONFIG_SCHEMA.md** - Aktualisiert mit:
  - `app.console_log_level` Parameter
  - `artnet.bit_depth` Parameter
  - `artnet.delta_encoding` Sektion
- **README.md** - Aktualisiert mit:
  - Performance v2.2 Features
  - Delta-Encoding Highlights
  - CLI Debug-Befehle
  - Art-Net API Endpoints

### 🔄 Geändert

#### REST API
- **GET /api/artnet/info** - Erweitert um `delta_encoding` Objekt
  ```json
  {
    "delta_encoding": {
      "enabled": true,
      "threshold": 8,
      "bit_depth": 8,
      "full_frame_interval": 30,
      "frame_counter": 1247
    }
  }
  ```
- **POST /api/artnet/delta-encoding** (NEU) - Runtime-Konfiguration
  ```json
  {
    "enabled": true,
    "threshold": 15,
    "full_frame_interval": 60
  }
  ```

#### Konfiguration
- **config.json** - Neue Standardeinstellungen:
  ```json
  {
    "app": {
      "console_log_level": "WARNING"
    },
    "artnet": {
      "bit_depth": 8,
      "delta_encoding": {
        "enabled": true,
        "threshold": 8,
        "threshold_16bit": 2048,
        "full_frame_interval": 30
      }
    }
  }
  ```

### 📊 Performance-Metriken

#### Benchmarks (300 LEDs, 8-bit, 30 FPS)

| Szenario | Vorher CPU | Nachher CPU | Vorher Netzwerk | Nachher Netzwerk |
|----------|------------|-------------|-----------------|------------------|
| Statisches Testbild | 45% | 12% (-73%) | 1.2 Mbps | 0.15 Mbps (-87%) |
| Langsames Video | 52% | 18% (-65%) | 1.2 Mbps | 0.6 Mbps (-50%) |
| Schnelles Video | 58% | 22% (-62%) | 1.2 Mbps | 0.9 Mbps (-25%) |

**Gesamt-Performance-Gewinn:** ~55-75% CPU-Reduktion, 50-90% Netzwerk-Reduktion (statische Szenen)

### ⚠️ Breaking Changes

Keine! Version 2.2 ist vollständig rückwärtskompatibel.

### 🔄 Migration von v2.1

Keine Änderungen erforderlich. Alte `config.json` Dateien funktionieren weiterhin.

**Empfohlene Schritte:**
1. Füge `app.console_log_level: "WARNING"` zur config.json hinzu (optional)
2. Füge `artnet.delta_encoding` Sektion hinzu (optional, Defaults werden verwendet)
3. Teste Delta-Encoding: `delta status` → `delta on`

---

## [2.1.0] - 2025-11-17

### Hinzugefügt
- **Unified Player Architecture** - Single Player für alle Media-Typen
- **Frame Source Pattern** - Austauschbare Frame-Quellen (Video, Script, Stream)
- **Hot Source Switching** - Wechsel zwischen Quellen ohne Player-Neustart
- **Player Manager** - Zentrale Player-Verwaltung
- **Command Executor** - Unified Command-Handling für CLI und Web Console

### Geändert
- Alte VideoPlayer/ScriptPlayer eliminiert (90% Code-Reduktion)
- API-Routen vereinheitlicht
- CLI-Handler refactored für bessere Wartbarkeit

---

## [2.0.0] - 2025-11-10

### Hinzugefügt
- **Web-Interface** - Bootstrap-basiertes GUI mit Canvas Editor
- **REST API** - Flask-basierte API mit WebSocket Support
- **Dynamic Config UI** - Web-basierte config.json Verwaltung
- **Server-Projektverwaltung** - Projekte speichern/laden/löschen im Backend
- **Multi-JSON Support** - Flexible Punkte-Konfigurationen
- **Dark Mode** - Theme-System mit LocalStorage
- **Toast-Benachrichtigungen** - Theme-aware Notifications

### Geändert
- Von CLI-only zu Hybrid (CLI + Web)
- Projekt-Struktur umorganisiert (modules/)
- Config-System erweitert

---

## [1.5.0] - 2025-10-15

### Hinzugefügt
- **Script Generator** - Prozedurale Grafiken via Python
- **RGB Cache System** - msgpack-basiertes Caching
- **GIF Support** - Animated GIFs mit Transparenz
- **DMX Input Control** - 9-Kanal Steuerung

### Geändert
- Performance-Verbesserungen für Video-Playback
- Hardware-Beschleunigung für OpenCV

---

## [1.0.0] - 2025-09-01

### Hinzugefügt
- Initial Release
- **Video Playback** - OpenCV-basierte Video-Wiedergabe
- **Art-Net Output** - Multi-Universe Support
- **RGB Channel Mapping** - Konfigurierbare Kanal-Reihenfolge
- **CLI Interface** - Kommandozeilen-Steuerung
- **Points-System** - JSON-basierte LED-Konfiguration

---

## Legende

- 🚀 Performance
- 🌐 Netzwerk
- 🐛 Bugfix
- 🔧 Konfiguration
- 📚 Dokumentation
- 🔄 Geändert
- ⚠️ Breaking Change
- 📊 Metriken
