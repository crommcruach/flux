"""
Test Script für Thumbnail-Generator und API-Endpoints

Testet:
1. Thumbnail-Generierung (Video + Bild)
2. Video-Preview-Generierung (GIF)
3. Cache-Funktionen
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from modules.thumbnail_generator import ThumbnailGenerator
from pathlib import Path
import json


def test_thumbnail_generator():
    """Testet ThumbnailGenerator direkt"""
    
    print("=" * 60)
    print("TEST: ThumbnailGenerator")
    print("=" * 60)
    
    # Config mit Standard-Werten
    config = {
        'thumbnails': {
            'enabled': True,
            'size': [200, 200],
            'quality': 85,
            'cache_dir': 'thumbnails',
            'cache_days': 30,
            'video_preview': {
                'enabled': True,
                'duration': 3.0,
                'fps': 10,
                'format': 'gif'
            }
        }
    }
    
    # Initialisiere Generator
    gen = ThumbnailGenerator(config=config)
    print(f"✅ Generator initialisiert")
    print(f"   Cache: {gen.cache_dir}")
    print(f"   Size: {gen.size}")
    print(f"   Quality: {gen.quality}")
    print()
    
    # Test 1: Suche Video-Datei im video/ Ordner
    video_dir = Path('video')
    if not video_dir.exists():
        print("⚠️ video/ Ordner nicht gefunden")
        return
    
    # Finde erste Video-Datei
    video_file = None
    for ext in ['.mp4', '.avi', '.mov', '.mkv']:
        videos = list(video_dir.rglob(f'*{ext}'))
        if videos:
            video_file = videos[0]
            break
    
    if not video_file:
        print("⚠️ Keine Video-Datei gefunden in video/")
        return
    
    print(f"📹 Test-Video gefunden: {video_file.name}")
    print()
    
    # Test 2: Thumbnail generieren
    print("Test 1: Thumbnail-Generierung")
    print("-" * 40)
    thumbnail_path = gen.generate_thumbnail(video_file, async_mode=False)
    
    if thumbnail_path:
        print(f"✅ Thumbnail generiert: {Path(thumbnail_path).name}")
        print(f"   Größe: {Path(thumbnail_path).stat().st_size / 1024:.1f} KB")
    else:
        print("❌ Thumbnail-Generierung fehlgeschlagen")
    print()
    
    # Test 3: Thumbnail aus Cache laden
    print("Test 2: Thumbnail aus Cache")
    print("-" * 40)
    cached_path = gen.get_thumbnail_path(video_file)
    
    if cached_path:
        print(f"✅ Thumbnail im Cache gefunden")
    else:
        print("❌ Thumbnail nicht im Cache")
    print()
    
    # Test 4: Video-Preview generieren
    if gen.video_preview_enabled:
        print("Test 3: Video-Preview-Generierung (GIF)")
        print("-" * 40)
        preview_path = gen.generate_video_preview(video_file)
        
        if preview_path:
            print(f"✅ Video-Preview generiert: {Path(preview_path).name}")
            print(f"   Größe: {Path(preview_path).stat().st_size / 1024:.1f} KB")
            print(f"   Format: {gen.video_preview_format}")
            print(f"   Dauer: {gen.video_preview_duration}s @ {gen.video_preview_fps}fps")
        else:
            print("❌ Video-Preview-Generierung fehlgeschlagen")
        print()
    
    # Test 5: Cache-Statistiken
    print("Test 4: Cache-Statistiken")
    print("-" * 40)
    stats = gen.get_cache_stats()
    print(f"✅ Cache-Statistiken:")
    print(f"   Dateien: {stats['count']}")
    print(f"   Größe: {stats['total_size_mb']} MB")
    print(f"   Verzeichnis: {stats['cache_dir']}")
    print()
    
    print("=" * 60)
    print("✅ Alle Tests abgeschlossen!")
    print("=" * 60)


def test_api_endpoints_info():
    """Gibt Info über API-Endpoints aus"""
    
    print()
    print("=" * 60)
    print("API-ENDPOINTS - Manuelle Tests")
    print("=" * 60)
    print()
    
    print("Starte den Server und teste folgende Endpoints:")
    print()
    
    print("1. Thumbnail abrufen (mit Generierung):")
    print("   GET http://localhost:5000/api/files/thumbnail/<filepath>?generate=true")
    print("   Beispiel: http://localhost:5000/api/files/thumbnail/test.mp4?generate=true")
    print()
    
    print("2. Video-Preview abrufen:")
    print("   GET http://localhost:5000/api/files/video-preview/<filepath>?generate=true")
    print()
    
    print("3. Batch-Generierung:")
    print("   POST http://localhost:5000/api/files/thumbnails/batch")
    print("   Body: {\"files\": [\"file1.mp4\", \"file2.jpg\"]}")
    print()
    
    print("4. Cache-Statistiken:")
    print("   GET http://localhost:5000/api/files/thumbnails/stats")
    print()
    
    print("5. Cache aufräumen:")
    print("   POST http://localhost:5000/api/files/thumbnails/cleanup")
    print("   Body: {\"days\": 30}")
    print()
    
    print("6. Dateiliste mit Thumbnail-Info:")
    print("   GET http://localhost:5000/api/files/videos")
    print("   → Enthält 'has_thumbnail' Property")
    print()
    
    print("=" * 60)
    print()
    
    print("PowerShell-Test-Commands:")
    print("-" * 60)
    print()
    print("# Stats abrufen:")
    print("Invoke-RestMethod -Uri 'http://localhost:5000/api/files/thumbnails/stats' -Method Get")
    print()
    print("# Dateiliste mit Thumbnails:")
    print("Invoke-RestMethod -Uri 'http://localhost:5000/api/files/videos' -Method Get")
    print()
    print("# Batch-Generierung:")
    print('$body = @{files=@("test.mp4")} | ConvertTo-Json')
    print("Invoke-RestMethod -Uri 'http://localhost:5000/api/files/thumbnails/batch' -Method Post -Body $body -ContentType 'application/json'")
    print()


if __name__ == '__main__':
    # Test 1: ThumbnailGenerator direkt
    test_thumbnail_generator()
    
    # Test 2: API-Endpoint Info
    test_api_endpoints_info()
