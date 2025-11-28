# Video Sources Konfiguration

## Übersicht

Mit `video_sources` können zusätzliche Ordner und Laufwerke in den File Browser aufgenommen werden. Dies ist nützlich für:

- 📀 **Externe Laufwerke** (USB-Sticks, externe HDDs)
- 🗂️ **Netzlaufwerke** (NAS, Netzwerkfreigaben)
- 👤 **Benutzerordner** (Desktop, Downloads, Dokumente)
- 💾 **Andere Partitionen** (D:\, E:\, etc.)

## Konfiguration

### config.json

```json
{
  "paths": {
    "video_dir": "video",
    "video_sources": [
      "D:\\Videos",
      "E:\\Media\\Movies",
      "C:\\Users\\YourName\\Videos",
      "\\\\nas\\shared\\videos"
    ]
  }
}
```

### Wichtige Hinweise

1. **Backslashes escapen**: In JSON müssen Backslashes verdoppelt werden: `"C:\\Users"`
2. **Absolute Pfade**: Vollständige Pfade verwenden (inkl. Laufwerksbuchstabe)
3. **Nicht-existierende Pfade**: Werden automatisch ignoriert (kein Fehler)
4. **Haupt video_dir**: Ist immer dabei, auch wenn `video_sources` leer ist

## Beispiele

### Windows

```json
{
  "paths": {
    "video_dir": "video",
    "video_sources": [
      "D:\\Videos\\ArtNet",           // Anderes Laufwerk
      "C:\\Users\\Max\\Desktop\\Test", // Desktop-Ordner
      "E:\\Backups\\Videos"            // Backup-Laufwerk
    ]
  }
}
```

### Netzwerkfreigaben (UNC-Pfade)

```json
{
  "paths": {
    "video_dir": "video",
    "video_sources": [
      "\\\\192.168.1.100\\videos",    // NAS via IP
      "\\\\mynas\\shared\\media",      // NAS via Hostname
      "Z:\\Videos"                     // Gemapptes Netzlaufwerk
    ]
  }
}
```

### Linux / macOS

```json
{
  "paths": {
    "video_dir": "video",
    "video_sources": [
      "/media/external/videos",        // Externe Festplatte
      "/mnt/nas/videos",               // Gemountetes NAS
      "/home/user/Videos"              // Home-Verzeichnis
    ]
  }
}
```

## API Verhalten

### GET /api/files/tree

Gibt Ordnerstruktur mit allen Quellen zurück:

```json
{
  "success": true,
  "sources": ["video", "D:\\Videos", "E:\\Media"],
  "tree": [
    {
      "type": "folder",
      "name": "video",
      "path": "video",
      "source": "video",
      "children": [...]
    },
    {
      "type": "folder",
      "name": "Videos",
      "path": "D:\\Videos",
      "source": "D:\\Videos",
      "children": [...]
    },
    {
      "type": "folder",
      "name": "Media",
      "path": "E:\\Media",
      "source": "E:\\Media",
      "children": [...]
    }
  ]
}
```

### GET /api/files/videos

Gibt alle Videos aus allen Quellen zurück:

```json
{
  "success": true,
  "total": 42,
  "videos": [
    {
      "filename": "test.mp4",
      "path": "kanal_1/test.mp4",
      "full_path": "C:\\flux\\video\\kanal_1\\test.mp4",
      "source": "video",
      "source_path": "video",
      "folder": "kanal_1",
      "size": 1048576,
      "size_human": "1.0 MB"
    },
    {
      "filename": "demo.mp4",
      "path": "demo.mp4",
      "full_path": "D:\\Videos\\demo.mp4",
      "source": "Videos",
      "source_path": "D:\\Videos",
      "folder": "root",
      "size": 2097152,
      "size_human": "2.0 MB"
    }
  ]
}
```

## UI Integration

Der File Browser zeigt jede Quelle als separaten Root-Ordner:

```
📁 video/
  📁 kanal_1/
    🎬 test.mp4
  📁 kanal_2/
    🎬 another.mp4

📁 Videos/                    ← D:\Videos
  🎬 demo.mp4
  📁 Tutorials/
    🎬 tutorial_01.mp4

📁 Media/                     ← E:\Media
  📁 Movies/
    🎬 movie.mp4
```

## Performance

### Viele Quellen

Bei vielen Video-Quellen kann der Scan länger dauern:

```json
{
  "paths": {
    "video_sources": [
      "D:\\Videos",      // 10.000 Dateien
      "E:\\Media",       // 5.000 Dateien
      "F:\\Backups"      // 20.000 Dateien
    ]
  }
}
```

**Optimierungen:**
- API cached nichts - Files werden live gescannt
- Große Ordner können mehrere Sekunden dauern
- Netzwerkfreigaben sind langsamer als lokale Laufwerke
- Überlege, nur aktiv genutzte Ordner zu inkludieren

### Empfehlungen

1. **Weniger ist mehr**: Nur aktiv genutzte Quellen hinzufügen
2. **Lokale Pfade bevorzugen**: Schneller als Netzwerk
3. **Unterordner nutzen**: Statt ganzes Laufwerk nur relevanten Ordner
4. **Testen**: Mit `/api/files/videos` Response-Zeit prüfen

## Sicherheit

### Zugriffskontrolle

⚠️ **Wichtig**: Der Server kann auf ALLE konfigurierten Pfade zugreifen:

```json
{
  "paths": {
    "video_sources": [
      "C:\\Users\\Admin\\Documents"  // Vorsicht: Sensible Daten!
    ]
  }
}
```

**Best Practices:**
- Nur Video-Ordner hinzufügen, keine persönlichen Dateien
- Netzwerkfreigaben mit read-only Rechten verwenden
- Server nicht öffentlich exponieren (nur localhost oder vertrauenswürdiges Netzwerk)

### Netzwerkfreigaben

Bei UNC-Pfaden Authentifizierung beachten:

```powershell
# Windows: Netzlaufwerk dauerhaft mappen
net use Z: \\nas\videos /persistent:yes

# Dann in config.json verwenden
"video_sources": ["Z:\\"]
```

## Troubleshooting

### Videos werden nicht angezeigt

1. **Pfad prüfen**:
   ```powershell
   Test-Path "D:\Videos"  # Sollte True zurückgeben
   ```

2. **Backslashes prüfen**:
   ```json
   ✗ "D:\Videos"          // Falsch (Escape-Fehler)
   ✓ "D:\\Videos"         // Richtig
   ✓ "D:/Videos"          // Auch OK (Forward-Slash)
   ```

3. **Berechtigungen prüfen**:
   - Server-Prozess muss Leserechte haben
   - Bei Netzlaufwerken: Authentifizierung nötig

4. **API testen**:
   ```bash
   curl http://localhost:5000/api/files/tree
   ```

### Quelle erscheint nicht im Tree

Mögliche Ursachen:
- Pfad existiert nicht → Wird ignoriert (kein Fehler)
- Keine Leserechte → Wird ignoriert
- Leer: `"video_sources": []` → Nur `video_dir` wird verwendet

### Langsame Ladezeiten

- **Große Ordner**: Tausende Dateien scannen dauert
- **Netzwerk**: NAS/UNC-Pfade sind langsamer
- **Lösung**: Spezifischere Unterordner verwenden

## Beispiel-Szenarien

### Szenario 1: Entwicklung + Produktion

```json
{
  "paths": {
    "video_dir": "video",              // Test-Videos (lokal)
    "video_sources": [
      "D:\\Production\\Videos"         // Produktions-Videos
    ]
  }
}
```

### Szenario 2: Multi-Kanal Setup

```json
{
  "paths": {
    "video_dir": "video",
    "video_sources": [
      "E:\\Channel_1",                 // LED-Wall 1
      "E:\\Channel_2",                 // LED-Wall 2
      "E:\\Channel_3",                 // LED-Wall 3
      "F:\\Backup"                     // Backup-Laufwerk
    ]
  }
}
```

### Szenario 3: NAS-Integration

```json
{
  "paths": {
    "video_dir": "video",
    "video_sources": [
      "\\\\nas.local\\media\\videos",  // Haupt-NAS
      "\\\\192.168.1.50\\backup"       // Backup-NAS
    ]
  }
}
```

## Migration

### Von einzelnem video_dir zu multi-source

**Vorher:**
```json
{
  "paths": {
    "video_dir": "D:\\AllMyVideos"
  }
}
```

**Nachher:**
```json
{
  "paths": {
    "video_dir": "video",              // Lokales Test-Dir
    "video_sources": [
      "D:\\AllMyVideos"                // Haupt-Bibliothek
    ]
  }
}
```

**Vorteil**: Trennung zwischen Test- und Produktions-Content

## Zusammenfassung

✅ **Vorteile:**
- Zugriff auf mehrere Laufwerke/Ordner
- Flexible Content-Organisation
- Kein Kopieren/Verschieben von Dateien nötig
- Netzwerk-Support

⚠️ **Nachteile:**
- Längere Scan-Zeiten bei vielen Quellen
- Netzwerk-Latenz bei UNC-Pfaden
- Mehr Komplexität in UI

💡 **Best Practice:**
- Nur aktiv genutzte Ordner hinzufügen
- Lokale Pfade bevorzugen
- Spezifische Unterordner statt ganzer Laufwerke
- Sicherheit beachten (nur Video-Ordner)
