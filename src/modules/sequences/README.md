# Dynamic Parameter Sequences Module

Automated, real-time parameter modulation for effects, sources, and transforms.

## Quick Start

```bash
# Install dependency
pip install sounddevice

# Start application (sequence system initializes automatically)
python src/main.py
```

## Features

### 🎵 Audio Reactive
Bind parameters to live audio input (microphone, line-in, or system audio):
- **Features:** RMS, Peak, Bass, Mid, Treble, Beat detection, BPM
- **Sources:** Configurable via `config.json` (microphone, line-in, speaker/system audio)
- **Smoothing:** Exponential attack/release
- **Range mapping:** Audio 0-1 → Parameter min-max

### 🌊 LFO (Low Frequency Oscillator)
Cyclic waveform modulation:
- **Waveforms:** Sine, Square, Triangle, Sawtooth, Random
- **Controls:** Frequency (Hz), Amplitude, Phase offset
- **Use cases:** Color cycling, pulsing effects, wobble transforms

### 📈 Timeline Keyframes
Time-based animation with keyframes:
- **Interpolation:** Linear, Ease In, Ease Out, Ease In/Out, Step
- **Loop modes:** Once, Loop, Ping-Pong
- **Dynamic:** Add/remove keyframes at runtime

## API Examples

### Start Audio Analyzer

```bash
curl -X POST http://localhost:5000/api/audio/start
```

### Create Audio-Reactive Brightness

```bash
curl -X POST http://localhost:5000/api/sequences \
  -H "Content-Type: application/json" \
  -d '{
    "type": "audio",
    "target_parameter": "player.video.clip.brightness",
    "config": {
      "feature": "bass",
      "min_value": 50,
      "max_value": 150,
      "smoothing": 0.1
    }
  }'
```

### Create LFO Color Cycling

```bash
curl -X POST http://localhost:5000/api/sequences \
  -H "Content-Type: application/json" \
  -d '{
    "type": "lfo",
    "target_parameter": "player.video.clip.effects[0].hue_shift",
    "config": {
      "waveform": "sine",
      "frequency": 0.5,
      "min_value": 0,
      "max_value": 360
    }
  }'
```

### Create Timeline Fade

```bash
curl -X POST http://localhost:5000/api/sequences \
  -H "Content-Type: application/json" \
  -d '{
    "type": "timeline",
    "target_parameter": "player.video.clip.opacity",
    "config": {
      "keyframes": [[0, 100], [8, 100], [10, 0]],
      "interpolation": "ease_out",
      "loop_mode": "once",
      "duration": 10.0
    }
  }'
```

## Configuration

Add to `config.json`:

```json
{
  "audio": {
    "audio_source": "microphone",
    "sample_rate": 44100,
    "block_size": 2048
  }
}
```

**Audio Source Options:**
- `"microphone"` - Default microphone
- `"line_in"` - Line-in input
- `"system_audio"` or `"speaker"` - System audio loopback (WASAPI on Windows)

## REST API Endpoints

### Sequences
```
POST   /api/sequences              # Create sequence
GET    /api/sequences              # List all
GET    /api/sequences/{id}         # Get details
PUT    /api/sequences/{id}         # Update
DELETE /api/sequences/{id}         # Delete
POST   /api/sequences/{id}/toggle  # Enable/disable
```

### Audio Analyzer
```
GET  /api/audio/devices     # List input devices
POST /api/audio/start       # Start analyzer
POST /api/audio/stop        # Stop analyzer
GET  /api/audio/features    # Get current audio features
GET  /api/audio/status      # Get status
```

## Architecture

```
src/modules/sequences/
├── __init__.py              # Module exports
├── base_sequence.py         # Abstract base class
├── sequence_manager.py      # Central coordinator
├── audio_analyzer.py        # Backend audio service (thread-safe)
├── audio_sequence.py        # Audio-reactive modulation
├── lfo_sequence.py          # LFO oscillator
└── timeline_sequence.py     # Keyframe animation
```

## Parameter Targeting

Use dot notation to target any parameter:

```
player.{player_id}.clip.{property}
player.{player_id}.clip.effects[{index}].{param}
player.{player_id}.clip.layers[{index}].{property}
```

**Examples:**
- `player.video.clip.brightness`
- `player.video.clip.effects[0].hue_shift`
- `player.artnet.clip.opacity`
- `player.video.clip.transform.scale`

## Thread Safety

- AudioAnalyzer runs in separate audio thread
- Features cached with thread-safe locks
- Sequence updates called from main render loop
- <5ms overhead per frame

## Frontend UI (Todo)

Backend is complete and functional via API. Frontend UI components pending:
- Sequence button (⚙️) next to parameters
- Modal editor with type-specific controls
- Live preview canvas
- Waveform visualizations

## Documentation

- [PARAMETER_SEQUENCES.md](../../docs/PARAMETER_SEQUENCES.md) - Full implementation plan
- [PARAMETER_SEQUENCES_STATUS.md](../../docs/PARAMETER_SEQUENCES_STATUS.md) - Status & examples
- [TODO.md](../../TODO.md) - Roadmap entry

## Testing

```bash
# List audio devices
curl http://localhost:5000/api/audio/devices

# Get current features
curl http://localhost:5000/api/audio/features

# List all sequences
curl http://localhost:5000/api/sequences

# Toggle sequence
curl -X POST http://localhost:5000/api/sequences/{id}/toggle
```

---

*Module implemented: December 23, 2025*
