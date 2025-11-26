"""Test if routes are registered correctly"""
from flask import Flask
import sys
sys.path.insert(0, 'src')

app = Flask(__name__)

# Mock objects
class MockPlayerManager:
    def get_video_player(self):
        return None

player_manager = MockPlayerManager()
video_dir = "video"
config = {}

# Register routes
from modules.api_videos import register_video_routes
register_video_routes(app, player_manager, video_dir, config)

# Check registered routes
print("\n✓ Registered routes:")
for rule in app.url_map.iter_rules():
    if '/api/video' in rule.rule:
        print(f"  {rule.rule:40} {sorted(rule.methods - {'HEAD', 'OPTIONS'})}")

print(f"\nTotal routes with /api/video: {sum(1 for r in app.url_map.iter_rules() if '/api/video' in r.rule)}")
