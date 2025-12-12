#!/usr/bin/env python3
"""
Test script for Master/Slave synchronization
Tests the backend API directly without frontend involvement
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

def set_master(player_id, enabled=True):
    """Set master playlist"""
    print_separator(f"Setting master: {player_id} = {enabled}")
    response = requests.post(
        f"{API_BASE}/api/player/{player_id}/set_master",
        json={"enabled": enabled}
    )
    result = response.json()
    print(f"✅ Result: {json.dumps(result, indent=2)}")
    return result

def get_sync_status():
    """Get sync status for all players"""
    response = requests.get(f"{API_BASE}/api/player/sync_status")
    return response.json()

def print_player_state(player_id):
    """Print current player state"""
    status = get_player_status(player_id)
    if status.get('success'):
        print(f"\n📊 [{player_id.upper()}] Status:")
        print(f"   Current Clip Index: {status.get('current_clip_index')}")
        print(f"   Playlist Index: {status.get('playlist_index')}")
        print(f"   Current File: {status.get('current_video')}")
        print(f"   Is Playing: {status.get('is_playing')}")
        print(f"   Autoplay: {status.get('autoplay')}")
        print(f"   Is Master: {status.get('is_master')}")
        print(f"   Master Playlist: {status.get('master_playlist')}")
    else:
        print(f"❌ Error getting {player_id} status: {status.get('error')}")

def wait_and_show_status(seconds=2):
    """Wait and show both players' status"""
    time.sleep(seconds)
    print_player_state('video')
    print_player_state('artnet')

def main():
    print_separator("🧪 Master/Slave Synchronization Test")
    
    # Step 1: Get initial status
    print_separator("STEP 1: Initial Status")
    print_player_state('video')
    print_player_state('artnet')
    
    # Step 2: Get sync status
    print_separator("STEP 2: Sync Status API")
    sync_status = get_sync_status()
    print(f"Sync Status: {json.dumps(sync_status, indent=2)}")
    
    # Step 3: Enable master on video
    print_separator("STEP 3: Enable Master on VIDEO")
    result = set_master('video', enabled=True)
    
    # Step 4: Wait and check if slaves jumped to index 0
    print_separator("STEP 4: Check if Slave Synced to Index 0")
    wait_and_show_status(2)
    
    video_status = get_player_status('video')
    artnet_status = get_player_status('artnet')
    
    if video_status.get('current_clip_index') == 0 and artnet_status.get('current_clip_index') == 0:
        print("\n✅ PASS: Both players at index 0")
    else:
        print(f"\n❌ FAIL: Video at {video_status.get('current_clip_index')}, Art-Net at {artnet_status.get('current_clip_index')}")
    
    # Step 5: Wait for master to advance (clips are ~5 seconds)
    print_separator("STEP 5: Waiting for Master to Advance to Clip 1...")
    print("Waiting 7 seconds for clip to finish...")
    time.sleep(7)
    
    # Step 6: Check if slave followed master
    print_separator("STEP 6: Check if Slave Followed Master")
    wait_and_show_status(1)
    
    video_status = get_player_status('video')
    artnet_status = get_player_status('artnet')
    
    video_index = video_status.get('current_clip_index')
    artnet_index = artnet_status.get('current_clip_index')
    
    if video_index == artnet_index:
        print(f"\n✅ PASS: Both at same index ({video_index})")
    else:
        print(f"\n❌ FAIL: Video at {video_index}, Art-Net at {artnet_index}")
    
    # Step 7: Check if master is still enabled
    print_separator("STEP 7: Verify Master Still Enabled")
    video_status = get_player_status('video')
    artnet_status = get_player_status('artnet')
    
    if video_status.get('master_playlist') == 'video':
        print("\n✅ PASS: Master still set to 'video'")
    else:
        print(f"\n❌ FAIL: Master is now '{video_status.get('master_playlist')}' (should be 'video')")
    
    # Step 8: Disable master
    print_separator("STEP 8: Disable Master")
    result = set_master('video', enabled=False)
    wait_and_show_status(1)
    
    # Step 9: Check if both are autonomous
    print_separator("STEP 9: Verify Both Players Autonomous")
    video_status = get_player_status('video')
    
    if video_status.get('master_playlist') is None:
        print("\n✅ PASS: Master disabled, both players autonomous")
    else:
        print(f"\n❌ FAIL: Master still set to '{video_status.get('master_playlist')}'")
    
    print_separator("🏁 Test Complete")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
    except requests.exceptions.ConnectionError:
        print("\n\n❌ ERROR: Cannot connect to server at http://localhost:5000")
        print("   Make sure the flux server is running!")
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
