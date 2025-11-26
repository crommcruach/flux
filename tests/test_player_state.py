"""Test player state to debug next/previous issue"""
import sys
sys.path.insert(0, 'src')

from flask import Flask
from modules import PlayerManager
from modules.player import Player
from modules.frame_source import VideoSource
import json

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

# Create a test player
video_path = "video/kanal_1/test.mp4"
canvas_width = config['video']['canvas_width']
canvas_height = config['video']['canvas_height']

source = VideoSource(video_path, canvas_width, canvas_height, config)
player = Player(source, "data/punkte_export.json", "127.0.0.1", 0, 30, config, enable_artnet=False, player_name="Test")

print("\n=== Player State ===")
print(f"Player object: {player}")
print(f"Has current_source: {hasattr(player, 'current_source')}")

if hasattr(player, 'current_source'):
    print(f"current_source: {player.current_source}")
    print(f"current_source type: {type(player.current_source)}")
    if player.current_source:
        print(f"Has video_path: {hasattr(player.current_source, 'video_path')}")
        if hasattr(player.current_source, 'video_path'):
            print(f"video_path: {player.current_source.video_path}")

print(f"\nHas source: {hasattr(player, 'source')}")
if hasattr(player, 'source'):
    print(f"source: {player.source}")
    print(f"source type: {type(player.source)}")
    if player.source:
        print(f"Has video_path: {hasattr(player.source, 'video_path')}")
        if hasattr(player.source, 'video_path'):
            print(f"video_path: {player.source.video_path}")
