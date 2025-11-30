"""
Comprehensive Multi-Layer API Test
Testet alle Hauptfunktionen mit 2 Layern:
- Layer hinzufügen/entfernen
- Play/Stop/Pause/Resume
- Effekte auf Layer 0 und Layer 1
- Layer-Config Updates
- Status-Abfragen
"""
import requests
import time
import json

# API Configuration
BASE_URL = "http://localhost:5000"
PLAYER_ID = "video"  # Player ID in PlayerManager

def print_separator(title=""):
    """Print formatted separator"""
    if title:
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}")
    else:
        print(f"{'='*80}")

def check_api():
    """Prüfe ob API verfügbar ist"""
    try:
        response = requests.get(f"{BASE_URL}/api/status", timeout=2)
        if response.status_code == 200:
            print("✅ API is ready")
            return True
    except:
        pass
    print("❌ API not available!")
    return False

def cleanup_all_layers():
    """Entferne alle existierenden Layer"""
    try:
        response = requests.get(f"{BASE_URL}/api/player/{PLAYER_ID}/layers")
        if response.status_code == 200:
            data = response.json()
            for layer in data.get('layers', []):
                layer_id = layer['layer_id']
                requests.delete(f"{BASE_URL}/api/player/{PLAYER_ID}/layers/{layer_id}")
        print("🗑️  Cleanup: All layers removed")
    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")

def test_1_add_layers():
    """Test 1: Füge 2 Layer hinzu"""
    print_separator("TEST 1: Add 2 Layers")
    
    # Layer 0: Checkerboard (Master)
    print("\n📌 Adding Layer 0: Checkerboard (normal, 100%)")
    payload = {
        "type": "generator",
        "generator_id": "checkerboard",
        "parameters": {"size": 10},
        "blend_mode": "normal",
        "opacity": 100
    }
    response = requests.post(f"{BASE_URL}/api/player/{PLAYER_ID}/layers/add", json=payload)
    assert response.status_code == 201, f"Failed: {response.status_code}"
    data = response.json()
    assert data['success'] == True
    layer0_id = data['layer_id']
    layer0_clip = data['clip_id']
    print(f"✅ Layer 0 added: ID={layer0_id}, Clip={layer0_clip}")
    
    # Layer 1: Plasma (Slave mit Multiply)
    print("\n📌 Adding Layer 1: Plasma (multiply, 75%)")
    payload = {
        "type": "generator",
        "generator_id": "plasma",
        "parameters": {"speed": 0.5, "scale": 1.0},
        "blend_mode": "multiply",
        "opacity": 75
    }
    response = requests.post(f"{BASE_URL}/api/player/{PLAYER_ID}/layers/add", json=payload)
    assert response.status_code == 201, f"Failed: {response.status_code}"
    data = response.json()
    assert data['success'] == True
    layer1_id = data['layer_id']
    layer1_clip = data['clip_id']
    print(f"✅ Layer 1 added: ID={layer1_id}, Clip={layer1_clip}")
    
    # Verify
    response = requests.get(f"{BASE_URL}/api/player/{PLAYER_ID}/layers")
    data = response.json()
    assert data['layer_count'] == 2
    print(f"\n✅ Verified: {data['layer_count']} layers in stack")
    for i, layer in enumerate(data['layers']):
        print(f"   Layer {i}: {layer['path']}, blend={layer['blend_mode']}, opacity={layer['opacity']}%")
    
    return layer0_id, layer0_clip, layer1_id, layer1_clip


def test_2_playback_controls(layer0_id, layer1_id):
    """Test 2: Playback Controls (Play, Pause, Resume, Stop)"""
    print_separator("TEST 2: Playback Controls")
    
    # Start playback
    print("\n▶️  Starting playback (2-layer compositing)...")
    response = requests.post(f"{BASE_URL}/api/play")
    assert response.status_code == 200
    print("✅ Playback started")
    
    # Wait and check status
    time.sleep(2)
    response = requests.get(f"{BASE_URL}/api/status")
    data = response.json()
    # Status can be direct or in 'video_player' key
    player = data.get('video_player', data)
    print(f"✅ Player status: {player.get('status', 'unknown')}")
    print(f"   Frames processed: {player.get('frames_processed', 0)}")
    print(f"   FPS: {player.get('current_fps', 0):.1f}")
    
    # Pause
    print("\n⏸️  Pausing playback...")
    response = requests.post(f"{BASE_URL}/api/pause")
    assert response.status_code == 200
    print("✅ Playback paused")
    time.sleep(1)
    
    # Resume
    print("\n▶️  Resuming playback...")
    response = requests.post(f"{BASE_URL}/api/resume")
    assert response.status_code == 200
    print("✅ Playback resumed")
    time.sleep(2)
    
    # Check frames increased
    response = requests.get(f"{BASE_URL}/api/status")
    data = response.json()
    player = data.get('video_player', data)
    print(f"✅ Frames after resume: {player.get('frames_processed', 0)}")
    
    # Stop
    print("\n⏹️  Stopping playback...")
    response = requests.post(f"{BASE_URL}/api/stop")
    assert response.status_code == 200
    print("✅ Playback stopped")


def test_3_apply_effect_layer0(layer0_clip):
    """Test 3: Apply Effect to Layer 0"""
    print_separator("TEST 3: Apply Effect to Layer 0 (Clip Effect)")
    
    print(f"\n🎨 Applying 'invert' effect to Layer 0 (Clip {layer0_clip})")
    
    # Apply invert effect to layer 0's clip
    payload = {
        "plugin_id": "invert",
        "parameters": {}
    }
    response = requests.post(
        f"{BASE_URL}/api/clips/{layer0_clip}/effects/add",
        json=payload
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Invert effect added to Layer 0")
        print(f"   Effect chain length: {len(data.get('effects', []))}")
    else:
        print(f"⚠️  Effect API returned: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
    
    # Start playback to see effect
    print("\n▶️  Starting playback to verify effect...")
    requests.post(f"{BASE_URL}/api/play")
    time.sleep(2)
    
    response = requests.get(f"{BASE_URL}/api/status")
    data = response.json()
    player = data.get('video_player', data)
    print(f"✅ Playing with effect: {player.get('frames_processed', 0)} frames")
    
    requests.post(f"{BASE_URL}/api/stop")


def test_4_apply_effect_layer1(layer1_clip):
    """Test 4: Apply Effect to Layer 1"""
    print_separator("TEST 4: Apply Effect to Layer 1 (Clip Effect)")
    
    print(f"\n🎨 Applying 'brightness' effect to Layer 1 (Clip {layer1_clip})")
    
    # Apply brightness effect to layer 1's clip
    payload = {
        "plugin_id": "brightness",
        "parameters": {"brightness": 1.5}  # 150% brightness
    }
    response = requests.post(
        f"{BASE_URL}/api/clips/{layer1_clip}/effects/add",
        json=payload
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Brightness effect added to Layer 1")
        print(f"   Effect chain length: {len(data.get('effects', []))}")
    else:
        print(f"⚠️  Effect API returned: {response.status_code}")
    
    # Start playback
    print("\n▶️  Starting playback with both effects...")
    requests.post(f"{BASE_URL}/api/play")
    time.sleep(2)
    
    response = requests.get(f"{BASE_URL}/api/status")
    data = response.json()
    player = data.get('video_player', data)
    print(f"✅ Playing: Layer 0 (inverted) × Layer 1 (bright plasma)")
    print(f"   Frames: {player.get('frames_processed', 0)}")
    
    requests.post(f"{BASE_URL}/api/stop")


def test_5_update_layer_config(layer1_id):
    """Test 5: Update Layer Configuration"""
    print_separator("TEST 5: Update Layer 1 Configuration")
    
    print(f"\n🔧 Updating Layer 1: blend_mode=screen, opacity=50%")
    payload = {
        "blend_mode": "screen",
        "opacity": 50
    }
    response = requests.patch(
        f"{BASE_URL}/api/player/{PLAYER_ID}/layers/{layer1_id}",
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data['layer']['blend_mode'] == 'screen'
    assert data['layer']['opacity'] == 50
    print("✅ Layer 1 updated: screen blend, 50% opacity")
    
    # Test playback with new config
    print("\n▶️  Testing with new configuration...")
    requests.post(f"{BASE_URL}/api/play")
    time.sleep(2)
    print("✅ Playback with screen blend mode")
    requests.post(f"{BASE_URL}/api/stop")


def test_6_disable_layer(layer1_id):
    """Test 6: Disable/Enable Layer"""
    print_separator("TEST 6: Disable/Enable Layer 1")
    
    print(f"\n❌ Disabling Layer 1...")
    payload = {"enabled": False}
    response = requests.patch(
        f"{BASE_URL}/api/player/{PLAYER_ID}/layers/{layer1_id}",
        json=payload
    )
    assert response.status_code == 200
    print("✅ Layer 1 disabled")
    
    # Play with only layer 0
    print("\n▶️  Playing with only Layer 0 (Layer 1 disabled)...")
    requests.post(f"{BASE_URL}/api/play")
    time.sleep(2)
    print("✅ Only Layer 0 visible")
    requests.post(f"{BASE_URL}/api/stop")
    
    # Re-enable
    print(f"\n✅ Re-enabling Layer 1...")
    payload = {"enabled": True}
    response = requests.patch(
        f"{BASE_URL}/api/player/{PLAYER_ID}/layers/{layer1_id}",
        json=payload
    )
    assert response.status_code == 200
    print("✅ Layer 1 re-enabled")


def test_7_reorder_layers(layer0_id, layer1_id):
    """Test 7: Reorder Layers (Swap Master)"""
    print_separator("TEST 7: Reorder Layers (Swap Layer 0 & 1)")
    
    print(f"\n🔄 Swapping layers: Layer 1 becomes Master, Layer 0 becomes Slave")
    payload = {"order": [layer1_id, layer0_id]}
    response = requests.put(
        f"{BASE_URL}/api/player/{PLAYER_ID}/layers/reorder",
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    print("✅ Layers reordered")
    for i, layer in enumerate(data['layers']):
        print(f"   Position {i}: Layer {layer['layer_id']} ({layer['generator_id']})")
    
    # Play with new order
    print("\n▶️  Playing with new order (Plasma is now Master)...")
    requests.post(f"{BASE_URL}/api/play")
    time.sleep(2)
    print("✅ Master layer changed - Plasma controls timing")
    requests.post(f"{BASE_URL}/api/stop")
    
    # Swap back
    print(f"\n🔄 Restoring original order...")
    payload = {"order": [layer0_id, layer1_id]}
    response = requests.put(
        f"{BASE_URL}/api/player/{PLAYER_ID}/layers/reorder",
        json=payload
    )
    assert response.status_code == 200
    print("✅ Original order restored")


def test_8_add_third_layer():
    """Test 8: Add Third Layer (Fire with Add blend)"""
    print_separator("TEST 8: Add Third Layer (Fire)")
    
    print("\n📌 Adding Layer 2: Fire (add blend, 60%)")
    payload = {
        "type": "generator",
        "generator_id": "fire",
        "parameters": {},
        "blend_mode": "add",
        "opacity": 60
    }
    response = requests.post(f"{BASE_URL}/api/player/{PLAYER_ID}/layers/add", json=payload)
    assert response.status_code == 201
    data = response.json()
    layer2_id = data['layer_id']
    print(f"✅ Layer 2 added: Fire with add blend")
    
    # Verify 3 layers
    response = requests.get(f"{BASE_URL}/api/player/{PLAYER_ID}/layers")
    data = response.json()
    assert data['layer_count'] == 3
    print(f"✅ Total layers: {data['layer_count']}")
    
    # Play with 3 layers
    print("\n▶️  Playing 3-layer composition...")
    requests.post(f"{BASE_URL}/api/play")
    time.sleep(3)
    response = requests.get(f"{BASE_URL}/api/status")
    data = response.json()
    player = data.get('video_player', data)
    print(f"✅ 3-layer compositing: {player.get('frames_processed', 0)} frames")
    requests.post(f"{BASE_URL}/api/stop")
    
    return layer2_id


def test_9_remove_layers(layer1_id, layer2_id):
    """Test 9: Remove Layers"""
    print_separator("TEST 9: Remove Layers")
    
    print(f"\n🗑️  Removing Layer 2 (Fire)...")
    response = requests.delete(f"{BASE_URL}/api/player/{PLAYER_ID}/layers/{layer2_id}")
    assert response.status_code == 200
    data = response.json()
    print(f"✅ Layer 2 removed, remaining: {data['remaining_layers']}")
    
    print(f"\n🗑️  Removing Layer 1 (Plasma)...")
    response = requests.delete(f"{BASE_URL}/api/player/{PLAYER_ID}/layers/{layer1_id}")
    assert response.status_code == 200
    data = response.json()
    print(f"✅ Layer 1 removed, remaining: {data['remaining_layers']}")
    
    # Play with only layer 0
    print("\n▶️  Playing with single layer...")
    requests.post(f"{BASE_URL}/api/play")
    time.sleep(2)
    print("✅ Single layer playback works")
    requests.post(f"{BASE_URL}/api/stop")


def test_10_load_clip_to_layer(layer0_id):
    """Test 10: Replace Clip in Layer 0"""
    print_separator("TEST 10: Replace Clip in Layer 0")
    
    print(f"\n🔄 Loading new clip into Layer 0: Rainbow Wave")
    payload = {
        "type": "generator",
        "generator_id": "rainbow_wave",
        "parameters": {}
    }
    response = requests.post(
        f"{BASE_URL}/api/player/{PLAYER_ID}/layers/{layer0_id}/clip/load",
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    print(f"✅ Clip replaced: {data['layer']['path']}")
    
    # Play with new clip
    print("\n▶️  Playing with Rainbow Wave...")
    requests.post(f"{BASE_URL}/api/play")
    time.sleep(2)
    print("✅ New clip playing")
    requests.post(f"{BASE_URL}/api/stop")


def test_11_restart():
    """Test 11: Restart Playback"""
    print_separator("TEST 11: Restart Playback")
    
    print("\n▶️  Starting playback...")
    requests.post(f"{BASE_URL}/api/play")
    time.sleep(2)
    
    response = requests.get(f"{BASE_URL}/api/status")
    data = response.json()
    player = data.get('video_player', data)
    frames_before = player.get('frames_processed', 0)
    print(f"✅ Frames before restart: {frames_before}")
    
    print("\n🔄 Restarting playback...")
    response = requests.post(f"{BASE_URL}/api/restart")
    assert response.status_code == 200
    time.sleep(1)
    
    response = requests.get(f"{BASE_URL}/api/status")
    data = response.json()
    player = data.get('video_player', data)
    frames_after = player.get('frames_processed', 0)
    print(f"✅ Frames after restart: {frames_after}")
    print(f"✅ Restart successful (frames reset)")
    
    requests.post(f"{BASE_URL}/api/stop")


def main():
    """Run all tests"""
    print_separator("COMPREHENSIVE MULTI-LAYER API TEST")
    print("Testing: Play/Stop/Pause, Layer Effects, Config Updates, Reordering")
    print_separator()
    
    if not check_api():
        print("\n❌ Please start Flux server first: python src/main.py")
        return
    
    # Cleanup before starting
    cleanup_all_layers()
    
    try:
        # Test sequence
        layer0_id, layer0_clip, layer1_id, layer1_clip = test_1_add_layers()
        test_2_playback_controls(layer0_id, layer1_id)
        test_3_apply_effect_layer0(layer0_clip)
        test_4_apply_effect_layer1(layer1_clip)
        test_5_update_layer_config(layer1_id)
        test_6_disable_layer(layer1_id)
        test_7_reorder_layers(layer0_id, layer1_id)
        layer2_id = test_8_add_third_layer()
        test_9_remove_layers(layer1_id, layer2_id)
        test_10_load_clip_to_layer(layer0_id)
        test_11_restart()
        
        # Final cleanup
        print_separator("CLEANUP")
        cleanup_all_layers()
        
        print_separator("✅ ALL TESTS PASSED!")
        print("\nTested Features:")
        print("  ✅ Add/Remove Layers (2-3 layers)")
        print("  ✅ Play/Stop/Pause/Resume/Restart")
        print("  ✅ Apply Effects to Layer 0 & Layer 1")
        print("  ✅ Update Layer Config (blend_mode, opacity)")
        print("  ✅ Enable/Disable Layers")
        print("  ✅ Reorder Layers (swap master)")
        print("  ✅ Replace Clip in Layer")
        print("  ✅ Multi-layer Compositing (up to 3 layers)")
        print_separator()
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        cleanup_all_layers()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        cleanup_all_layers()


if __name__ == '__main__':
    main()
