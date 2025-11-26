# Py_artnet - TODO Liste

> **Siehe [HISTORY.md](HISTORY.md) für abgeschlossene Features (v1.x - v2.3)**

## 🚀 Geplante Features (nach Komplexität & Priorität sortiert)

---

## 🔥 PRIORITÄT 1 - Quick Wins (Hoch-Wert, Niedrig-Komplex)

### 1.1 🔌 Plugin-System erweitern (~8-12h, Hoch-Priorität)

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

### 1.2 🔄 Transition-Plugin-System (~8-10h, Hoch-Priorität)

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

### 1.3 🎬 Playlist-Sequenzer (~8-12h, Hoch-Priorität)

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

### 1.4 🎹 MIDI-over-Ethernet Support (~6-10h, Hoch-Priorität)

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

## ⚡ PRIORITÄT 2 - Mittel-Komplex, Hoch-Wert

### 2.1 ⚡ WebSocket Command Channel (~4-6h, Mittel-Priorität)

- [ ] **Preview Stream Optimierung (4-6h):**
  - **Problem aktuell:**
    - MJPEG-Stream (Motion JPEG) → jedes Frame einzeln als JPEG
    - Hohe CPU-Last durch ständiges JPEG-Encoding
    - Hohe Bandbreite (1-5 Mbps pro Stream)
    - Ruckler bei schwacher CPU oder schlechtem Netzwerk
  - **Lösung 1: Adaptive Framerate & Qualität (2-3h)**
    - **Dynamische FPS:** 30 FPS → 15 FPS wenn CPU-Last hoch
    - **Adaptive JPEG-Qualität:** 85% → 60% bei Bandbreiten-Engpass
    - **Frame-Skip:** Bei Überlast nur jedes 2. Frame senden
    - **Resolution-Scaling:** Automatisch auf 50% bei schwacher Performance
  - **Lösung 2: WebRTC/HLS statt MJPEG (2-3h)**
    - **WebRTC (empfohlen):**
      - Hardware-beschleunigtes H.264-Encoding (GPU)
      - Ultra-niedrige Latenz (<100ms)
      - Automatische Bandbreiten-Anpassung
      - ~10x weniger CPU-Last vs. MJPEG
      - ~5x weniger Bandbreite (0.2-1 Mbps)
    - **HLS (HTTP Live Streaming):**
      - Für Browser ohne WebRTC-Support
      - Segment-basiert (2-5s Latenz)
      - CDN-freundlich für Remote-Access
  - **Features:**
    - **Multi-Quality:** Low (480p), Medium (720p), High (1080p)
    - **Bandwidth-Limiter:** Max. Bitrate pro Stream konfigurierbar
    - **Connection-Limit:** Max. 5 Preview-Clients (konfigurierbar)
    - **Preview-Modes:**
      - `live` - Echtzeit (volle FPS, höchste CPU)
      - `smooth` - Adaptive FPS (Balance)
      - `efficient` - Niedrige FPS, niedrige Qualität (Energie sparen)
    - **Frame-Buffer:** Letzte N Frames cachen für neue Clients (sofortiger Start)
  - **Config-Beispiel:**
    ```json
    {
      "preview_streams": {
        "protocol": "webrtc",           // webrtc, hls, mjpeg
        "max_clients": 5,
        "qualities": {
          "low": {"width": 640, "height": 480, "fps": 15, "bitrate": "200k"},
          "medium": {"width": 1280, "height": 720, "fps": 30, "bitrate": "500k"},
          "high": {"width": 1920, "height": 1080, "fps": 30, "bitrate": "1500k"}
        },
        "adaptive": {
          "enabled": true,
          "min_fps": 10,
          "max_fps": 30,
          "cpu_threshold": 80,         // Bei >80% CPU → FPS reduzieren
          "bandwidth_limit": "5Mbps"   // Max. Bandbreite für alle Streams
        }
      }
    }
    ```
  - **UI-Integration:**
    - Quality-Selector: Low/Medium/High
    - Bandwidth-Meter: Anzeige aktueller Bandbreite
    - FPS-Counter: Echte FPS anzeigen
    - Latency-Display: Stream-Latenz in ms
  - **Implementierung:**
    - Phase 1: Adaptive FPS & Quality (~2h)
    - Phase 2: WebRTC Integration (~2h)
    - Phase 3: Connection-Limit & Bandwidth-Limiter (~1h)
    - Phase 4: UI (Quality-Selector, Stats) (~1h)
  - **Performance-Ziel:**
    - MJPEG: ~40-60% CPU, 2-5 Mbps
    - WebRTC: ~5-10% CPU, 0.2-1 Mbps
    - Latenz: <100ms (WebRTC), <200ms (MJPEG optimiert)

### 2.2 🌐 Multi-Network-Adapter Support (~4-6h, Mittel-Priorität)
  - Thread-Pool für cv2.imencode()
  - Nur für MJPEG-Fallback (wenn WebRTC nicht verfügbar)
  - Geschätzter Gewinn: 25-35% CPU-Reduktion
  
- [ ] **Video-Optimierungs-Script (2-5h):**
  - Automatische Skalierung auf Canvas-Größe
  - Hardware-Codec Encoding (H.264 mit NVENC/QSV)
  - Bitrate-Optimierung, Keyframe-Intervall

### 2.3 ⚡ Preview Stream Optimierung (~4-6h, Mittel-Priorität)

- [ ] **HAP Codec Decoder (4-5h):**
  - **Grundidee:** Ultra-schnelles Decoding für Performance-kritische Installationen
  - **HAP Varianten:**
    - HAP (DXT1) - Verlustbehaftet, klein, schnell
    - HAP Alpha (DXT5) - Mit Alpha-Kanal
    - HAP Q (BC7) - Höhere Qualität
  - **FFmpeg Integration:**
    - libavcodec HAP Support prüfen/aktivieren
    - Direktes Decoding ohne CPU-intensive Decompression
    - GPU-Texture-Upload (wenn möglich)
  - **Features:**
    - Automatische HAP-Format-Erkennung
    - Fallback auf Standard-Codecs wenn HAP nicht verfügbar
    - Performance-Messung (HAP vs. H.264)
  - **Vorteile:**
    - 5-10x schnelleres Decoding vs. H.264
    - Geringere CPU-Last (ideal für Multi-Video-Setups)
    - Frame-genaues Seeking ohne Verzögerung

- [ ] **Universal Video Converter (4-7h):**
  - **Grundidee:** Batch-Converter für alle Formate → HAP/H.264
  - **Input-Formate:**
    - Videos: AVI, MP4, MOV, MKV, WMV, FLV, WEBM
    - Image-Sequenzen: PNG, JPG, TIFF, BMP
    - GIF → Video-Konvertierung
    - Codecs: MPEG-4, H.264, H.265, VP9, ProRes, etc.
  - **Output-Profile:**
    - **HAP** (empfohlen für Performance)
    - **H.264** (Hardware-Encoding, NVENC/QSV falls verfügbar)
    - **Optimiert für LED:** Canvas-Größe, Loop-ready (Keyframes)
  - **Features:**
    - **Batch-Processing:** Ganze Ordner konvertieren
    - **Auto-Resize:** Auf Canvas-Größe skalieren (aus config.json)
    - **Loop-Optimierung:** Keyframe am Start/Ende für nahtlose Loops
    - **Metadata-Preservation:** Behalte FPS, Duration, etc.
    - **Progress-UI:** Live-Fortschritt im Web-Interface
    - **CLI-Tool:** `convert video <input> <output> --format hap --resize auto`
  - **UI-Integration:**
    - Converter-Tab im Web-Interface
    - Drag & Drop für Videos
    - Preset-Auswahl (HAP Fast, HAP Quality, H.264 HW, etc.)
    - Batch-Queue mit Progress-Bars
    - Preview: Before/After Vergleich
  - **Implementierung:**
    - Phase 1: FFmpeg-Wrapper für HAP/H.264 Encoding (~2h)
    - Phase 2: Batch-Processing Engine (~2h)
    - Phase 3: CLI-Tool (~1h)
    - Phase 4: Web-UI (Converter-Tab) (~2h)
  - **CLI-Beispiele:**
    ```bash
    # Einzelnes Video zu HAP
    python convert.py video.mp4 --format hap --resize 60x300
    
    # Batch-Convert ganzer Ordner
    python convert.py kanal_1/*.mp4 --format hap --auto-resize
    
    # GIF zu HAP-Video
    python convert.py animation.gif --format hap --loop
    
    # PNG-Sequenz zu HAP
    python convert.py frames/*.png --format hap --fps 30
    ```

---

## 🔧 PRIORITÄT 3 - Mittel-Komplex, Mittel-Wert

### 3.1 🎨 Effect-Bibliothek erweitern (~15-25h, Mittel-Priorität)

- [ ] **Multi-Video-Routing per Art-Net-Objekt (6-10h):**
  - **Grundidee:** Mehrere Videos gleichzeitig als Eingänge, jedes LED-Objekt bekommt eigenes Video
  - **Architektur:**
    - Mehrere Player-Instanzen parallel (Video1, Video2, Video3, ...)
    - LED-Objekte in config.json definieren (Name, Universe-Range, Pixel-Count)
    - Routing-Config: `{"object": "strip_1", "video_player_id": "video_1"}`
    - ArtNetManager sammelt Frames von allen zugewiesenen Playern
  - **Features:**
    - Objekt-Definition: `{"name": "strip_1", "universes": [1,2,3], "pixels": 300}`
    - Video-Assignment per Objekt: Objekt 1 → Video A, Objekt 2 → Video B
    - Unabhängige Playback-Controls pro Player (Play, Pause, Speed, Brightness)
    - **Deck-basiertes UI:** Clips als Layers übereinander (wie VJ-Software)
    - **Pro Deck/Layer:** Video-Auswahl, Effekte, Output-Objekt-Zuweisung
    - Preview-Ansicht: Alle Objekte mit ihren Videos gleichzeitig
  - **Use-Cases:**
    - Verschiedene LED-Streifen an verschiedenen Positionen mit eigenen Videos
    - Multiple LED-Panels mit unterschiedlichen Inhalten synchron
    - Beispiel: Strip 1 (Feuer), Strip 2 (Wasser), Panel (Logo)
  - **UI-Konzept (Gestapelte Clips wie Kartendeck):**
    ```
    PLAYLIST (Horizontal Scroll)
    ┌─────────────┬─────────────┬─────────────┬─────────────┐
    │   DECK 1    │   DECK 2    │   DECK 3    │   DECK 4    │
    │ ┌─────────┐ │ ┌─────────┐ │ ┌─────────┐ │ ┌─────────┐ │
    │ │ Clip 1  │ │ │ Clip 5  │ │ │ Clip 8  │ │    [+]    │ │  ← Neues Deck
    │ │fire.mp4 │ │ │water.mp4│ │ │plasma   │ │           │ │
    │ │▶ 00:15  │ │ │▶ 00:30  │ │ │▶ 01:00  │ │           │ │
    │ │→strip_1 │ │ │→panel_1 │ │ │→ring_1  │ │           │ │
    │ └─────────┘ │ └─────────┘ │ └─────────┘ │           │ │
    │   ┌───────┐ │   ┌───────┐ │             │           │ │
    │   │Clip 2 │ │   │Clip 6 │ │             │           │ │
    │   │glow.mp│ │   │spark.m│ │             │           │ │
    │   │→strip2│ │   │→panel2│ │             │           │ │
    │   └───────┘ │   └───────┘ │             │           │ │
    │     ┌─────┐ │     ┌─────┐ │             │           │ │
    │     │Clip3│ │     │Clip7│ │             │           │ │
    │     │logo │ │     │rain │ │             │           │ │
    │     └─────┘ │     └─────┘ │             │           │ │
    │      ┌───┐  │              │             │           │ │
    │      │C4 │  │              │             │           │ │
    │      └───┘  │              │             │           │ │
    └─────────────┴─────────────┴─────────────┴─────────────┘
         ↑ Gestapelt wie Karten - Platzsparend!
    
    DETAIL-ANSICHT (Click auf Deck öffnet)
    ┌───────────────────────────────────────────────────────┐
    │ DECK 1 - Clips                              [×]       │
    ├───────────────────────────────────────────────────────┤
    │ ┌─────────────────────────────────────────────────┐   │
    │ │ Clip 1: fire.mp4                    [▶][⏸][⏹] │   │
    │ │ Effects: Blur, Tint                             │   │
    │ │ Output: ☑ strip_1  ☑ strip_2  ☐ panel_1       │   │
    │ │ Duration: 00:15  Speed: 1.0x  Brightness: 100% │   │
    │ └─────────────────────────────────────────────────┘   │
    │ ┌─────────────────────────────────────────────────┐   │
    │ │ Clip 2: glow.mp4                    [▶][⏸][⏹] │   │
    │ │ Effects: Trails                                 │   │
    │ │ Output: ☑ strip_2  ☐ strip_1  ☐ panel_1       │   │
    │ └─────────────────────────────────────────────────┘   │
    │ ┌─────────────────────────────────────────────────┐   │
    │ │ Clip 3: logo.mp4                    [▶][⏸][⏹] │   │
    │ │ Output: ☐ strip_1  ☐ strip_2  ☑ panel_1       │   │
    │ └─────────────────────────────────────────────────┘   │
    │                                                        │
    │ [+ Add Clip]  [Reorder ↕]  [Play All Sequential]     │
    └───────────────────────────────────────────────────────┘
    ```
    - **Deck = Spalte in Playlist** (enthält gestapelte Clips)
    - **Clips = Karten im Deck** (übereinander gestapelt, minimiert dargestellt)
    - **Kompakte Darstellung:** Nur Top-Clip voll sichtbar, darunter nur Thumbnail-Stack
    - **Click auf Deck:** Öffnet Detail-Ansicht mit allen Clips
    - **Drag & Drop:** Videos auf Deck ziehen = neuer Clip im Stack
    - **Reorder:** Clips innerhalb Deck sortieren (Drag & Drop)
    - **Pro Clip:** Eigene Effekte, eigene Output-Zuweisung
    - **Playback-Modi:**
      - **Parallel:** Alle Clips gleichzeitig (Standard)
      - **Sequential:** Clips nacheinander abspielen
    - **Vorteile:**
      - ✅ Extrem platzsparend (1 Spalte = beliebig viele Clips)
      - ✅ Übersichtlich (auf einen Blick alle Decks sehen)
      - ✅ Schnelles Arbeiten (Drag & Drop, Click zum Erweitern)
      - ✅ Flexibel (gleicher Clip kann in mehreren Decks sein)
  - **Implementierung:**
    - Phase 1: LED-Objekt-Definition & Config (~2h)
    - Phase 2: Multi-Player-Manager (~2h)
    - Phase 3: Routing-System & Frame-Collection (~2h)
    - Phase 4: API-Endpoints (~2h)
    - Phase 5: UI (Deck-Layer-System, Multi-Preview) (~3h)
  - **JSON-Config Beispiel:**
    ```json
    {
      "led_objects": [
        {"name": "strip_left", "universes": [1, 2], "pixels": 200, "start_channel": 1},
        {"name": "strip_right", "universes": [3, 4], "pixels": 200, "start_channel": 1},
        {"name": "panel_center", "universes": [5, 6], "pixels": 256, "start_channel": 1}
      ],
      "routing": [
        {"object": "strip_left", "player_id": "video_1"},
        {"object": "strip_right", "player_id": "video_2"},
        {"object": "panel_center", "player_id": "video_3"}
      ]
    }
    ```

- [ ] **Effect-Profile/Presets für Videos (4-6h):**
  - Named Presets (z.B. "psychedelic", "glitch", "vintage")
  - Per-Video Preset-Zuweisung in Playlist
  - Preset-Manager API (CRUD)
  - Import/Export von Preset-Bibliotheken

---

## 🚀 PRIORITÄT 4 - Hoch-Komplex, Hoch-Wert

### 4.1 🎥 Multi-Video-Routing per Art-Net-Objekt (~12-20h, Mittel-Priorität)
  - Separate Preview & ArtNet Ausgaben
  - Preview kann LayerSource sein (Overlays)
  - ArtNet bleibt einfache VideoSource (Performance)

### 4.2 🔮 Neue Frame Sources (~12-20h, Niedrig-Priorität)

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

## 🎨 PRIORITÄT 5 - Niedrig-Komplex, Niedrig-Priorität

### 5.1 🎨 GUI-Optimierungen (~8-12h, Niedrig-Priorität)

- [ ] **Drag & Drop Layout-Editor:**
  - GridStack.js Integration
  - Panels frei verschieben & resizen
  - LocalStorage-Persistierung
  - Preset-Layouts: "Standard", "Video-Focus", "Compact"

### 5.2 🛠️ Weitere Verbesserungen (Niedrig-Priorität)

- [ ] **MIDI Control via Ethernet (minimale Latenz) (6-10h):**
  - **Grundidee:** MIDI-Signale über Ethernet statt USB für <5ms Latenz
  - **Problem mit klassischem MIDI:**
    - USB-MIDI: ~10-30ms Latenz (USB-Polling, OS-Overhead)
    - MIDI-Hardware: Zusätzliche Verkabelung, begrenzte Reichweite
    - Kein Multicast (1:1 Verbindung)
  - **Lösung: MIDI-over-Ethernet:**
    - MIDI-Controller auf Client-Gerät (Laptop, Tablet, Smartphone)
    - MIDI-Signale über WebSocket/UDP an Server
    - Direkte Verarbeitung ohne USB-Overhead
    - <5ms Latenz (LAN), <20ms (WiFi)
  - **Protokolle:**
    - **WebSocket-MIDI (empfohlen):**
      - Web-MIDI API (Browser nativ)
      - Bidirektional (Server → Client Feedback)
      - Automatische Reconnect
      - JSON oder Binary (MIDI-Raw-Bytes)
    - **RTP-MIDI (optional):**
      - Standard-Protokoll (Apple MIDI-Network)
      - UDP-basiert (noch niedriger Latenz)
      - Multicast-fähig (1:N)
  - **Client-Optionen:**
    - **Browser (empfohlen):** Web-MIDI API + WebSocket
    - **TouchOSC:** MIDI-Bridge zu WebSocket
    - **Lemur:** OSC/MIDI-Bridge
    - **Python-Client:** mido + WebSocket
    - **Hardware-Bridge:** USB-MIDI → Ethernet-Converter
  - **MIDI-Mapping:**
    ```json
    {
      "midi_mappings": [
        {
          "control": "CC",
          "channel": 1,
          "cc_number": 1,
          "target": "player_1.brightness",
          "min": 0.0,
          "max": 1.0,
          "curve": "linear"
        },
        {
          "control": "CC",
          "channel": 1,
          "cc_number": 2,
          "target": "player_1.speed",
          "min": 0.5,
          "max": 2.0,
          "curve": "exponential"
        },
        {
          "control": "Note",
          "channel": 1,
          "note": 60,
          "action": "player_1.play"
        },
        {
          "control": "Note",
          "channel": 1,
          "note": 61,
          "action": "blackout.toggle"
        }
      ]
    }
    ```
  - **Features:**
    - **MIDI-Learn:** Click auf Parameter → nächster MIDI-Input wird gemappt
    - **Multi-Controller:** Mehrere MIDI-Geräte gleichzeitig (via Ethernet)
    - **Feedback:** LED-Status zurück an Controller (Fader-Position, Button-LEDs)
    - **Curve-Mapping:** Linear, Exponential, Logarithmic, Custom
    - **Range-Mapping:** MIDI 0-127 → beliebiger Parameter-Range
    - **Latch-Mode:** Toggle statt Momentary
    - **Velocity-Sensitive:** Note-Velocity → Parameter-Intensity
  - **Use-Cases:**
    - **DJ-Setup:** MIDI-Controller (Fader, Knobs) für Live-Performance
    - **Tablet-Control:** iPad/Android mit TouchOSC über WiFi
    - **Remote-Control:** MIDI-Controller an entferntem Laptop → Ethernet → Server
    - **Multi-User:** Mehrere Techniker mit eigenen MIDI-Controllern gleichzeitig
  - **Client-Beispiel (Browser Web-MIDI):**
    ```javascript
    // Web-MIDI API + WebSocket
    navigator.requestMIDIAccess().then((midi) => {
      const inputs = midi.inputs.values();
      for (let input of inputs) {
        input.onmidimessage = (msg) => {
          // MIDI-Daten über WebSocket an Server
          ws.send(JSON.stringify({
            type: 'midi',
            status: msg.data[0],
            data1: msg.data[1],
            data2: msg.data[2],
            timestamp: msg.timeStamp
          }));
        };
      }
    });
    ```
  - **Server-Mapping-Engine:**
    - MIDI-Message → Parameter-Lookup
    - Value-Transformation (Curve, Range)
    - Command-Execution via WebSocket Command Channel
    - Feedback-Generation (zurück an Controller)
  - **Implementierung:**
    - Phase 1: WebSocket-MIDI-Handler (~2h)
    - Phase 2: MIDI-Mapping-Engine (~2h)
    - Phase 3: MIDI-Learn UI (~2h)
    - Phase 4: Client-Library (Browser) (~1h)
    - Phase 5: Feedback-System (~1h)
    - Phase 6: RTP-MIDI Support (optional) (~2h)
  - **UI-Integration:**
    - MIDI-Mapping-Tab im Web-Interface
    - Live-MIDI-Monitor (eingehende Messages anzeigen)
    - MIDI-Learn-Button bei jedem Parameter
    - Controller-Status (Verbunden/Getrennt)
    - Mapping-Presets (speichern/laden)
  - **Performance-Ziel:**
    - WebSocket-MIDI: <5ms Latenz (LAN), <20ms (WiFi)
    - RTP-MIDI: <3ms Latenz (LAN)
    - USB-MIDI (Vergleich): ~15-30ms
  - **Vorteile:**
    - ✅ Minimale Latenz (<5ms LAN)
    - ✅ Keine USB-Verkabelung nötig
    - ✅ Multi-Controller gleichzeitig
    - ✅ Remote-Steuerung möglich
    - ✅ Browser-basiert (keine extra Software)
    - ✅ Bidirektionales Feedback

---

## 🔬 PRIORITÄT 6 - Optional / Langfristig

### 6.1 ⏱️ Script-basierter Sequenzer (Optional, ~4-6h)
  - **Grundidee:** Separate WebSocket-Verbindung für Low-Latency Commands (parallel zu REST API)
  - **Problem mit REST:**
    - HTTP-Request-Overhead (Header, Connection-Setup)
    - Typisch 10-50ms Latenz pro Request
    - Nicht ideal für Echtzeit-Steuerung (MIDI, OSC, Live-Performance)
  - **WebSocket-Vorteile:**
    - Persistent Connection (einmalig verbinden)
    - Binär-Protokoll möglich (noch schneller)
    - <5ms Latenz für Commands
    - Bidirektional (Server kann Push-Updates senden)
  - **Zeitkritische Commands:**
    - **Playback:** play, pause, stop, seek (für MIDI/OSC-Sync)
    - **Parameter:** brightness, speed, effect_param (Live-Tweaking)
    - **Blackout:** sofortiger Blackout-Toggle
    - **Cue-Trigger:** Jump to Cue (für Show-Control)
    - **BPM-Sync:** Tempo-Updates von Audio-Analyse
  - **Protokoll-Design:**
    ```json
    // Request (JSON oder MessagePack)
    {
      "cmd": "play",
      "player_id": "video_1",
      "params": {"speed": 1.5}
    }
    
    // Response
    {
      "status": "ok",
      "latency_ms": 2.3
    }
    
    // Server Push (Status-Updates)
    {
      "event": "player_state_changed",
      "player_id": "video_1",
      "state": "playing",
      "frame": 1234
    }
    ```
  - **Features:**
    - **Command-Queue:** Befehle werden in Reihenfolge abgearbeitet
    - **Priority-Commands:** Blackout, Stop überspringen Queue
    - **Batch-Commands:** Mehrere Commands in einem Paket
    - **Compression:** Optional MessagePack statt JSON (50% kleiner)
    - **Fallback:** REST API bleibt verfügbar (Backward-Compatibility)
  - **Use-Cases:**
    - MIDI-Controller-Integration (Fader, Buttons)
    - OSC-Steuerung (TouchOSC, Lemur)
    - Live-Performance mit DJ/VJ-Setup
    - Audio-Reaktive Parameter-Updates (BPM-Sync)
    - Externe Show-Control-Software
  - **Implementierung:**
    - Phase 1: WebSocket Command Handler (~2h)
    - Phase 2: Command-Queue & Priority-System (~1h)
    - Phase 3: MessagePack Support (optional) (~1h)
    - Phase 4: Client-Library (Python/JS) (~1h)
  - **Client-Beispiel (JavaScript):**
    ```javascript
    const ws = new WebSocket('ws://localhost:5000/ws/commands');
    
    // Blackout sofort
    ws.send(JSON.stringify({cmd: 'blackout', value: true}));
    
    // Parameter live ändern
    ws.send(JSON.stringify({
      cmd: 'set_param',
      player_id: 'video_1',
      plugin_id: 'blur',
      param: 'strength',
      value: 15
    }));
    
    // Server-Events empfangen
    ws.onmessage = (msg) => {
      const event = JSON.parse(msg.data);
      if (event.event === 'frame_changed') {
        updateTimecode(event.frame);
      }
    };
    ```
  - **Performance-Ziel:**
    - REST API: ~20-50ms Latenz
    - WebSocket: <5ms Latenz
    - Command-Throughput: >200 Commands/Sekunde

### 6.2 📈 Timeline-Sequenzer (Optional, ~60-80h)
  - **Grundidee:** Control-Traffic (API, WebSocket) getrennt von Art-Net-Output (mehrere Adapter möglich)
  - **Problem aktuell:**
    - Alles läuft über einen Netzwerk-Adapter
    - Art-Net-Broadcast kann Control-Traffic stören (hohe Bandbreite)
    - Keine Trennung zwischen Management- und Output-Netzwerk
  - **Lösung: Network-Binding per Adapter:**
    ```json
    {
      "network_adapters": {
        "api": {
          "interface": "192.168.1.10",      // Adapter A: Control-Netzwerk
          "description": "Management LAN",
          "services": ["api", "websocket", "web_interface"]
        },
        "artnet_primary": {
          "interface": "10.0.0.50",         // Adapter B: Art-Net Netzwerk 1
          "description": "LED Strips 1-100",
          "services": ["artnet"],
          "universes": [1, 2, 3, 4, 5]      // Universes auf diesem Adapter
        },
        "artnet_secondary": {
          "interface": "10.0.1.50",         // Adapter C: Art-Net Netzwerk 2
          "description": "LED Panels 101-200",
          "services": ["artnet"],
          "universes": [6, 7, 8, 9, 10]
        }
      }
    }
    ```
  - **Features:**
    - **API-Binding:** Flask bindet an spezifisches Interface (z.B. 192.168.1.10)
    - **Art-Net-Routing:** Unterschiedliche Universes auf unterschiedlichen Adaptern
    - **Multi-Art-Net:** Mehrere Art-Net-Netzwerke parallel (z.B. Raum A + Raum B)
    - **Broadcast-Control:** Targeted Broadcast statt Broadcast-All
    - **Failover:** Automatischer Switch auf Backup-Adapter
    - **Auto-Discovery:** Liste aller verfügbaren Network-Interfaces
  - **Use-Cases:**
    - **Professionelle Installation:**
      - Adapter 1: Management (192.168.1.x) - API, WebSocket, Monitoring
      - Adapter 2: Art-Net Output (10.0.0.x) - LED Strips Links
      - Adapter 3: Art-Net Output (10.0.1.x) - LED Panels Rechts
    - **Multi-Location Setup:**
      - Adapter 1: Raum A (10.1.0.x) - Universes 1-10
      - Adapter 2: Raum B (10.2.0.x) - Universes 11-20
      - Adapter 3: Control (192.168.x.x) - Management
    - **Redundanz:**
      - Primary Art-Net über Adapter A
      - Backup Art-Net über Adapter B (gleiche Universes)
  - **Vorteile:**
    - ✅ Netzwerk-Segmentierung (weniger Kollisionen)
    - ✅ Höhere Bandbreite (Art-Net verteilt auf mehrere NICs)
    - ✅ Bessere Skalierbarkeit (>100 Universen möglich)
    - ✅ Professionelles Setup (Management getrennt von Output)
    - ✅ Flexibles Routing (Universe → Adapter-Mapping)
  - **Implementierung:**
    - Phase 1: Network-Interface-Discovery (~1h)
    - Phase 2: API-Binding-Config (~1h)
    - Phase 3: Art-Net Multi-Adapter-Routing (~2h)
    - Phase 4: UI (Network-Adapter-Auswahl) (~1h)
  - **Config-Beispiel (einfach):**
    ```json
    {
      "api_interface": "192.168.1.10",     // Management
      "artnet_interface": "10.0.0.50"      // Art-Net Output
    }
    ```
  - **Config-Beispiel (advanced):**
    ```json
    {
      "network": {
        "api": {
          "bind_address": "192.168.1.10",
          "port": 5000
        },
        "artnet": {
          "adapters": [
            {
              "interface": "10.0.0.50",
              "universes": [1, 2, 3, 4, 5],
              "broadcast": "10.0.0.255"
            },
            {
              "interface": "10.0.1.50",
              "universes": [6, 7, 8, 9, 10],
              "broadcast": "10.0.1.255"
            }
          ]
        }
      }
    }
    ```
  - **CLI-Tool:**
    ```bash
    # Liste aller Netzwerk-Interfaces
    python network.py list
    
    # Test Art-Net auf Interface
    python network.py test-artnet --interface 10.0.0.50
    
    # Bandbreiten-Messung
    python network.py measure --interface 10.0.0.50
    ```

- Upgrade von Playlist-Sequenzer zu visueller Timeline
- Features: Clip-Trimming, Scrubbing, Multi-Track, Audio-Sync
- **Nur bei komplexeren Anforderungen**

---

## 📊 Aktueller Status (Stand: 2025-11-26)

### ✅ Fertiggestellt (v2.3)
- **Unified API Architecture** mit UUID-basiertem Clip-Management
- **Dual-Player-System** (Video Preview + Art-Net Output)
- **Plugin-System** vollständig implementiert (PluginBase, PluginManager, API)
- **17 Effect-Plugins:** 11 Farb-Manipulation, 5 Time & Motion, 1 Blur
- **ClipRegistry** mit UUID-basierter Clip-Identifikation
- **Code-Cleanup** (~1500 Zeilen deprecated Code entfernt)

### 🎯 Empfohlene Reihenfolge
1. **Generator-Plugins** migrieren (Scripts → plugins/generators/)
2. **Preset-System** implementieren (Parameter-Sets speichern/laden)
3. **UI-Generierung** (automatische Forms aus PARAMETERS)
4. **Transition-System** (Fade, Wipe, Dissolve)
5. **Playlist-Sequenzer** (Show-Editor mit Transitions)
6. **Weitere Effekte** nach Bedarf (~30 Effekte offen)

### 🚀 Langfristige Vision
- **Audio-Reactive Support** - FFT-Analyse, BPM-Detection
- **Timeline-Sequenzer** - Full-Featured Show-Control
- **ShaderToy Integration** - GLSL Shader Support

---

## 📚 Hinweise
- ✅ ~~Plugin-System vor Sequenzer implementieren~~ **Erledigt!**
- **Playlist-Sequenzer als MVP** - Deckt 80% der Use-Cases ab
- **Timeline-Sequenzer optional** - Nur bei komplexeren Anforderungen

---

*Siehe [HISTORY.md](HISTORY.md) für abgeschlossene Features (v1.x - v2.3)*
