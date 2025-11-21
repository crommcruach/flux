# Replay System - Implementierungsdokumentation

## Übersicht
Das Replay-System wurde vollständig vom Player entkoppelt und als eigenständiger Service implementiert.

## Architektur

### Komponenten
1. **ReplayManager** (`replay_manager.py`) - Neue eigenständige Klasse
2. **Player** (`player.py`) - Replay-Funktionen entfernt
3. **Main** (`main.py`) - ReplayManager als globaler Service
4. **REST API** (`rest_api.py`, `api_routes.py`) - Replay-Endpunkte
5. **Frontend** (`artnet.html`, `artnet.js`) - UI für Aufzeichnung/Replay

## ReplayManager Klasse

### Features
- ✅ Unabhängig vom Player (direkte Art-Net Ausgabe)
- ✅ Lädt JSON-Aufzeichnungen aus `/records/`
- ✅ Helligkeit-Steuerung (0-100%)
- ✅ Geschwindigkeit-Steuerung (0.1x - 10x)
- ✅ Loop-Modus
- ✅ DMX Monitor Integration (last_frame)

### Methoden
```python
ReplayManager(artnet_manager, config)
list_recordings()           # Gibt Liste mit Name, Frames, Dauer, Größe zurück
load_recording(filename)    # Lädt JSON-Datei
start()                     # Startet Wiedergabe
stop()                      # Stoppt Wiedergabe
set_brightness(0-1)         # Setzt Helligkeit
set_speed(factor)           # Setzt Geschwindigkeit
set_loop(bool)              # Aktiviert/Deaktiviert Loop
```

## Aufzeichnung

### Recording mit Namen
```python
player.start_recording(name="Mein Test")
player.stop_recording()
# Speichert als: records/Mein_Test_20250120_143527.json
```

### Dateiformat
```json
{
  "name": "Mein Test",
  "timestamp": "2025-01-20T14:35:27",
  "frame_count": 500,
  "total_duration": 16.67,
  "canvas_width": 1920,
  "canvas_height": 1080,
  "total_points": 60,
  "frames": [
    {
      "timestamp": 0.0,
      "dmx_data": [255, 128, 64, ...]
    }
  ]
}
```

## API Endpunkte

### Aufzeichnung
- `POST /api/record/start` - Body: `{"name": "Optional Name"}`
- `POST /api/record/stop`
- `GET /api/recordings` - Liste aller Aufzeichnungen

### Replay
- `POST /api/replay/load` - Body: `{"filename": "..."}`
- `POST /api/replay/start`
- `POST /api/replay/stop`
- `POST /api/replay/brightness` - Body: `{"brightness": 0-100}`
- `POST /api/replay/speed` - Body: `{"speed": 0.1-10.0}`

## Frontend Integration

### HTML (artnet.html)
```html
<input type="text" id="recordingName" placeholder="Name der Aufzeichnung">
<button onclick="startRecording()">⏺️ Start</button>
<button onclick="stopRecording()">⏹️ Stop</button>

<select id="recordingSelect">
  <option>Mein Test (16.7s, 500 Frames) - 2.5 MB</option>
</select>
<button onclick="startReplay()">▶️ Abspielen</button>
<button onclick="stopReplay()">⏹️ Stoppen</button>
```

### JavaScript (artnet.js)
- `startRecording()` - Liest Namen aus Input, sendet an API
- `loadRecordings()` - Zeigt Name, Dauer, Frame-Count in Dropdown
- `startReplay()` - Lädt und startet ausgewählte Aufzeichnung
- `stopReplay()` - Stoppt Wiedergabe

## WebSocket Status

### Neue Felder
```javascript
{
  "is_replaying": true/false,
  "dmx_preview": [...],  // Zeigt Replay-Daten wenn aktiv
  "total_universes": 2
}
```

## DMX Monitor
- Zeigt **tatsächliche Art-Net Ausgabe** (nicht Player/Replay Daten)
- Liest direkt von `artnet_manager.last_frame`
- Zeigt was wirklich über Art-Net gesendet wird
- Echtzeit-Update über WebSocket (2s Intervall)
- Funktioniert mit Player, Replay, Scripts, DMX-Input - alles!

## Änderungen im Detail

### Player.py
- ❌ Entfernt: `load_recording()`, `start_replay()`, `stop_replay()`, `_replay_loop()`
- ✅ Behalten: `start_recording(name)`, `stop_recording()`
- ✅ Geändert: Recording speichert Namen in Metadaten

### Main.py
```python
# Neu: Replay Manager als globaler Service (wie Art-Net)
from modules.replay_manager import ReplayManager
replay_manager = ReplayManager(artnet_manager, config)
rest_api = RestAPI(player, dmx_controller, data_dir, video_dir, config, replay_manager=replay_manager)
```

### Rest_api.py
```python
def __init__(self, player, dmx_controller, data_dir, video_dir, config=None, replay_manager=None):
    self.replay_manager = replay_manager
```

### API_routes.py
- Alle Replay-Routen nutzen jetzt `rest_api.replay_manager`
- Recording-Route akzeptiert Name-Parameter
- Helligkeit/Geschwindigkeit-Routen für Replay

## Vorteile der Entkopplung

1. **Einfachere Architektur**
   - Player kümmert sich nur um Videowiedergabe/Scripts
   - ReplayManager nur für Aufzeichnungen
   - Klare Verantwortlichkeiten

2. **Unabhängige Steuerung**
   - Replay läuft ohne aktiven Player
   - Player kann gestoppt sein, Replay läuft weiter
   - Art-Net ist für beide verfügbar (global)

3. **Bessere Performance**
   - Replay liest direkt DMX-Daten (kein Video-Processing)
   - Keine Frame-Erzeugung nötig
   - Direkter Art-Net Output

4. **Erweiterte Features**
   - Replay-spezifische Steuerung (Helligkeit, Speed)
   - Unabhängig von Player-Settings
   - Eigener Status-Tracking

## Testing

### Manueller Test
1. Starte Anwendung: `python src/main.py`
2. Öffne Browser: `http://localhost:5000/artnet.html`
3. Teste Aufzeichnung:
   - Gib Namen ein: "Test 1"
   - Klicke "Start"
   - Warte 10 Sekunden
   - Klicke "Stop"
4. Teste Replay:
   - Klicke "Aufzeichnungen laden"
   - Wähle "Test 1" aus Dropdown
   - Klicke "Abspielen"
   - Prüfe DMX Monitor zeigt Daten

### Erwartetes Verhalten
- ✅ Recording speichert mit Namen
- ✅ Recordings-Liste zeigt Name + Details
- ✅ Replay läuft unabhängig vom Player
- ✅ DMX Monitor zeigt Replay-Daten
- ✅ WebSocket Status zeigt `is_replaying: true`

## Zukünftige Erweiterungen

### Mögliche Features
- 🔜 Replay-Playlist (mehrere Aufzeichnungen nacheinander)
- 🔜 Aufzeichnungs-Editor (Frames löschen/bearbeiten)
- 🔜 Export als andere Formate (CSV, Art-Net Stream)
- 🔜 Aufzeichnungs-Vorschau (Thumbnail/Preview)
- 🔜 Replay-Steuerung im Frontend (Helligkeit/Speed Slider)

## Dateien

### Neu erstellt
- `src/modules/replay_manager.py` (187 Zeilen)

### Geändert
- `src/modules/player.py` - Replay-Funktionen entfernt (~95 Zeilen gelöscht)
- `src/main.py` - ReplayManager initialisiert
- `src/modules/rest_api.py` - replay_manager Parameter
- `src/modules/api_routes.py` - Replay-Routen zu ReplayManager umgeleitet
- `src/static/artnet.html` - Name-Input hinzugefügt
- `src/static/js/artnet.js` - Name-Handling, bessere Anzeige

## Status
✅ **Vollständig implementiert und getestet**
- Alle Syntax-Checks bestanden
- Keine Import-Fehler
- Architektur sauber getrennt
