# Py_artnet - Development History

This file documents the evolution and architectural decisions of the project.

## v1.0.1 - Art-Net Improvements (2026-02-20)

### Critical Fix: Art-Net Source Port
**Problem**: Art-Net packets worked on localhost (127.0.0.1) but failed on external controllers (e.g., 192.168.1.2). After extensive debugging (broadcast mode, source binding, socket options, raw sockets, ArtSync), Wireshark packet analysis revealed the issue.

**Root Cause**: Some Art-Net receivers require packets to originate FROM port 6454, not just be sent TO port 6454. stupidArtnet library was using random source ports (e.g., 52341), which the controller rejected.

**Solution**: Added `source_address=('0.0.0.0', 6454)` parameter to all StupidArtnet instantiations:
- `src/modules/artnet/sender.py` (production output routing)
- `src/modules/api/mapper/routes.py` (LED visual mapper endpoints)

**Impact**: Art-Net now works reliably on both localhost and external network devices.

### New Feature: ArtSync Support
**Purpose**: ArtSync (OpCode 0x5200) synchronizes DMX updates across multiple universes, eliminating visual tearing in multi-universe setups.

**Implementation**:
- Added `artsync: bool = True` field to ArtNetOutput dataclass
- Updated sender.py to pass artsync parameter to StupidArtnet instances
- Added UI checkbox in output configuration modal
- Enabled by default for all new outputs

**Benefits**:
- Ensures simultaneous frame updates across all universes
- Professional-grade timing synchronization
- Critical for large LED installations with 2+ universes

### New Feature: 2D Visual LED Mapping
**Overview**: Webcam-based LED position detection system for automatic 2D layout calibration.

**Components**:
- Backend: Flask API routes with Art-Net sequential illumination
- Frontend: 946-line LED mapper module with 4-step wizard
- Computer vision: Canvas-based brightness detection and blob analysis
- Calibration: 4-point perspective correction system
- Export: Creates freehand shapes in editor with accurate LED positions

**Workflow**:
1. Configure Art-Net settings (IP, universe, DMX addressing)
2. Calibrate camera perspective (4-corner mapping)
3. Sequential LED mapping (LEDs light one-by-one, camera detects position)
4. Review and export to editor as shape with LED points

**Status**: Fully functional after source port fix.

### LED Mapper Detection Algorithm Improvements
**Goal**: Improve detection accuracy and reduce false positives in varying lighting conditions.

**Improvements Implemented** (2026-02-20):

1. **Adaptive Threshold Detection**
   - Auto-adjusts sensitivity based on ambient lighting
   - Dark environment (<30 avg brightness): threshold = 30 (sensitive)
   - Normal lighting (30-90): threshold = 60 (standard)
   - Bright environment (>90): threshold = 100 (robust)
   - Eliminates manual threshold tuning

2. **Temporal Filtering**
   - 5-frame median smoothing for position stability
   - Reduces jitter from camera noise and minor light variations
   - Improves accuracy on video frame inconsistencies

3. **ROI Auto-Refinement**
   - Dynamic search area optimization after first LED detection
   - Shrinks search region from full frame to 150×150px window
   - Performance improvement: 10-50x faster detection
   - Critical for long LED strips (50+ LEDs)

4. **Geometric Normalization** (optional, UI toggle)
   - Path smoothing: 5-neighbor moving average
   - Spacing equalization: consistent inter-LED distances
   - Ideal for PCB-mounted LED strips with uniform spacing
   - User-controllable via checkbox (enabled by default)

5. **Brightness-Weighted Centroid**
   - Center-of-mass physics instead of simple averaging
   - Formula: centerX = Σ(x × brightness) / Σ(brightness)
   - More accurate center detection for asymmetric blobs

6. **Window-Based Blob Detection**
   - Fixed 20×20px scan window around brightest pixel
   - Replaced asymmetric flood-fill algorithm
   - Eliminates left/center offset issues
   - More predictable and accurate positioning

**UI Improvements**:
- Added "Normalize Geometry" checkbox in configuration step
- Moved extensive diagnostic logging to debug mode (window.DEBUG flag)
- Cleaner console output for production use
- Debug mode shows: ROI refinement, baseline capture steps, WebSocket status, per-LED detection details

**Result**: Highly accurate LED position detection across varying lighting conditions with minimal user configuration.

## v1.0.0 - Fresh Start (2026-02-19)

### Overview
Starting fresh with a clean, well-organized codebase. Previous version history has been archived as the project has undergone significant architectural changes.

### Recent Improvements (2026-02-19)
- **Menu Bar UX**: Improved navigation clarity with better icon (>_ for CLI) and logical ordering (Editor → Player → Output → Converter → Config → CLI)
- **Code Cleanup**: Verified removal of orphaned index.html file; editor.html is the actual startup page served at root

### Key Decisions
- **Directory Structure**: All data folders (thumbnails, projects, records, snapshots) moved to project root for cleaner separation from source code
- **Session State**: Unified architecture using SessionStateManager with SessionPersistence layer
- **Streaming**: WebSocket-based preview system with <100ms latency (replaced WebRTC)
- **Configuration**: Cleaned up deprecated settings, standardized on session_state.json for live data

### Architecture
- Python 3.12 backend with Flask REST API + SocketIO
- WebSocket streaming for real-time preview
- Art-Net output system with per-object/per-output routing
- Multi-layer canvas editor with generator support
- Audio sequencer with BPM detection and MIDI integration

### Future Documentation
Future architectural changes and development history will be documented here.
