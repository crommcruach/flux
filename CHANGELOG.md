# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **2D Visual LED Mapper**: Webcam-based LED position detection system with calibration workflow
  - Adaptive threshold detection (auto-adjusts for ambient lighting: dark/normal/bright)
  - Temporal filtering (5-frame median smoothing for stability)
  - ROI auto-refinement (dynamic search area optimization, 10-50x speedup)
  - Geometric normalization with UI toggle (path smoothing + spacing equalization)
  - Brightness-weighted centroid detection (center-of-mass physics)
  - Window-based blob detection (fixed 20×20px scan for accuracy)
- **ArtSync Support**: Configurable ArtSync packet transmission for multi-universe synchronization (enabled by default)
- ArtSync checkbox in Art-Net output configuration UI
- Geometry normalization checkbox in LED mapper configuration (enabled by default)
- Debug logging mode for LED mapper (window.DEBUG flag)
- **Canvas Editor Handle System Improvements**:
  - Hover feedback for rotation (outer ring) and scaling (inner square) handles - highlights to full cyan opacity
  - Context menu options for horizontal and vertical flip (moved from canvas handle)
  - Global context menu prevention except in UI areas (menu bar, toolbar, sidebar, object list)
  - Edge-based scaling with fixed opposite edge for all 4 sides (top, bottom, left, right)
  - Corner-based scaling with fixed opposite corner

### Changed
- CLI menu icon changed from 💻 to >_ for clearer terminal representation
- Menu items reordered for improved workflow: Editor → Player → Output Settings → Converter → Config → CLI
- LED mapper extensive logging moved to debug mode (reduces console noise)
- Corner scale handles now 30% smaller for better visual clarity
- Line shapes no longer have vertical (Y-axis) scaling handles (1-dimensional shape)
- Flip functionality moved from canvas handle to context menu (rarely used feature)

### Fixed
- **Art-Net Source Port**: Fixed Art-Net transmission to external controllers by binding to source port 6454 (some controllers require packets FROM port 6454, not just TO port 6454)
- Art-Net packets now work correctly on both localhost and external network devices
- **Edge Scaling Stutter**: Fixed edge scaling calculations to use dragStartX/Y consistently, eliminating stuttering during drag
- **Corner Scaling Jump**: Fixed corner scaling calculation to divide by full shape size instead of half-size, eliminating initial jump on first drag

### Removed
- Confirmed removal of unused index.html (editor.html is the actual startup page)
- Flip handle/icon from canvas (moved to context menu)

## [1.0.0] - 2026-02-19

### Added
- Initial stable release
- Video-to-Art-Net DMX control system
- Web-based interface with real-time preview
- Multi-layer canvas editor with effects
- Generator system (checkerboard, fire, plasma, pulse, etc.)
- Transport controls (speed, reverse, trim, loop)
- Audio sequencer with BPM detection
- MIDI support with parameter mapping
- Session state persistence
- Project save/load system
- Thumbnail generation with caching
- WebSocket-based preview streaming (<100ms latency)

### Changed
- Reorganized directory structure (data folders moved to project root)
- Cleaned up deprecated configuration settings

### Removed
- WebRTC streaming system (replaced by WebSocket)
- Orphaned startup.log file
