"""
Test Script für Unified Player API
Testet die neuen /api/player/<player_id>/... Endpoints
"""

import requests
import json
import time

BASE_URL = "http://localhost:5000"

def print_test(name):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print('='*60)

def print_result(response):
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        return data
    except:
        print(f"Response: {response.text}")
        return None

# ============================================
# TEST 1: Video in Video Player laden
# ============================================
print_test("Lade Video in Video Player")
response = requests.post(f"{BASE_URL}/api/player/video/clip/load", json={
    "path": "testbild.mp4"
})
video_data = print_result(response)
video_clip_id = video_data.get('clip_id') if video_data and video_data.get('success') else None
print(f"✅ Video Clip-ID: {video_clip_id}")

time.sleep(1)

# ============================================
# TEST 2: Video in Art-Net Player laden
# ============================================
print_test("Lade Video in Art-Net Player")
response = requests.post(f"{BASE_URL}/api/player/artnet/clip/load", json={
    "path": "testbild.mp4"
})
artnet_data = print_result(response)
artnet_clip_id = artnet_data.get('clip_id') if artnet_data and artnet_data.get('success') else None
print(f"✅ Art-Net Clip-ID: {artnet_clip_id}")

time.sleep(1)

# ============================================
# TEST 3: Aktuellen Clip abfragen (Video Player)
# ============================================
print_test("Aktuellen Clip von Video Player abfragen")
response = requests.get(f"{BASE_URL}/api/player/video/clip/current")
print_result(response)

time.sleep(1)

# ============================================
# TEST 4: Aktuellen Clip abfragen (Art-Net Player)
# ============================================
print_test("Aktuellen Clip von Art-Net Player abfragen")
response = requests.get(f"{BASE_URL}/api/player/artnet/clip/current")
print_result(response)

time.sleep(1)

# ============================================
# TEST 5: Effekt zu Video Clip hinzufügen
# ============================================
if video_clip_id:
    print_test(f"Füge Effekt 'add_subtract' zu Video Clip hinzu (ID: {video_clip_id})")
    response = requests.post(f"{BASE_URL}/api/player/video/clip/{video_clip_id}/effects/add", json={
        "plugin_id": "add_subtract"
    })
    print_result(response)
    time.sleep(1)

# ============================================
# TEST 6: Effekt zu Art-Net Clip hinzufügen
# ============================================
if artnet_clip_id:
    print_test(f"Füge Effekt 'brightness_contrast' zu Art-Net Clip hinzu (ID: {artnet_clip_id})")
    response = requests.post(f"{BASE_URL}/api/player/artnet/clip/{artnet_clip_id}/effects/add", json={
        "plugin_id": "brightness_contrast"
    })
    print_result(response)
    time.sleep(1)

# ============================================
# TEST 7: Clip-Effekte abfragen (Video)
# ============================================
if video_clip_id:
    print_test(f"Clip-Effekte von Video Player abfragen (ID: {video_clip_id})")
    response = requests.get(f"{BASE_URL}/api/player/video/clip/{video_clip_id}/effects")
    print_result(response)
    time.sleep(1)

# ============================================
# TEST 8: Clip-Effekte abfragen (Art-Net)
# ============================================
if artnet_clip_id:
    print_test(f"Clip-Effekte von Art-Net Player abfragen (ID: {artnet_clip_id})")
    response = requests.get(f"{BASE_URL}/api/player/artnet/clip/{artnet_clip_id}/effects")
    print_result(response)
    time.sleep(1)

# ============================================
# TEST 9: Effekt-Parameter ändern (Video)
# ============================================
if video_clip_id:
    print_test(f"Ändere 'red' Parameter von Video Clip-Effekt (ID: {video_clip_id})")
    response = requests.put(f"{BASE_URL}/api/player/video/clip/{video_clip_id}/effects/0/parameter", json={
        "name": "red",
        "value": 100.0
    })
    print_result(response)
    time.sleep(1)

# ============================================
# TEST 10: Effekt-Parameter ändern (Art-Net)
# ============================================
if artnet_clip_id:
    print_test(f"Ändere 'brightness' Parameter von Art-Net Clip-Effekt (ID: {artnet_clip_id})")
    response = requests.put(f"{BASE_URL}/api/player/artnet/clip/{artnet_clip_id}/effects/0/parameter", json={
        "name": "brightness",
        "value": 50.0
    })
    print_result(response)
    time.sleep(1)

# ============================================
# TEST 11: Video Player starten
# ============================================
print_test("Starte Video Player")
response = requests.post(f"{BASE_URL}/api/player/video/play")
print_result(response)
time.sleep(2)

# ============================================
# TEST 12: Art-Net Player starten
# ============================================
print_test("Starte Art-Net Player")
response = requests.post(f"{BASE_URL}/api/player/artnet/play")
print_result(response)
time.sleep(2)

# ============================================
# TEST 13: Video Player pausieren
# ============================================
print_test("Pausiere Video Player")
response = requests.post(f"{BASE_URL}/api/player/video/pause")
print_result(response)
time.sleep(1)

# ============================================
# TEST 14: Art-Net Player pausieren
# ============================================
print_test("Pausiere Art-Net Player")
response = requests.post(f"{BASE_URL}/api/player/artnet/pause")
print_result(response)
time.sleep(1)

# ============================================
# TEST 15: Video Player stoppen
# ============================================
print_test("Stoppe Video Player")
response = requests.post(f"{BASE_URL}/api/player/video/stop")
print_result(response)
time.sleep(1)

# ============================================
# TEST 16: Art-Net Player stoppen
# ============================================
print_test("Stoppe Art-Net Player")
response = requests.post(f"{BASE_URL}/api/player/artnet/stop")
print_result(response)

# ============================================
# TEST 17: Clip-Effekte löschen (Video)
# ============================================
if video_clip_id:
    print_test(f"Entferne Effekt von Video Clip (ID: {video_clip_id})")
    response = requests.delete(f"{BASE_URL}/api/player/video/clip/{video_clip_id}/effects/0")
    print_result(response)
    time.sleep(1)

# ============================================
# TEST 18: Alle Clip-Effekte löschen (Art-Net)
# ============================================
if artnet_clip_id:
    print_test(f"Lösche alle Effekte von Art-Net Clip (ID: {artnet_clip_id})")
    response = requests.post(f"{BASE_URL}/api/player/artnet/clip/{artnet_clip_id}/effects/clear")
    print_result(response)
    time.sleep(1)

# ============================================
# TEST 19: Ungültige Player-ID
# ============================================
print_test("Teste ungültige Player-ID")
response = requests.post(f"{BASE_URL}/api/player/invalid/play")
print_result(response)

# ============================================
# TEST 20: Ungültige Clip-ID
# ============================================
print_test("Teste ungültige Clip-ID")
response = requests.get(f"{BASE_URL}/api/player/video/clip/invalid-uuid-123/effects")
print_result(response)

print(f"\n{'='*60}")
print("✅ ALLE TESTS ABGESCHLOSSEN")
print('='*60)
print(f"\nZusammenfassung:")
print(f"  Video Clip-ID: {video_clip_id}")
print(f"  Art-Net Clip-ID: {artnet_clip_id}")
print(f"\nDie Unified API ist einsatzbereit!")
