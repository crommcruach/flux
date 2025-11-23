# Py_artnet - Version History

## v2.2 - Performance-Optimierungen (2025-11-23)

### Performance-Features
- ✓ **NumPy-Vektorisierung Stream-Loops** - 40-60% CPU-Reduktion
- ✓ **Redundante Frame-Copies entfernt** - 15-20% CPU-Reduktion  
- ✓ **NumPy Channel-Reordering** - 5-10% CPU-Reduktion
- ✓ **Gradient-Pattern Cache** - 1-3ms pro Generation gespart
- ✓ **Memory Leak Prevention** - Deque-basierte Recording (verhindert 195MB nach 1h)
- ✓ **Event-basierte Synchronisation** - Sofortige Pause/Resume
- ✓ **Lock-free Stats** - Atomic Counters, 2-5% CPU-Reduktion

### Art-Net Delta-Encoding
- ✓ **LED Bit-Tiefe Unterstützung** - 8-bit und 16-bit Modi
- ✓ **Basic Delta-Encoding** - Threshold-basierte Differenz-Erkennung
- ✓ **Full-Frame Sync** - Periodische komplette Updates (alle N Frames)
- ✓ **Runtime Controls** - CLI/API-Befehle für delta on/off/status/threshold/interval

### Weitere Features
- ✓ **CLI Debug-Modus** - Konfigurierbares Console-Logging (config.json: console_log_level)
- ✓ **Art-Net Reaktivierung Bugfix** - `is_active` wird in start() korrekt gesetzt

### Messergebnisse
- **Gesamt-Performance-Gewinn:** ~55-75% CPU-Reduktion, 50-90% Netzwerk-Reduktion (statische Szenen)
- **Delta-Encoding (300 LEDs, 8-bit, 30 FPS):**
  - Statisches Testbild: 87% Netzwerk-Reduktion (1.2 Mbps → 0.15 Mbps)
  - Langsames Video: 50% Netzwerk-Reduktion (1.2 Mbps → 0.6 Mbps)
  - Schnelles Video: 25% Netzwerk-Reduktion (1.2 Mbps → 0.9 Mbps)
  - CPU-Overhead: 0-5% (NumPy-optimiert)
  - Memory: ~6 MB für last_sent_frame Buffer

### Dokumentation
- ✓ docs/DELTA_ENCODING.md - Vollständige technische Dokumentation
- ✓ docs/PERFORMANCE.md - Performance-Metriken und Benchmarks
- ✓ docs/USAGE.md - Art-Net Optimierung Sektion
- ✓ CHANGELOG.md - Version 2.2.0 Release Notes

---

## v2.1 - Architecture Refactoring (2025-11-22)

### PlayerManager Refactoring
- **Problem:** DMXController wurde als Player-Container missbraucht
  - Verletzt Single Responsibility Principle
  - Namens-Verwirrung: Module nutzten `dmx_controller` nur für `player`-Zugriff
  - Zirkuläre Abhängigkeiten und Code-Duplikation

- **Lösung:** PlayerManager-Klasse eingeführt
  - Zentraler Player-Container (Single Source of Truth)
  - DMXController bleibt rein für DMX-Input zuständig
  - Betrifft: main.py, cli_handler.py, rest_api.py, api_videos.py, api_points.py, api_routes.py, command_executor.py

- **Vorteile:**
  - Klare Verantwortlichkeit und Modulgrenzen
  - Einfacherer Player-Wechsel (nur `player_manager.set_player()`)
  - Reduziert Coupling zwischen Modulen
  - Bessere Testbarkeit

- **Implementierung:**
  - `PlayerManager` Klasse mit `player` Property und `set_player()` Methode
  - DMXController nutzt PlayerManager statt direktem Player
  - Backward Compatibility: DMXController.player Property delegiert zu PlayerManager
  - Alle API-Routen aktualisiert (playback, settings, artnet, info, recording, scripts, videos, points)
  - RestAPI und CLIHandler nutzen PlayerManager
  - CommandExecutor nutzt player_provider Lambda für PlayerManager-Zugriff

### Bugfixes
- ✓ Restart-Funktion repariert: Startet Video jetzt immer neu vom ersten Frame (egal ob pausiert/gestoppt)
- ✓ Preview & Fullscreen Stream funktionieren wieder
- ✓ Traffic-Messung funktioniert
- ✓ Cache-System-Reste entfernt (cache_loaded AttributeError behoben)

---

## v2.0 - Unified Player Architecture (2025-11-20)

### Architektur-Refactoring
- ✓ Frame Source Abstraction (FrameSource base class)
- ✓ VideoSource Implementation (OpenCV-basiert, GIF-Support)
- ✓ ScriptSource Implementation (ScriptGenerator-Integration)
- ✓ Unified Player mit source switching
- ✓ Alle API-Routen aktualisiert (video/script loading)
- ✓ CLI Handler Migration (video/script/points)
- ✓ DMX Controller Integration
- ✓ Backward Compatibility (alte VideoPlayer/ScriptPlayer als deprecated)
- ✓ Stop/Start/Restart Playback-Fixes
- ✓ 90% Code-Duplikation eliminiert (~1300 → 850 Zeilen + neue Architektur)

---

## v1.x - Initial Implementation

### Core Features
- ✓ CLI-Steuerung implementiert
- ✓ DMX-Input über Art-Net (Universum 100)
- ✓ DMX-Test-App erstellt
- ✓ Video-Player mit Art-Net Output
- ✓ Numpy-Optimierung für RGB-Extraktion
- ✓ 8-Universen-Grenze Logik
- ✓ Brightness/Speed/Loop Steuerung
- ✓ Pause/Resume Funktionalität
- ✓ Blackout Funktion
- ✓ Code-Refactoring (Module-Struktur)
- ✓ Konfigurationsdatei (config.json)

### Video-System
- ✓ Video-Slot System (4 Kanäle, 1020 Videos, DMX Ch6-9)
- ✓ Hardware-Beschleunigung aktiviert mit Status-Ausgabe
- ✓ Kanal-Ordner System (kanal_1 bis kanal_4)
- ✓ RGB-Aufzeichnung
- ✓ Canvas-Größe Skalierung

### Art-Net Features
- ✓ Art-Net Code Separation (artnet_manager.py Modul)
- ✓ Test-Pattern mit Gradient
- ✓ Automatischer Art-Net Start
- ✓ RGB-Kanal-Reihenfolge pro Universum (Channel Mapping)
- ✓ Unterstützt alle 6 Permutationen (RGB, GRB, BGR, RBG, GBR, BRG)
- ✓ universe_configs in config.json
- ✓ _reorder_channels() Methode in ArtNetManager
- ✓ CLI-Befehle: artnet map/show mit Range-Syntax
- ✓ Testmuster berücksichtigen Channel Mapping

### Points Management
- ✓ Multi-JSON Punkte-Verwaltung (list/validate/switch/reload)
- ✓ JSON Schema Validierung mit jsonschema
- ✓ Points Switch/Reload via REST API
- ✓ /api/points/switch mit Validierung
- ✓ /api/points/reload für aktuelles File
- ✓ Auto-restart bei laufendem Video

### Flask REST API
- ✓ Flask REST API komplett implementiert
- ✓ Alle Playback Endpoints (play/stop/pause/resume/restart)
- ✓ Settings Endpoints (brightness/speed/fps/loop)
- ✓ Art-Net Endpoints (blackout/test)
- ✓ Video Management (list/load)
- ✓ Points Management (list/switch/reload/validate/current)
- ✓ Status & Info & Stats Endpoints
- ✓ Recording Endpoints (start/stop)
- ✓ Console Endpoints (log/command/clear)
- ✓ CORS Support aktiviert

### API Modularisierung
- ✓ api_routes.py (Playback, Settings, Art-Net)
- ✓ api_points.py (Points Management)
- ✓ api_videos.py (Video Management)
- ✓ api_console.py (Console & Commands)

### Web-Interface
- ✓ Bootstrap GUI (index.html) - Canvas Editor
- ✓ Control Panel (controls.html) - Playback Steuerung
- ✓ Dark Mode mit LocalStorage
- ✓ Externe CSS-Datei (styles.css)
- ✓ Externe JS-Dateien (editor.js, controls.js)
- ✓ Navigation zwischen GUIs
- ✓ Console Component in separates JS-Modul ausgelagert
- ✓ Responsive Design für Mobile optimiert
- ✓ LocalStorage für Settings Persistence (Brightness, Speed)
- ✓ Canvas-Zoom & Scrollbars (Zoom per Maus & Buttons, automatische Scrollbalken)
- ✓ Toast-Benachrichtigungen (statt alert, Theme-aware)
- ✓ Server-Projektverwaltung (CRUD, Download, Modal-UI)

### WebSocket Support
- ✓ Flask-SocketIO Integration
- ✓ Status Broadcasting (alle 2s)
- ✓ Console Live-Updates
- ✓ Fallback auf REST Polling
- ✓ Werkzeug "write() before start_response" Bug gefixt (manage_session=False + disconnect error handling)

### Script Generator (Procedural Graphics)
- ✓ ScriptGenerator Klasse (list/load/generate)
- ✓ ScriptPlayer Klasse (kompatibel mit VideoPlayer API)
- ✓ Python Script API: generate_frame(frame_number, width, height, time, fps)
- ✓ 10 Beispiel-Shaders (rainbow_wave, plasma, pulse, matrix_rain, fire, heartbeat, falling_blocks, line_*)
- ✓ METADATA-System für Script-Infos
- ✓ CLI-Befehle: scripts list, script:<name>
- ✓ REST API Endpoints: GET /api/scripts, POST /api/load_script
- ✓ Vollständige Dokumentation (scripts/README.md)
- ✓ Error Handling mit Traceback
- ✓ Lazy Module Loading (__init__.py __getattr__)

### Command Execution
- ✓ CommandExecutor Klasse für gemeinsame Command-Handler Logik
- ✓ CLIHandler nutzt CommandExecutor.execute()
- ✓ API Console nutzt gemeinsamen Command-Handler
- ✓ Code-Deduplizierung zwischen CLI und Web Console
- ✓ Einheitliche CommandResult-Struktur

### Konfiguration
- ✓ API Host/Port/Secret Key in config.json
- ✓ Art-Net FPS/Even Packet/Broadcast
- ✓ Video Delays (shutdown/frame_wait/recording_stop)
- ✓ Console Log Buffer Size
- ✓ Status Broadcast Interval
- ✓ Frontend Polling Interval
- ✓ Frontend-Config API Endpoint (/api/config/frontend)

### Dokumentation & Testing
- ✓ docs/API.md (500+ Zeilen, alle Endpoints)
- ✓ WebSocket Events dokumentiert
- ✓ Dokumentation in README und API.md
- ✓ tests/test_main.py (4 Test-Klassen)
- ✓ Validator, ArtNetManager, Cache, Error Tests

### Projekt-Infrastruktur
- ✓ RGB Cache Infrastruktur (cache/ Ordner, CLI-Befehle)
- ✓ requirements-lock.txt erstellt (27 Packages mit exakten Versionen)
- ✓ .gitignore Patterns
