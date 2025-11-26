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

### 1.1 🔌 Plugin-System erweitern (~8-12h)

- [ ] **Generator-Plugins (3-4h):**
  - Scripts nach `plugins/generators/` migrieren
  - plasma, rainbow_wave, pulse, matrix_rain, fire, etc.
  - METADATA + PARAMETERS für alle Generatoren
  
- [ ] **Preset-System (2-3h):**
  - Parameter-Sets speichern/laden
  - Preset-Manager API (CRUD)
  - UI: Preset-Selector & Editor

- [ ] **UI-Generierung (3-4h):**
  - Automatische Form-Generierung aus PARAMETERS-Array
  - Parameter-Panel im Web-Interface
  - Live-Preview beim Parameter-Ändern

- [ ] **Source-Plugins (optional, 4-6h):**
  - Webcam, LiveStream, Screencapture

---

### 1.2 🔄 Transition-Plugin-System (~8-10h)

- [ ] **PluginType.TRANSITION (3h):**
  - `process_transition(frame_a, frame_b, progress)` Methode
  - Basis Transition-Plugins: Fade, Wipe (Left/Right/Top/Bottom), Dissolve

- [ ] **Player Integration (2h):**
  - Transition-Buffering (letzter Frame)
  - apply_transition() bei Clip-Wechsel

- [ ] **API & Config (2h):**
  - `/api/player/transition/config` Endpoints
  - Global & Per-Clip Transition-Settings

- [ ] **UI (3h):**
  - Transition-Settings Section
  - Enable/Disable Toggle
  - Effect-Dropdown + Duration-Slider (0.1s - 5.0s)
  - Easing-Function Selector

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

### 4.1 🎥 Multi-Video-Routing per Art-Net-Objekt (~12-20h)

- [ ] **Grundidee:** Mehrere Videos gleichzeitig, jedes LED-Objekt bekommt eigenes Video
- [ ] **Architektur:**
  - Mehrere Player-Instanzen parallel (Video1, Video2, Video3)
  - LED-Objekte definieren (Name, Universe-Range, Pixel-Count)
  - Routing-Config: `{"object": "strip_1", "video_player_id": "video_1"}`
  
- [ ] **Kartendeck-UI:**
  ```
  PLAYLIST (Horizontal Scroll)
  ┌─────────────┬─────────────┬─────────────┬─────────────┐
  │   DECK 1    │   DECK 2    │   DECK 3    │   DECK 4    │
  │ ┌─────────┐ │ ┌─────────┐ │ ┌─────────┐ │    [+]    │ │
  │ │ Clip 1  │ │ │ Clip 5  │ │ │ Clip 8  │ │ Neu       │ │
  │ │fire.mp4 │ │ │water.mp4│ │ │plasma   │ │           │ │
  │ │▶ 00:15  │ │ │▶ 00:30  │ │ │▶ 01:00  │ │           │ │
  │ │→strip_1 │ │ │→panel_1 │ │ │→ring_1  │ │           │ │
  │ └─────────┘ │ └─────────┘ │ └─────────┘ │           │ │
  │   ┌───────┐ │   ┌───────┐ │             │           │ │
  │   │Clip 2 │ │   │Clip 6 │ │             │           │ │
  │   │glow   │ │   │spark  │ │             │           │ │
  │   └───────┘ │   └───────┘ │             │           │ │
  │     ┌─────┐ │     ┌─────┐ │             │           │ │
  │     │Clip3│ │     │Clip7│ │             │           │ │
  │     └─────┘ │     └─────┘ │             │           │ │
  └─────────────┴─────────────┴─────────────┴─────────────┘
       ↑ Clips gestapelt wie Karten - Platzsparend!
  ```

- [ ] **Features:**
  - Deck = Spalte (enthält gestapelte Clips)
  - Clips = übereinander gestapelt, minimiert
  - Click auf Deck → Detail-Ansicht mit allen Clips
  - Pro Clip: Eigene Effekte, eigene Output-Zuweisung
  - Playback-Modi: Parallel (alle gleichzeitig) oder Sequential

- [ ] **Implementierung:**
  - Phase 1: LED-Objekt-Definition & Config (~2h)
  - Phase 2: Multi-Player-Manager (~2h)
  - Phase 3: Routing-System & Frame-Collection (~2h)
  - Phase 4: API-Endpoints (~2h)
  - Phase 5: UI (Deck-System, Multi-Preview) (~3h)

**JSON-Config Beispiel:**
```json
{
  "led_objects": [
    {"name": "strip_left", "universes": [1,2], "pixels": 200},
    {"name": "strip_right", "universes": [3,4], "pixels": 200},
    {"name": "panel_center", "universes": [5,6], "pixels": 256}
  ],
  "routing": [
    {"object": "strip_left", "player_id": "video_1"},
    {"object": "strip_right", "player_id": "video_2"},
    {"object": "panel_center", "player_id": "video_3"}
  ]
}
```

---

### 4.2 🔮 Neue Frame Sources (~12-20h)

- [ ] **ShaderToy Source (8-12h):**
  - ModernGL/PyOpenGL Integration
  - GLSL Shader Support (Shadertoy-kompatibel)
  - Uniform Variables (iTime, iResolution, iMouse)

- [ ] **ImageSequence Source (2-3h):**
  - PNG/JPG Sequenz-Support
  - Automatische Frame-Nummerierung

- [ ] **LiveStream Source (2-5h):**
  - RTSP/HTTP Stream Support
  - FFmpeg/GStreamer Integration

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

### 5.2 🛠️ Weitere Verbesserungen

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

## 📚 Status (Stand: 2025-11-26)

### ✅ Fertiggestellt (v2.3)
- **Unified API Architecture** mit UUID-basiertem Clip-Management
- **Dual-Player-System** (Video Preview + Art-Net Output)
- **Plugin-System** vollständig implementiert (PluginBase, PluginManager, API)
- **17 Effect-Plugins:** 11 Farb-Manipulation, 5 Time & Motion, 1 Blur
- **ClipRegistry** mit UUID-basierter Clip-Identifikation
- **Code-Cleanup** (~1500 Zeilen deprecated Code entfernt)

---

*Siehe [HISTORY.md](HISTORY.md) für abgeschlossene Features (v1.x - v2.3)*
