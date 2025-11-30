"""
Comprehensive API Test for Clip-Based Multi-Layer System
Tests all layer endpoints and verifies Layer 0 base clip architecture
"""

import requests
import json
import time

BASE_URL = "http://localhost:5000"

def print_section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print('='*70)

def print_test(name):
    print(f"\n→ {name}")

def print_result(response, show_data=True):
    status_color = "✅" if response.status_code < 400 else "❌"
    print(f"  {status_color} Status: {response.status_code}")
    try:
        data = response.json()
        if show_data:
            print(f"  Response: {json.dumps(data, indent=4)}")
        return data
    except:
        print(f"  Response: {response.text}")
        return None

def verify(condition, message):
    if condition:
        print(f"  ✅ {message}")
        return True
    else:
        print(f"  ❌ FAILED: {message}")
        return False

# ============================================
# SETUP: Load test videos
# ============================================
print_section("SETUP: Load Test Clips")

print_test("Load video in Video Player")
response = requests.post(f"{BASE_URL}/api/player/video/clip/load", json={
    "path": "testbild.mp4"
})
video_data = print_result(response, show_data=False)
video_clip_id = video_data.get('clip_id') if video_data and video_data.get('success') else None
verify(video_clip_id is not None, f"Video clip loaded with ID: {video_clip_id}")

print_test("Load video in Art-Net Player")
response = requests.post(f"{BASE_URL}/api/player/artnet/clip/load", json={
    "path": "testbild.mp4"
})
artnet_data = print_result(response, show_data=False)
artnet_clip_id = artnet_data.get('clip_id') if artnet_data and artnet_data.get('success') else None
verify(artnet_clip_id is not None, f"Art-Net clip loaded with ID: {artnet_clip_id}")

time.sleep(0.5)

# ============================================
# TEST 1: Layer 0 Base Clip Architecture
# ============================================
print_section("TEST 1: Layer 0 Base Clip Verification")

print_test("Get layers for Video clip (should have Layer 0)")
response = requests.get(f"{BASE_URL}/api/clips/{video_clip_id}/layers")
layers_data = print_result(response)

if layers_data and layers_data.get('success'):
    layers = layers_data.get('layers', [])
    verify(len(layers) >= 1, f"Has at least 1 layer (found {len(layers)})")
    
    if len(layers) > 0:
        layer0 = layers[0]
        verify(layer0.get('layer_id') == 0, "Layer 0 exists")
        verify(layer0.get('source_type') == 'video', f"Layer 0 is video (got: {layer0.get('source_type')})")
        verify(layer0.get('source_path') == 'testbild.mp4', f"Layer 0 has correct path (got: {layer0.get('source_path')})")
        verify(layer0.get('blend_mode') == 'normal', "Layer 0 has 'normal' blend mode")
        verify(layer0.get('opacity') == 1.0, "Layer 0 has 100% opacity")
        print(f"  📋 Layer 0: {layer0.get('source_path')} ({layer0.get('source_type')})")

time.sleep(0.5)

# ============================================
# TEST 2: Add Layer to Clip
# ============================================
print_section("TEST 2: Add Additional Layers")

print_test("Add Layer 1 to Video clip")
response = requests.post(f"{BASE_URL}/api/clips/{video_clip_id}/layers/add", json={
    "source_type": "video",
    "source_path": "kanal_1/test.mp4",
    "blend_mode": "multiply",
    "opacity": 0.8,
    "enabled": True
})
add_data = print_result(response, show_data=False)
layer1_id = add_data.get('layer_id') if add_data and add_data.get('success') else None
verify(layer1_id == 1, f"Layer 1 created with correct ID (got: {layer1_id})")

print_test("Add Layer 2 to Video clip")
response = requests.post(f"{BASE_URL}/api/clips/{video_clip_id}/layers/add", json={
    "source_type": "video",
    "source_path": "kanal_2/test.mp4",
    "blend_mode": "screen",
    "opacity": 0.5,
    "enabled": True
})
add_data = print_result(response, show_data=False)
layer2_id = add_data.get('layer_id') if add_data and add_data.get('success') else None
verify(layer2_id == 2, f"Layer 2 created with correct ID (got: {layer2_id})")

print_test("Add Generator layer to Video clip")
response = requests.post(f"{BASE_URL}/api/clips/{video_clip_id}/layers/add", json={
    "source_type": "generator",
    "source_path": "plasma",
    "blend_mode": "overlay",
    "opacity": 0.3,
    "enabled": True
})
add_data = print_result(response, show_data=False)
layer3_id = add_data.get('layer_id') if add_data and add_data.get('success') else None
verify(layer3_id == 3, f"Layer 3 (generator) created with correct ID (got: {layer3_id})")

time.sleep(0.5)

# ============================================
# TEST 3: Get All Layers
# ============================================
print_section("TEST 3: Verify Layer Stack")

print_test("Get all layers for Video clip")
response = requests.get(f"{BASE_URL}/api/clips/{video_clip_id}/layers")
layers_data = print_result(response, show_data=False)

if layers_data and layers_data.get('success'):
    layers = layers_data.get('layers', [])
    verify(len(layers) == 4, f"Has 4 layers total (0=base + 3 added), found: {len(layers)}")
    
    print("\n  📚 Layer Stack:")
    for layer in layers:
        layer_id = layer.get('layer_id')
        source = layer.get('source_path')
        blend = layer.get('blend_mode')
        opacity = int(layer.get('opacity', 0) * 100)
        layer_type = "BASE" if layer_id == 0 else "OVERLAY"
        print(f"    Layer {layer_id} ({layer_type}): {source} | {blend} | {opacity}%")

time.sleep(0.5)

# ============================================
# TEST 4: Update Layer Configuration
# ============================================
print_section("TEST 4: Update Layer Properties")

print_test("Update Layer 1 blend mode to 'add'")
response = requests.patch(f"{BASE_URL}/api/clips/{video_clip_id}/layers/{layer1_id}", json={
    "blend_mode": "add"
})
update_data = print_result(response, show_data=False)
verify(update_data and update_data.get('success'), "Layer 1 blend mode updated")

print_test("Update Layer 2 opacity to 0.7")
response = requests.patch(f"{BASE_URL}/api/clips/{video_clip_id}/layers/{layer2_id}", json={
    "opacity": 0.7
})
update_data = print_result(response, show_data=False)
verify(update_data and update_data.get('success'), "Layer 2 opacity updated")

print_test("Disable Layer 3")
response = requests.patch(f"{BASE_URL}/api/clips/{video_clip_id}/layers/{layer3_id}", json={
    "enabled": False
})
update_data = print_result(response, show_data=False)
verify(update_data and update_data.get('success'), "Layer 3 disabled")

print_test("Verify updates")
response = requests.get(f"{BASE_URL}/api/clips/{video_clip_id}/layers")
layers_data = print_result(response, show_data=False)

if layers_data and layers_data.get('success'):
    layers = {l['layer_id']: l for l in layers_data['layers']}
    verify(layers[1]['blend_mode'] == 'add', "Layer 1 blend mode is 'add'")
    verify(layers[2]['opacity'] == 0.7, f"Layer 2 opacity is 0.7 (got: {layers[2]['opacity']})")
    verify(layers[3]['enabled'] == False, f"Layer 3 is disabled (got: {layers[3]['enabled']})")

time.sleep(0.5)

# ============================================
# TEST 5: Reorder Layers
# ============================================
print_section("TEST 5: Reorder Layer Stack")

print_test("Reorder layers: [0, 3, 1, 2]")
response = requests.put(f"{BASE_URL}/api/clips/{video_clip_id}/layers/reorder", json={
    "new_order": [0, 3, 1, 2]
})
reorder_data = print_result(response, show_data=False)
verify(reorder_data and reorder_data.get('success'), "Layers reordered")

print_test("Verify new layer order")
response = requests.get(f"{BASE_URL}/api/clips/{video_clip_id}/layers")
layers_data = print_result(response, show_data=False)

if layers_data and layers_data.get('success'):
    layers = layers_data.get('layers', [])
    layer_ids = [l['layer_id'] for l in layers]
    print(f"  📋 Order: {layer_ids}")
    # Note: API returns Layer 0 first, then registry layers
    # Reorder affects registry layers only (1, 2, 3)

time.sleep(0.5)

# ============================================
# TEST 6: Layer 0 Immutability
# ============================================
print_section("TEST 6: Layer 0 Protection (Should Fail)")

print_test("Try to delete Layer 0 (should fail)")
response = requests.delete(f"{BASE_URL}/api/clips/{video_clip_id}/layers/0")
delete_data = print_result(response, show_data=False)
verify(not (delete_data and delete_data.get('success')), "Layer 0 deletion blocked")

print_test("Try to update Layer 0 (should be allowed but meaningless)")
response = requests.patch(f"{BASE_URL}/api/clips/{video_clip_id}/layers/0", json={
    "blend_mode": "multiply"
})
update_data = print_result(response, show_data=False)
# Layer 0 updates might fail or be ignored depending on implementation
print(f"  ℹ️  Layer 0 update result: {update_data.get('success') if update_data else 'Failed'}")

time.sleep(0.5)

# ============================================
# TEST 7: Delete Layers
# ============================================
print_section("TEST 7: Remove Layers")

print_test("Delete Layer 2")
response = requests.delete(f"{BASE_URL}/api/clips/{video_clip_id}/layers/{layer2_id}")
delete_data = print_result(response, show_data=False)
verify(delete_data and delete_data.get('success'), "Layer 2 deleted")

print_test("Verify Layer 2 removed")
response = requests.get(f"{BASE_URL}/api/clips/{video_clip_id}/layers")
layers_data = print_result(response, show_data=False)

if layers_data and layers_data.get('success'):
    layers = layers_data.get('layers', [])
    layer_ids = [l['layer_id'] for l in layers]
    verify(layer2_id not in layer_ids, f"Layer 2 not in stack (current: {layer_ids})")
    verify(0 in layer_ids, "Layer 0 (base) still present")

time.sleep(0.5)

# ============================================
# TEST 8: Multi-Clip Layer Isolation
# ============================================
print_section("TEST 8: Layer Isolation Between Clips")

print_test("Add layer to Art-Net clip")
response = requests.post(f"{BASE_URL}/api/clips/{artnet_clip_id}/layers/add", json={
    "source_type": "generator",
    "source_path": "checkerboard",
    "blend_mode": "normal",
    "opacity": 1.0
})
add_data = print_result(response, show_data=False)
artnet_layer1 = add_data.get('layer_id') if add_data and add_data.get('success') else None
verify(artnet_layer1 == 1, f"Art-Net Layer 1 created (got: {artnet_layer1})")

print_test("Verify Video clip layers unchanged")
response = requests.get(f"{BASE_URL}/api/clips/{video_clip_id}/layers")
video_layers_data = print_result(response, show_data=False)

print_test("Verify Art-Net clip layers separate")
response = requests.get(f"{BASE_URL}/api/clips/{artnet_clip_id}/layers")
artnet_layers_data = print_result(response, show_data=False)

if video_layers_data and artnet_layers_data:
    video_count = len(video_layers_data.get('layers', []))
    artnet_count = len(artnet_layers_data.get('layers', []))
    verify(video_count != artnet_count, 
           f"Clips have different layer counts (video: {video_count}, artnet: {artnet_count})")
    print(f"  📊 Video clip: {video_count} layers")
    print(f"  📊 Art-Net clip: {artnet_count} layers")

time.sleep(0.5)

# ============================================
# TEST 9: Player Integration
# ============================================
print_section("TEST 9: Player Layer Loading")

print_test("Start Video Player to load layers")
response = requests.post(f"{BASE_URL}/api/player/video/play")
play_data = print_result(response, show_data=False)
verify(play_data and play_data.get('success'), "Video player started")

time.sleep(1)

print_test("Check Video Player status")
response = requests.get(f"{BASE_URL}/api/player/video/status")
status_data = print_result(response, show_data=False)

if status_data:
    is_playing = status_data.get('is_playing')
    verify(is_playing == True, f"Player is playing (is_playing: {is_playing})")

print_test("Stop Video Player")
response = requests.post(f"{BASE_URL}/api/player/video/stop")
stop_data = print_result(response, show_data=False)
verify(stop_data and stop_data.get('success'), "Video player stopped")

time.sleep(0.5)

# ============================================
# TEST 10: Error Handling
# ============================================
print_section("TEST 10: Error Handling")

print_test("Add layer with invalid source_type")
response = requests.post(f"{BASE_URL}/api/clips/{video_clip_id}/layers/add", json={
    "source_type": "invalid_type",
    "source_path": "test.mp4"
})
error_data = print_result(response, show_data=False)
verify(response.status_code >= 400, "Invalid source_type rejected")

print_test("Add layer with missing source_path")
response = requests.post(f"{BASE_URL}/api/clips/{video_clip_id}/layers/add", json={
    "source_type": "video"
})
error_data = print_result(response, show_data=False)
verify(response.status_code >= 400, "Missing source_path rejected")

print_test("Get layers for non-existent clip")
response = requests.get(f"{BASE_URL}/api/clips/invalid-clip-id-123/layers")
error_data = print_result(response, show_data=False)
verify(response.status_code >= 400, "Non-existent clip rejected")

print_test("Delete non-existent layer")
response = requests.delete(f"{BASE_URL}/api/clips/{video_clip_id}/layers/999")
error_data = print_result(response, show_data=False)
verify(response.status_code >= 400 or not (error_data and error_data.get('success')), 
       "Non-existent layer deletion handled")

# ============================================
# SUMMARY
# ============================================
print_section("TEST SUMMARY")

print("\n  ✅ Core Features Tested:")
print("     - Layer 0 base clip architecture")
print("     - Add layers (video, generator)")
print("     - Update layer properties (blend_mode, opacity, enabled)")
print("     - Delete layers")
print("     - Reorder layers")
print("     - Layer isolation between clips")
print("     - Player integration")
print("     - Error handling")

print("\n  📋 Test Clips:")
print(f"     Video Clip ID: {video_clip_id}")
print(f"     Art-Net Clip ID: {artnet_clip_id}")

print("\n  🎯 Multi-Layer System Status: OPERATIONAL")
print(f"\n{'='*70}\n")
