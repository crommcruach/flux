# 🧪 Dynamic Parameter Sequences - Testing & Installation Guide

## 📦 Installation

### 1. Install Python Dependencies

The feature requires `sounddevice` for audio capture:

```bash
pip install sounddevice>=0.4.0
```

**Or install from requirements.txt:**

```bash
pip install -r requirements.txt
```

### 2. Verify Installation

Check if sounddevice is installed:

```bash
python -c "import sounddevice; print('✅ sounddevice installed:', sounddevice.__version__)"
```

Expected output:
```
✅ sounddevice installed: 0.4.6
```

### 3. List Available Audio Devices

Run this to see available audio input devices:

```bash
python -c "import sounddevice as sd; print(sd.query_devices())"
```

### 4. Configure Audio Source

Edit `config.json` to select audio source:

```json
{
  "audio_source": "loopback"
}
```

**Options**:
- `"mic"` - Default microphone
- `"line-in"` - Line input (if available)
- `"loopback"` - System audio (requires virtual audio cable on Windows)

---

## 🖥️ Platform-Specific Setup

### Windows

#### System Audio Capture (Loopback)

**Option 1: VB-Audio Virtual Cable (Recommended)**

1. Download [VB-Audio Virtual Cable](https://vb-audio.com/Cable/)
2. Install the driver
3. Set VB-Cable as default playback device in Windows Sound settings
4. In `config.json`, set `"audio_source": "loopback"`
5. Restart the application

**Option 2: Stereo Mix (Built-in)**

1. Right-click speaker icon → Sounds → Recording tab
2. Right-click empty area → Show Disabled Devices
3. Enable "Stereo Mix" if available
4. Set as default recording device
5. In `config.json`, set `"audio_source": "loopback"`

### macOS

#### System Audio Capture

1. Install [BlackHole](https://github.com/ExistentialAudio/BlackHole)
   ```bash
   brew install blackhole-2ch
   ```
2. Create Multi-Output Device in Audio MIDI Setup:
   - Open Audio MIDI Setup (Applications → Utilities)
   - Click **+** → Create Multi-Output Device
   - Check BlackHole and Built-in Output
   - Right-click → Use This Device For Sound Output
3. In `config.json`, set `"audio_source": "loopback"`
4. Restart the application

### Linux

#### System Audio Capture

**PulseAudio**:
```bash
pactl load-module module-loopback
```

**PipeWire**:
```bash
pw-loopback
```

**ALSA**: Configure `.asoundrc` with loopback device

---

## 🧪 Testing Checklist

### Backend Tests

#### 1. Test Audio Analyzer

```bash
python -c "
from src.modules.sequences.audio_analyzer import AudioAnalyzer
import time

config = {'audio_source': 'loopback'}
analyzer = AudioAnalyzer(config)

print('Starting analyzer...')
analyzer.start()

for i in range(5):
    time.sleep(1)
    features = analyzer.get_features()
    print(f'RMS: {features.get(\"rms\", 0):.3f}, Bass: {features.get(\"bass\", 0):.3f}')

analyzer.stop()
print('✅ Test complete')
"
```

**Expected Output** (with audio playing):
```
Starting analyzer...
RMS: 0.123, Bass: 0.456
RMS: 0.234, Bass: 0.567
...
✅ Test complete
```

#### 2. Test Sequence Manager

```bash
python -c "
from src.modules.sequences import SequenceManager, AudioSequence, LFOSequence

config = {}
manager = SequenceManager(config, None)

# Create audio sequence
seq = AudioSequence('test_param', 'bass', 0, 100, 0.1)
manager.add_sequence(seq)

# Update and get value
manager.update_all(0.016, None)
value = seq.get_value()
print(f'✅ Audio sequence value: {value}')

# Create LFO sequence
lfo = LFOSequence('test_param2', 'sine', 1.0, 1.0, 0.0, 0, 100)
manager.add_sequence(lfo)

manager.update_all(0.016, None)
value = lfo.get_value()
print(f'✅ LFO sequence value: {value}')
"
```

#### 3. Test API Endpoints

Start the Flask server:
```bash
python src/main.py
```

In another terminal:
```bash
# List sequences
curl http://localhost:5000/api/sequences

# Create audio sequence
curl -X POST http://localhost:5000/api/sequences \
  -H "Content-Type: application/json" \
  -d '{
    "type": "audio",
    "parameter_id": "clip.effects[0].parameters.intensity",
    "audio_feature": "bass",
    "min_value": 0,
    "max_value": 100,
    "smoothing": 0.15
  }'

# Start audio analyzer
curl -X POST http://localhost:5000/api/sequences/audio/start

# Check audio status
curl http://localhost:5000/api/sequences/audio/status

# Get audio features
curl http://localhost:5000/api/sequences/audio/features

# Stop audio analyzer
curl -X POST http://localhost:5000/api/sequences/audio/stop
```

---

### Frontend Tests

#### 1. Open Application

1. Start Flask server: `python src/main.py`
2. Open browser: `http://localhost:5000/player.html`
3. Open browser console (F12)

#### 2. Test Modal Opening

1. Navigate to **Clip Effects** panel
2. Select a video clip
3. Add an effect (e.g., Color Shift)
4. Expand the effect
5. Look for **⚙️** button next to any parameter (e.g., Intensity)
6. Click the **⚙️** button
7. **Expected**: Sequence editor modal opens

**Console Check**:
```javascript
// Should see:
✅ Sequence Manager initialized
```

#### 3. Test Audio Sequence

1. In modal, ensure **🎵 Audio Reactive** is selected
2. Click **Start** button
3. **Expected**: 
   - Status indicator turns green and pulses
   - Status text shows "Audio analyzer running"
   - Audio spectrum canvas displays live bars

**Console Check**:
```javascript
// Should see:
✅ Audio analyzer started
```

4. Select different audio features (RMS, Bass, Mid, etc.)
5. **Expected**: Spectrum bars move in real-time with audio
6. Adjust **Smoothing** slider
7. **Expected**: Bar motion becomes smoother
8. Click **Save Sequence**
9. **Expected**: Toast notification "Sequence saved successfully"

#### 4. Test LFO Sequence

1. Click **🌊 LFO** button
2. Select waveform (e.g., Sine)
3. Adjust **Frequency** slider
4. **Expected**: LFO preview canvas updates with new frequency
5. Change waveform to **Square**, **Triangle**, etc.
6. **Expected**: Canvas shows corresponding waveform shape
7. Adjust **Amplitude** and **Phase**
8. **Expected**: Preview reflects changes
9. Click **Save Sequence**
10. **Expected**: Toast notification "Sequence saved successfully"

#### 5. Test Timeline Sequence

1. Click **📈 Timeline** button
2. Enter keyframe: Time: 0, Value: 0
3. Click **➕ Add Keyframe**
4. **Expected**: Keyframe appears in list, canvas shows blue dot
5. Add more keyframes:
   - Time: 2, Value: 100
   - Time: 5, Value: 50
   - Time: 10, Value: 0
6. **Expected**: Timeline canvas displays interpolated curve
7. Change **Interpolation** to different modes
8. **Expected**: Canvas curve shape changes
9. Click **🗑️** next to a keyframe
10. **Expected**: Keyframe removed, canvas updates
11. Click **Save Sequence**
12. **Expected**: Toast notification "Sequence saved successfully"

#### 6. Test Parameter Modulation

1. After saving an audio sequence on **Intensity**:
2. Start playing music (or audio source)
3. Play the video clip
4. **Expected**: Intensity parameter changes in real-time with audio

**Backend Console Check**:
```
🎛️ Applying modulation: clip.effects[0].parameters.intensity = 75.3
```

#### 7. Test Sequence Deletion

1. Click **⚙️** button on parameter with existing sequence
2. Click **Delete Sequence** (bottom left)
3. **Expected**: 
   - Toast notification "Sequence deleted"
   - Modal closes
   - Parameter returns to manual control

---

## 🐛 Troubleshooting

### Backend Errors

#### `Import "sounddevice" could not be resolved`

**Solution**:
```bash
pip install sounddevice>=0.4.0
```

#### `OSError: PortAudio library not found`

**Windows**:
- sounddevice should include PortAudio binaries automatically
- If error persists, reinstall: `pip uninstall sounddevice; pip install sounddevice`

**Linux**:
```bash
sudo apt-get install libportaudio2
```

**macOS**:
```bash
brew install portaudio
```

#### `AudioAnalyzer.start() fails with device error`

**Check available devices**:
```python
import sounddevice as sd
print(sd.query_devices())
```

**Set device manually in audio_analyzer.py**:
```python
# Line ~120
stream = sd.InputStream(
    device=None,  # Change to device index (e.g., 0, 1, 2)
    channels=1,
    ...
)
```

### Frontend Errors

#### Modal doesn't open

1. Check console for JavaScript errors
2. Verify `sequences.js` is loaded:
   ```javascript
   console.log(typeof SequenceManager); // Should be "function"
   ```
3. Verify modal HTML exists:
   ```javascript
   console.log(document.getElementById('sequenceModal')); // Should be element
   ```

#### Audio analyzer won't start

1. Check backend is running (`http://localhost:5000`)
2. Check console for fetch errors
3. Test API manually:
   ```bash
   curl -X POST http://localhost:5000/api/sequences/audio/start
   ```
4. Check backend logs for Python exceptions

#### Canvas not rendering

1. Verify canvas elements exist:
   ```javascript
   console.log(document.getElementById('audioSpectrumCanvas'));
   console.log(document.getElementById('lfoPreviewCanvas'));
   console.log(document.getElementById('timelineCanvas'));
   ```
2. Check canvas dimensions are set correctly (width/height attributes)
3. Open browser console and look for rendering errors

---

## 📊 Performance Testing

### Backend Performance

**Test sequence update performance**:
```python
import time
from src.modules.sequences import SequenceManager, LFOSequence

config = {}
manager = SequenceManager(config, None)

# Add 100 LFO sequences
for i in range(100):
    seq = LFOSequence(f'param_{i}', 'sine', 1.0, 1.0, 0.0, 0, 100)
    manager.add_sequence(seq)

# Measure update time
start = time.perf_counter()
for _ in range(1000):
    manager.update_all(0.016, None)
elapsed = time.perf_counter() - start

print(f'100 sequences x 1000 updates: {elapsed:.3f}s')
print(f'Average per frame: {elapsed / 1000 * 1000:.2f}ms')
```

**Expected**: < 1ms per frame for 100 sequences

### Frontend Performance

**Test canvas rendering**:
```javascript
// In browser console
let start = performance.now();
for (let i = 0; i < 100; i++) {
  sequenceManager.drawAudioSpectrum();
}
let elapsed = performance.now() - start;
console.log(`100 canvas draws: ${elapsed.toFixed(2)}ms`);
console.log(`Average per draw: ${(elapsed / 100).toFixed(2)}ms`);
```

**Expected**: < 5ms per draw

---

## ✅ Final Verification

After completing all tests, verify:

- [ ] Backend starts without errors
- [ ] Frontend loads without console errors
- [ ] Sequence modal opens when ⚙️ clicked
- [ ] All three sequence types (Audio/LFO/Timeline) are selectable
- [ ] Audio analyzer starts and captures audio
- [ ] All canvases render visualizations
- [ ] Sequences save successfully
- [ ] Parameters modulate in real-time
- [ ] Sequences delete successfully
- [ ] No memory leaks after 10+ minutes of use

---

## 🚀 Ready for Production

Once all tests pass:

1. **Update README.md** with feature description
2. **Create release notes** highlighting new feature
3. **Record demo video** showing audio-reactive effects
4. **Collect user feedback** and iterate

**Congratulations! 🎉 Dynamic Parameter Sequences are fully operational!**
