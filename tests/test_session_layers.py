"""
Session State Test für Multi-Layer System
Testet Save/Load/Migration von Layer-Stack
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import json
import tempfile
from modules.session_state import SessionStateManager
from modules.player import Player
from modules.player_manager import PlayerManager
from modules.clip_registry import ClipRegistry
from modules.frame_source import GeneratorSource
from modules.logger import get_logger
from modules.plugin_manager import get_plugin_manager

# Setup
logger = get_logger("test_session_layers")
config = {
    'canvas': {'width': 50, 'height': 50},
    'video': {'frame_wait_delay': 0.1},
    'paths': {'video_dir': 'video', 'plugins': 'src/plugins'}
}

# Initialize plugin manager
plugin_manager = get_plugin_manager()


def test_save_with_layers():
    """Test 1: Speichere Player mit 2 Layern"""
    print("\n[TEST 1] Save Session State with 2 Layers")
    
    # Erstelle temporäre Session-Datei
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    temp_path = temp_file.name
    temp_file.close()
    
    try:
        # Setup Player
        dummy_source = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
        dummy_source.initialize()
        
        player = Player(
            frame_source=dummy_source,
            points_json_path='data/punkte_export.json',
            config=config,
            enable_artnet=False,
            player_name='video'
        )
        
        # Füge 2 Layer hinzu
        gen1 = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
        gen1.initialize()
        player.add_layer(source=gen1, clip_id='clip-1', blend_mode='normal', opacity=100)
        
        gen2 = GeneratorSource('plasma', {'speed': 0.5}, 50, 50, config)
        gen2.initialize()
        player.add_layer(source=gen2, clip_id='clip-2', blend_mode='multiply', opacity=75)
        
        print(f"[INFO] Player has {len(player.layers)} layers")
        
        # Setup PlayerManager und ClipRegistry
        class DummyPlayerManager:
            def __init__(self, p):
                self.player = p
            def get_player(self, pid):
                return self.player if pid == 'video' else None
        
        player_manager = DummyPlayerManager(player)
        clip_registry = ClipRegistry()
        
        # Speichere Session State
        session_state = SessionStateManager(temp_path)
        success = session_state.save(player_manager, clip_registry, force=True)
        
        assert success == True, "Save failed"
        print("[OK] Session State saved")
        
        # Lade gespeicherte Datei und prüfe Inhalt
        with open(temp_path, 'r') as f:
            saved_data = json.load(f)
        
        assert 'players' in saved_data
        assert 'video' in saved_data['players']
        
        video_state = saved_data['players']['video']
        assert 'layers' in video_state
        assert len(video_state['layers']) == 2
        print(f"[OK] Saved state has {len(video_state['layers'])} layers")
        
        # Prüfe Layer 0
        layer0 = video_state['layers'][0]
        assert layer0['layer_id'] == 0
        assert layer0['blend_mode'] == 'normal'
        assert layer0['opacity'] == 100
        assert layer0['type'] == 'generator'
        assert layer0['generator_id'] == 'checkerboard'
        print(f"[OK] Layer 0: {layer0['generator_id']}, {layer0['blend_mode']}, {layer0['opacity']}%")
        
        # Prüfe Layer 1
        layer1 = video_state['layers'][1]
        assert layer1['layer_id'] == 1
        assert layer1['blend_mode'] == 'multiply'
        assert layer1['opacity'] == 75
        assert layer1['type'] == 'generator'
        assert layer1['generator_id'] == 'plasma'
        print(f"[OK] Layer 1: {layer1['generator_id']}, {layer1['blend_mode']}, {layer1['opacity']}%")
        
        return temp_path, saved_data
        
    except Exception as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise e


def test_restore_with_layers(temp_path):
    """Test 2: Restauriere Player mit Layern aus Session State"""
    print("\n[TEST 2] Restore Session State with Layers")
    
    try:
        # Erstelle neuen Player (leer)
        dummy_source = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
        dummy_source.initialize()
        
        player = Player(
            frame_source=dummy_source,
            points_json_path='data/punkte_export.json',
            config=config,
            enable_artnet=False,
            player_name='video'
        )
        
        print(f"[INFO] New player has {len(player.layers)} layers (should be 0)")
        assert len(player.layers) == 0
        
        # Setup PlayerManager
        class DummyPlayerManager:
            def __init__(self, p):
                self.player = p
            def get_player(self, pid):
                return self.player if pid == 'video' else None
        
        player_manager = DummyPlayerManager(player)
        clip_registry = ClipRegistry()
        
        # Restauriere Session State
        session_state = SessionStateManager(temp_path)
        success = session_state.restore(player_manager, clip_registry, config)
        
        assert success == True, "Restore failed"
        print("[OK] Session State restored")
        
        # Prüfe restaurierte Layer
        assert len(player.layers) == 2, f"Expected 2 layers, got {len(player.layers)}"
        print(f"[OK] Player has {len(player.layers)} layers after restore")
        
        # Prüfe Layer 0
        layer0 = player.layers[0]
        assert layer0.blend_mode == 'normal'
        assert layer0.opacity == 100
        assert layer0.clip_id == 'clip-1'
        print(f"[OK] Layer 0: blend={layer0.blend_mode}, opacity={layer0.opacity}%, clip={layer0.clip_id}")
        
        # Prüfe Layer 1
        layer1 = player.layers[1]
        assert layer1.blend_mode == 'multiply'
        assert layer1.opacity == 75
        assert layer1.clip_id == 'clip-2'
        print(f"[OK] Layer 1: blend={layer1.blend_mode}, opacity={layer1.opacity}%, clip={layer1.clip_id}")
        
        # Prüfe dass Sources funktionieren
        frame0, _ = layer0.source.get_next_frame()
        assert frame0 is not None
        print(f"[OK] Layer 0 source works: frame shape={frame0.shape}")
        
        frame1, _ = layer1.source.get_next_frame()
        assert frame1 is not None
        print(f"[OK] Layer 1 source works: frame shape={frame1.shape}")
        
        print("[OK] Restore complete and functional\n")
        
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_migration_old_format():
    """Test 3: Migration von altem Format (ohne layers) zu neuem Format"""
    print("\n[TEST 3] Migration: Old Format (playlist) -> New Format (layers)")
    
    # Erstelle temporäre Session-Datei mit ALTEM Format
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    temp_path = temp_file.name
    temp_file.close()  # Close before writing to avoid lock
    
    # Schreibe altes Format (ohne layers field)
    old_format = {
        "last_updated": "2025-11-30T12:00:00",
        "players": {
            "video": {
                "playlist": [
                    {
                        "path": "generator:fire",
                        "type": "generator",
                        "generator_id": "fire",
                        "parameters": {"intensity": 0.8},
                        "id": "old-clip-1",
                        "effects": []
                    }
                ],
                "current_index": 0,
                "autoplay": True,
                "loop": False,
                "global_effects": []
                # KEIN "layers" field! (altes Format)
            }
        }
    }
    
    with open(temp_path, 'w') as f:
        json.dump(old_format, f, indent=2)
    
    print("[INFO] Created old format session state (without layers)")
    
    try:
        # Erstelle Player (leer)
        dummy_source = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
        dummy_source.initialize()
        
        player = Player(
            frame_source=dummy_source,
            points_json_path='data/punkte_export.json',
            config=config,
            enable_artnet=False,
            player_name='video'
        )
        
        # Setup PlayerManager
        class DummyPlayerManager:
            def __init__(self, p):
                self.player = p
            def get_player(self, pid):
                return self.player if pid == 'video' else None
        
        player_manager = DummyPlayerManager(player)
        clip_registry = ClipRegistry()
        
        # Restauriere (sollte Migration durchführen)
        session_state = SessionStateManager(temp_path)
        success = session_state.restore(player_manager, clip_registry, config)
        
        assert success == True, "Restore/Migration failed"
        print("[OK] Migration executed")
        
        # Prüfe dass Layer erstellt wurde
        assert len(player.layers) == 1, f"Expected 1 layer after migration, got {len(player.layers)}"
        print(f"[OK] Migration created {len(player.layers)} layer from playlist")
        
        # Prüfe Layer 0 (konvertiert aus playlist item 0)
        layer0 = player.layers[0]
        assert layer0.blend_mode == 'normal'  # Default für Migration
        assert layer0.opacity == 100.0  # Default für Migration
        assert layer0.clip_id == 'old-clip-1'
        print(f"[OK] Layer 0 migrated: clip={layer0.clip_id}, blend={layer0.blend_mode}")
        
        # Prüfe dass Source Fire Generator ist
        assert hasattr(layer0.source, 'generator_id')
        assert layer0.source.generator_id == 'fire'
        print(f"[OK] Layer 0 source is Fire generator")
        
        # Prüfe dass autoplay übernommen wurde
        assert player.autoplay == True
        print(f"[OK] Autoplay setting preserved: {player.autoplay}")
        
        print("[OK] Migration successful\n")
        
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_save_and_restore_cycle():
    """Test 4: Vollständiger Save -> Restore Cycle"""
    print("\n[TEST 4] Full Save-Restore Cycle")
    
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    temp_path = temp_file.name
    temp_file.close()
    
    try:
        # ========== SAVE ==========
        # Setup Player mit 3 Layern
        dummy_source = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
        dummy_source.initialize()
        
        player1 = Player(
            frame_source=dummy_source,
            points_json_path='data/punkte_export.json',
            config=config,
            enable_artnet=False,
            player_name='video'
        )
        
        # Layer 0: Checkerboard (normal, 100%)
        gen1 = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
        gen1.initialize()
        player1.add_layer(source=gen1, clip_id='cycle-1', blend_mode='normal', opacity=100)
        
        # Layer 1: Plasma (multiply, 50%)
        gen2 = GeneratorSource('plasma', {}, 50, 50, config)
        gen2.initialize()
        player1.add_layer(source=gen2, clip_id='cycle-2', blend_mode='multiply', opacity=50)
        
        # Layer 2: Fire (add, 80%)
        gen3 = GeneratorSource('fire', {}, 50, 50, config)
        gen3.initialize()
        player1.add_layer(source=gen3, clip_id='cycle-3', blend_mode='add', opacity=80)
        
        print(f"[INFO] Player 1 has {len(player1.layers)} layers")
        
        # Save
        class DummyPlayerManager:
            def __init__(self, p):
                self.player = p
            def get_player(self, pid):
                return self.player if pid == 'video' else None
        
        pm1 = DummyPlayerManager(player1)
        clip_registry = ClipRegistry()
        
        session_state = SessionStateManager(temp_path)
        success = session_state.save(pm1, clip_registry, force=True)
        assert success == True
        print("[OK] Saved 3 layers")
        
        # ========== RESTORE ==========
        # Erstelle neuen Player (leer)
        dummy_source2 = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
        dummy_source2.initialize()
        
        player2 = Player(
            frame_source=dummy_source2,
            points_json_path='data/punkte_export.json',
            config=config,
            enable_artnet=False,
            player_name='video'
        )
        
        pm2 = DummyPlayerManager(player2)
        
        # Restore
        session_state2 = SessionStateManager(temp_path)
        success = session_state2.restore(pm2, clip_registry, config)
        assert success == True
        print("[OK] Restored to new player")
        
        # ========== VERIFY ==========
        assert len(player2.layers) == 3, f"Expected 3 layers, got {len(player2.layers)}"
        print(f"[OK] Player 2 has {len(player2.layers)} layers")
        
        # Verify Layer 0
        assert player2.layers[0].blend_mode == 'normal'
        assert player2.layers[0].opacity == 100
        assert player2.layers[0].clip_id == 'cycle-1'
        
        # Verify Layer 1
        assert player2.layers[1].blend_mode == 'multiply'
        assert player2.layers[1].opacity == 50
        assert player2.layers[1].clip_id == 'cycle-2'
        
        # Verify Layer 2
        assert player2.layers[2].blend_mode == 'add'
        assert player2.layers[2].opacity == 80
        assert player2.layers[2].clip_id == 'cycle-3'
        
        print("[OK] All 3 layers verified identical")
        print("[OK] Full cycle successful\n")
        
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


if __name__ == '__main__':
    print("=" * 80)
    print("SESSION STATE TESTS - MULTI-LAYER")
    print("=" * 80)
    
    try:
        temp_path, saved_data = test_save_with_layers()
        test_restore_with_layers(temp_path)
        test_migration_old_format()
        test_save_and_restore_cycle()
        
        print("\n" + "=" * 80)
        print("[SUCCESS] All Session State tests passed!")
        print("=" * 80)
        
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
