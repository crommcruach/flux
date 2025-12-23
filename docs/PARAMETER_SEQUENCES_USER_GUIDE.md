# 🎛️ Dynamic Parameter Sequences - User Guide

## Overview

Dynamic Parameter Sequences allow you to animate any effect parameter with **audio-reactive**, **LFO oscillator**, or **timeline keyframe** modulation. This adds motion, rhythm, and life to your visual effects.

---

## 🚀 Quick Start

### 1. Open the Sequence Editor

1. Select a clip with effects in the **Clip Effects** panel
2. Find any parameter (e.g., Intensity, Speed, Scale)
3. Click the **⚙️** button next to the parameter name
4. The **Parameter Sequence** editor opens

### 2. Choose a Sequence Type

Three types available:

- **🎵 Audio Reactive** - Modulate based on audio input (bass, mid, treble, RMS, etc.)
- **🌊 LFO** - Periodic oscillation with sine, square, triangle, sawtooth, or random waveforms
- **📈 Timeline** - Keyframe-based animation with custom timing

---

## 🎵 Audio Reactive Sequences

Modulate parameters in real-time based on audio analysis.

### Setup

1. Click **Start** to begin audio analyzer
2. Select **Audio Feature**:
   - **RMS Level** - Average volume
   - **Peak** - Maximum amplitude
   - **Bass** - Low frequencies (20-250Hz)
   - **Mid** - Mid frequencies (250-4000Hz)
   - **Treble** - High frequencies (4000-20000Hz)
   - **Beat Detection** - Spike on transients
3. Set **Min Value** and **Max Value** (output range)
4. Adjust **Smoothing** (0.0 = instant, 1.0 = very smooth)
5. Toggle **Invert** if needed
6. Watch the **live spectrum visualization**

### Audio Source Configuration

In `config.json`, set the audio source:

```json
{
  "audio_source": "loopback"  // Options: "mic", "line-in", "loopback" (system audio)
}
```

**Windows Tip**: For system audio capture (loopback), install [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) or use built-in "Stereo Mix" (if available).

### Example Use Cases

- **Intensity → Bass** - Pulse effect with music
- **Speed → RMS** - Speed up/slow down with volume
- **Scale → Beat** - Jump on drum hits
- **Rotation → Treble** - Spin with high frequencies

---

## 🌊 LFO Sequences

Periodic oscillation for smooth, repeating motion.

### Parameters

- **Waveform**: sine, square, triangle, sawtooth, random
- **Frequency**: 0.01 - 10 Hz (cycles per second)
- **Amplitude**: 0.0 - 1.0 (modulation depth)
- **Phase**: 0.0 - 1.0 (starting offset)
- **Min/Max Value**: Output range

### Waveform Types

- **Sine** - Smooth, natural oscillation
- **Square** - On/off toggle
- **Triangle** - Linear up/down
- **Sawtooth** - Ramp up, snap down
- **Random** - Smooth random walk

### Example Use Cases

- **Rotation → Sine LFO (0.2 Hz)** - Slow spin
- **Opacity → Square LFO (4 Hz)** - Strobe effect
- **Position X → Triangle LFO (1 Hz)** - Bounce left/right
- **Scale → Sawtooth LFO (0.5 Hz)** - Pulse in/out

---

## 📈 Timeline Sequences

Keyframe-based animation with precise timing control.

### Creating Keyframes

1. Enter **Time** (seconds) and **Value**
2. Click **➕ Add Keyframe**
3. Repeat to build animation curve
4. Click **🗑️** next to keyframe to remove it

### Parameters

- **Interpolation**: 
  - **Linear** - Straight lines between keyframes
  - **Ease In** - Slow start, fast end
  - **Ease Out** - Fast start, slow end
  - **Ease In/Out** - Smooth S-curve
  - **Step** - Jump instantly (no interpolation)
- **Loop Mode**:
  - **Once** - Play once and stop at last keyframe
  - **Loop** - Repeat from start after reaching end
  - **Ping-Pong** - Reverse direction at endpoints
- **Duration**: Total timeline length (seconds)

### Timeline Preview Canvas

The **timeline preview canvas** shows your animation curve in real-time. The graph displays:
- **X-axis** = Time (seconds)
- **Y-axis** = Parameter value
- **Blue dots** = Keyframes
- **Blue line** = Interpolated curve

### Example Use Cases

- **Position Y → Timeline**: Drop in at 0s, bounce at 2s, settle at 5s
- **Opacity → Timeline**: Fade in (0s: 0 → 2s: 100), fade out (8s: 100 → 10s: 0)
- **Rotation → Timeline**: Spin 0° → 360° over 10 seconds
- **Scale → Timeline**: Start small (0.5), grow large (2.0), return to normal (1.0)

---

## 🎨 Tips & Best Practices

### 1. Sequence Button Visibility

The **⚙️ sequence button** appears next to all numeric parameters (INT, FLOAT). Look for it in:
- Effect parameters (Intensity, Speed, Scale, etc.)
- Transform controls (Position, Rotation, Opacity)
- Generator parameters (depending on generator)

### 2. Combining Sequences

You **cannot** stack multiple sequences on the same parameter - the last saved sequence wins. However, you can:
- Use different sequences on different parameters
- Quickly switch between sequence types by reopening the editor

### 3. Performance Optimization

- **Audio Reactive**: Smoothing helps reduce CPU usage (higher = smoother but slower response)
- **LFO**: Very efficient - use as many as needed
- **Timeline**: Minimal overhead - keyframes are pre-calculated

### 4. Audio Analyzer Status

The **audio status indicator** shows:
- **🔴 Red** = Stopped
- **🟢 Green pulsing** = Running and capturing audio

**Note**: Audio analyzer runs globally for all audio sequences. Starting it once enables all audio-reactive modulations.

### 5. Previewing Changes

- **Audio**: Live spectrum visualization updates in real-time
- **LFO**: Waveform preview updates as you adjust frequency
- **Timeline**: Timeline canvas redraws when keyframes or interpolation changes

### 6. Deleting Sequences

1. Open the sequence editor (⚙️ button)
2. Click **Delete Sequence** (bottom left)
3. The parameter returns to manual control

---

## 🐛 Troubleshooting

### Audio Analyzer Won't Start

**Possible causes**:
1. **No audio input device** - Check system audio settings
2. **Python sounddevice error** - Ensure `sounddevice>=0.4.0` is installed:
   ```bash
   pip install sounddevice>=0.4.0
   ```
3. **Permission denied** - Grant microphone access to Python

### No Audio in Loopback Mode

**Windows**: 
- Install [VB-Audio Virtual Cable](https://vb-audio.com/Cable/)
- Enable "Stereo Mix" in Sound settings (if available)
- Set `"audio_source": "loopback"` in `config.json`

**macOS**:
- Install [BlackHole](https://github.com/ExistentialAudio/BlackHole) virtual audio device
- Route system audio through BlackHole

**Linux**:
- Use PulseAudio loopback module:
  ```bash
  pactl load-module module-loopback
  ```

### Sequence Not Saving

1. Check browser console (F12) for errors
2. Verify backend is running (`http://localhost:5000`)
3. Ensure REST API endpoint `/api/sequences` is accessible
4. Check server logs for Python exceptions

### Parameter Not Modulating

1. Verify sequence is **enabled** (check backend logs)
2. Ensure PlayerManager calls `update_sequences(dt)` each frame
3. Check parameter path is correct (e.g., `clip.effects[0].parameters.intensity`)
4. Confirm sequence value is within Min/Max range

---

## 📚 Advanced: Parameter Paths

Sequences target parameters via **dot notation paths**:

```
clip.effects[0].parameters.intensity
clip.effects[1].parameters.speed
artnet.effects[2].parameters.rotation
```

**Format**: `{player}.effects[{index}].parameters.{param_name}`

This allows backend to resolve and apply modulation automatically.

---

## 🎉 Example Workflow

### Audio-Reactive Intensity Pulse

1. Add **Color Shift** effect to video clip
2. Click **⚙️** next to **Intensity** parameter
3. Select **🎵 Audio Reactive**
4. Click **Start** audio analyzer
5. Choose **Bass** feature
6. Set Min: 0, Max: 100
7. Smoothing: 0.15
8. Click **Save Sequence**
9. Play music and watch intensity pulse with bass!

### Smooth Rotation LFO

1. Add **Transform** effect to clip
2. Click **⚙️** next to **Rotation** parameter
3. Select **🌊 LFO**
4. Waveform: **Sine**
5. Frequency: 0.5 Hz
6. Min: -45, Max: 45
7. Click **Save Sequence**
8. Enjoy smooth oscillation!

### Keyframe Fade In/Out

1. Add **Transform** effect to clip
2. Click **⚙️** next to **Opacity** parameter
3. Select **📈 Timeline**
4. Add keyframes:
   - Time: 0s, Value: 0 (invisible)
   - Time: 2s, Value: 100 (visible)
   - Time: 8s, Value: 100 (visible)
   - Time: 10s, Value: 0 (invisible)
5. Interpolation: **Ease In/Out**
6. Loop Mode: **Once**
7. Duration: 10 seconds
8. Click **Save Sequence**
9. Watch smooth fade in and fade out!

---

## 🔧 Config Reference

### config.json

```json
{
  "audio_source": "loopback",  // "mic" | "line-in" | "loopback"
  "audio_analyzer": {
    "sample_rate": 44100,
    "buffer_size": 1024,
    "fft_size": 2048,
    "bass_freq_max": 250,
    "mid_freq_max": 4000,
    "treble_freq_min": 4000
  }
}
```

---

## 🚀 Next Steps

- Experiment with **multiple sequences** on different parameters
- Combine **audio + LFO** on different effects for complex visuals
- Build **timeline animations** synchronized to specific song sections
- Use **beat detection** for reactive strobes and flashes

**Have fun creating dynamic, living visuals! 🎨✨**
