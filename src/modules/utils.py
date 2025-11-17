"""
Hilfsfunktionen für die CLI-Anwendung
"""
import os
from .constants import VIDEO_EXTENSIONS_LIST


def print_help():
    """Zeigt alle verfügbaren Befehle."""
    print("\n" + "=" * 80)
    print("BEFEHLE")
    print("=" * 80)
    print("\n📹 Playback:")
    print("  restart            - Startet Video neu")
    print("  stop               - Stoppt Video-Wiedergabe")
    print("  pause              - Pausiert Wiedergabe")
    print("  resume             - Setzt Wiedergabe fort")
    print("\n🎬 Video-Verwaltung:")
    print("  load <pfad>        - Lädt ein Video")
    print("  list               - Zeigt alle Videos im video-Ordner")
    print("  switch <name>      - Wechselt zu anderem Video")
    print("\n📍 Punkte-Verwaltung:")
    print("  points list        - Zeigt alle Punkte-Listen")
    print("  points validate [name] - Validiert Punkte-Liste (JSON Schema)")
    print("  points switch <name> - Wechselt Punkte-Liste (mit Validierung)")
    print("  points reload      - Lädt aktuelle Punkte-Liste neu")
    print("\n⚙️ Einstellungen:")
    print("  fps <wert>         - Ändert FPS-Limit (z.B. fps 30)")
    print("  speed <faktor>     - Wiedergabe-Geschwindigkeit (z.B. speed 0.5)")
    print("  brightness <0-100> - Globale Helligkeit (z.B. brightness 50)")
    print("  loop <anzahl>      - Loop-Limit (0 = unendlich)")
    print("\n🌐 Art-Net:")
    print("  ip <adresse>       - Ändert Ziel-IP")
    print("  universe <start>   - Ändert Start-Universum")
    print("  blackout           - Alle DMX-Kanäle auf 0")
    print("  test <farbe>       - Testmuster: red/green/blue/white/yellow/cyan/magenta/gradient")
    print("\n🔌 REST API & WebSocket:")
    print("  api start [port]   - Startet REST API + WebSocket (Standard: Port aus config.json)")
    print("  api stop           - Stoppt REST API Server")
    print("                       Web-Interface: http://localhost:<port>")
    print("                       Control Panel: http://localhost:<port>/controls")
    print("\nℹ️  Info & Status:")
    print("  status             - Zeigt aktuellen Status")
    print("  info               - Zeigt detaillierte System-Informationen")
    print("  stats              - Live-Statistiken (FPS, Frame-Zeit)")
    print("\n⏺️  Aufzeichnung:")
    print("  record start       - Startet RGB-Aufzeichnung")
    print("  record stop [file] - Stoppt Aufzeichnung (optional: Dateiname)")
    print("\n💾 Cache:")
    print("  cache clear        - Löscht alle Cache-Dateien")
    print("  cache info         - Zeigt Cache-Informationen (Größe, Dateien)")
    print("  cache delete <name> - Löscht Cache für spezifisches Video")
    print("  cache enable       - Aktiviert RGB-Caching")
    print("  cache disable      - Deaktiviert RGB-Caching")
    print("  cache size         - Zeigt Größe aller Cache-Dateien")
    print("  cache fill         - Cached alle Videos neu (dauert lange!)")
    print("\n🔧 Allgemein:")
    print("  help               - Zeigt diese Hilfe")
    print("  exit/quit          - Beendet die Anwendung")
    print("\n💡 Hinweis: REST API startet automatisch beim Programmstart")
    print("   Alle Befehle sind auch via Web-Interface verfügbar!")
    print("=" * 80)


def list_videos(video_dir):
    """Listet alle Videos im Ordner auf."""
    if not os.path.exists(video_dir):
        print(f"Video-Ordner nicht gefunden: {video_dir}")
        return []
    
    video_extensions = VIDEO_EXTENSIONS_LIST
    videos = [f for f in os.listdir(video_dir) 
              if os.path.isfile(os.path.join(video_dir, f)) 
              and any(f.lower().endswith(ext) for ext in video_extensions)]
    
    if not videos:
        print("Keine Videos gefunden")
        return []
    
    print(f"\nVideos in {video_dir}:")
    for i, video in enumerate(videos, 1):
        print(f"  {i}. {video}")
    
    return videos


def list_points_files(data_dir):
    """Listet alle Punkte-JSON-Dateien auf."""
    if not os.path.exists(data_dir):
        print(f"Data-Ordner nicht gefunden: {data_dir}")
        return []
    
    json_files = sorted([f for f in os.listdir(data_dir) 
                        if f.endswith('.json') and os.path.isfile(os.path.join(data_dir, f))])
    
    if not json_files:
        print("Keine JSON-Dateien gefunden")
        return []
    
    print(f"\nPunkte-Listen in {data_dir}:")
    for i, json_file in enumerate(json_files, 1):
        print(f"  {i}. {json_file}")
    
    return json_files
