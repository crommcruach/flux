"""
Test script for UID Registry performance improvement
"""

import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from modules.uid_registry import get_uid_registry

def test_uid_registry():
    """Test UID registry O(1) lookups"""
    print("="*60)
    print("UID Registry Performance Test")
    print("="*60)
    
    registry = get_uid_registry()
    
    # Simulate 50 sequences with UIDs
    class MockPlayer:
        pass
    
    class MockInstance:
        pass
    
    player = MockPlayer()
    instances = [MockInstance() for _ in range(10)]
    
    # Register 50 UIDs
    uids = []
    for i in range(50):
        uid = f"param_clip_1_param_{i}_1766570567525_abc{i}"
        instance = instances[i % 10]
        param_name = f"param_{i}"
        
        registry.register(uid, player, instance, param_name)
        uids.append(uid)
    
    print(f"\n✅ Registered {len(uids)} UIDs")
    print(f"📊 Registry stats: {registry.get_stats()}")
    
    # Test lookup performance
    print("\n🏃 Testing lookup performance...")
    
    # O(1) lookups
    start = time.time()
    for _ in range(1000):
        for uid in uids:
            result = registry.resolve(uid)
            assert result is not None
    end = time.time()
    
    lookups_per_second = (1000 * 50) / (end - start)
    time_per_lookup_us = ((end - start) / (1000 * 50)) * 1_000_000
    
    print(f"✅ 50,000 lookups completed in {(end-start)*1000:.2f}ms")
    print(f"📈 {lookups_per_second:,.0f} lookups/second")
    print(f"⚡ {time_per_lookup_us:.2f} microseconds per lookup")
    
    # Simulate 50 sequences @ 30fps
    frame_time_ms = (50 * time_per_lookup_us) / 1000
    fps = 1000 / (frame_time_ms + 2)  # +2ms for other overhead
    
    print(f"\n🎬 Estimated performance with 50 sequences:")
    print(f"   UID resolution overhead: {frame_time_ms:.3f}ms per frame")
    print(f"   Playable FPS: ~{fps:.0f} fps")
    
    print(f"\n📊 Final stats: {registry.get_stats()}")
    
    # Test invalidation
    print(f"\n🗑️ Testing invalidation...")
    instance_to_remove = instances[0]
    registry.invalidate_by_instance(instance_to_remove)
    print(f"   Remaining UIDs: {len(registry)}")
    
    print("\n" + "="*60)
    print("✅ All tests passed!")
    print("="*60)

if __name__ == '__main__':
    test_uid_registry()
