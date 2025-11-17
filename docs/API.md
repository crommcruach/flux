# API Documentation

## REST API Endpoints

### Playback Control

#### POST /api/play
Startet Video-Wiedergabe.
```json
Response: {"status": "success", "message": "Video gestartet"}
```

#### POST /api/stop
Stoppt Video-Wiedergabe.
```json
Response: {"status": "success", "message": "Video gestoppt"}
```

#### POST /api/pause
Pausiert Wiedergabe.
```json
Response: {"status": "success", "message": "Video pausiert"}
```

#### POST /api/resume
Setzt Wiedergabe fort.
```json
Response: {"status": "success", "message": "Wiedergabe fortgesetzt"}
```

#### POST /api/restart
Startet Video neu.
```json
Response: {"status": "success", "message": "Video neu gestartet"}
```

---

### Settings

#### POST /api/brightness
Setzt Helligkeit (0-100).
```json
Request: {"value": 75}
Response: {"status": "success", "brightness": 75}
```

#### POST /api/speed
Setzt Wiedergabe-Geschwindigkeit.
```json
Request: {"value": 1.5}
Response: {"status": "success", "speed": 1.5}
```

#### POST /api/fps
Setzt FPS-Limit.
```json
Request: {"value": 30}
Response: {"status": "success", "fps": 30}
```

#### POST /api/loop
Setzt Loop-Limit (0 = unendlich).
```json
Request: {"value": 5}
Response: {"status": "success", "loop_limit": 5}
```

---

### Art-Net

#### POST /api/blackout
Aktiviert Blackout (alle Kanäle auf 0).
```json
Response: {"status": "success", "message": "Blackout aktiviert"}
```

#### POST /api/test
Sendet Testmuster.
```json
Request: {"color": "red"}
Response: {"status": "success", "message": "Testmuster 'red' gesendet"}
```
**Colors:** red, green, blue, white, yellow, cyan, magenta, gradient

---

### Info & Status

#### GET /api/status
Gibt aktuellen Player-Status zurück.
```json
Response: {
  "status": "playing",
  "is_playing": true,
  "is_paused": false,
  "current_frame": 42,
  "total_frames": 1200,
  "current_loop": 1,
  "brightness": 100,
  "speed": 1.0
}
```

#### GET /api/info
Gibt detaillierte Player-Informationen zurück.
```json
Response: {
  "video": "testbild.mp4",
  "canvas_width": 1024,
  "canvas_height": 768,
  "total_points": 340,
  "total_universes": 2,
  ...
}
```

#### GET /api/stats
Gibt Live-Statistiken zurück.
```json
Response: {
  "fps": 29.8,
  "runtime": "00:02:15",
  "frames_processed": 3580,
  ...
}
```

---

### Points Management

#### GET /api/points/list
Listet alle verfügbaren Points-Dateien auf.
```json
Response: {
  "status": "success",
  "files": [
    {
      "filename": "punkte_export.json",
      "size": 12345,
      "is_current": true,
      "path": "/full/path/to/file.json"
    }
  ],
  "current": "punkte_export.json",
  "total": 3
}
```

#### POST /api/points/switch
Wechselt zu anderer Points-Datei.
```json
Request: {"filename": "other_points.json"}
Response: {
  "status": "success",
  "message": "Points gewechselt zu: other_points.json",
  "filename": "other_points.json",
  "was_playing": true
}
```

#### POST /api/points/reload
Lädt aktuelle Points-Datei neu.
```json
Response: {
  "status": "success",
  "message": "Points neu geladen",
  "filename": "punkte_export.json",
  "was_playing": false
}
```

#### POST /api/points/validate
Validiert eine Points-Datei.
```json
Request: {"filename": "points.json"}
Response: {
  "status": "success",
  "is_valid": true,
  "message": "Points-Datei ist gültig",
  "filename": "points.json",
  "info": {
    "canvas_width": 1024,
    "canvas_height": 768,
    "objects_count": 5
  }
}
```

#### GET /api/points/current
Gibt aktuell geladene Points-Datei zurück.
```json
Response: {
  "status": "success",
  "filename": "punkte_export.json",
  "path": "/full/path/punkte_export.json",
  "total_points": 340,
  "canvas_width": 1024,
  "canvas_height": 768
}
```

---

### Video Management

#### GET /api/videos
Listet alle verfügbaren Videos auf.
```json
Response: {
  "status": "success",
  "videos": [
    {
      "filename": "test.mp4",
      "path": "kanal_1/test.mp4",
      "full_path": "/full/path/test.mp4",
      "size": 1048576,
      "folder": "kanal_1"
    }
  ],
  "current": "kanal_1/test.mp4",
  "total": 42
}
```

#### POST /api/video/load
Lädt ein Video.
```json
Request: {"path": "kanal_1/video.mp4"}
Response: {
  "status": "success",
  "message": "Video geladen: video.mp4",
  "video": "video.mp4",
  "was_playing": true
}
```

#### GET /api/video/current
Gibt aktuell geladenes Video zurück.
```json
Response: {
  "status": "success",
  "filename": "test.mp4",
  "path": "kanal_1/test.mp4",
  "full_path": "/full/path/test.mp4",
  "is_playing": true,
  "is_paused": false,
  "current_frame": 120,
  "total_frames": 300
}
```

---

### Console & Commands

#### GET /api/console/log?lines=100
Gibt Console Log zurück (letzte N Zeilen).
```json
Response: {
  "log": ["line1", "line2", ...],
  "total": 500
}
```

#### POST /api/console/command
Führt CLI-Befehl aus.
```json
Request: {"command": "status"}
Response: {
  "status": "success",
  "output": "Status: playing"
}
```

#### POST /api/console/clear
Löscht Console Log.
```json
Response: {"status": "success", "message": "Console gelöscht"}
```

---

### Recording

#### POST /api/record/start
Startet RGB-Aufzeichnung.
```json
Response: {"status": "success", "message": "Aufzeichnung gestartet"}
```

#### POST /api/record/stop
Stoppt Aufzeichnung.
```json
Request: {"filename": "recording.json"} // optional
Response: {"status": "success", "message": "Aufzeichnung gestoppt"}
```

---

## WebSocket Events

### Client → Server

#### `connect`
Verbindet WebSocket Client.

#### `request_status`
Fordert aktuellen Status an.

#### `request_console`
Fordert Console Log an.
```javascript
socket.emit('request_console', { lines: 100 });
```

### Server → Client

#### `status`
Status-Update (alle 2 Sekunden).
```javascript
{
  "status": "playing",
  "is_playing": true,
  "is_paused": false,
  "current_frame": 42,
  "total_frames": 1200,
  ...
}
```

#### `console_update`
Console Log Update.
```javascript
{
  "log": ["new line"],
  "total": 501,
  "append": true  // true = append, false = replace
}
```

---

## Error Responses

Alle Endpunkte können Fehler zurückgeben:
```json
{
  "status": "error",
  "message": "Fehlerbeschreibung",
  "validation_errors": ["..."]  // optional, bei Validierungsfehlern
}
```

HTTP Status Codes:
- `200` - Erfolg
- `400` - Ungültige Anfrage
- `404` - Ressource nicht gefunden
- `500` - Server-Fehler
