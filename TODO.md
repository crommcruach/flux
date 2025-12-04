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

## 🔥 PRIORITÄT 1 - Quick Wins (~22-34h)
**Niedriger Aufwand, hoher Nutzen - sofort umsetzbar**

### 1.0 🔌 Plugin-System erweitern (~8-12h)

- [ ] **Layer-Effekte über Clip FX Tab (8-12h):**
  - API-Endpoints für Layer-Effekte (POST/PATCH/DELETE `/api/clips/<clip_id>/layers/<layer_id>/effects`)
  - Layer-Selection-Logik: Click auf Layer-Card → Layer ausgewählt (visuelles Feedback)
  - Clip FX Tab erweitern: Dynamischer Titel ('Clip FX' vs 'Layer FX')
  - API-Calls umleiten wenn Layer ausgewählt (zu Layer-Endpoints statt Clip-Endpoints)
  - Drag & Drop von Effekten funktioniert für Clip UND Layer
  - Backend: apply_layer_effects() Integration, Layer.effects Array populieren

---

### 1.1 🎬 Playlist-Sequenzer (~8-12h)

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

### 1.3 🎹 MIDI-over-Ethernet Support (~6-10h)

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

### 3.3 🎬 HAP Codec Support & Video Converter ✅ COMPLETED (~12h)

- [x] **HAP Codec Decoder (4-5h):** ✅ COMPLETED (2025-12-02)
  - ✅ HAP Varianten: HAP (DXT1), HAP Alpha (DXT5), HAP Q (BC7)
  - ✅ FFmpeg Integration: libavcodec HAP Support
  - ✅ Automatische HAP-Format-Erkennung
  - ✅ Fallback auf Standard-Codecs
  - ✅ Performance-Messung

- [x] **Universal Video Converter (4-7h):** ✅ COMPLETED (2025-12-02)
  - ✅ Input-Formate: AVI, MP4, MOV, GIF, PNG-Sequences
  - ✅ Output-Profile: HAP (Performance), H.264 (Hardware-Encoding), H.264 NVENC (GPU)
  - ✅ Batch-Processing: Ganze Ordner konvertieren mit glob patterns (recursive)
  - ✅ Resize Modes: none, fit, fill, stretch, auto
  - ✅ Loop-Optimierung: Nahtlose Loops mit FFmpeg fade filters
  - ✅ Separate HTML-Page: Eigenständige Converter-UI (converter.html)
  - ✅ FFmpeg-Wrapper mit Progress-Tracking
  - ✅ REST API Endpoints: status, formats, info, convert, batch, upload, canvas-size
  - ✅ Web-UI mit separater HTML-Page und Dark Mode

- [x] **Converter UI Implementation (3h):** ✅ COMPLETED (2025-12-02)
  - ✅ File Browser Integration (FilesTab component mit tree/list view)
  - ✅ Drag & Drop Zone (from file browser + from file system)
  - ✅ Local File Upload (browse button + drag & drop support)
  - ✅ Dual-Mode Selection: Browser Mode (drag & drop) vs Pattern Mode (glob)
  - ✅ Multi-file Sequential Conversion mit progress tracking
  - ✅ Canvas Size Integration (loads from config.json, fallback 60x300)
  - ✅ Output Directory Selection
  - ✅ Format Selection Cards (HAP, HAP Alpha, HAP Q, H.264, H.264 NVENC)
  - ✅ Conversion Options (Resize Mode, Optimize Loop, Target Size)
  - ✅ Progress Bar & Queue Display
  - ✅ Results Summary (success/failed counts, compression ratio)
  - ✅ Consistent Styling (matches app design with CSS variables)
  - ✅ Search Filter für File Browser (works in both tree and list view)
  - ✅ Auto-expand folders when searching in tree view

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

## 🎨 PRIORITÄT 5 - Niedrig-Komplex, Niedrig-Priorität (~14-20h)
**Maintenance, Polishing, Nice-to-have**

### 5.1 🔌 Plugin-System (Optional) (~2-3h)

- [ ] **Preset System für Effect Parameters (2-3h):**
  - Effect-Preset-Speicherung (Name + Parameter-Werte)
  - Preset-Library pro Effect-Plugin
  - UI: Save/Load/Delete Presets im Effect-Panel
  - API: `/api/effects/<effect_id>/presets` CRUD
  - Dokumentation: `docs/EFFECT_PRESETS.md`

---

### 5.2 🎨 GUI-Optimierungen (~12-18h)

- [ ] **Art-Net Preview Expansion (4-6h):**
  - **Realtime LED Object Visualization:**
    - Live-View aller LED-Objekte mit aktuellen Farben
    - 2D-Representation: LED-Strip/Matrix als Pixel-Reihe
    - Farbcodierung: RGB-Werte als colored boxes
    - Auto-Update: 10-30 FPS live refresh
  - **Object-List View:**
    - Universe-Info pro Objekt (Universe 1-4, etc.)
    - Pixel-Count & Status (Online/Offline)
    - DMX-Address-Range anzeigen
  - **Features:**
    - Toggle zwischen Compact-View (Icons) und Expanded-View (Full Colors)
    - Click auf Objekt → Highlight in Preview
    - Color-Picker: Click auf Pixel → zeigt RGB-Wert
    - Performance-Mode: Reduced FPS bei niedriger CPU
  - **Implementierung:**
    - Phase 1: WebSocket für Live-DMX-Data (~2h)
    - Phase 2: Canvas-Renderer für LED-Objects (~2h)
    - Phase 3: UI-Controls & Toggle (~1h)
    - Phase 4: Performance-Optimierung (~1h)

- [ ] **Drag & Drop Layout-Editor:**
  - GridStack.js Integration
  - Panels frei verschieben & resizen
  - LocalStorage-Persistierung
  - Preset-Layouts: "Standard", "Video-Focus", "Compact"

---

### 5.3 🧪 Testing & Verification

- [ ] **Milkdrop via Screencapture testen:**
  - Screencapture-Generator mit Milkdrop/projectM-Fenster
  - Region-Capture für optimale Performance
  - Alternative: Window-Capture API

- [x] **Multi-Layer System Testing (~2-4h):** ✅ COMPLETED (2025-12-02)
  - ✅ Run `tests/test_api_layers.py` to verify all tests pass
  - ✅ Test live multi-layer playback with different FPS sources
    - ✅ Verify: Overlay läuft nicht doppelt so schnell bei höherer FPS
    - ✅ Verify: Frame-Skipping funktioniert bei niedrigerer FPS
  - ✅ Verify snapshot restore with layers
  - ✅ Test generator + video layer combinations
  - ✅ Test layer with effects + blend modes
  - ✅ Test autoplay with multi-layer clips
  - ✅ Test transitions on layer 0 with overlays active

### 5.4 🛠️ Weitere Verbesserungen

- [ ] **File Browser Thumbnails (~6-10h):**
  - **Thumbnail Generation:**
    - Video: Erstes Frame als Thumbnail (FFmpeg -ss 0 -vframes 1)
    - Image: Resized Preview (Pillow/OpenCV)
    - Cache-System: Thumbnails in `data/thumbnails/` speichern
    - Lazy-Loading: Thumbnails on-demand generieren
  - **UI Features:**
    - Toggle-Button: Enable/Disable Thumbnail-Anzeige
    - List-View: Thumbnail neben Dateinamen (50x50px)
    - Tree-View: Thumbnail neben File-Icon (40x40px)
    - Hover-Popup: Größeres Preview (200x200px) bei Mouse-Hover
    - Loading-State: Spinner während Thumbnail-Generation
  - **Performance:**
    - Thumbnail-Size: 100x100px (JPEG, 85% Qualität)
    - Max. Generation-Time: 500ms pro Video
    - Batch-Generation: API-Endpoint `/api/files/thumbnails/generate`
    - Cache-Cleanup: Alte Thumbnails nach 30 Tagen löschen
  - **Implementation:**
    - Phase 1: Thumbnail-Generator (FFmpeg + Pillow) (~2h)
    - Phase 2: Cache-System & API (~2h)
    - Phase 3: FilesTab UI Integration (~2h)
    - Phase 4: Toggle & Settings (~1h)

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
| **P1** | Niedrig | Hoch | ~22-34h |
| **P2** | Mittel | Hoch | ~14-24h |
| **P3** | Mittel | Mittel | ~21-39h (✅ 12h completed) |
| **P4** | Hoch | Hoch | ~24-40h |
| **P5** | Niedrig | Niedrig | ~14-21h |
| **P6** | Sehr Hoch | Mittel | ~64-86h |
| **GESAMT** | | | **~159-244h** |

---

## 🎯 Empfohlene Umsetzungs-Reihenfolge

### Phase 1: Foundation (P1) - ~22-34h
1. Plugin-System erweitern (Layer-Effekte)
2. Playlist-Sequenzer
3. MIDI-over-Ethernet Support

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

### Phase 5+: Polish & Future (P5+P6) - ~78-107h
1. Effect Presets (Optional)
2. GUI-Optimierungen
3. Maintenance & Tests
4. Optional: Timeline-Sequenzer

**Ziel:** Production-Polishing & Langzeit-Features

---

## 📚 Status (Stand: 2025-12-02)

### ✅ Fertiggestellt (v2.3)
- **Unified API Architecture** mit UUID-basiertem Clip-Management
- **Dual-Player-System** (Video Preview + Art-Net Output)
- **Plugin-System** vollständig implementiert (PluginBase, PluginManager, API)
- **18 Effect-Plugins:** 11 Farb-Manipulation, 5 Time & Motion, 1 Blur, 1 Blending
- **ClipRegistry** mit UUID-basierter Clip-Identifikation
- **Code-Cleanup** (~1500 Zeilen deprecated Code entfernt)
- **Universal Search Filter** für Effects, Sources, Files (v2.3.1)
- **Multi-Video-Source Support** via `video_sources` config (v2.3.1)
- **Default Effect Chains** via config.json (Player & Clip-Level) (v2.3.1)
- **Transition Plugin System** mit Fade Transition & Reusable UI Component (v2.3.1)
- **Multi-Layer Compositing System** (v2.3.2):
  - Clip-based layers (per playlist item)
  - Layer 0 = base clip (immutable)
  - Overlay layers with blend modes (Normal, Multiply, Screen, Overlay, Add, Subtract)
  - Per-layer opacity control (0-100%)
  - Layer CRUD API (`/api/clips/{clip_id}/layers`)
  - Drag-drop layer management in UI
  - Thread-safe layer loading with auto-reload
  - Session state persistence for layers
- **Clip Trimming System** (v2.3.3):
  - In/Out Points pro Clip mit Non-Destructive Editing
  - Reverse Playback Support
  - Ion.RangeSlider UI mit Collapsible Section
  - Right-Click Reset to Full Range
  - Backend as Source of Truth für Clip IDs
  - Live-Apply bei aktiver Wiedergabe
- **HAP Codec & Universal Video Converter** (v2.3.4):
  - FFmpeg-based video converter mit HAP codec support
  - Multiple output formats: HAP, HAP Alpha, HAP Q, H.264, H.264 NVENC
  - Batch processing mit glob patterns (recursive support)
  - Resize modes: none, fit, fill, stretch, auto
  - Loop optimization mit fade in/out
  - Standalone converter.html page mit dark mode
  - File browser integration (FilesTab component)
  - Drag & drop from file browser and file system
  - Local file upload support
  - Dual-mode selection: Browser Mode vs Pattern Mode
  - Multi-file sequential conversion mit progress tracking
  - Smart path resolution (workspace root + video/ directory)
  - Search filter for file browser (tree + list view)
  - Auto-expand folders when searching

---

*Siehe [HISTORY.md](HISTORY.md) für abgeschlossene Features (v1.x - v2.3)*
