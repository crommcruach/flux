"""
Helper functions for the CLI application
"""
import os
from .constants import VIDEO_EXTENSIONS_LIST


def print_help():
    """Shows all available commands."""
    print("\n" + "=" * 80)
    print("BEFEHLE")
    print("=" * 80)
    print("\n📹 Playback:")
    print("  start              - Startet Script/Video-Wiedergabe")
    print("  restart            - Startet Script/Video von vorne neu")
    print("  stop               - Stoppt Script/Video-Wiedergabe")
    print("  pause              - Pausiert Script/Video-Wiedergabe")
    print("  resume             - Setzt Script/Video-Wiedergabe fort")
    print("  next               - Loads next video/script")
    print("  back               - Loads previous video/script")
    print("\n🎬 Video-Verwaltung:")
    print("  videos             - Lists all available videos")
    print("  video:<name>       - Loads and starts video (e.g. video:testimage)")
    print("\n📍 Punkte-Verwaltung:")
    print("  points list        - Zeigt alle Punkte-Listen")
    print("  points validate [name] - Validiert Punkte-Liste (JSON Schema)")
    print("  points switch <name> - Wechselt Punkte-Liste (mit Validierung)")
    print("  points reload      - Reloads current points list")
    print("\n⚙️ Einstellungen:")
    print("  fps <value>        - Changes FPS limit (e.g. fps 30)")
    print("  speed <faktor>     - Wiedergabe-Geschwindigkeit (z.B. speed 0.5)")
    print("  brightness <0-100> - Globale Helligkeit (z.B. brightness 50)")
    print("  loop <anzahl>      - Loop-Limit (0 = unendlich)")
    print("\n🌐 Art-Net:")
    print("  ip <address>       - Changes target IP")
    print("  universe <start>   - Changes start universe")
    print("  blackout           - All DMX channels to 0")
    print("  test <farbe>       - Testmuster: red/green/blue/white/yellow/cyan/magenta/gradient")
    print("  artnet map <format> <universes> - RGB-Kanal-Reihenfolge (z.B. artnet map grb 0-5)")
    print("  artnet show        - Zeigt aktuelle Kanal-Mappings")
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
    print("\n Plugins:")
    print("  plugin list        - Zeigt alle registrierten Plugins")
    print("  plugin reload      - Reloads all plugins (hot-reload)")
    print("\n🎨 Prozedural:")
    print("  scripts [list]     - Shows all available Python scripts")
    print("  script:<name>      - Loads and starts script (e.g. script:rainbow_wave)")
    print("                       Scripts laufen endlos und generieren Grafiken in Echtzeit")
    print("\n🔧 Allgemein:")
    print("  help               - Zeigt diese Hilfe")
    print("  exit/quit          - Beendet die Anwendung")
    print("\n💡 Hinweis: REST API startet automatisch beim Programmstart")
    print("   All commands are also available via web interface!")
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
