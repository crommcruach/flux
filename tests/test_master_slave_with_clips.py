#!/usr/bin/env python3
"""
Test script for Master/Slave synchronization WITH CLIPS
This test loads actual clips and tests autoplay sync
"""

import requests
import time
import json

API_BASE = "http://localhost:5000"

def print_separator(title=""):
    print("\n" + "="*80)
    if title:
        print(f"  {title}")
        print("="*80)

def get_player_status(player_id):
    """Get player status"""
    response = requests.get(f"{API_BASE}/api/player/{player_id}/status")
    return response.json()

def set_playlist(player_id, files, autoplay=True, loop=True):
    """Set playlist for a player"""
    playlist = [{"path": f, "type": "video"} for f in files]
    response = requests.post(
        f"{API_BASE}/api/player/{player_id}/playlist/set",
        json={"playlist": playlist, "autoplay": autoplay, "loop": loop}
    )
    return response.json()

def set_master(player_id, enabled=True):
    """Set master playlist"""
    response = requests.post(
        f"{API_BASE}/api/player/{player_id}/set_master",
        json={"enabled": enabled}
    )
    return response.json()

def print_player_state(player_id):
    """Print current player state"""
    status = get_player_status(player_id)
    if status.get('success'):
        print(f"📊 [{player_id.upper()}]:")
        print(f"   Clip Index: {status.get('current_clip_index')}")
        print(f"   Playing: {status.get('is_playing')}")
        print(f"   File: {status.get('current_video')}")
        print(f"   Is Master: {status.get('is_master')}")
        print(f"   Master Playlist: {status.get('master_playlist')}")
        return status
    else:
        print(f"❌ Error: {status.get('error')}")
        return None

def main():
    print_separator("🧪 Master/Slave Test WITH CLIPS")
    
    # Step 1: Load clips into both playlists
    print_separator("STEP 1: Load Clips into Both Playlists")
    print("Loading video playlist...")
    result = set_playlist('video', ['testbild.mp4', 'test.mp4'], autoplay=True, loop=True)
    print(f"Video playlist: {result.get('playlist_length')} clips")
    
    print("Loading artnet playlist...")
    result = set_playlist('artnet', ['testbild.mp4', 'test.mp4'], autoplay=True, loop=True)
    print(f"Art-Net playlist: {result.get('playlist_length')} clips")
    
    time.sleep(2)  # Wait for clips to load and start playing
    
    # Step 2: Check both are playing
    print_separator("STEP 2: Verify Both Playing Independently")
    video_status = print_player_state('video')
    artnet_status = print_player_state('artnet')
    
    if not (video_status.get('is_playing') and artnet_status.get('is_playing')):
        print("\n⚠️ WARNING: Players not playing! Starting them...")
        requests.post(f"{API_BASE}/api/player/video/play")
        requests.post(f"{API_BASE}/api/player/artnet/play")
        time.sleep(1)
        video_status = print_player_state('video')
        artnet_status = print_player_state('artnet')
    
    print(f"\n✅ Both playing: Video={video_status.get('is_playing')}, Art-Net={artnet_status.get('is_playing')}")
    
    # Step 3: Enable master on video
    print_separator("STEP 3: Enable Master on VIDEO")
    result = set_master('video', enabled=True)
    print(f"Master result: {json.dumps(result, indent=2)}")
    
    time.sleep(1)
    
    # Step 4: Check initial sync to index 0
    print_separator("STEP 4: Verify Initial Sync to Index 0")
    video_status = print_player_state('video')
    artnet_status = print_player_state('artnet')
    
    video_idx = video_status.get('current_clip_index')
    artnet_idx = artnet_status.get('current_clip_index')
    
    if video_idx == 0 and artnet_idx == 0:
        print(f"\n✅ PASS: Both jumped to index 0")
    else:
        print(f"\n❌ FAIL: Video={video_idx}, Art-Net={artnet_idx} (expected both at 0)")
    
    # Step 5: Wait for master to advance
    print_separator("STEP 5: Wait for Master to Advance to Index 1")
    print("Waiting 6 seconds for clip to finish...")
    
    for i in range(6):
        time.sleep(1)
        print(f"  {i+1}s...", end="", flush=True)
    print()
    
    # Step 6: Check if slave followed
    print_separator("STEP 6: Verify Slave Followed Master")
    video_status = print_player_state('video')
    artnet_status = print_player_state('artnet')
    
    video_idx = video_status.get('current_clip_index')
    artnet_idx = artnet_status.get('current_clip_index')
    master = video_status.get('master_playlist')
    
    print(f"\n📍 Indices: Video={video_idx}, Art-Net={artnet_idx}")
    print(f"📍 Master: {master}")
    
    if master == 'video':
        print("✅ Master still set to 'video'")
    else:
        print(f"❌ FAIL: Master changed to '{master}'!")
    
    if video_idx == artnet_idx:
        print(f"✅ PASS: Both at same index ({video_idx})")
    else:
        print(f"❌ FAIL: Desynchronized! Video={video_idx}, Art-Net={artnet_idx}")
    
    # Step 7: Monitor for 10 seconds to catch auto-toggle
    print_separator("STEP 7: Monitor Master Status for 10s")
    print("Watching for automatic master toggle...")
    
    for i in range(10):
        time.sleep(1)
        status = get_player_status('video')
        master = status.get('master_playlist')
        video_idx = status.get('current_clip_index')
        artnet_status = get_player_status('artnet')
        artnet_idx = artnet_status.get('current_clip_index')
        
        print(f"  {i+1}s: Master={master}, Video={video_idx}, ArtNet={artnet_idx}")
        
        if master != 'video':
            print(f"\n❌ DETECTED: Master changed to '{master}' after {i+1} seconds!")
            break
    else:
        print("\n✅ Master remained stable for 10 seconds")
    
    print_separator("🏁 Test Complete")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted")
    except requests.exceptions.ConnectionError:
        print("\n\n❌ ERROR: Cannot connect to server")
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
