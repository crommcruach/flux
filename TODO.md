# Py_artnet - TODO Liste

> **Siehe [HISTORY.md](HISTORY.md) für abgeschlossene Features (v1.x - v2.3)**

## 🚀 Geplante Features (nach Komplexität & Priorität)

Die Features sind in 6 Prioritätsstufen organisiert basierend auf **Implementierungs-Komplexität** und **Business-Value**:
- **P1**: Quick Wins (niedriger Aufwand, hoher Nutzen)
- **P2**: Mittlere Komplexität, hoher Nutzen
- **P3**: Mittlere Komplexität, mittlerer Nutzen
- **P4**: Hohe Komplexität, hoher Nutzen
- **P5**: Niedrige Priorität / Maintenance
- **P6**: Optional / Langfristig

---

## 🔥 PRIORITÄT 1 - Quick Wins (~30-42h)
**Niedriger Aufwand, hoher Nutzen - sofort umsetzbar**

### 1.0 🔍 UI/UX Verbesserungen (~6-8h)

- [x] **Universal Search/Filter Komponente (3-4h):** ✅ COMPLETED (2025-11-28)
  - Wiederverwendbare Suchfeld-Komponente für Listen
  - Debounced Input (200ms) für Performance
  - Live-Resultat-Zähler und Clear-Button
  - Implementiert für: Effects, Sources, Files Tabs
  - Komponenten: `search-filter.html`, `search-filter-loader.js`
  - Dokumentation: `docs/SEARCH_FILTER.md`

- [x] **Multi-Video-Source Support (2-3h):** ✅ COMPLETED (2025-11-28)
  - `video_sources` Array in config.json
  - Unterstützung für mehrere Laufwerke/Ordner
  - Netzwerkfreigaben (UNC-Pfade) möglich
  - File Browser zeigt alle Quellen als Root-Ordner
  - API: `get_file_tree()` und `get_all_videos()` erweitert
  - Dokumentation: `docs/VIDEO_SOURCES.md`, `docs/CONFIG_SCHEMA.md`

### 1.1 🔌 Plugin-System erweitern (~8-12h)

- [x] **Default Effect Chains via config.json (3-4h):** ✅ COMPLETED (2025-11-28)
  - `effects.video`: Effect chain automatisch beim Start auf Video-Player
  - `effects.artnet`: Effect chain automatisch beim Start auf Art-Net-Player
  - `effects.clips`: Per-Clip Default-Effekte (UUID oder Pfad-basiert)
  - config.json Schema validiert und dokumentiert
  - Auto-Apply beim Player-Init und Clip-Registrierung
  - DefaultEffectsManager mit vollständiger Validierung
  - Dokumentation: `docs/DEFAULT_EFFECTS.md`

- [x] **Blend Mode Effect Plugin (4-6h):** ✅ COMPLETED (2025-12-01)
  - 14 Blend-Modes implementiert: Normal, Multiply, Screen, Overlay, Add, Subtract, Darken, Lighten, Color Dodge, Color Burn, Hard Light, Soft Light, Difference, Exclusion
  - Blending mit konfigurierbarer RGB-Farbe
  - Opacity-Parameter (0-100%) für Blend-Intensität
  - Mix-Parameter (0-100%) für Blend zwischen Original und Effekt
  - Alle mathematischen Blend-Formeln korrekt implementiert
  - Vollständig getestet mit allen Blend-Modi
  - Plugin-Datei: `src/plugins/effects/blend_mode.py`

- [ ] **Clip Trimming & Playback Control (6-10h):**
  - **In/Out Points:** Start/End-Frame pro Clip definieren (Dual-Range-Slider)
  - **Reverse Playback:** Clip rückwärts abspielen (Toggle-Option)
  - **Backend (ClipRegistry):**
    - Metadata: `in_point` (Frame), `out_point` (Frame), `reverse` (bool)
    - API: POST `/api/clips/<clip_id>/trim` (in_point, out_point)
    - API: POST `/api/clips/<clip_id>/reverse` (enabled: bool)
  - **Backend (VideoSource):**
    - Frame-Range-Check bei get_next_frame()
    - Reverse-Mode: Frame-Counter rückwärts
    - Loop-Verhalten: Zurück zu in_point (forward) / out_point (reverse)
  - **Frontend UI:**
    - Dual-Range-Slider im Clip FX Tab (Section: ⏱️ Clip Timing)
    - Live-Preview: "Playing 5.0s - 8.0s (3.0s trimmed)"
    - Frame/Sekunden-Toggle für Anzeige
    - Reverse-Checkbox mit Icon (⏪)
    - Reset-Button ("Full Clip")
  - **Features:**
    - Non-destructive (Original bleibt unberührt)
    - Per-Clip individuell (jede Playlist-Instanz eigene Settings)
    - Projekt-JSON-Persistierung
    - Auto-Advance basiert auf getrimter Duration

- [ ] **Layer-Effekte über Clip FX Tab (8-12h):**
  - API-Endpoints für Layer-Effekte (POST/PATCH/DELETE `/api/clips/<clip_id>/layers/<layer_id>/effects`)
  - Layer-Selection-Logik: Click auf Layer-Card → Layer ausgewählt (visuelles Feedback)
  - Clip FX Tab erweitern: Dynamischer Titel ('Clip FX' vs 'Layer FX')
  - API-Calls umleiten wenn Layer ausgewählt (zu Layer-Endpoints statt Clip-Endpoints)
  - Drag & Drop von Effekten funktioniert für Clip UND Layer
  - Backend: apply_layer_effects() Integration, Layer.effects Array populieren

- [x] **Generator-Plugins (3-4h):** ✅ COMPLETED
  - Scripts nach `plugins/generators/` migriert
  - plasma, rainbow_wave, pulse, matrix_rain, fire implementiert
  - METADATA + PARAMETERS für alle Generatoren hinzugefügt

- [x] **Source-Plugins (4-6h):** ✅ COMPLETED
  - Webcam: Live-Video von lokalen USB-/integrierten Kameras
  - LiveStream: HTTP/RTSP/HLS/RTMP/YouTube Streaming-Protokolle
  - Screencapture: Screen/Monitor-Capture mit mss

- [x] **UI-Generierung (3-4h):** ✅ COMPLETED
  - Automatische Form-Generierung aus PARAMETERS-Array
  - Parameter-Panel im Web-Interface (Generator + Effects)
  - Live-Preview beim Parameter-Ändern
  - Unterstützt: FLOAT, INT, BOOL, STRING, SELECT, COLOR, RANGE
  
- [ ] **Preset-System (2-3h):**
  - Parameter-Sets speichern/laden
  - Preset-Manager API (CRUD)
  - UI: Preset-Selector & Editor

---

### 1.2 🔄 Transition-Plugin-System (~8-10h) ✅ COMPLETED (2025-11-29)

- [x] **PluginType.TRANSITION (3h):** ✅ COMPLETED (2025-11-29)
  - `blend_frames(frame_a, frame_b, progress)` Methode implementiert
  - Fade Transition Plugin mit Easing-Funktionen (linear, ease_in, ease_out, ease_in_out)
  - Tests bestanden (Progress 0.0-1.0, alle Easing-Modi)
  - Dokumentation: `docs/TRANSITION_SYSTEM.md`

- [x] **Player Integration (2h):** ✅ COMPLETED (2025-11-29)
  - Transition-Buffering (letzter Frame): `self.transition_buffer`
  - apply_transition() bei Clip-Wechsel (automatisch in Playback-Loop)
  - Frame-Blending mit Progress-Berechnung (elapsed / duration)
  - Transition-State: active, start_time, frames_count

- [x] **API & Config (2h):** ✅ COMPLETED (2025-11-29)
  - `/api/transitions/list` - Verfügbare Transitions
  - `/api/player/{player_id}/transition/config` - Transition setzen (POST)
  - `/api/player/{player_id}/transition/status` - Status abrufen (GET)
  - Player-spezifische Konfiguration (Video & Art-Net)

- [x] **UI (3h):** ✅ COMPLETED (2025-11-29)
  - Reusable Transition-Menu-Komponente (`components/transition-menu.html`)
  - Enable/Disable Toggle mit Settings-Panel
  - Effect-Dropdown: Dynamisch geladen von API
  - Duration-Slider: 0.1-5.0s, 0.1s Steps, Live-Value-Display
  - Easing-Function Selector: All 4 Modi
  - Integration in Video & Art-Net Player-UI
  - Automatisches Config-Loading beim Start
  - Dokumentation: `docs/TRANSITION_FRONTEND_INTEGRATION.md`, `docs/TRANSITION_QUICKSTART.md`

---

### 1.3 🎬 Playlist-Sequenzer (~8-12h)

- [ ] **Show-Editor UI (4h):**
  - Liste von Clips mit Drag & Drop
  - Clip-Properties: Video/Script, Duration, Transition, Brightness

- [ ] **Persistence (2h):**
  - Save/Load Show-Dateien (JSON `.fluxshow`)
  - Show-Library (Liste aller Shows)

- [ ] **Playback Engine (4h):**
  - Sequential Playback mit Transitions
  - Cue-System (Next Cue, Jump to Cue N)
  - Loop-Mode

- [ ] **REST API (2h):**
  - GET/POST/PUT/DELETE `/api/sequencer/shows`
  - POST `/api/sequencer/play`, `/api/sequencer/stop`
  - POST `/api/sequencer/cue/<index>`

**JSON-Format Beispiel:**
```json
{
  "name": "Halloween Show 2025",
  "clips": [
    {"type": "video", "source": "kanal_1/intro.mp4", "duration": 15, "transition": "fade", "brightness": 1.0},
    {"type": "script", "source": "plasma", "duration": 30, "transition": "cut"}
  ],
  "loop": true
}
```

---

### 1.4 🎹 MIDI-over-Ethernet Support (~6-10h)

- [ ] **MIDI Control via Ethernet (minimale Latenz) (6-10h):**
  - **Grundidee:** MIDI-Signale über Ethernet statt USB für <5ms Latenz
  - **WebSocket-MIDI (empfohlen):**
    - Web-MIDI API (Browser nativ)
    - Bidirektional (Server → Client Feedback)
    - <5ms Latenz (LAN), <20ms (WiFi)
  - **RTP-MIDI (optional):**
    - Standard-Protokoll (Apple MIDI-Network)
    - UDP-basiert (noch niedriger Latenz)
  - **Features:**
    - MIDI-Learn: Click auf Parameter → nächster MIDI-Input wird gemappt
    - Multi-Controller: Mehrere MIDI-Geräte gleichzeitig
    - Feedback: LED-Status zurück an Controller
    - Curve-Mapping: Linear, Exponential, Logarithmic
  - **Implementierung:**
    - Phase 1: WebSocket-MIDI-Handler (~2h)
    - Phase 2: MIDI-Mapping-Engine (~2h)
    - Phase 3: MIDI-Learn UI (~2h)
    - Phase 4: Client-Library (Browser) (~1h)
    - Phase 5: Feedback-System (~1h)
    - Phase 6: RTP-MIDI Support (optional) (~2h)

---

## ⚡ PRIORITÄT 2 - Mittel-Komplex, Hoch-Wert (~14-24h)
**Mittlerer Aufwand, hoher Performance-Gewinn**

### 2.1 ⚡ WebSocket Command Channel (~4-6h)

- [ ] **Zeitkritische Commands über WebSocket:**
  - **Problem mit REST:** 10-50ms Latenz pro Request
  - **WebSocket-Vorteile:** <5ms Latenz, Persistent Connection
  - **Zeitkritische Commands:**
    - Playback: play, pause, stop, seek
    - Parameter: brightness, speed, effect_param
    - Blackout: sofortiger Blackout-Toggle
  - **Features:**
    - Command-Queue mit Priority-System
    - Batch-Commands
    - MessagePack Support (optional)
  - **Implementierung:**
    - Phase 1: WebSocket Command Handler (~2h)
    - Phase 2: Command-Queue & Priority (~1h)
    - Phase 3: MessagePack Support (~1h)
    - Phase 4: Client-Library (~1h)

---

### 2.2 🌐 Multi-Network-Adapter Support (~4-6h)

- [ ] **Separate Netzwerk-Interfaces:**
  - **Grundidee:** Control-Traffic (API) getrennt von Art-Net-Output
  - **Features:**
    - API-Binding auf spezifisches Interface
    - Art-Net-Routing: Universes auf verschiedenen Adaptern
    - Multi-Art-Net: Mehrere Art-Net-Netzwerke parallel
    - Failover: Automatischer Switch auf Backup-Adapter
  - **Use-Cases:**
    - Adapter 1: Management (192.168.1.x)
    - Adapter 2: Art-Net Output 1 (10.0.0.x)
    - Adapter 3: Art-Net Output 2 (10.0.1.x)
  - **Implementierung:**
    - Phase 1: Network-Interface-Discovery (~1h)
    - Phase 2: API-Binding-Config (~1h)
    - Phase 3: Art-Net Multi-Adapter-Routing (~2h)
    - Phase 4: UI (Network-Adapter-Auswahl) (~1h)

**Config-Beispiel:**
```json
{
  "network": {
    "api": {"bind_address": "192.168.1.10", "port": 5000},
    "artnet": {
      "adapters": [
        {"interface": "10.0.0.50", "universes": [1,2,3,4,5]},
        {"interface": "10.0.1.50", "universes": [6,7,8,9,10]}
      ]
    }
  }
}
```

---

### 2.3 ⚡ Preview Stream Optimierung (~6-10h)

- [ ] **WebRTC statt MJPEG:**
  - **Problem aktuell:** MJPEG = hohe CPU-Last, hohe Bandbreite
  - **Lösung: WebRTC:**
    - Hardware-beschleunigtes H.264-Encoding (GPU)
    - ~10x weniger CPU-Last vs. MJPEG
    - ~5x weniger Bandbreite (0.2-1 Mbps)
    - Ultra-niedrige Latenz (<100ms)
  - **Features:**
    - Multi-Quality: Low (480p), Medium (720p), High (1080p)
    - Adaptive FPS: 10-30 FPS je nach CPU-Last
    - Connection-Limit: Max. 5 Preview-Clients
    - Bandwidth-Limiter: Max. Bitrate konfigurierbar
  - **Implementierung:**
    - Phase 1: Adaptive FPS & Quality (~2h)
    - Phase 2: WebRTC Integration (~2h)
    - Phase 3: Connection-Limit & Bandwidth-Limiter (~1h)
    - Phase 4: UI (Quality-Selector, Stats) (~1h)
  - **Performance-Ziel:**
    - MJPEG: ~40-60% CPU, 2-5 Mbps
    - WebRTC: ~5-10% CPU, 0.2-1 Mbps

---

## 🔧 PRIORITÄT 3 - Mittel-Komplex, Mittel-Wert (~33-51h)
**Mittlerer Aufwand, mittlere Business-Priorität**

### 3.1 🎨 Effect-Bibliothek erweitern (~15-25h)

- [ ] **Geometrie & Transform (3-5h):**
  - Flip, Mirror, Slide, Keystone, Fish Eye, Twist

- [ ] **Blur & Distortion (2-3h):**
  - Radial Blur, Pixelate (LoRez), Displace, Wave Warp

- [ ] **Glitch & Noise (2-3h):**
  - Shift Glitch, Distortion, Static, Shift RGB

- [ ] **Edge & Detection (1-2h):**
  - Edge Detection, Auto Mask

- [ ] **Composite & Mask (2-3h):**
  - ChromaKey, Keystone Mask, Vignette, Drop Shadow

- [ ] **Simple 3D & Kaleidoscope (3-5h):**
  - Kaleidoscope, Tile, Circles, Bendoscope

- [ ] **Leicht implementierbare Zusatz-Effekte:**
  - Sharpen, Emboss, Sepia, Gamma Correction
  - Color Temperature, Channel Mixer, Noise, Solarize
  - Duotone, Oil Paint, Mosaic, Zoom, Rotate
  - Border, Crop, Alpha Blend, Lumetri Color

---

### 3.2 🎵 Audio-Reactive Support (~10-14h)

- [ ] **Audio-Input (4h):**
  - Microphone-Input (pyaudio/sounddevice)
  - System-Audio-Capture (WASAPI Loopback)
  
- [ ] **Audio-Analyse (3h):**
  - FFT (Bass/Mid/Treble Frequenz-Bänder)
  - BPM-Detection (tempo tracking)
  - Onset-Detection (Beat-Trigger)
  
- [ ] **Reaktive Parameter (3h):**
  - Brightness ← RMS/Peak-Level
  - Speed ← BPM
  - Color ← Frequenz-Mapping
  - Effect-Intensity ← Audio-Level
  
- [ ] **UI & API (2h):**
  - Audio-Device-Auswahl
  - Live-Spektrum-Anzeige
  - Parameter-Mapping-Editor

---

### 3.3 🎬 HAP Codec Support & Video Converter (~8-12h)

- [ ] **HAP Codec Decoder (4-5h):**
  - **HAP Varianten:** HAP (DXT1), HAP Alpha (DXT5), HAP Q (BC7)
  - **Vorteile:** 5-10x schnelleres Decoding vs. H.264
  - **FFmpeg Integration:** libavcodec HAP Support
  - **Features:**
    - Automatische HAP-Format-Erkennung
    - Fallback auf Standard-Codecs
    - Performance-Messung

- [ ] **Universal Video Converter (4-7h):**
  - **Input-Formate:** AVI, MP4, MOV, GIF, PNG-Sequences
  - **Output-Profile:** HAP (Performance), H.264 (Hardware-Encoding)
  - **Features:**
    - Batch-Processing: Ganze Ordner konvertieren
    - Auto-Resize: Auf Canvas-Größe skalieren
    - Loop-Optimierung: Nahtlose Loops
  - **Implementierung:**
    - Phase 1: FFmpeg-Wrapper (~2h)
    - Phase 2: Batch-Processing (~2h)
    - Phase 3: CLI-Tool (~1h)
    - Phase 4: Web-UI (~2h)

**CLI-Beispiele:**
```bash
# Einzelnes Video zu HAP
python convert.py video.mp4 --format hap --resize 60x300

# Batch-Convert ganzer Ordner
python convert.py kanal_1/*.mp4 --format hap --auto-resize
```

---

## 🚀 PRIORITÄT 4 - Hoch-Komplex, Hoch-Wert (~24-40h)
**Hoher Aufwand, strategisch wichtig**

### 4.1 🎥 Multi-Video-Routing per Art-Net-Objekt (~40-54h)

- [ ] **Grundidee:** Mehrere Videos gleichzeitig, jedes LED-Objekt bekommt eigenes Video
- [ ] **Architektur:**
  - Mehrere Player-Instanzen parallel (Video1, Video2, Video3)
  - LED-Objekte definieren (Name, Universe-Range, Pixel-Count)
  - Routing-Config: `{"object": "strip_1", "video_player_id": "video_1"}`
  
- [ ] **Kartendeck-UI mit Slot-Compositing:**
  - **Slot-Struktur (Kartendeck-Metapher):**
    - Slot = Playlist-Position mit gestapelten Clip-Alternativen (wie Kartendeck 🎴)
    - Minimiert: Zeigt Icon + Anzahl (`[3 Clips] 🎴`)
    - Ausklappen: Zeigt alle Clips im Stack mit Compositing-Settings
  
  - **Compositing innerhalb eines Slots:**
    - Alle Clips im Slot laufen parallel (Layer-Stack)
    - Werden automatisch übereinander komponiert
    - Jeder Clip hat eigene Effect-Chain
    - Blend Mode pro Clip (Normal, Multiply, Screen, Overlay, Add, Subtract)
    - Opacity pro Clip (0-100%)
    - Layer-Reihenfolge via Drag & Drop änderbar
  
  - **Sequential zwischen Slots:**
    - Slot 1 → Slot 2 → Slot 3 (mit Transitions)
    - Transition-Effekte zwischen Slots (Fade, Wipe, Dissolve, etc.)
    - Auto-Next oder manueller Trigger (Button/Keyboard/MIDI)
    - Loop-Mode für Slot-Sequenz
  
  - **Trigger-Modi pro Slot:**
    - **Manual:** Button-Click oder Keyboard (Nummerntaste)
    - **Auto:** Nach Duration automatisch zum nächsten Slot
    - **Random:** Zufälliger Slot aus Sequenz
    - **MIDI:** MIDI-Note triggert spezifischen Slot
  
  - **Pro Clip im Slot:**
    - Eigene Effect-Chain
    - Blend Mode & Opacity (für Compositing)
    - Weight für Random-Auswahl (bei mehreren Clips)
    - Auto-Loop oder Play-Once
  
  - **Pro Slot:**
    - Name/Label (z.B. "Intro Varianten", "Drop", "Outro")
    - Duration (für Auto-Mode)
    - Transition zum nächsten Slot (Type + Duration)
    - Output-Routing (LED-Objekt-Zuweisung)
    - Enable/Disable Toggle

- [ ] **Implementierung:**
  - Phase 1: LED-Objekt-Definition & Config (~2h)
  - Phase 2: Slot-Manager (Slot-Sequenz, Trigger-System) (~3h)
  - Phase 3: Layer-Compositor für Slot-Compositing (Blend Modes, Opacity) (~3h)
  - Phase 4: Transition-System zwischen Slots (~2h)
  - Phase 5: Routing-System & Frame-Collection (~2h)
  - Phase 6: API-Endpoints (Slot CRUD, Clip Management, Trigger) (~3h)
  - Phase 7: UI (Kartendeck-View, Ausklapp-Mechanik, Compositing-Controls) (~5h)

**JSON-Config Beispiel:**
```json
{
  "led_objects": [
    {"name": "strip_left", "universes": [1,2], "pixels": 200},
    {"name": "strip_right", "universes": [3,4], "pixels": 200},
    {"name": "panel_center", "universes": [5,6], "pixels": 256}
  ],
  "slots": [
    {
      "slot_id": 1,
      "name": "Intro Varianten",
      "duration": 30,
      "clips": [
        {
          "path": "intro_v1.mp4",
          "effects": [{"plugin_id": "blur", "params": {"strength": 2.0}}],
          "blend_mode": "normal",
          "opacity": 100,
          "layer_order": 0
        },
        {
          "path": "generator:plasma",
          "effects": [],
          "blend_mode": "multiply",
          "opacity": 50,
          "layer_order": 1
        }
      ],
      "transition_to_next": {"type": "fade", "duration": 1.5},
      "output_routing": {"led_object": "strip_left"}
    },
    {
      "slot_id": 2,
      "name": "Drop Section",
      "duration": 60,
      "clips": [
        {"path": "drop_bg.mp4", "blend_mode": "normal", "opacity": 100},
        {"path": "generator:fire", "blend_mode": "screen", "opacity": 70},
        {"path": "overlay.mp4", "blend_mode": "add", "opacity": 40}
      ],
      "transition_to_next": {"type": "wipe_left", "duration": 0.5},
      "output_routing": {"led_object": "strip_left"}
    }
  ]
}
```

---

### 4.2 🔮 Neue Frame Sources (~12-20h)

- [ ] **ShaderToy Source (8-12h):**
  - ModernGL/PyOpenGL Integration
  - GLSL Shader Support (Shadertoy-kompatibel)
  - Uniform Variables (iTime, iResolution, iMouse)

- [x] **LiveStream Source (2-5h):** ✅ COMPLETED
  - RTSP/HTTP/HLS/RTMP Stream Support
  - FFmpeg Integration via OpenCV
  - YouTube URL Support (yt-dlp)

---

## 🎨 PRIORITÄT 5 - Niedrig-Komplex, Niedrig-Priorität (~8-12h)
**Maintenance, Polishing, Nice-to-have**

### 5.1 🎨 GUI-Optimierungen (~8-12h)

- [ ] **Drag & Drop Layout-Editor:**
  - GridStack.js Integration
  - Panels frei verschieben & resizen
  - LocalStorage-Persistierung
  - Preset-Layouts: "Standard", "Video-Focus", "Compact"

---

### 5.2 🧪 Testing & Verification

- [ ] **Milkdrop via Screencapture testen:**
  - Screencapture-Generator mit Milkdrop/projectM-Fenster
  - Region-Capture für optimale Performance
  - Alternative: Window-Capture API

- [ ] **Multi-Layer System Testing (~2-4h):**
  - [ ] Run `tests/test_api_layers.py` to verify all tests pass
  - [ ] Test live multi-layer playback with different FPS sources
    - [ ] Verify: Overlay läuft nicht doppelt so schnell bei höherer FPS
    - [ ] Verify: Frame-Skipping funktioniert bei niedrigerer FPS
  - [ ] Verify snapshot restore with layers
  - [ ] Test generator + video layer combinations
  - [ ] Test layer with effects + blend modes
  - [ ] Test autoplay with multi-layer clips
  - [ ] Test transitions on layer 0 with overlays active

### 5.3 🛠️ Weitere Verbesserungen

- [ ] **Vollständige Player/Playlist-Generalisierung (~8-12h):**
  - Hardcodierte Playlist-Arrays entfernen (`videoFiles`, `artnetFiles`)
  - Hardcodierte Current-Item-IDs zu `playerConfigs[playerId].currentItemId` migrieren
  - Spezifische Lade-Funktionen (`loadVideoFile`, `loadArtnetFile`) durch generische Funktion mit `playerId` Parameter ersetzen
  - HTML/UI dynamisch aus `playerConfigs` generieren (Player-Container, Buttons)
  - Legacy-onclick-Handler (`window.playVideo`, etc.) entfernen und durch generische Event-Handler ersetzen
  - **Ziel:** Neuer Player nur durch Hinzufügen in `playerConfigs` möglich, ohne Code-Änderungen

- [ ] **Playlist Playback Refactoring (~4-6h):**
  - Überarbeitung Loop/Autoplay/Play-Funktionen
  - Clip-Add-Handling vereinheitlichen
  - Auto-Start beim ersten Clip konsistent implementieren
  - State-Management zwischen Frontend/Backend synchronisieren
  - **Hinweis:** Aktuell inkonsistentes Verhalten - tiefergehende Überarbeitung nötig

- [ ] **player.js Performance-Optimierung (~8-12h):**
  - **Event-Handler-Leak beheben (Kritisch):**
    - Event-Delegation statt mehrfacher addEventListener
    - Memory-Leak bei jedem Playlist-Render
    - Geschätzte Einsparung: 40-60% Memory
  - **Generator-Map für O(1) Lookups (Kritisch):**
    - Map statt Array.find() in Hover-Events
    - Reduziert CPU-Last bei Hover um 5-10%
  - **Unified Update-Loop (Wichtig):**
    - 2 separate setInterval zu einem kombinieren
    - Halbiert Polling-Last (~10-15% CPU)
  - **DOM-Query-Caching (Mittel):**
    - Wiederholte querySelectorAll() cachen
    - Einsparung: 3-8% CPU
  - **setTimeout-Cleanup (Mittel):**
    - Verschachtelte setTimeout durch requestAnimationFrame
    - Besseres Timing, 2-5% CPU
  - **Gesamt-Potenzial:** 35-68% CPU, 49-80% Memory
  - **Dokumentation:** `PERFORMANCE_IMPROVEMENTS_PLAYER.md`

- [ ] Unit Tests erweitern (Player, FrameSource, API)
- [ ] API-Authentifizierung (Basic Auth/Token)
- [ ] PyInstaller EXE Build Setup
- [ ] Environment Variable Support für config.json
- [ ] JSON Schema Validation für config.json
- [ ] Hot-Reload (config.json watcher)
- [ ] Dockerfile erstellen

---

## 🔬 PRIORITÄT 6 - Optional / Langfristig (~64-86h)
**Zukünftige Features mit hohem Aufwand**

### 6.1 ⏱️ Script-basierter Sequenzer (Optional, ~4-6h)

- **Power-User Feature:** Python-DSL für Show-Definition
- **Features:** CLI-Befehl, Script-Loader, Volle Python-Kontrolle
- **Empfehlung:** Nice-to-have, niedrige Priorität

---

### 6.2 📈 Timeline-Sequenzer (Optional, ~60-80h)

- Upgrade von Playlist-Sequenzer zu visueller Timeline
- Features: Clip-Trimming, Scrubbing, Multi-Track, Audio-Sync
- **Nur bei komplexeren Anforderungen**

---

## 📊 Zusammenfassung nach Priorität

| Priorität | Aufwand | Nutzen | Summe Stunden |
|-----------|---------|--------|---------------|
| **P1** | Niedrig | Hoch | ~30-42h |
| **P2** | Mittel | Hoch | ~14-24h |
| **P3** | Mittel | Mittel | ~33-51h |
| **P4** | Hoch | Hoch | ~24-40h |
| **P5** | Niedrig | Niedrig | ~8-12h |
| **P6** | Sehr Hoch | Mittel | ~64-86h |
| **GESAMT** | | | **~173-255h** |

---

## 🎯 Empfohlene Umsetzungs-Reihenfolge

### Phase 1: Foundation (P1) - ~30-42h
1. Plugin-System erweitern (Generator-Plugins, Presets, UI)
2. Transition-System implementieren
3. Playlist-Sequenzer
4. MIDI-over-Ethernet Support

**Ziel:** Vollständige Show-Control mit Effects & Transitions

---

### Phase 2: Performance (P2) - ~14-24h
1. WebSocket Command Channel
2. Multi-Network-Adapter Support
3. Preview Stream Optimierung (WebRTC)

**Ziel:** Production-ready Performance & Latenz-Optimierung

---

### Phase 3: Content (P3) - ~33-51h
1. Effect-Bibliothek erweitern (~30 neue Effekte)
2. Audio-Reactive Support
3. HAP Codec & Video Converter

**Ziel:** Umfangreiche Effect-Library & bessere Video-Performance

---

### Phase 4: Advanced (P4) - ~24-40h
1. Multi-Video-Routing mit Kartendeck-UI
2. Neue Frame Sources (ShaderToy, LiveStream)

**Ziel:** Multi-Output-Setups & Advanced Content-Sources

---

### Phase 5+: Polish & Future (P5+P6) - ~72-98h
1. GUI-Optimierungen
2. Maintenance & Tests
3. Optional: Timeline-Sequenzer

**Ziel:** Production-Polishing & Langzeit-Features

---

## 📚 Status (Stand: 2025-11-28)

### ✅ Fertiggestellt (v2.3)
- **Unified API Architecture** mit UUID-basiertem Clip-Management
- **Dual-Player-System** (Video Preview + Art-Net Output)
- **Plugin-System** vollständig implementiert (PluginBase, PluginManager, API)
- **17 Effect-Plugins:** 11 Farb-Manipulation, 5 Time & Motion, 1 Blur
- **ClipRegistry** mit UUID-basierter Clip-Identifikation
- **Code-Cleanup** (~1500 Zeilen deprecated Code entfernt)
- **Universal Search Filter** für Effects, Sources, Files (v2.3.1)
- **Multi-Video-Source Support** via `video_sources` config (v2.3.1)
- **Default Effect Chains** via config.json (Player & Clip-Level) (v2.3.1)
- **Multi-Layer Compositing System** (v2.3.2):
  - Clip-based layers (per playlist item)
  - Layer 0 = base clip (immutable)
  - Overlay layers with blend modes (Normal, Multiply, Screen, Overlay, Add, Subtract)
  - Per-layer opacity control (0-100%)
  - Layer CRUD API (`/api/clips/{clip_id}/layers`)
  - Drag-drop layer management in UI
  - Thread-safe layer loading with auto-reload
  - Session state persistence for layers

---

*Siehe [HISTORY.md](HISTORY.md) für abgeschlossene Features (v1.x - v2.3)*
