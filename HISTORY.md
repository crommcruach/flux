# Py_artnet - Development History

This file documents the evolution and architectural decisions of the project.

## v1.0.0 - Fresh Start (2026-02-19)

### Overview
Starting fresh with a clean, well-organized codebase. Previous version history has been archived as the project has undergone significant architectural changes.

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
