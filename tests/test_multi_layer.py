"""
Test Multi-Layer Compositing
Testet das neue Layer-System mit Master-Slave Komposition
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import numpy as np
import time
from modules.player import Player
from modules.layer import Layer
from modules.frame_source import GeneratorSource
from modules.logger import get_logger
from modules.plugin_manager import get_plugin_manager

# Setup
logger = get_logger("test_multi_layer")
config = {
    'canvas': {'width': 50, 'height': 50},
    'video': {'frame_wait_delay': 0.1},
    'paths': {'video_dir': 'video', 'plugins': 'src/plugins'}
}

# Initialize plugin manager (plugins are loaded on-demand)
plugin_manager = get_plugin_manager()

def test_layer_creation():
    """Test Layer Class erstellen"""
    print("\n[TEST 1] Layer Creation")
    
    # Erstelle generator source (checkerboard is simple)
    gen_source = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
    gen_source.initialize()
    
    # Erstelle Layer
    layer = Layer(layer_id=1, source=gen_source, blend_mode='normal', opacity=100, clip_id='test-123')
    
    assert layer.layer_id == 1
    assert layer.blend_mode == 'normal'
    assert layer.opacity == 100
    assert layer.enabled == True
    assert layer.clip_id == 'test-123'
    
    print("[OK] Layer created with correct properties")
    
    # Test to_dict serialization
    layer_dict = layer.to_dict()
    assert layer_dict['layer_id'] == 1
    assert layer_dict['blend_mode'] == 'normal'
    assert layer_dict['type'] == 'generator'  # Fixed: Key is 'type' not 'source_type'
    
    print("[OK] Layer serialization works")
    
    layer.cleanup()
    print("[OK] Layer cleanup works\n")

def test_player_layer_management():
    """Test Player Layer Management Methods"""
    print("[TEST 2] Player Layer Management")
    
    # Create dummy frame source
    dummy_source = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
    dummy_source.initialize()
    
    player = Player(frame_source=dummy_source, points_json_path='data/punkte_export.json', 
                    config=config, enable_artnet=False, player_name='test-player')
    
    # Test add_layer
    gen1 = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
    gen1.initialize()
    
    layer_id = player.add_layer(source=gen1, clip_id='clip-1', blend_mode='normal', opacity=100)
    assert layer_id == 0  # Layer counter starts at 0
    assert len(player.layers) == 1
    print("[OK] add_layer() works")
    
    # Test get_layer
    layer = player.get_layer(layer_id)
    assert layer is not None
    assert layer.layer_id == 0
    print("[OK] get_layer() works")
    
    # Test add second layer
    gen2 = GeneratorSource('rainbow_wave', {}, 50, 50, config)
    gen2.initialize()
    layer_id2 = player.add_layer(source=gen2, clip_id='clip-2', blend_mode='multiply', opacity=50)
    assert layer_id2 == 1  # Second layer is ID 1
    assert len(player.layers) == 2
    print("[OK] Second layer added")
    
    # Test update_layer_config
    success = player.update_layer_config(layer_id2, blend_mode='screen', opacity=75, enabled=False)
    assert success == True
    layer2 = player.get_layer(layer_id2)
    assert layer2.blend_mode == 'screen'
    assert layer2.opacity == 75
    assert layer2.enabled == False
    print("[OK] update_layer_config() works")
    
    # Test remove_layer
    success = player.remove_layer(layer_id2)
    assert success == True
    assert len(player.layers) == 1
    assert player.get_layer(layer_id2) is None
    print("[OK] remove_layer() works\n")

def test_backward_compatibility():
    """Test Backward Compatibility Properties"""
    print("[TEST 3] Backward Compatibility")
    
    # Create dummy frame source
    dummy_source = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
    dummy_source.initialize()
    
    player = Player(frame_source=dummy_source, points_json_path='data/punkte_export.json',
                    config=config, enable_artnet=False, player_name='test-player')
    
    # Test legacy source property (no layers yet)
    gen1 = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
    gen1.initialize()
    
    player.source = gen1  # Should set _legacy_source
    assert player.source == gen1
    print("[OK] Legacy source property works (no layers)")
    
    # Add layer - now source should map to layers[0]
    gen2 = GeneratorSource('pulse', {}, 50, 50, config)
    gen2.initialize()
    player.add_layer(source=gen2, clip_id='clip-1')
    
    assert player.source == gen2  # Should return layers[0].source
    print("[OK] source property maps to layers[0]")
    
    # Test current_clip_id property
    assert player.current_clip_id == 'clip-1'
    print("[OK] current_clip_id property maps to layers[0]")
    print("[OK] Backward compatibility complete\n")

def test_helper_methods():
    """Test Helper Methods (apply_layer_effects, get_blend_plugin)"""
    print("[TEST 4] Helper Methods")
    
    # Create dummy frame source
    dummy_source = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
    dummy_source.initialize()
    
    player = Player(frame_source=dummy_source, points_json_path='data/punkte_export.json',
                    config=config, enable_artnet=False, player_name='test-player')
    
    # Test get_blend_plugin
    blend_plugin = player.get_blend_plugin('multiply', 50)
    assert blend_plugin is not None
    assert blend_plugin.blend_mode == 'multiply'
    assert blend_plugin.opacity == 50
    print("[OK] get_blend_plugin() works")
    
    # Test apply_layer_effects (no effects yet)
    gen = GeneratorSource('fire', {}, 50, 50, config)
    gen.initialize()
    layer = Layer(layer_id=1, source=gen, blend_mode='normal', opacity=100, clip_id='test')
    
    test_frame = np.ones((50, 50, 3), dtype=np.uint8) * 128
    result_frame = player.apply_layer_effects(layer, test_frame)
    
    assert result_frame.shape == test_frame.shape
    assert np.array_equal(result_frame, test_frame)  # No effects, should be unchanged
    print("[OK] apply_layer_effects() works (no effects)")
    
    layer.cleanup()
    print("[OK] Helper methods complete\n")

def test_multi_layer_compositing():
    """Test Multi-Layer Compositing in _play_loop (kurzer Test)"""
    print("[TEST 5] Multi-Layer Compositing (Manual)")
    
    # Create dummy frame source
    dummy_source = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
    dummy_source.initialize()
    
    player = Player(frame_source=dummy_source, points_json_path='data/punkte_export.json',
                    config=config, enable_artnet=False, player_name='test-player')
    
    # Layer 0: Checkerboard (Master)
    gen1 = GeneratorSource('checkerboard', {'size': 10}, 50, 50, config)
    gen1.initialize()
    player.add_layer(source=gen1, clip_id='checkerboard', blend_mode='normal', opacity=100)
    
    # Layer 1: Plasma mit Multiply (Slave)
    gen2 = GeneratorSource('plasma', {}, 50, 50, config)
    gen2.initialize()
    player.add_layer(source=gen2, clip_id='plasma', blend_mode='multiply', opacity=100)
    
    print(f"[INFO] Layers: {len(player.layers)}")
    print(f"[INFO] Layer 0: {player.layers[0].get_source_name()} (Master)")
    print(f"[INFO] Layer 1: {player.layers[1].get_source_name()} (Slave, multiply)")
    
    # Simuliere einen Frame-Fetch
    frame1, _ = player.layers[0].source.get_next_frame()
    assert frame1 is not None
    print(f"[OK] Master frame fetched: shape={frame1.shape}")
    
    frame2, _ = player.layers[1].source.get_next_frame()
    assert frame2 is not None
    print(f"[OK] Slave frame fetched: shape={frame2.shape}")
    
    # Test compositing manually
    blend_plugin = player.get_blend_plugin('multiply', 100)
    composited = blend_plugin.process_frame(frame1, overlay=frame2)
    
    assert composited is not None
    assert composited.shape == frame1.shape
    print(f"[OK] Compositing works: shape={composited.shape}")
    
    # Just verify compositing runs without error
    # (Checkerboard * Plasma will give some pattern)
    pixel = composited[25, 25]
    print(f"[INFO] Center pixel after multiply: R={pixel[0]} G={pixel[1]} B={pixel[2]}")
    print("[OK] Multiply blend executed successfully")
    print("[OK] Multi-layer compositing test complete\n")

if __name__ == '__main__':
    print("=" * 60)
    print("MULTI-LAYER SYSTEM TESTS")
    print("=" * 60)
    
    try:
        test_layer_creation()
        test_player_layer_management()
        test_backward_compatibility()
        test_helper_methods()
        test_multi_layer_compositing()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] All tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
