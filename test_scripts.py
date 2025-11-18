"""Test script for ScriptGenerator - Standalone test without dependencies"""
import sys
import os

# Füge src zum Path hinzu
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Test nur ScriptGenerator
print("=" * 60)
print("TEST: ScriptGenerator")
print("=" * 60)

try:
    from modules.script_generator import ScriptGenerator
    
    sg = ScriptGenerator('scripts')
    
    # Liste Scripts
    scripts = sg.list_scripts()
    print(f"\n✓ Gefundene Scripts: {len(scripts)}")
    for s in scripts:
        print(f"  - {s['name']}: {s.get('description', 'keine Beschreibung')}")
    
    # Lade rainbow_wave
    print("\n📥 Lade rainbow_wave.py...")
    if sg.load_script('rainbow_wave.py'):
        print("✓ Script geladen")
        
        # Info
        info = sg.get_info()
        print(f"\nScript-Info:")
        print(f"  Name: {info.get('name')}")
        print(f"  Beschreibung: {info.get('description')}")
        print(f"  Parameter: {list(info.get('parameters', {}).keys())}")
        
        # Generiere Frame
        print("\n🎨 Generiere Test-Frame...")
        frame = sg.generate_frame(100, 100, 30)
        
        if frame is not None:
            print(f"✓ Frame generiert: shape={frame.shape}, dtype={frame.dtype}")
            print(f"  Min: {frame.min()}, Max: {frame.max()}")
            print(f"  Sample Pixel [50,50]: RGB={frame[50,50]}")
        else:
            print("❌ Frame ist None")
    else:
        print("❌ Fehler beim Laden")
    
    print("\n" + "=" * 60)
    print("✅ TEST ABGESCHLOSSEN")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ FEHLER: {e}")
    import traceback
    traceback.print_exc()
