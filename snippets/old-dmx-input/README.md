# Old DMX Input System Archive

**Archived Date:** 2026-02-13

## Purpose
This directory contains the old DMX INPUT controller implementation for reference. This was removed to be reimplemented later with a better architecture.

## File
- **dmx_controller.py** - DMX INPUT controller that receives Art-Net packets to control the application

## Features (DMX Input Control)

### Channel Mapping
- **Channel 1**: Play/Stop (0-127=Stop, 128-255=Play)
- **Channel 2**: Brightness (0-255)
- **Channel 3**: Speed (0-255, where 128=1x, 0=0.25x, 255=4x)
- **Channel 4**: Pause/Resume (0-127=Resume, 128-255=Pause)
- **Channel 5**: Blackout (0-127=Normal, 128-255=Blackout)
- **Channels 6-9**: Video Slot Selection
  - Ch6: Channel select (1-4)
  - Ch7-9: Slot within channel (0-255 per channel)
  - Supports up to 1020 videos across 4 channels
- **Channel 10**: Script Slot (0-255, deprecated - generators used instead)

### Video Cache System
- Organized videos into `kanal_1/` through `kanal_4/` directories
- Each channel supports up to 255 videos
- Total capacity: 1020 videos
- Automatic caching on startup

### Network Configuration
- Listened on UDP port 6454 (Art-Net)
- Default control universe: 100
- Processed Art-Net DMX packets (OpCode 0x5000)

## Technical Details

### Implementation
- **Protocol**: Art-Net (DMX over UDP)
- **Port**: 6454
- **Universe**: Configurable (default 100)
- **Threading**: Separate listener thread
- **Trigger Detection**: Value change detection to prevent repeated triggers

### Dependencies
- Standard library only (socket, struct, threading)
- No external DMX libraries required

## Reasons for Removal
- Early implementation from project's initial phase
- Needs redesign for better architecture
- Will be reimplemented with:
  - Better error handling
  - Configuration management
  - Integration with new routing system
  - Proper command mapping system

## Future Reimplementation

When reimplementing DMX input:

1. **Consider Using Libraries**
   - sacn (sACN/E1.31)
   - python-artnet
   - Instead of raw socket implementation

2. **Architecture Improvements**
   - Separate DMX input handler from player control
   - Command pattern for DMX-to-action mapping
   - Configuration-based channel mapping
   - Hot-reload of channel mappings

3. **Feature Additions**
   - Multiple universe support
   - Configurable channel assignments
   - DMX input monitoring/debugging
   - Integration with session state
   - Support for 16-bit channels

4. **Integration Points**
   - Connect to PlayerManager (not direct player)
   - Use routing system for output control
   - Integrate with command executor
   - Support playlist control
   - Layer control

## Related Systems
- **Output**: `src/modules/artnet_routing/` - Art-Net OUTPUT (sending DMX)
- **Control**: This was INPUT (receiving DMX commands)
- **API**: REST API endpoints for web control

## Notes
- This is INPUT control, not OUTPUT lighting
- Script loading was already deprecated (generators preferred)
- Video cache system could be useful pattern for future implementation
- Trigger detection with hysteresis was good UX practice
