# Py_artnet - Version History

## v2.3 - Unified API & Plugin System (2025-11-26 - 2025-12-02)

### v2.3.4 - Effect Library Expansion (2025-12-02)
- ✓ **60+ neue Effect-Plugins implementiert** - Massive Erweiterung der Effect-Bibliothek
- ✓ **Geometrie & Transform (6 Effekte):**
  - Flip (Horizontal/Vertical/Both Spiegelung)
  - Mirror (5 Modi: left-to-right, right-to-left, top-to-bottom, bottom-to-top, quad)
  - Slide (Endlose X/Y Verschiebung mit Wrap-Around)
  - Keystone (Perspektivische Trapez-Verzerrung, horizontal/vertikal)
  - Fish Eye (Sphärische Linsenverzerrung, -2.0 bis +2.0)
  - Twist (Spiralförmige Drehung mit konfigurierbarem Radius)
- ✓ **Blur & Distortion (4 Effekte):**
  - Radial Blur (Motion/Zoom Blur von Zentrum aus)
  - Pixelate (LoRez Retro-Look mit konfigurierbarer Blockgröße)
  - Displace (Verschiebung basierend auf Helligkeits-Map)
  - Wave Warp (Sinusförmige Wellenverzerrung horizontal/vertikal)
- ✓ **Glitch & Noise (4 Effekte):**
  - Shift Glitch (Digitale Zeilenverschiebung mit konfigurierbarer Intensität)
  - Distortion (Barrel/Pincushion Linsenverzerrung)
  - Static (TV-Static/Schnee-Rauschen, schwarz/weiß oder farbig)
  - Shift RGB (RGB-Kanal-Verschiebung für chromatische Aberration)
- ✓ **Edge & Detection (2 Effekte):**
  - Edge Detection (Sobel/Canny/Laplacian mit mehreren Farbmodi)
  - Auto Mask (Automatische Maskierung durch Helligkeit/Farbbereich/Kanten)
- ✓ **Composite & Mask (4 Effekte):**
  - Chroma Key (Green/Blue screen removal mit Spill Suppression)
  - Keystone Mask (Perspektivische Maskierung mit 4-Punkt-Kontrolle)
  - Vignette (Rand-Abdunklung/-Aufhellung mit Circular/Rectangular Shape)
  - Drop Shadow (Schatten mit Offset, Blur, Opacity und Detection Modes)
- ✓ **Simple 3D & Kaleidoscope (4 Effekte):**
  - Kaleidoscope (Mirror segments mit Rotation und Zoom)
  - Tile (Grid-Repeat mit Mirror-Modi und Offset)
  - Circles (Concentric circle mapping mit 3 Modi: radial_warp, circular_repeat, spiral)
  - Bendoscope (Kaleidoskop + Circular Bending + Twist für psychedelische Effekte)
- ✓ **Leicht implementierbare Zusatz-Effekte (15 Effekte):**
  - Sharpen (Unsharp Mask mit konfigurierbarer Stärke)
  - Emboss (3D-Relief-Effekt mit 4 Hauptrichtungen)
  - Sepia (Vintage-Ton mit Intensitäts-Parameter)
  - Gamma Correction (Lookup-Table-basiert, schnell)
  - Color Temperature (Warm/Kalt-Anpassung)
  - Channel Mixer (9 Parameter für vollständige RGB-Kontrolle)
  - Noise (Gaussian & Salt/Pepper)
  - Solarize (Invertierung über Schwellwert)
  - Duotone (Zwei-Farben-Mapping für Schatten/Highlights)
  - Oil Paint (Ölmalerei-Simulation mit Pinselgröße)
  - Mosaic (Pixelation/Blockierung)
  - Zoom (Zoom In/Out mit Zentrum-Kontrolle)
  - Rotate (Rotation mit Zentrum-Kontrolle)
  - Border (3 Modi: Solid, Replicate, Reflect)
  - Crop (Prozentuale Zuschnitt mit Scale-Back-Option)
- ✓ **NumPy String Type Bugfix** - COLOR Parameter handling korrigiert für np.str_ types

### v2.3.3 - Clip Trimming & ion.rangeSlider UI (2025-12-01)
- ✓ **Clip Trimming System** - In/Out Points pro Clip mit Non-Destructive Editing
  - **ClipRegistry Integration:** Metadata für in_point, out_point, reverse, total_frames
  - **REST API:** POST `/api/clips/<clip_id>/trim`, `/api/clips/<clip_id>/reverse`, `/api/clips/<clip_id>/reset-trim`, `/api/clips/<clip_id>/reload`
  - **VideoSource Frame-Range-Check:** current_frame initialisiert auf in_point statt 0
  - **Reverse Playback:** Frame-Counter rückwärts, Loop zurück zu out_point
  - **Live-Apply:** reload_trim_settings() für aktive Wiedergabe
- ✓ **Ion.RangeSlider Integration** - Professional UI Component für Trim Points
  - **Double Range Slider:** Zwei Handles für in_point/out_point mit Grid Display
  - **jQuery & ion.rangeSlider 2.3.1** via CDN
  - **Collapsible Section:** Toggle-Arrow wie Effects-System
  - **Right-Click Reset:** Context-Menu setzt Slider auf volle Clip-Range zurück
  - **Dark Theme Styling:** Custom CSS für ion.rangeSlider
- ✓ **Backend as Source of Truth:** Frontend nutzt backend-generierte clip_id statt eigene UUID
  - **Bug Fix:** controls.js verwendet `data.clip_id` statt `crypto.randomUUID()`
  - **Konsistente Clip-ID:** UUID über gesamten Lifecycle (Playlist → Playback → Loops)

### v2.3.2 - Multi-Layer Compositing System (2025-11-28)
- ✓ **Clip-Based Layer Architecture** - Layer-Stack pro Clip (Layer 0 = Base)
- ✓ **BlendEffect Plugin** - 6 Blend Modes: Normal, Multiply, Screen, Overlay, Add, Subtract
- ✓ **Layer CRUD API** - `/api/clips/{clip_id}/layers/*` Endpoints
- ✓ **Frontend Layer Panel** - Drag & Drop, Blend Mode/Opacity Controls
- ✓ **Thread-Safe Layer Loading** - Auto-Reload bei Clip-Wechsel
- ✓ **Session State Persistence** - Layer-Stack in Snapshots/Projects

### v2.3.1 - UI/UX Improvements (2025-11-28)
- ✓ **Universal Search Filter Component** - Debounced Search mit Live-Resultat-Zähler
  - Implementiert für: Effects, Sources, Files Tabs
  - Komponenten: `search-filter.html`, `search-filter-loader.js`
  - Dokumentation: `docs/SEARCH_FILTER.md`
- ✓ **Multi-Video-Source Support** - `video_sources` Array in config.json
  - UNC-Pfade (Netzwerkfreigaben) unterstützt
  - File Browser zeigt alle Quellen als Root-Ordner
  - API: `get_file_tree()` und `get_all_videos()` erweitert
  - Dokumentation: `docs/VIDEO_SOURCES.md`, `docs/CONFIG_SCHEMA.md`
- ✓ **Default Effect Chains** - Auto-Apply via config.json
  - `effects.video`: Effect Chain beim Video-Player-Start
  - `effects.artnet`: Effect Chain beim Art-Net-Player-Start
  - `effects.clips`: Per-Clip Default-Effekte (UUID oder Pfad-basiert)
  - DefaultEffectsManager mit vollständiger Validierung
  - Dokumentation: `docs/DEFAULT_EFFECTS.md`

### Unified API Architecture mit UUID-basiertem Clip-Management
- ✓ **ClipRegistry System** - UUID-basierte Clip-Identifikation (Singleton-Pattern)
- ✓ **Vereinheitlichte API** - `/api/player/{player_id}/clip/{clip_id}/...` Endpoints
- ✓ **Dual-Player-Architektur** - Video Player (Preview) + Art-Net Player (Output)
- ✓ **Unabhängige Clip-Effekte** - Jeder Player verwaltet eigene Effekt-Chains
- ✓ **PlayerManager** - `get_player(player_id)` für einheitlichen Zugriff
- ✓ **Frontend Migration** - controls.js nutzt UUID-basierte Endpoints
- ✓ **Lazy VideoSource-Initialisierung** - Verhindert FFmpeg-Konflikte beim Multi-Instance-Zugriff
- ✓ **Clip-basierte Effekte** - Player lädt Effekte aus ClipRegistry statt lokaler Liste

### Plugin-System (vollständig implementiert)
- ✓ **PluginBase** - Standardisiertes Interface mit METADATA + PARAMETERS
- ✓ **PluginManager** - Auto-Discovery, Lazy Loading, Error-Isolation
- ✓ **Parameter-System** - 5 Typen (float, int, bool, select, color) mit Validation
- ✓ **Runtime-Updates** - Parameter während Playback änderbar
- ✓ **Plugin-API** - `/api/plugins/*` Endpoints für CRUD-Operationen
- ✓ **18 Effect-Plugins implementiert:**
  - **Farb-Manipulation (11):** add_subtract, brightness_contrast, colorize, tint, hue_rotate, invert, saturation, exposure, levels, posterize, threshold
  - **Time & Motion (5):** trails, stop_motion, delay_rgb, freeze, strobe
  - **Blur (1):** blur (Gaussian/Box)
  - **Blending (1):** blend_mode (14 Modi: Normal, Multiply, Screen, Overlay, Add, Subtract, Darken, Lighten, Color Dodge, Color Burn, Hard Light, Soft Light, Difference, Exclusion)

### Multi-Layer Compositing System (v2.3.2)
- ✓ **Clip-Based Layer Architecture** - Jeder Clip hat eigenen Layer-Stack (Layer 0 = Base)
- ✓ **Layer Class** - `layer.py` mit blend_mode, opacity, effects, clip_id
- ✓ **Player Layer Management** - add_layer(), remove_layer(), reorder_layers(), load_clip_layers()
- ✓ **Multi-Layer Compositing Loop** - Sequential frame-fetching, auto-loop overlays
- ✓ **Clip-Based Layer API** - `/api/clips/{clip_id}/layers/*` REST Endpoints
- ✓ **ClipRegistry Layer Storage** - Per-clip layers array mit persistence
- ✓ **Session State Integration** - Layer-Stack in Snapshots/Projects gespeichert
- ✓ **Frontend Layer Panel** - Drag & drop, blend mode/opacity controls, add/remove layers
- ✓ **BlendEffect Plugin** - 6 blend modes (normal, multiply, screen, overlay, add, subtract)
- ✓ **Per-Layer Effects** - Effekte vor Compositing angewendet
- ✓ **Backward Compatibility** - Alte Sessions automatisch konvertiert
- ✓ **Thread-Safe Loading** - Auto-reload bei Clip-Wechsel

### Transition Plugin System (v2.3.1)
- ✓ **PluginType.TRANSITION** - `blend_frames(frame_a, frame_b, progress)` Methode
- ✓ **Fade Transition Plugin** - Easing-Funktionen: linear, ease_in, ease_out, ease_in_out
- ✓ **Player Integration** - Transition-Buffering mit apply_transition() bei Clip-Wechsel
- ✓ **REST API** - `/api/transitions/list`, `/api/player/{player_id}/transition/config`, `/api/player/{player_id}/transition/status`
- ✓ **Reusable UI Component** - `components/transition-menu.html`
  - Enable/Disable Toggle mit Settings-Panel
  - Effect-Dropdown dynamisch geladen von API
  - Duration-Slider: 0.1-5.0s, 0.1s Steps, Live-Value-Display
  - Easing-Function Selector: 4 Modi
  - Integration in Video & Art-Net Player-UI
- ✓ **Dokumentation** - `docs/TRANSITION_SYSTEM.md`, `docs/TRANSITION_FRONTEND_INTEGRATION.md`, `docs/TRANSITION_QUICKSTART.md`

### Code Cleanup & Deprecation
- ✓ **Legacy Player gelöscht** - video_player.py (868 Zeilen) und script_player.py (~620 Zeilen)
- ✓ **~1500 Zeilen toter Code eliminiert**
- ✓ **Unified Player** - Nur noch eine Player-Klasse mit austauschbaren FrameSource Implementierungen
- ✓ **Deprecated Properties entfernt** - `self.effect_chain`, `self.clip_effects`
- ✓ **Backward-Compatibility-Code entfernt** - Alle Legacy-Funktionen gelöscht
- ✓ **Test-Dateien organisiert** - Verschoben nach `tests/` Ordner
- ✓ **__init__.py bereinigt** - Deprecated exports entfernt, ClipRegistry hinzugefügt
- ✓ **Static Content bereinigt** - Backup-Dateien gelöscht (~36 KB)

### Dokumentation
- ✓ **CHANGELOG.md** - v2.3.0 Release Notes
- ✓ **TODO.md aktualisiert** - Erledigtes markiert, neue Struktur
- ✓ **ARCHITECTURE.md** - Unified API Dokumentation
- ✓ **docs/UNIFIED_API.md** - API-Referenz mit allen Endpoints
- ✓ **docs/MIGRATION.md** - Migration Guide von alten APIs
- ✓ **docs/MULTI_LAYER_ARCHITECTURE.md** - Layer-System Architektur
- ✓ **docs/BLEND_EFFECT.md** - BlendEffect Plugin Dokumentation
- ✓ **TODO_LAYERS.md** - Multi-Layer Implementation Tracking

### Vorteile
- **Keine Pfad-basierten Kollisionen** - UUID-basierte Identifikation
- **Saubere Trennung** - Video-Preview vs. Art-Net-Output
- **Einfachere API** - Konsistente RESTful Endpoints
- **Unabhängige Player** - Verschiedene Videos mit verschiedenen Effekten gleichzeitig
- **Erweiterbar** - Plugin-System für neue Effekte ohne Core-Changes
- **Testbar** - Jedes Plugin isoliert testbar
- **Flexible Compositing** - Clip-basierte Layer-Stacks mit individuellen Effekten

---

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
