# Old Art-Net System Archive

**Archived Date:** 2026-02-12

## Purpose
This directory contains the old Art-Net control system files for reference. These files were removed during the consolidation to the new `artnet_routing/` system.

## Files
- **artnet.html** - Old Art-Net control interface with brightness slider, blackout, test patterns
- **artnet.js** - JavaScript for old Art-Net control API calls

## Features to Re-implement in New System
The old system had these features that need to be added to the new `artnet_routing/` system:

### UI Features
- [x] Brightness slider (global brightness control)
- [x] Blackout button (all outputs black)
- [ ] Test patterns (red, green, blue solid colors)
- [ ] Resume video button
- [ ] FPS limiter

### Backend Features (from artnet_manager.py)
- [ ] Delta encoding for optimized network traffic
- [ ] Test pattern generation
- [ ] Global brightness control
- [ ] FPS limiting

## New System
The replacement system is located at:
- Backend: `src/modules/artnet_routing/`
- Frontend: `frontend/output-settings.html` + `frontend/js/output-settings.js`
- Integration: `src/modules/artnet_routing/routing_bridge.py`

## Notes
- The old system used simple points-based rendering
- The new system uses object-based routing with multi-output support
- Old API endpoints: `/api/artnet/info`, `/blackout`, `/test`, `/resume`
- New API endpoints: `/api/artnet/routing/*`, `/api/artnet/outputs/*`
