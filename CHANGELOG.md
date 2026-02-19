# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

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
