# Py_artnet - TODO Liste

> **Siehe [HISTORY.md](HISTORY.md) für abgeschlossene Features (v1.x - v2.3)**

## 🚀 Geplante Features (Priorität: Hoch → Niedrig)

### 1. 🎨 Effect-Bibliothek erweitern (Mittel-Priorität, ~15-25h)

- [ ] **Geometrie & Transform (3-5h):**
  - [ ] Flip - Horizontal/Vertikal spiegeln (cv2.flip)
  - [ ] Mirror - Spiegel an X/Y-Position
  - [ ] Slide - Horizontales/Vertikales Looping-Shift (np.roll)
  - [ ] Keystone - 4-Punkt-Perspektive (cv2.getPerspectiveTransform)
  - [ ] Fish Eye - Linsen-Verzerrung (cv2.remap)
  - [ ] Twist - Spiral-Rotation um Zentrum (polar coordinates)

- [ ] **Blur & Distortion (2-3h):**
  - [ ] Radial Blur - Zoom-Blur vom Zentrum
  - [ ] Pixelate (LoRez) - Blocky-Effekt (resize down+up)
  - [ ] Displace - Luminanz-basierte Verschiebung
  - [ ] Wave Warp - Sinus-basierte Verzerrung (cv2.remap)

- [ ] **Glitch & Noise (2-3h):**
  - [ ] Shift Glitch - Zufälliges horizontales Shifting
  - [ ] Distortion - TV-Glitch-Effekt (Zeilen-Verschiebung)
  - [ ] Static - TV-Rauschen (np.random)
  - [ ] Shift RGB - Kanal-Verschiebung horizontal/vertikal

- [ ] **Edge & Detection (1-2h):**
  - [ ] Edge Detection - Sobel/Canny (cv2.Canny)
  - [ ] Auto Mask - Luminanz → Alpha (cv2.cvtColor)

- [ ] **Composite & Mask (2-3h):**
  - [ ] ChromaKey - Farb-basierte Transparenz (HSV-Range)
  - [ ] Keystone Mask - Transparenz außerhalb Keystone-Bereich
  - [ ] Vignette - Radiales Fade zu Schwarz (Gaußsche Maske)
  - [ ] Drop Shadow - Schatten für transparente Clips (cv2.filter2D)

- **Simple 3D & Kaleidoscope (3-5h):**
  - [ ] Kaleidoscope, Tile, Circles, Bendoscope
- **Leicht implementierbare Zusatz-Effekte:**
  - [ ] Sharpen, Emboss, Sepia, Gamma Correction
  - [ ] Color Temperature, Channel Mixer, Noise, Solarize
  - [ ] Duotone, Oil Paint, Mosaic, Zoom, Rotate
  - [ ] Border, Crop, Alpha Blend, Lumetri Color

---

### 2. 🔌 Plugin-System erweitern (Hoch-Priorität, ~8-12h)

- [ ] **Generator-Plugins (3-4h):**
  - [ ] Scripts nach `plugins/generators/` migrieren
  - [ ] plasma, rainbow_wave, pulse, matrix_rain, fire, etc.
  - [ ] METADATA + PARAMETERS für alle Generatoren
  
- [ ] **Preset-System (2-3h):**
  - [ ] Parameter-Sets speichern/laden
  - [ ] Preset-Manager API (CRUD)
  - [ ] UI: Preset-Selector & Editor

- [ ] **UI-Generierung (3-4h):**
  - [ ] Automatische Form-Generierung aus PARAMETERS-Array
  - [ ] Parameter-Panel im Web-Interface
  - [ ] Live-Preview beim Parameter-Ändern

- [ ] **Source-Plugins (optional, 4-6h):**
  - [ ] Webcam, LiveStream, Screencapture

---

### 3. 🔄 Transition-Plugin-System (Mittel-Priorität, ~8-10h)
- **Grundidee:** Plugin-basierte Übergänge zwischen Clips mit konfigurierbarer Duration
- **Features:**
  - [ ] PluginType.TRANSITION zu plugin_base.py hinzufügen
  - [ ] `process_transition(frame_a, frame_b, progress)` Methode
  - [ ] Konfigurierbare Duration (0.1s - 5.0s) mit UI-Slider
  - [ ] Easing-Funktionen (linear, ease_in_out, ease_out_cubic)
- **Standard-Transitions:**
  - [ ] Fade (Alpha-Blending)
  - [ ] Wipe (Left, Right, Top, Bottom)
  - [ ] Dissolve, Push, Zoom
- **Implementierung:**
  - [ ] Phase 1: PluginType.TRANSITION + Base-Plugins (3h)
  - [ ] Phase 2: Player Integration (2h)
  - [ ] Phase 3: API-Endpoints (2h)
  - [ ] Phase 4: UI (Settings Panel + Duration Slider) (3h)

---

### 4. 🎬 Playlist-Sequenzer (Hoch-Priorität, ~8-12h)

### 🎥 Player & Video System
- [ ] **NEU: Effect-Profile/Presets für einzelne Videos (Konzept 2025-11-24)**
  - **Grundidee:** Vordefinierte Effect-Kombinationen die einzelnen Videos zugewiesen werden können
  - **Features:**
    - Named Presets mit Effect-Konfigurationen (z.B. "psychedelic", "glitch", "vintage")
    - Per-Video Preset-Zuweisung in Playlist
    - Preset-Manager API (create, update, delete, list)
    - Import/Export von Preset-Bibliotheken (JSON)
    - Live-Switching zwischen Presets während Playback
  - **Architektur:**
    - Preset-Speicherung: `data/effect_presets.json`
    - Playlist erweitert: `{'path': 'video.mp4', 'preset': 'psychedelic'}`
    - Player lädt Effect-Chain automatisch beim Video-Wechsel
    - API-Endpoints: `/api/presets/*` (CRUD operations)
  - **Use-Cases:**
    - Konsistente Effect-Styles über mehrere Videos
    - Schnelles Experimentieren mit Effect-Kombinationen
    - Preset-Bibliotheken für verschiedene Events/Shows
    - Community-Sharing von Effect-Setups
  - **Implementierung:**
    - Phase 1: Preset-Manager Modul (CRUD, Speicherung)
    - Phase 2: Player Integration (Auto-Load beim Video-Wechsel)
    - Phase 3: API-Endpoints (Preset-Management)
    - Phase 4: UI-Integration (Preset-Selector, Editor)

- [ ] **MITTEL: Dual-Source Player - Separate Preview & ArtNet Ausgaben (Konzept 2025-11-23)**
  - **Grundidee:** Zwei unabhängige Video-Quellen gleichzeitig abspielen
    - **Preview-Ausgabe:** Volle Auflösung mit Layern, Effekten, Overlays (Web-Interface)
    - **ArtNet-Ausgabe:** Optimiertes Video nur für LED-Mapping (Performance)
  - **Architektur: Option 1 - Dual-Source Player (Empfohlen)**
    - Player bekommt `preview_source` und `artnet_source` Parameter
    - `_play_loop()` rendert beide Sources parallel im gleichen Thread
    - Beide synchron (gleicher Frame-Counter, gleiche Playback-Controls)
    - `last_video_frame` kommt von preview_source
    - `artnet_manager.send_frame()` nutzt artnet_source
  - **Features:**
    - Unabhängige Video-Auswahl für Preview/ArtNet
    - Preview kann LayerSource sein (mehrere Videos überlagert)
    - ArtNet bleibt einfache VideoSource (Performance)
    - API-Erweiterung: `/api/player/source/preview` und `/api/player/source/artnet`
    - Switch zwischen Sources ohne Playback zu stoppen
  - **Use-Cases:**
    - Hochaufgelöster Preview mit Overlays, komprimiertes Video für LEDs
    - Test-Video im Preview, finales Video über ArtNet
    - Layer-Compositing nur für Visualisierung, nicht für LED-Output
  - **Vorteile:**
    - Minimale Code-Änderungen (Player-Struktur bleibt gleich)
    - Ein Thread, ein Timing (keine Sync-Probleme)
    - Ressourcen-effizient
    - Erweiterbar für zukünftige Layer-System Integration
  - **Implementierung:**
    - Phase 1: Player-Refactoring (dual sources support)
    - Phase 2: API-Erweiterung (source switching endpoints)
    - Phase 3: UI-Integration (separate Source-Auswahl)
    - Phase 4: LayerSource-Implementierung (optional)

### ⚡ Performance-Optimierung
- [ ] **HOCH:** Async JPEG-Encoding (api_routes.py Stream-Generator)
    - Thread-Pool für cv2.imencode() oder Frame-Skip (30→15 FPS)
    - **NUR für Preview-Ansichten** (Web-Interface Thumbnails, Status-Updates)
    - **NICHT für:** Fullscreen-Ausgabe, Art-Net Output (Performance kritisch)
    - Geschätzter Gewinn: 25-35% CPU-Reduktion bei Preview-Streams, -8ms Latenz
    - Betroffene Endpoints: `/api/stream/preview`, `/api/stream/thumbnail`
    - Art-Net und Fullscreen bleiben synchron (keine Encoding-Latenz)
- [ ] Video-Optimierungs-Script erstellen
  - [ ] Automatische Skalierung auf Canvas-Größe
  - [ ] Hardware-Codec Encoding (H.264 mit NVENC/QSV)
  - [ ] Bitrate-Optimierung für schnelleres Decoding
  - [ ] Keyframe-Intervall anpassen (g=30 für bessere Loop-Performance)
  - [ ] Batch-Processing für alle Videos in Kanal-Ordnern

### 🎬 Show-Sequenzer

#### Hinweis: Plugin-System bereits vollständig implementiert! ✅
Das Plugin-basierte Script/Effect-System mit Parametrierung ist **bereits fertig**:
- ✅ PluginBase mit METADATA + PARAMETERS
- ✅ PluginManager mit Auto-Discovery & Registry
- ✅ 17 Effect-Plugins implementiert
- ✅ Parameter-Validation & Runtime-Updates
- ✅ Plugin-API-Endpunkte (`/api/plugins/*`)

Nächste Schritte für Sequenzer:
      ```python
#### Zu implementieren:
- [ ] **Generator-Plugins** - Scripts nach `plugins/generators/` migrieren (plasma, rainbow_wave, etc.)
- [ ] **Source-Plugins** - Webcam, LiveStream, Screencapture
- [ ] **Preset-System** - Speichern/Laden von Parameter-Sets für Plugins
- [ ] **UI-Generierung** - Automatische Form-Generierung aus PARAMETERS-Array

### 🔮 Neue Frame Sources
- [ ] ShaderToy Source (Echtzeit-3D-Shader)
  - [ ] ModernGL/PyOpenGL Integration
  - [ ] GLSL Shader Support (Shadertoy-kompatibel)
  - [ ] Uniform Variables (iTime, iResolution, iMouse)
  - [ ] Shader-Dateien aus shaders/ Ordner laden
  - [ ] Shadertoy-URL Import (API oder Scraping)
  - [ ] Performance-Profiling und GPU-Monitoring
- [ ] ImageSequence Source
  - [ ] PNG/JPG Sequenz-Support
  - [ ] Automatische Frame-Nummerierung
  - [ ] Variable Frame-Delays
- [ ] LiveStream Source
  - [ ] RTSP/HTTP Stream Support
  - [ ] FFmpeg/GStreamer Integration
  - [ ] Stream-Buffering und Reconnect

### 🎨 Video-Effekt-Bibliothek (Plugin-basiert)

#### ✅ Implementiert (17 Effekte)
- **Farb-Manipulation (11/11 ✅):**
  - AddSubtract, Brightness/Contrast, Colorize, Tint, Hue Rotate
  - Invert RGB, Saturation, Exposure, Levels, Posterize, Threshold
- **Time & Motion (5/5 ✅):**
  - Trails, Stop Motion, Delay RGB, Freeze, Strobe
- **Blur (1/1 ✅):**
  - Blur - Gaussian/Box Blur

#### 🚧 Zu implementieren
- **Geometrie & Transform (3-5h):**
  - [ ] Flip - Horizontal/Vertikal spiegeln (cv2.flip)
  - [ ] Mirror - Spiegel an X/Y-Position
  - [ ] Slide - Horizontales/Vertikales Looping-Shift (np.roll)
  - [ ] Keystone - 4-Punkt-Perspektive (cv2.getPerspectiveTransform)
  - [ ] Fish Eye - Linsen-Verzerrung (cv2.remap)
  - [ ] Twist - Spiral-Rotation um Zentrum (polar coordinates)
- **Blur & Distortion (2-3h):**
  - [ ] Radial Blur - Zoom-Blur vom Zentrum
  - [ ] Pixelate (LoRez) - Blocky-Effekt (resize down+up)
  - [ ] Displace - Luminanz-basierte Verschiebung
  - [ ] Wave Warp - Sinus-basierte Verzerrung (cv2.remap)
- **Edge & Detection (1-2h):**
  - [ ] Edge Detection - Sobel/Canny (cv2.Canny)
  - [ ] Auto Mask - Luminanz → Alpha (cv2.cvtColor)
- **Composite & Mask (2-3h):**
  - [ ] ChromaKey - Farb-basierte Transparenz (HSV-Range)
  - [ ] Keystone Mask - Transparenz außerhalb Keystone-Bereich
  - [ ] Vignette - Radiales Fade zu Schwarz (Gaußsche Maske)
  - [ ] Drop Shadow - Schatten für transparente Clips (cv2.filter2D)
- **Glitch & Noise (2-3h):**
  - [ ] Shift Glitch - Zufälliges horizontales Shifting
  - [ ] Distortion - TV-Glitch-Effekt (Zeilen-Verschiebung)
  - [ ] Static - TV-Rauschen (np.random)
  - [ ] Shift RGB - Kanal-Verschiebung horizontal/vertikal
  - **Simple 3D & Kaleidoscope (3-5h):**
    - [ ] Kaleidoscope - Spiegel-Effekt mit N Segmenten
    - [ ] Tile - Grid-basierte Wiederholung
    - [ ] Circles - Konzentrische Kreis-Interpretation
    - [ ] Bendoscope - Kurven-Kaleidoskop

- [ ] **Leicht implementierbare Zusatz-Effekte (Empfohlen für MVP)**
  - [ ] **Sharpen** - Schärfen (cv2.filter2D mit Kernel) - 1h
  - [ ] **Emboss** - Präge-Effekt (Sobel-basiert) - 1h
  - [ ] **Sepia** - Vintage-Farbton (Matrix-Multiplikation) - 1h
  - [ ] **Gamma Correction** - Gamma-Kurve (cv2.LUT) - 1h
  - [ ] **Color Temperature** - Warm/Cool (RGB-Shift) - 1h
  - [ ] **Channel Mixer** - RGB-Kanal-Kreuzung - 2h
  - [ ] **Noise** - Grain/Noise hinzufügen (np.random) - 1h
  - [ ] **Solarize** - Helligkeits-Invertierung ab Threshold - 1h
  - [ ] **Duotone** - 2-Farben-Gradient-Mapping - 2h
  - [ ] **Oil Paint** - Öl-Malerei-Effekt (Median-Filter) - 2h
  - [ ] **Mosaic** - Pixelate mit variablen Tile-Größen - 2h
  - [ ] **Zoom** - Einfacher Zoom-In/Out (cv2.resize) - 1h
  - [ ] **Rotate** - Rotation um Zentrum (cv2.getRotationMatrix2D) - 1h
  - [ ] **Border** - Rahmen hinzufügen (cv2.copyMakeBorder) - 1h
  - [ ] **Crop** - Rechteckiger Zuschnitt - 1h
  - [ ] **Alpha Blend** - Transparenz-basiertes Blending - 2h
  - [ ] **Lumetri Color** - Cinema-Grade-Grading (Lift/Gamma/Gain) - 3h

---

### 5. 🎵 Audio-Reactive Support (Mittel-Priorität, ~10-14h)

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

### 6. ⚡ Performance-Optimierung (Niedrig-Priorität, ~4-8h)

- [ ] **Async JPEG-Encoding (2-3h):**
  - Thread-Pool für cv2.imencode()
  - Nur für Preview-Streams (nicht Fullscreen/Art-Net)
  - Geschätzter Gewinn: 25-35% CPU-Reduktion
  
- [ ] **Video-Optimierungs-Script (2-5h):**
  - Automatische Skalierung auf Canvas-Größe
  - Hardware-Codec Encoding (H.264 mit NVENC/QSV)
  - Bitrate-Optimierung, Keyframe-Intervall

---

### 7. 🎥 Player-Features (Niedrig-Priorität, ~8-12h)

- [ ] **Effect-Profile/Presets für Videos (4-6h):**
  - Named Presets (z.B. "psychedelic", "glitch", "vintage")
  - Per-Video Preset-Zuweisung in Playlist
  - Preset-Manager API (CRUD)
  - Import/Export von Preset-Bibliotheken

- [ ] **Dual-Source Player (4-6h):**
  - Separate Preview & ArtNet Ausgaben
  - Preview kann LayerSource sein (Overlays)
  - ArtNet bleibt einfache VideoSource (Performance)

---

### 8. 🔮 Neue Frame Sources (Niedrig-Priorität, ~12-20h)

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

### 9. 🎨 GUI-Optimierungen (Niedrig-Priorität, ~8-12h)

- [ ] **Drag & Drop Layout-Editor:**
  - GridStack.js Integration
  - Panels frei verschieben & resizen
  - LocalStorage-Persistierung
  - Preset-Layouts

---

### 10. 🛠️ Weitere Verbesserungen (Niedrig-Priorität)

- [ ] Unit Tests erweitern (Player, FrameSource, API)
- [ ] API-Authentifizierung (Basic Auth/Token)
- [ ] PyInstaller EXE Build Setup
- [ ] Environment Variable Support für config.json
- [ ] Dockerfile erstellen

---

### 11. ⏱️ Script-basierter Sequenzer (Optional, ~4-6h)
  - **Grundidee:** Python-Script definiert Show-Ablauf (Code-First Approach)
  - **Features:**
    - Python-DSL für Show-Definition
    - CLI-Befehl: `show play <script.py>` oder `show:<script_name>`
    - Script-Loader in `shows/` Ordner (analog zu `scripts/`)
    - Volle Python-Kontrolle: Loops, Conditionals, Random, Math
    - Zugriff auf alle Player-APIs (brightness, speed, artnet)
  - **Python-DSL-Beispiel:**
    ```python
    from show_dsl import Show, Clip, wait, cue
    
    show = Show("My Show")
    
    # Sequentielle Clips
    show.play_video("intro.mp4", duration=15, fade_in=1.0)
    show.play_video("main.mp4", duration=60, crossfade=2.0, brightness=0.8)
    show.play_script("plasma", duration=30, fade_out=1.0)
    
    # Cue-Marker
    cue("Chorus")
    show.play_video("chorus.mp4", duration=30)
    
    # Loops & Conditionals
    for i in range(3):
        show.play_script(f"rainbow_wave", duration=10)
        wait(1.0)  # Pause zwischen Clips
    
    # Brightness-Ramps
    show.brightness_ramp(from=0.0, to=1.0, duration=5.0)
    ```
  - **REST API:**
    - GET `/api/sequencer/scripts` - Liste aller Show-Scripts
    - POST `/api/sequencer/scripts/<name>/play` - Script ausführen
    - POST `/api/sequencer/scripts/<name>/stop` - Script abbrechen
  - **Implementierung:**
    - Phase 1: Show-DSL Modul (`show_dsl.py`) (~2h)
    - Phase 2: Show-Script-Loader & Executor (~2h)
    - Phase 3: CLI & API Integration (~2h)
  - **Vorteile:**
    - Maximale Flexibilität für Power-User
    - Programmierbare Shows (Random, Conditionals, API-Calls)
    - Versionierbar mit Git
    - Kein UI-Overhead
  - **Use-Cases:**
    - Komplexe generative Shows
    - Shows mit externen Triggern (MQTT, HTTP, Files)
    - Prozedural generierte Clip-Reihenfolgen
    - A/B-Testing verschiedener Sequenzen
  - **Empfehlung:** Nice-to-have für Freaks, niedrige Priorität

- [ ] **OPTIONAL: Timeline-Sequenzer (60-80h Aufwand) - Full-Featured Show-Control**
  - Upgrade von Playlist-Sequenzer zu visueller Timeline (später)
  - Features: Clip-Trimming, Scrubbing, Multi-Track, Audio-Sync, Automation-Tracks
  - Nur wenn User komplexere Anforderungen haben (Trimming, Overlays, etc.)

### 🎨 GUI-Optimierungen
- [ ] **MITTEL: Drag & Drop Layout-Editor (8-12h Aufwand)**
  - **Library-Optionen:**
    - GridStack.js (Empfohlen) - Bewährte Dashboard-Library mit Grid-Snapping
    - Muuri.js - Leichtgewichtig mit schönen Animationen
    - Eigene Implementierung mit HTML5 Drag & Drop API
  - **Features:**
    - Panels frei verschieben (Preview, Playback, Settings, Videos, etc.)
    - Resize-Handles für Größenanpassung
    - Grid-Snapping für automatisches Ausrichten
    - LocalStorage-Persistierung (Position + Größe)
    - JSON-Export/Import für Layout-Backup
    - Preset-Layouts: "Standard", "Video-Focus", "Compact", "Multi-Monitor"
    - Panel-Collapse (Ein-/Ausklappen einzelner Bereiche)
    - Mobile-responsive Fallback
  - **Implementierung:**
    - Phase 1: GridStack.js Integration (~4h)
    - Phase 2: Panel-Header mit Drag-Handles (~2h)
    - Phase 3: Layout-Persistierung & Presets (~3h)
    - Phase 4: Mobile-Optimierung (~3h)
  - **Vorteile:**
    - Personalisierbare UI für verschiedene Use-Cases
    - Bessere UX für Multi-Monitor Setups
    - Professioneller Look
  - **Alternativen mit weniger Aufwand:**
    - Quick-Win: Panel-Collapse (2-3h) - Panels nur ein/ausklappen
    - Medium: Tab-Layout (4-6h) - Panels als Tabs organisieren
  - **Empfehlung:** Erst nach User-Feedback zu aktuellem Layout

### 🛠️ Weitere Verbesserungen
- [ ] Unit Tests erweitern (Player, FrameSource, API)
- [ ] API-Authentifizierung (Basic Auth/Token)
- [ ] PyInstaller EXE Build Setup
  - [ ] Spec-Datei erstellen mit allen Dependencies
  - [ ] Single-File oder Folder-basierte Distribution testen
- [ ] Konfiguration erweitern
  - [ ] Environment Variable Support (target_ip, ports)
  - [ ] JSON Schema Validation für config.json
  - [ ] Hot-Reload (config.json watcher)
- [ ] Projekt-Struktur
  - [ ] Dockerfile erstellen

---

---

## 📊 Aktueller Status (Stand: 2025-11-26)

### ✅ Fertiggestellt
- **Unified API Architecture** mit UUID-basiertem Clip-Management
- **Dual-Player-System** (Video Preview + Art-Net Output)
- **Plugin-System** vollständig implementiert (PluginBase, PluginManager, API)
- **17 Effect-Plugins** implementiert (11 Farb-Manipulation, 5 Time & Motion, 1 Blur)
- **ClipRegistry** mit UUID-basierter Clip-Identifikation
- **Code-Cleanup** (~1500 Zeilen deprecated Code entfernt)

### 🎯 Nächste Schritte (Priorität)
1. **Generator-Plugins** - Scripts nach `plugins/generators/` migrieren
2. **Preset-System** - Parameter-Sets speichern/laden
3. **Playlist-Sequenzer** - Show-Editor mit Transitions
4. **Weitere Effekte** - Geometrie, Glitch, Composite (noch ~30 Effekte offen)

### 🚀 Vision
- **Audio-Reactive Support** - FFT-Analyse, BPM-Detection, Reaktive Parameter
- **Transition-Plugin-System** - Crossfade, Wipe, Dissolve zwischen Clips
- **Timeline-Sequenzer** (langfristig) - Full-Featured Show-Control

---

## 📚 Hinweise
- ✅ ~~Plugin-System vor Sequenzer implementieren~~ **Erledigt!**
- **Playlist-Sequenzer als MVP** - Deckt 80% der Use-Cases ab
- **Timeline-Sequenzer optional** - Nur bei komplexeren Anforderungen

---

*Siehe [HISTORY.md](HISTORY.md) für abgeschlossene Features (v1.x - v2.2)*