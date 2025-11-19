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

#### GET /api/local_ips
Gibt alle lokalen IP-Adressen zurück (für Art-Net Konfiguration).
```json
Response: {
  "status": "success",
  "ips": ["2.255.255.255", "255.255.255.255", "127.0.0.1", "192.168.1.100"],
  "current": "192.168.1.11"
}
```

#### POST /api/ip
Setzt Art-Net Ziel-IP und speichert in config.json.
```json
Request: {"ip": "192.168.1.11"}
Response: {"status": "success", "ip": "192.168.1.11"}
```

---

### Script Generator

#### GET /api/scripts
Gibt Liste aller verfügbaren Scripts zurück.
```json
Response: {
  "status": "success",
  "scripts": ["rainbow_wave", "plasma", "pulse", "line_vertical", "line_horizontal"],
  "count": 5
}
```

#### POST /api/load_script
Lädt und startet ein prozedurales Script.
```json
Request: {"script": "rainbow_wave"}
Response: {"status": "success", "message": "Script 'rainbow_wave' geladen"}
```

#### GET /api/script/info/<script_name>
Gibt Metadaten eines Scripts zurück.
```json
Response: {
  "status": "success",
  "name": "Rainbow Wave",
  "description": "Animierte Regenbogen-Welle",
  "parameters": {
    "speed": 1.0,
    "wavelength": 100
  }
}
```

---

### Configuration Management

#### GET /api/config
Gibt die aktuelle Konfiguration zurück.
```json
Response: {
  "status": "success",
  "config": {
    "artnet": {...},
    "video": {...},
    "paths": {...}
  }
}
```

#### POST /api/config
Speichert neue Konfiguration (erstellt automatisch Backup).
```json
Request: {
  "artnet": {...},
  "video": {...},
  "paths": {...}
}
Response: {
  "status": "success",
  "message": "Konfiguration gespeichert",
  "backup_created": true
}
```

#### POST /api/config/validate
Validiert Konfiguration ohne zu speichern.
```json
Request: {"artnet": {...}, "video": {...}}
Response: {
  "status": "success",
  "valid": true,
  "errors": []
}
```

#### POST /api/config/restore
Stellt Konfiguration von Backup wieder her.
```json
Response: {
  "status": "success",
  "message": "Konfiguration von Backup wiederhergestellt"
}
```

#### GET /api/config/schema
Gibt das vollständige JSON-Schema zurück.
```json
Response: {
  "status": "success",
  "schema": {
    "type": "object",
    "properties": { ... }
  }
}
```

#### GET /api/config/default
Gibt Standard-Konfiguration zurück.
```json
Response: {
  "status": "success",
  "config": {
    "artnet": { ... },
    "video": { ... },
    "paths": { ... }
  }
}
```

**Hinweis:** Die Config wird beim Speichern automatisch gegen das Schema validiert. Siehe `docs/CONFIG_SCHEMA.md` für Details.

---

### Cache Management

#### POST /api/cache/clear
Löscht alle Cache-Dateien.
```json
Response: {
  "status": "success",
  "deleted_files": 15,
  "message": "15 Cache-Dateien gelöscht"
}
```

#### GET /api/cache/stats
Gibt Cache-Statistiken zurück.
```json
Response: {
  "status": "success",
  "total_files": 15,
  "total_size_mb": 234.5
}
Response: {
  "status": "success",
  "ip": "192.168.1.11",
  "message": "✅ Art-Net IP geändert...\n🔄 Art-Net wurde automatisch neu geladen"
}
```

#### GET /api/ip
Gibt aktuelle Art-Net Ziel-IP zurück.
```json
Response: {"status": "success", "ip": "192.168.1.11"}
```

---

### RGB Channel Mapping

Das System unterstützt pro Universum unterschiedliche RGB-Kanal-Reihenfolgen.

**Unterstützte Formate:**
- `RGB` - Standard (WS2812B)
- `GRB` - Häufig bei WS2811
- `BGR` - Manche China-LEDs
- `RBG`, `GBR`, `BRG` - Weitere Permutationen

**Konfiguration in config.json:**
```json
"artnet": {
  "universe_configs": {
    "default": "RGB",
    "0": "GRB",
    "1": "BGR"
  }
}
```

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

### Scripts (Prozedural)

#### GET /api/scripts
Listet alle verfügbaren Python-Scripts.
```json
Response: {
  "status": "success",
  "scripts": [
    {
      "name": "rainbow_wave.py",
      "description": "Animated rainbow wave",
      "parameters": {
        "speed": 1.0,
        "wave_length": 200
      }
    },
    {
      "name": "plasma.py",
      "description": "Classic plasma effect",
      "parameters": {}
    }
  ],
  "count": 2
}
```

#### POST /api/load_script
Lädt und startet ein Python-Script als Videoquelle.
```json
Request: {"script": "rainbow_wave"}
Response: {
  "status": "success",
  "message": "Script geladen: rainbow_wave.py",
  "info": {
    "name": "rainbow_wave.py",
    "description": "Animated rainbow wave",
    "parameters": {...},
    "canvas_width": 1920,
    "canvas_height": 1080,
    "total_points": 150
  }
}
```

**Hinweis:** Scripts laufen endlos und generieren Frames prozedural. Der ScriptPlayer ersetzt den VideoPlayer während der Laufzeit. Alle Standard-Befehle (brightness, speed, etc.) funktionieren weiterhin.

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
