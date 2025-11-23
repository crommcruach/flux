# Py_artnet - TODO Liste

## 🚀 Geplante Features

### 🔌 Plugin-System (Vorbereitung für Sequenzer)
### 🎥 Player & Video System
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
- [ ] **HOCH: Plugin-basiertes Script/Effect-System mit Parametrierung (14-18h Aufwand)**
  - **Grundidee:** Scripts und Effekte als austauschbare Plugins mit UI-konfigurierbaren Parametern
  - **Plugin-Architektur:**
    - **Base-Class:** `PluginBase` mit standardisiertem Interface
      ```python
      class PluginBase:
          METADATA = {
              "name": "Plugin Name",
              "author": "Author",
              "version": "1.0",
              "description": "Plugin description",
              "category": "generator|effect|source|transition"
          }
          
          # Parameter-Definition für UI-Generierung
          PARAMETERS = [
              {
                  "name": "speed",
                  "type": "float",
                  "default": 1.0,
                  "min": 0.1,
                  "max": 5.0,
                  "step": 0.1,
                  "label": "Animation Speed",
                  "description": "How fast the effect animates"
              },
              {
                  "name": "intensity",
                  "type": "int",
                  "default": 50,
                  "min": 0,
                  "max": 100,
                  "step": 1,
                  "label": "Effect Intensity",
                  "description": "Strength of the effect"
              },
              {
                  "name": "color_mode",
                  "type": "select",
                  "default": "rainbow",
                  "options": ["rainbow", "monochrome", "gradient"],
                  "label": "Color Mode",
                  "description": "Color scheme to use"
              },
              {
                  "name": "enable_glow",
                  "type": "bool",
                  "default": False,
                  "label": "Enable Glow",
                  "description": "Add glow effect"
              },
              {
                  "name": "custom_color",
                  "type": "color",
                  "default": "#FF0000",
                  "label": "Custom Color",
                  "description": "Pick a custom color"
              }
          ]
          
          def __init__(self):
              self.params = {}  # Aktuelle Parameter-Werte
          
          def initialize(self, config: dict) -> None:
              """Plugin initialisieren mit Config"""
              # Merge user config mit defaults
              self.params = self._merge_params(config)
              pass
          
          def generate_frame(self, frame_number: int, width: int, height: int, time: float, **kwargs) -> np.ndarray:
              """Frame generieren (für Scripts) mit self.params"""
              pass
          
          def process_frame(self, frame: np.ndarray, **kwargs) -> np.ndarray:
              """Frame verarbeiten (für Effekte) mit self.params"""
              pass
          
          def update_parameter(self, name: str, value: any) -> None:
              """Parameter zur Laufzeit ändern"""
              if self._validate_param(name, value):
                  self.params[name] = value
          
          def get_parameters(self) -> dict:
              """Aktuelle Parameter-Werte zurückgeben"""
              return self.params.copy()
          
          def cleanup(self) -> None:
              """Plugin aufräumen"""
              pass
      ```
    - **Plugin-Typen:**
      - **Generator-Plugins:** Erstellen Frames von Grund auf (bisherige Scripts: plasma, rainbow_wave, etc.)
      - **Effect-Plugins:** Verarbeiten existierende Frames (blur, color_grading, distortion, etc.)
      - **Source-Plugins:** Externe Quellen (webcam, livestream, screencapture, etc.)
      - **Transition-Plugins:** Übergänge zwischen Clips (crossfade, wipe, dissolve, etc.)
    - **Plugin-Loader:**
      - Automatisches Discovery aus `plugins/` Ordner
      - Lazy Loading (Import nur wenn benötigt)
      - Hot-Reload (Plugins zur Laufzeit neu laden)
      - Dependency-Check (numpy, opencv, etc.)
      - Error-Isolation (Fehler in einem Plugin crasht nicht das System)
    - **Plugin-Registry:**
      - Zentrale Registry für alle verfügbaren Plugins
      - Kategorisierung (Generators, Effects, Sources, Transitions)
      - Metadata-Parsing aus METADATA-Dict
      - API-Endpoint: `GET /api/plugins` (Liste aller Plugins mit Metadata)
  - **Ordner-Struktur:**
    ```
    plugins/
    ├── generators/          # Frame-Generatoren (bisherige scripts/)
    │   ├── __init__.py
    │   ├── plasma.py
    │   ├── rainbow_wave.py
    │   └── ...
    ├── effects/             # Frame-Prozessoren (NEU)
    │   ├── __init__.py
    │   ├── blur.py
    │   ├── color_grading.py
    │   ├── brightness.py
    │   └── ...
    ├── sources/             # Externe Quellen (NEU)
    │   ├── __init__.py
    │   ├── webcam.py
    │   ├── livestream.py
    │   └── screencapture.py
    ├── transitions/         # Übergänge (NEU)
    │   ├── __init__.py
    │   ├── crossfade.py
    │   ├── wipe.py
    │   └── dissolve.py
    └── README.md            # Plugin Development Guide
    ```
  - **Migration:**
    - Bestehende Scripts (`scripts/*.py`) nach `plugins/generators/` migrieren
    - `ScriptGenerator` → `PluginManager` umbenennen
    - `ScriptSource` → `GeneratorSource` umbenennen
    - Backward Compatibility: Alte API-Endpunkte weiterleiten
  - **Effect-Pipeline (NEU):**
    - Plugins können gekettet werden: `Video → Blur → ColorGrading → Output`
    - Config pro Plugin: `{"plugin": "blur", "config": {"strength": 5}}`
    - Per-Clip Effect-Stack im Sequenzer
  - **Parameter-Typen:**
    - **float/int:** Slider mit min/max/step (z.B. Geschwindigkeit, Intensität)
    - **bool:** Checkbox (z.B. Enable/Disable Feature)
    - **select:** Dropdown-Auswahl (z.B. Color-Mode, Blend-Mode)
    - **color:** Color-Picker (z.B. Custom-Color)
    - **string:** Text-Input (z.B. Text-Overlay, Filename)
    - **range:** Dual-Slider für Min/Max (z.B. Brightness-Range)
  - **Parameter-Features:**
    - **Default-Werte:** Jeder Parameter hat sinnvollen Default
    - **Validation:** Min/Max/Options werden enforced
    - **Runtime-Updates:** Parameter können während Playback geändert werden
    - **Presets:** Speichern/Laden von Parameter-Sets
    - **Automation:** Parameter über Zeit animieren (Keyframes)
    - **API-Zugriff:** Parameter über REST API lesen/schreiben
  - **API-Endpunkte (NEU):**
    - `GET /api/plugins` - Liste aller Plugins mit METADATA + PARAMETERS
    - `GET /api/plugins/<name>` - Details zu einem Plugin
    - `GET /api/plugins/<name>/parameters` - Aktuelle Parameter-Werte
    - `PUT /api/plugins/<name>/parameters` - Parameter setzen (Runtime)
    - `POST /api/plugins/<name>/presets` - Preset speichern
    - `GET /api/plugins/<name>/presets` - Presets auflisten
    - `POST /api/plugins/<name>/presets/<preset>/load` - Preset laden
  - **UI-Generierung:**
    - Automatische Form-Generierung aus PARAMETERS-Array
    - Parameter-Panel im Web-Interface (rechts neben Preview)
    - Live-Preview beim Parameter-Ändern
    - Preset-Auswahl-Dropdown
  - **Beispiel-Plugin (Blur Effect):**
    ```python
    class BlurEffect(PluginBase):
        METADATA = {
            "name": "Blur",
            "category": "effect",
            "description": "Gaussian blur effect"
        }
        
        PARAMETERS = [
            {
                "name": "strength",
                "type": "int",
                "default": 5,
                "min": 1,
                "max": 31,
                "step": 2,  # Muss ungerade sein für cv2.GaussianBlur
                "label": "Blur Strength",
                "description": "Kernel size for blur"
            },
            {
                "name": "sigma",
                "type": "float",
                "default": 0.0,
                "min": 0.0,
                "max": 10.0,
                "step": 0.1,
                "label": "Sigma",
                "description": "Gaussian kernel standard deviation"
            }
        ]
        
        def process_frame(self, frame: np.ndarray, **kwargs) -> np.ndarray:
            strength = self.params["strength"]
            sigma = self.params["sigma"]
            return cv2.GaussianBlur(frame, (strength, strength), sigma)
    ```
  - **Implementierung:**
    - Phase 1: PluginBase mit PARAMETERS & Validation (~4h)
    - Phase 2: PluginManager & Registry (~3h)
    - Phase 3: Parameter-API-Endpunkte (~3h)
    - Phase 4: UI-Generierung & Parameter-Panel (~4h)
    - Phase 5: Bestehende Scripts migrieren & parametrieren (~3h)
    - Phase 6: Effect-Pipeline Integration (~3h)
    - Phase 7: Preset-System (~2h)
  - **Vorteile:**
    - Maximale Flexibilität (User können eigene Plugins erstellen)
    - Hot-Reload (Plugins ändern ohne Neustart)
    - Saubere Separation of Concerns
    - Einfaches Hinzufügen neuer Features (z.B. Blur-Effect)
    - Community-Plugins möglich
    - Besser testbar (jedes Plugin isoliert)
  - **Use-Cases:**
    - **Generator:** `plasma` mit parametrierbarer Geschwindigkeit, Farbschema, Wellenlänge
    - **Effect:** `blur` mit einstellbarer Stärke, `color_grading` mit Brightness/Contrast/Saturation
    - **Transition:** `crossfade` mit einstellbarer Duration, `wipe` mit Direction-Parameter
    - **Source:** `webcam` mit Device-ID-Auswahl, Resolution-Parameter
  - **Vorteile der Parametrierung:**
    - **UI-Friendly:** User müssen keinen Code anfassen
    - **Live-Tuning:** Parameter während Playback anpassen (instant feedback)
    - **Presets:** Speichern von "Plasma Langsam", "Plasma Schnell" etc.
    - **Sequenzer-Integration:** Pro Clip eigene Parameter-Sets
    - **A/B-Testing:** Einfaches Vergleichen verschiedener Settings
    - **User-Friendly:** Auch für Non-Coder benutzbar
  - **Empfehlung:** Vor Sequenzer implementieren, da Sequenzer auf Plugins aufbaut

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
- [ ] **Basis-Effekte (leicht implementierbar mit OpenCV/NumPy)**
  - **Farb-Manipulation (2-4h):**
    - [x] AddSubtract - RGB-Werte addieren/subtrahieren
    - [x] Brightness/Contrast - Basic Helligkeits-/Kontraststeuerung
    - [x] Colorize - Einfärben mit Hue-Beibehaltung der Luminanz
    - [x] Tint - Bild mit Basisfarbe einfärben (z.B. Rot-Tint: Bild × [1.0, 0.5, 0.5])
    - [x] Hue Rotate - Hue-Verschiebung auf HSV
    - [x] Invert RGB - Kanal-weise Invertierung
    - [x] Saturation - Entsättigung zu Greyscale
    - [x] Exposure - Exposure-Kurve (cv2.LUT)
    - [x] Levels - Input/Output Levels (cv2.normalize)
    - [x] Posterize - Farbreduktion (bit-shift)
    - [x] Threshold - 2-Farben-Bild (cv2.threshold)
  - **Geometrie & Transform (3-5h):**
    - [ ] Flip - Horizontal/Vertikal spiegeln (cv2.flip)
    - [ ] Mirror - Spiegel an X/Y-Position
    - [ ] Slide - Horizontales/Vertikales Looping-Shift (np.roll)
    - [ ] Keystone - 4-Punkt-Perspektive (cv2.getPerspectiveTransform)
    - [ ] Fish Eye - Linsen-Verzerrung (cv2.remap)
    - [ ] Twist - Spiral-Rotation um Zentrum (polar coordinates)
  - **Blur & Distortion (2-3h):**
    - [ ] Blur - Gaussian/Box Blur (cv2.GaussianBlur) - bereits geplant
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
  - **Time & Motion (2-3h):**
    - [x] Trails - Ghost-Trails (Frame-Blending mit Deque)
    - [x] Stop Motion - Frame-Hold mit Frequenz
    - [x] Delay RGB - RGB-Kanal-Verzögerung (Frame-Buffer)
    - [x] Freeze - Frame einfrieren (statisch oder partiell)
    - [x] Strobe - Alternierend blank frames
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

- [ ] **Implementierungs-Hinweise:**
  - Alle Effekte als Plugins mit PARAMETERS-Array
  - Effekte kombinierbar via Effect-Pipeline
  - Presets für jeden Effekt (z.B. "Blur Soft", "Blur Heavy")
  - Performance-Optimierung mit NumPy-Vektorisierung
  - GPU-Beschleunigung für rechenintensive Effekte (cv2.UMat)
  - Real-time Preview im Web-Interface

### 🎵 Audio-Reactive Support
- [ ] **MITTEL: Audio-Analyse & Reaktive Effekte (10-14h Aufwand)**
  - **Grundidee:** Echtzeit-Audio-Analyse für reaktive Visualisierungen
  - **Audio-Input:**
    - Microphone-Input (pyaudio, sounddevice)
    - Audio-File-Playback (wav, mp3, flac)
    - System-Audio-Capture (WASAPI Loopback auf Windows)
    - Line-In / External Audio-Interface
  - **Audio-Analyse Features:**
    - **FFT (Fast Fourier Transform):** Frequenz-Spektrum-Analyse
      - Bass (20-250 Hz), Mid (250-4000 Hz), Treble (4000-20000 Hz)
      - Frequenz-Bänder konfigurierbar (z.B. 8, 16, 32, 64 Bins)
    - **BPM-Detection:** Automatische Beat-Erkennung (tempo tracking)
    - **Onset-Detection:** Transient/Beat-Trigger für Effekte
    - **RMS/Peak-Level:** Lautstärke-Tracking
    - **Waveform-Buffer:** Zeitbasierte Audio-Visualisierung
  - **Reaktive Parameter:**
    - **Brightness:** Gekoppelt an RMS/Peak-Level (laut = heller)
    - **Speed:** Gekoppelt an BPM (tempo-sync für Animationen)
    - **Color:** Frequenz → Farbe (Bass = Rot, Mid = Grün, Treble = Blau)
    - **Effect-Intensity:** Plugin-Parameter reaktiv (z.B. Blur-Stärke)
    - **Pattern-Switch:** Automatischer Wechsel bei Beat-Detection
  - **Audio-Reactive Plugins:**
    - **Spectrum-Visualizer:** Frequenz-Balken als LED-Output
    - **Beat-Pulse:** Flash/Pulse-Effekt bei Onset
    - **Waveform-Renderer:** Audio-Wellenform als Grafik
    - **VU-Meter:** Classic Lautstärke-Anzeige
    - **Audio-Driven-Plasma:** Plasma-Geschwindigkeit folgt BPM
  - **Konfiguration:**
    - Audio-Device-Auswahl (Dropdown mit verfügbaren Inputs)
    - FFT-Größe (512, 1024, 2048, 4096)
    - Frequenz-Range (Low/High Cutoff)
    - Smoothing-Factor (Glättung für weniger Flackern)
    - Gain/Sensitivity (Input-Verstärkung)
  - **API-Endpunkte:**
    - `GET /api/audio/devices` - Liste verfügbarer Audio-Inputs
    - `POST /api/audio/start` - Audio-Capture starten
    - `POST /api/audio/stop` - Audio-Capture stoppen
    - `GET /api/audio/spectrum` - Aktuelles Frequenz-Spektrum (JSON)
    - `GET /api/audio/bpm` - Aktuelles BPM (Beats per Minute)
    - `PUT /api/audio/config` - Audio-Analyse Config ändern
  - **UI-Features:**
    - Live-Spektrum-Anzeige (Frequenz-Balken)
    - BPM-Display mit Tap-Tempo-Button
    - Audio-Level-Meter (Echtzeit-Lautstärke)
    - Parameter-Mapping-Editor (Audio → Plugin-Parameter)
  - **Implementierung:**
    - Phase 1: Audio-Input & FFT-Analyse (~4h)
    - Phase 2: BPM/Onset-Detection (~3h)
    - Phase 3: Parameter-Mapping-System (~3h)
    - Phase 4: Audio-Reactive Plugins (~3h)
    - Phase 5: UI & API Integration (~2h)
  - **Dependencies:**
    - `numpy` (bereits vorhanden) - FFT-Berechnung
    - `pyaudio` oder `sounddevice` - Audio-Input
    - `librosa` (optional) - Fortgeschrittene Audio-Analyse (BPM, Onset)
    - `scipy` (optional) - Signal-Processing
  - **Use-Cases:**
    - Club/Party-Visualisierungen (Beat-synchronized)
    - Live-Musik-Events (reaktive LED-Shows)
    - Installation mit Ambient-Audio-Reaktion
    - VJ-Setup mit Audio-Input
  - **Performance-Hinweis:**
    - FFT-Berechnung: ~2-5 ms (1024 samples)
    - Audio-Thread läuft parallel zu Player (kein Blocking)
    - Smoothing reduziert CPU-Last (weniger Frame-Updates)

### 🎬 Show-Sequenzer
- [ ] **HOCH: Playlist-Sequenzer (8-12h Aufwand) - Für Standard-Wiedergabe**
  - **Grundidee:** Einfache Liste statt Timeline für Show-Abläufe
  - **Features:**
    - Show-Editor UI (Liste von Clips mit Duration, Transition, Settings)
    - Drag & Drop zum Umordnen von Clips
    - Clip-Properties: Video/Script-Auswahl, Duration, Transition-Typ (Crossfade, Cut, Fade), Brightness
    - Transition-Typen: Crossfade (0.5-5s), Hard Cut (0s), Fade to/from Black
    - Save/Load Show-Dateien (JSON-Format `.fluxshow`)
    - Show-Library (Liste aller gespeicherten Shows)
    - Playback-Controls: Play, Stop, Pause, Resume, Loop-Mode
    - Cue-System: Index-basierte Sprungpunkte (Next Cue, Jump to Cue N)
  - **JSON-Format:**
    ```json
    {
      "name": "Halloween Show 2025",
      "clips": [
        {"type": "video", "source": "kanal_1/intro.mp4", "duration": 15, "transition": "fade", "transition_duration": 1.0, "brightness": 1.0},
        {"type": "video", "source": "kanal_1/main.mp4", "duration": 60, "transition": "crossfade", "transition_duration": 2.0, "brightness": 0.8},
        {"type": "script", "source": "plasma", "duration": 30, "transition": "cut", "brightness": 1.0}
      ],
      "loop": true,
      "cues": [0, 1, 2]
    }
    ```
  - **REST API:**
    - GET `/api/sequencer/shows` - Liste aller Shows
    - POST `/api/sequencer/shows` - Neue Show erstellen
    - GET `/api/sequencer/shows/<name>` - Show laden
    - PUT `/api/sequencer/shows/<name>` - Show aktualisieren
    - DELETE `/api/sequencer/shows/<name>` - Show löschen
    - POST `/api/sequencer/play` - Show abspielen
    - POST `/api/sequencer/stop` - Show stoppen
    - POST `/api/sequencer/cue/<index>` - Zu Cue springen
  - **Implementierung:**
    - Phase 1: Show-Editor UI (Liste, Properties Panel) (~4h)
    - Phase 2: Save/Load/CRUD Operations (~2h)
    - Phase 3: Playback Engine (Sequential mit Transitions) (~4h)
    - Phase 4: Cue-System & Loop-Mode (~2h)
  - **Vorteile:**
    - Deckt 80% der Use-Cases (Shows mit festen Clip-Abfolgen)
    - Viel schneller als Timeline-Editor
    - Perfekt für wiederkehrende Shows (Events, Installationen)
    - Einfach erweiterbar zu Timeline später
  - **Use-Cases:**
    - Event-Shows mit festem Ablauf
    - Installation mit Loop-Wiedergabe
    - Automatisierte Nacht-Shows

- [ ] **NIEDRIG: Script-basierter Sequenzer (4-6h Aufwand) - Für Power-User**
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

## ✅ Aktuell in Arbeit
- [ ] **Test & Validate Delta-Encoding**
  - Test mit verschiedenen Videos (static, high-motion)
  - CPU/Network Savings messen
  - Visuelle Artefakte prüfen

---

## 📚 Hinweise
- **Plugin-System vor Sequenzer implementieren** - Sequenzer baut auf Plugins auf
- **Playlist-Sequenzer als MVP** - Deckt 80% der Use-Cases ab
- **Timeline-Sequenzer optional** - Nur bei komplexeren Anforderungen

---

*Siehe [HISTORY.md](HISTORY.md) für abgeschlossene Features (v1.x - v2.2)*