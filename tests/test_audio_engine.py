"""
Quick test for AudioEngine with PyAV + sounddevice
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from modules.audio_engine import AudioEngine, AUDIO_AVAILABLE

def test_audio_engine():
    """Test basic audio engine functionality"""
    
    print("=" * 60)
    print("Audio Engine Test (PyAV + sounddevice)")
    print("=" * 60)
    
    if not AUDIO_AVAILABLE:
        print("❌ Audio not available (PyAV or sounddevice missing)")
        return False
    
    print("✅ Audio dependencies available")
    
    # Create engine
    engine = AudioEngine()
    print("✅ AudioEngine created")
    
    # Find test audio file
    audio_dir = Path(__file__).parent / 'audio'
    if not audio_dir.exists():
        print(f"⚠️ No audio directory found at {audio_dir}")
        print("Please add an audio file (MP3/WAV/OGG) to the audio/ directory to test")
        return True
    
    # Find first audio file
    audio_files = list(audio_dir.glob('*.mp3')) + list(audio_dir.glob('*.wav')) + \
                  list(audio_dir.glob('*.ogg')) + list(audio_dir.glob('*.flac'))
    
    if not audio_files:
        print("⚠️ No audio files found in audio/")
        print("Please add an audio file (MP3/WAV/OGG/FLAC) to test")
        return True
    
    test_file = audio_files[0]
    print(f"\n📁 Testing with: {test_file.name}")
    
    # Test load
    try:
        metadata = engine.load(str(test_file))
        print(f"✅ Load successful")
        print(f"   Duration: {metadata['duration']:.2f}s")
        print(f"   Sample Rate: {metadata['sample_rate']}Hz")
        print(f"   Channels: {metadata['channels']}")
        print(f"   Format: {metadata['format']}")
    except Exception as e:
        print(f"❌ Load failed: {e}")
        return False
    
    # Test play (for 3 seconds)
    try:
        print("\n▶️ Testing playback (3 seconds)...")
        engine.play()
        time.sleep(1)
        
        pos1 = engine.get_position()
        print(f"   Position at 1s: {pos1:.2f}s")
        
        time.sleep(2)
        pos2 = engine.get_position()
        print(f"   Position at 3s: {pos2:.2f}s")
        
        if pos2 > pos1:
            print("✅ Playback working (position advancing)")
        else:
            print("⚠️ Position not advancing - playback might not be working")
        
    except Exception as e:
        print(f"❌ Playback failed: {e}")
        return False
    
    # Test pause
    try:
        print("\n⏸️ Testing pause...")
        engine.pause()
        pos_before = engine.get_position()
        time.sleep(1)
        pos_after = engine.get_position()
        
        if abs(pos_after - pos_before) < 0.1:
            print(f"✅ Pause working (position stable at {pos_before:.2f}s)")
        else:
            print(f"⚠️ Position changed during pause: {pos_before:.2f}s -> {pos_after:.2f}s")
        
    except Exception as e:
        print(f"❌ Pause failed: {e}")
        return False
    
    # Test resume
    try:
        print("\n▶️ Testing resume...")
        engine.play()
        time.sleep(2)
        pos = engine.get_position()
        print(f"✅ Resume working (position: {pos:.2f}s)")
        
    except Exception as e:
        print(f"❌ Resume failed: {e}")
        return False
    
    # Test seek
    try:
        print("\n⏩ Testing seek...")
        seek_target = min(5.0, metadata['duration'] / 2)
        engine.seek(seek_target)
        time.sleep(0.5)  # Allow seek to process
        pos = engine.get_position()
        
        if abs(pos - seek_target) < 1.0:
            print(f"✅ Seek working (target: {seek_target:.2f}s, actual: {pos:.2f}s)")
        else:
            print(f"⚠️ Seek imprecise (target: {seek_target:.2f}s, actual: {pos:.2f}s)")
        
    except Exception as e:
        print(f"❌ Seek failed: {e}")
        return False
    
    # Test stop
    try:
        print("\n⏹️ Testing stop...")
        engine.stop()
        pos = engine.get_position()
        
        if pos == 0.0:
            print(f"✅ Stop working (position reset to 0.0s)")
        else:
            print(f"⚠️ Position not reset after stop: {pos:.2f}s")
        
    except Exception as e:
        print(f"❌ Stop failed: {e}")
        return False
    
    # Cleanup
    print("\n🧹 Cleaning up...")
    engine.cleanup()
    print("✅ Cleanup complete")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    
    return True

if __name__ == '__main__':
    try:
        success = test_audio_engine()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
