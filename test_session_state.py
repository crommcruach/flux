"""
Test Script für Session State Auto-Save/Restore Funktionalität

Testet:
1. Playlist-Verwaltung (Add/Remove Clips)
2. Generator-Parameter
3. Clip-Effekte
4. Player-Effekte (Global)
5. Autoplay/Loop Settings
6. State Persistence über Restart
"""

import requests
import json
import time
import os
from pathlib import Path

# API Base URL
API_BASE = "http://localhost:5000"

# Test Results
test_results = []


def log_test(name, passed, message=""):
    """Logge Test-Ergebnis."""
    status = "✅ PASSED" if passed else "❌ FAILED"
    result = f"{status} - {name}"
    if message:
        result += f": {message}"
    print(result)
    test_results.append({"name": name, "passed": passed, "message": message})


def get_session_state_file():
    """Hole Pfad zur session_state.json."""
    return Path(__file__).parent / "session_state.json"


def check_api_health():
    """Prüfe ob API erreichbar ist."""
    try:
        response = requests.get(f"{API_BASE}/api/status", timeout=2)
        return response.status_code == 200
    except:
        return False


def test_1_initial_cleanup():
    """Test 1: Initiales Cleanup - Lösche alte Session State."""
    print("\n" + "="*80)
    print("TEST 1: Initial Cleanup")
    print("="*80)
    
    state_file = get_session_state_file()
    
    try:
        if state_file.exists():
            state_file.unlink()
            print(f"🗑️ Gelöscht: {state_file}")
        
        # Setze leere Playlists
        for player_id in ['video', 'artnet']:
            response = requests.post(
                f"{API_BASE}/api/player/{player_id}/playlist/set",
                json={"playlist": [], "autoplay": False, "loop": False}
            )
            if response.status_code == 200:
                print(f"✅ {player_id} Playlist geleert")
        
        log_test("Initial Cleanup", True)
        time.sleep(0.5)  # Warte auf auto-save
        
    except Exception as e:
        log_test("Initial Cleanup", False, str(e))


def test_2_add_video_to_playlist():
    """Test 2: Füge Video zur Playlist hinzu."""
    print("\n" + "="*80)
    print("TEST 2: Add Video to Playlist")
    print("="*80)
    
    try:
        # Hole verfügbare Videos
        response = requests.get(f"{API_BASE}/api/files/videos")
        data = response.json()
        
        if not data.get('success') or not data.get('videos'):
            log_test("Add Video to Playlist", False, "Keine Videos verfügbar")
            return None
        
        # Nimm erstes Video
        video_path = data['videos'][0]['path']
        print(f"📹 Video: {video_path}")
        
        # Setze Playlist mit Video
        response = requests.post(
            f"{API_BASE}/api/player/video/playlist/set",
            json={
                "playlist": [video_path],
                "autoplay": True,
                "loop": False
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            success = data.get('success', False)
            log_test("Add Video to Playlist", success, f"Playlist: {data.get('playlist_length', 0)} items")
            time.sleep(0.5)  # Warte auf auto-save
            return video_path
        else:
            log_test("Add Video to Playlist", False, f"Status: {response.status_code}")
            return None
            
    except Exception as e:
        log_test("Add Video to Playlist", False, str(e))
        return None


def test_3_add_generator_to_playlist():
    """Test 3: Füge Generator zur Playlist hinzu."""
    print("\n" + "="*80)
    print("TEST 3: Add Generator to Playlist")
    print("="*80)
    
    try:
        # Hole verfügbare Generatoren
        response = requests.get(f"{API_BASE}/api/plugins?type=generator")
        data = response.json()
        
        if not data.get('success') or not data.get('generators'):
            log_test("Add Generator to Playlist", False, "Keine Generatoren verfügbar")
            return None
        
        # Nimm ersten Generator
        generator = data['generators'][0]
        gen_id = generator['id']
        print(f"🌟 Generator: {gen_id}")
        
        # Hole aktuelle Playlist
        status_response = requests.get(f"{API_BASE}/api/player/video/status")
        status_data = status_response.json()
        current_playlist = status_data.get('playlist', [])
        
        # Füge Generator hinzu
        new_playlist = current_playlist + [f"generator:{gen_id}"]
        
        response = requests.post(
            f"{API_BASE}/api/player/video/playlist/set",
            json={
                "playlist": new_playlist,
                "autoplay": True,
                "loop": True
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            success = data.get('success', False)
            log_test("Add Generator to Playlist", success, f"Playlist: {data.get('playlist_length', 0)} items")
            time.sleep(0.5)
            return gen_id
        else:
            log_test("Add Generator to Playlist", False, f"Status: {response.status_code}")
            return None
            
    except Exception as e:
        log_test("Add Generator to Playlist", False, str(e))
        return None


def test_4_load_generator_and_set_parameters(gen_id):
    """Test 4: Lade Generator und setze Parameter."""
    print("\n" + "="*80)
    print("TEST 4: Load Generator and Set Parameters")
    print("="*80)
    
    if not gen_id:
        log_test("Load Generator and Set Parameters", False, "Keine Generator-ID")
        return None
    
    try:
        # Lade Generator
        response = requests.post(
            f"{API_BASE}/api/player/video/clip/load",
            json={
                "type": "generator",
                "generator_id": gen_id,
                "parameters": {"speed": 0.5, "intensity": 0.8}
            }
        )
        
        if response.status_code != 200:
            log_test("Load Generator and Set Parameters", False, f"Status: {response.status_code}")
            return None
        
        data = response.json()
        clip_id = data.get('clip_id')
        
        if not clip_id:
            log_test("Load Generator and Set Parameters", False, "Keine Clip-ID")
            return None
        
        print(f"🎬 Clip-ID: {clip_id}")
        
        # Ändere Parameter
        param_response = requests.post(
            f"{API_BASE}/api/player/video/clip/{clip_id}/generator/parameter",
            json={"parameter": "speed", "value": 0.75}
        )
        
        if param_response.status_code == 200:
            param_data = param_response.json()
            success = param_data.get('success', False)
            log_test("Load Generator and Set Parameters", success, "Parameter 'speed' = 0.75")
            time.sleep(0.5)
            return clip_id
        else:
            log_test("Load Generator and Set Parameters", False, f"Param Status: {param_response.status_code}")
            return None
            
    except Exception as e:
        log_test("Load Generator and Set Parameters", False, str(e))
        return None


def test_5_add_clip_effect(clip_id):
    """Test 5: Füge Effekt zu Clip hinzu."""
    print("\n" + "="*80)
    print("TEST 5: Add Clip Effect")
    print("="*80)
    
    if not clip_id:
        log_test("Add Clip Effect", False, "Keine Clip-ID")
        return
    
    try:
        # Hole verfügbare Effekte
        response = requests.get(f"{API_BASE}/api/plugins?type=effect")
        data = response.json()
        
        if not data.get('success') or not data.get('effects'):
            log_test("Add Clip Effect", False, "Keine Effekte verfügbar")
            return
        
        # Nimm ersten Effekt (z.B. brightness)
        effect = data['effects'][0]
        effect_id = effect['id']
        print(f"✨ Effekt: {effect_id}")
        
        # Füge Effekt zum Clip hinzu
        response = requests.post(
            f"{API_BASE}/api/player/video/clip/{clip_id}/effects/add",
            json={"plugin_id": effect_id}
        )
        
        if response.status_code == 200:
            data = response.json()
            success = data.get('success', False)
            log_test("Add Clip Effect", success, f"Effekt '{effect_id}' hinzugefügt")
            time.sleep(0.5)
        else:
            log_test("Add Clip Effect", False, f"Status: {response.status_code}")
            
    except Exception as e:
        log_test("Add Clip Effect", False, str(e))


def test_6_add_player_effect():
    """Test 6: Füge globalen Player-Effekt hinzu."""
    print("\n" + "="*80)
    print("TEST 6: Add Player Effect (Global)")
    print("="*80)
    
    try:
        # Hole verfügbare Effekte
        response = requests.get(f"{API_BASE}/api/plugins?type=effect")
        data = response.json()
        
        if not data.get('success') or not data.get('effects'):
            log_test("Add Player Effect", False, "Keine Effekte verfügbar")
            return
        
        # Nimm zweiten Effekt falls vorhanden
        effects = data['effects']
        effect = effects[1] if len(effects) > 1 else effects[0]
        effect_id = effect['id']
        print(f"✨ Player-Effekt: {effect_id}")
        
        # Füge Player-Effekt hinzu
        response = requests.post(
            f"{API_BASE}/api/player/effects/add",
            json={"plugin_id": effect_id, "config": {}}
        )
        
        if response.status_code == 200:
            data = response.json()
            success = data.get('success', False)
            log_test("Add Player Effect", success, f"Player-Effekt '{effect_id}' hinzugefügt")
            time.sleep(0.5)
        else:
            log_test("Add Player Effect", False, f"Status: {response.status_code}")
            
    except Exception as e:
        log_test("Add Player Effect", False, str(e))


def test_7_verify_session_state_file():
    """Test 7: Prüfe ob session_state.json erstellt wurde."""
    print("\n" + "="*80)
    print("TEST 7: Verify session_state.json Created")
    print("="*80)
    
    try:
        state_file = get_session_state_file()
        
        if not state_file.exists():
            log_test("Verify session_state.json", False, "Datei existiert nicht")
            return None
        
        # Lade und parse JSON
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        print(f"📄 Datei: {state_file}")
        print(f"📅 Last Updated: {state.get('last_updated', 'N/A')}")
        
        # Prüfe Struktur
        players = state.get('players', {})
        video_player = players.get('video', {})
        
        playlist_len = len(video_player.get('playlist', []))
        autoplay = video_player.get('autoplay', False)
        loop = video_player.get('loop', False)
        
        print(f"📋 Video Playlist: {playlist_len} items")
        print(f"▶️ Autoplay: {autoplay}")
        print(f"🔁 Loop: {loop}")
        
        # Zeige Playlist-Details
        for i, item in enumerate(video_player.get('playlist', [])):
            item_type = item.get('type', 'unknown')
            path = item.get('path', '')
            print(f"   [{i}] Type: {item_type}, Path: {path}")
            
            if item_type == 'generator':
                params = item.get('parameters', {})
                print(f"       Parameters: {params}")
            
            effects = item.get('effects', [])
            if effects:
                print(f"       Effects: {len(effects)}")
        
        # Global effects
        global_effects = video_player.get('global_effects', [])
        if global_effects:
            print(f"✨ Global Effects: {len(global_effects)}")
        
        success = playlist_len > 0
        log_test("Verify session_state.json", success, f"{playlist_len} items in playlist")
        
        return state
        
    except Exception as e:
        log_test("Verify session_state.json", False, str(e))
        return None


def test_8_simulate_restart():
    """Test 8: Simuliere Server-Restart durch erneutes Laden der Playlist."""
    print("\n" + "="*80)
    print("TEST 8: Simulate Restart (Reload Playlist)")
    print("="*80)
    print("⚠️ HINWEIS: Für vollständigen Test bitte Server manuell neustarten!")
    print("           Dieser Test prüft nur ob session_state.json lesbar ist.")
    
    try:
        state_file = get_session_state_file()
        
        if not state_file.exists():
            log_test("Simulate Restart", False, "session_state.json nicht gefunden")
            return
        
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        video_state = state.get('players', {}).get('video', {})
        playlist = video_state.get('playlist', [])
        
        print(f"📋 Gespeichert: {len(playlist)} items")
        
        # Hole aktuelle Playlist vom Server
        response = requests.get(f"{API_BASE}/api/player/video/status")
        data = response.json()
        
        if not data.get('success'):
            log_test("Simulate Restart", False, "Kann Status nicht abrufen")
            return
        
        current_playlist = data.get('playlist', [])
        current_autoplay = data.get('autoplay', False)
        current_loop = data.get('loop', False)
        
        print(f"📋 Aktuell: {len(current_playlist)} items")
        print(f"▶️ Autoplay: {current_autoplay}")
        print(f"🔁 Loop: {current_loop}")
        
        # Vergleiche
        playlist_match = len(playlist) == len(current_playlist)
        autoplay_match = video_state.get('autoplay') == current_autoplay
        loop_match = video_state.get('loop') == current_loop
        
        all_match = playlist_match and autoplay_match and loop_match
        
        log_test("Simulate Restart", all_match, 
                f"Playlist: {playlist_match}, Autoplay: {autoplay_match}, Loop: {loop_match}")
        
    except Exception as e:
        log_test("Simulate Restart", False, str(e))


def print_summary():
    """Drucke Test-Zusammenfassung."""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total = len(test_results)
    passed = sum(1 for r in test_results if r['passed'])
    failed = total - passed
    
    print(f"\nTotal Tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    if failed > 0:
        print("\n❌ FAILED TESTS:")
        for r in test_results:
            if not r['passed']:
                print(f"   - {r['name']}: {r['message']}")
    
    print("\n" + "="*80)
    
    if failed == 0:
        print("🎉 ALLE TESTS BESTANDEN!")
    else:
        print(f"⚠️ {failed} Test(s) fehlgeschlagen")
    
    print("="*80)


def main():
    """Hauptfunktion - Führe alle Tests aus."""
    print("\n" + "="*80)
    print("SESSION STATE AUTO-SAVE/RESTORE TEST")
    print("="*80)
    print(f"API: {API_BASE}")
    print("="*80)
    
    # Prüfe API
    if not check_api_health():
        print("❌ API ist nicht erreichbar! Bitte starte den Server:")
        print("   python src/main.py")
        return
    
    print("✅ API ist erreichbar\n")
    
    # Führe Tests aus
    test_1_initial_cleanup()
    
    video_path = test_2_add_video_to_playlist()
    gen_id = test_3_add_generator_to_playlist()
    clip_id = test_4_load_generator_and_set_parameters(gen_id)
    
    test_5_add_clip_effect(clip_id)
    test_6_add_player_effect()
    
    state = test_7_verify_session_state_file()
    test_8_simulate_restart()
    
    # Zusammenfassung
    print_summary()
    
    # Instructions
    print("\n" + "="*80)
    print("NÄCHSTE SCHRITTE FÜR VOLLSTÄNDIGEN TEST:")
    print("="*80)
    print("1. Stoppe den Server (Ctrl+C)")
    print("2. Starte den Server neu: python src/main.py")
    print("3. Öffne das Frontend: http://localhost:5000")
    print("4. Prüfe ob:")
    print("   - Playlist beide Clips enthält (Video + Generator)")
    print("   - Generator-Parameter erhalten sind (speed=0.75)")
    print("   - Effekte angezeigt werden")
    print("   - Autoplay/Loop Settings erhalten sind")
    print("="*80)


if __name__ == "__main__":
    main()
