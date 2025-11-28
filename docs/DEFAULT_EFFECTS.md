# Default Effect Chains

## Übersicht

Mit Default Effect Chains können Effekte automatisch beim Start auf Player oder spezifische Clips angewendet werden. Dies ist konfiguriert in `config.json` unter der Sektion `effects`.

## Konfiguration

### config.json Schema

```json
{
  "effects": {
    "video": [
      {
        "plugin_id": "brightness",
        "params": {"brightness": 1.2}
      }
    ],
    "artnet": [
      {
        "plugin_id": "hue_shift",
        "params": {"shift": 30}
      }
    ],
    "clips": [
      {
        "plugin_id": "fade_in",
        "params": {"duration": 2.0}
      },
      {
        "plugin_id": "brightness",
        "params": {"brightness": 1.1}
      }
    ]
  }
}
```

### Eigenschaften

#### `effects.video` (Array)
- **Zweck**: Default Effect Chain für Video-Player
- **Anwendung**: Beim Start automatisch auf Video-Player geladen
- **Format**: Array von Effect-Configs

#### `effects.artnet` (Array)
- **Zweck**: Default Effect Chain für Art-Net-Player
- **Anwendung**: Beim Start automatisch auf Art-Net-Player geladen
- **Format**: Array von Effect-Configs

#### `effects.clips` (Array)
- **Zweck**: Default Effect Chain für ALLE Clips
- **Anwendung**: Automatisch beim Registrieren jedes neuen Clips
- **Format**: Array von Effect-Configs
- **Hinweis**: Diese Effekte werden auf alle Clips angewendet, egal welcher Pfad oder UUID

### Effect Config Format

```json
{
  "plugin_id": "effect_name",
  "params": {
    "param1": value1,
    "param2": value2
  }
}
```

- **`plugin_id`** (required): ID des Effect-Plugins (z.B. "brightness", "blur", "hue_shift")
- **`params`** (optional): Parameter-Werte für den Effekt

## Beispiele

### Beispiel 1: Video Player mit Brightness & Color Balance

```json
{
  "effects": {
    "video": [
      {
        "plugin_id": "brightness",
        "params": {"brightness": 1.3}
      },
      {
        "plugin_id": "color_balance",
        "params": {
          "red": 1.1,
          "green": 1.0,
          "blue": 0.9
        }
      }
    ]
  }
}
```

**Ergebnis**: Video-Player startet mit 30% erhöhter Helligkeit und leicht warmer Farbbalance.

### Beispiel 2: Art-Net Player mit Hue Shift

```json
{
  "effects": {
    "artnet": [
      {
        "plugin_id": "hue_shift",
        "params": {"shift": 45}
      },
      {
        "plugin_id": "saturation",
        "params": {"saturation": 1.5}
      }
    ]
  }
}
```

**Ergebnis**: Art-Net-Output hat verschobenen Farbton (45°) und erhöhte Sättigung.

### Beispiel 3: Clip Default-Effekte (auf ALLE Clips angewendet)

```json
{
  "effects": {
    "clips": [
      {
        "plugin_id": "brightness",
        "params": {"brightness": 1.1}
      },
      {
        "plugin_id": "fade_in",
        "params": {"duration": 0.5}
      }
    ]
  }
}
```

**Ergebnis**: 
- **Alle** Clips bekommen automatisch 10% mehr Helligkeit
- **Alle** Clips haben einen 0.5s Fade-In beim Start
- Dies wird beim Registrieren eines Clips automatisch angewendet

### Beispiel 4: Kombination aller Features

```json
{
  "effects": {
    "video": [
      {
        "plugin_id": "brightness",
        "params": {"brightness": 1.2}
      }
    ],
    "artnet": [
      {
        "plugin_id": "gamma",
        "params": {"gamma": 2.2}
      }
    ],
    "clips": [
      {
        "plugin_id": "fade_in",
        "params": {"duration": 0.5}
      }
    ]
  }
}
```

**Ergebnis**:
- Video-Player: 20% heller
- Art-Net-Player: Gamma-Korrektur 2.2
- Alle Clips: 0.5s Fade-In beim Laden

## Funktionsweise

### Player-Level Effects

1. **Beim Start**: 
   - DefaultEffectsManager wird initialisiert
   - Liest `effects.video` und `effects.artnet` aus config
   - Validiert Plugin-IDs
   - Wendet Effekte auf beide Player an

2. **Logging**:
   ```
   🎨 Default Effects Manager initialized
     📹 Video default effects: 2 configured
     💡 Art-Net default effects: 1 configured
   ✅ Applied 'brightness' to video player
   ✅ Applied 'color_balance' to video player
   🎨 Applied 2/2 default effects to video player
   ```

### Clip-Level Effects

1. **Beim Registrieren**:
   - ClipRegistry ruft `register_clip()` auf
   - DefaultEffectsManager prüft `effects.clips` Array
   - Wendet **alle** konfigurierten Effekte auf den neuen Clip an
   - Gilt für **jeden** Clip, unabhängig von Pfad oder UUID

2. **Logging**:
   ```
   ✅ Clip registriert: abc123-uuid → video/intro.mp4
   ✅ Applied 'brightness' to clip abc123-uuid
   ✅ Applied 'fade_in' to clip abc123-uuid
   🎨 Auto-applied 2 default effects to new clip
   ```

## Verfügbare Effect Plugins

Hier eine Liste häufig verwendeter Plugins (vollständige Liste via `/api/plugins/list`):

### Farb-Manipulation
- `brightness` - Helligkeit anpassen
- `contrast` - Kontrast ändern
- `saturation` - Sättigung
- `hue_shift` - Farbton verschieben
- `color_balance` - RGB-Balance
- `invert` - Farben invertieren
- `grayscale` - Schwarzweiß
- `sepia` - Sepia-Ton

### Zeit & Motion
- `strobe` - Stroboskop-Effekt
- `speed` - Geschwindigkeit
- `reverse` - Rückwärts
- `time_stretch` - Zeitdehnung
- `fade_in` - Einblenden
- `fade_out` - Ausblenden

### Geometrie & Transform
- `flip_horizontal` - Horizontal spiegeln
- `flip_vertical` - Vertikal spiegeln
- `rotate` - Rotation
- `scale` - Skalierung

### Blur & Distortion
- `blur` - Weichzeichner
- `motion_blur` - Bewegungsunschärfe

## Parameter-Typen

Jedes Plugin hat spezifische Parameter. Beispiele:

### Float/Int
```json
{"plugin_id": "brightness", "params": {"brightness": 1.5}}
```

### Range (0.0 - 1.0)
```json
{"plugin_id": "opacity", "params": {"opacity": 0.8}}
```

### Boolean
```json
{"plugin_id": "invert", "params": {"enabled": true}}
```

### Color (RGB)
```json
{"plugin_id": "tint", "params": {"color": [255, 128, 0]}}
```

## Troubleshooting

### Effects werden nicht angewendet

1. **Plugin-ID prüfen**:
   ```bash
   curl http://localhost:5000/api/plugins/list
   ```
   - Vergleiche `plugin_id` mit `id` in Response

2. **Logs überprüfen**:
   ```
   ❌ Plugin 'invalid_name' not found
   ⚠️ Effect config missing 'plugin_id'
   ```

3. **Parameter-Werte prüfen**:
   - Falsche Typen → Effect wird nicht angewendet
   - Außerhalb Min/Max → Wird auf Grenzwert korrigiert

### Clip-Effects funktionieren nicht

1. **Pfad-Format prüfen**:
   ```json
   ✓ "kanal_1/video.mp4"    // Relativ, Forward-Slash
   ✗ "kanal_1\\video.mp4"   // Backslash (nur Windows-intern)
   ✗ "/full/path/video.mp4" // Absoluter Pfad
   ```

2. **UUID vs Pfad**:
   - UUID ist bevorzugt (persistent)
   - Pfad funktioniert nur bei exakter Übereinstimmung

3. **Timing**:
   - Clip-Effects werden bei `register_clip()` angewendet
   - Bereits registrierte Clips werden nicht nachträglich aktualisiert

### Performance-Impact

**Player-Effects**:
- Minimal: 1-2 Effects (~1-5% CPU)
- Moderate: 3-5 Effects (~5-15% CPU)
- Heavy: 6+ Effects (~15-30% CPU)

**Clip-Effects**:
- Nur für aktiven Clip aktiv
- Keine Performance-Impact auf Playlist

## Best Practices

### 1. Minimale Effect Chains

```json
// ✓ Gut: 1-3 Basis-Effekte
"video": [
  {"plugin_id": "brightness", "params": {"brightness": 1.2}},
  {"plugin_id": "gamma", "params": {"gamma": 2.2}}
]

// ✗ Schlecht: Zu viele Effekte
"video": [
  {"plugin_id": "brightness", ...},
  {"plugin_id": "contrast", ...},
  {"plugin_id": "saturation", ...},
  {"plugin_id": "hue_shift", ...},
  {"plugin_id": "blur", ...},
  // ... 10 more effects
]
```

### 2. Sinnvolle Parameter

```json
// ✓ Gut: Subtile Anpassungen
{"plugin_id": "brightness", "params": {"brightness": 1.2}}

// ✗ Schlecht: Extreme Werte
{"plugin_id": "brightness", "params": {"brightness": 5.0}}
```

### 3. Clip-Effects sparsam

```json
// ✓ Gut: Nur spezielle Clips
"clips": {
  "intro.mp4": [{"plugin_id": "fade_in", ...}],
  "outro.mp4": [{"plugin_id": "fade_out", ...}]
}

// ✗ Schlecht: Alle Clips konfigurieren
"clips": {
  "video1.mp4": [...],
  "video2.mp4": [...],
  "video3.mp4": [...],
  // ... 100 more entries
}
```

### 4. UUID statt Pfad

```json
// ✓ Bevorzugt: UUID (persistent)
"clips": {
  "a1b2c3d4-5678-90ab-cdef-1234567890ab": [...]
}

// ✗ Weniger robust: Pfad (bricht bei Umbenennung)
"clips": {
  "kanal_1/video.mp4": [...]
}
```

## API Endpunkte

Programmgesteuerte Verwaltung von Default Effects:

### GET /api/config
```bash
curl http://localhost:5000/api/config
```

Gibt aktuelle Config inkl. `effects`-Sektion zurück.

### POST /api/config
```bash
curl -X POST http://localhost:5000/api/config \
  -H "Content-Type: application/json" \
  -d @config.json
```

Speichert neue Config (inkl. Effects).

### GET /api/plugins/list
```bash
curl http://localhost:5000/api/plugins/list
```

Gibt alle verfügbaren Plugins mit Parametern zurück.

## Zusammenfassung

**Vorteile:**
- ✅ Konsistente Basis-Effekte beim Start
- ✅ Clip-spezifische Anpassungen automatisch
- ✅ Konfigurierbar ohne Code-Änderungen
- ✅ Validierung beim Start (schlägt nicht fehl)

**Nachteile:**
- ⚠️ Keine UI für Config-Bearbeitung (aktuell)
- ⚠️ Config-Änderungen erfordern Neustart
- ⚠️ Clip-UUID schwer zu ermitteln

**Empfehlung:**
- Player-Effects für globale Anpassungen
- Clip-Effects nur für spezielle Cases
- Moderat mit Effect-Count umgehen
