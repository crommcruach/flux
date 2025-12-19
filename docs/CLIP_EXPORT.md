# Clip Export/Record - Implementation Guide

## Overview

This document describes the implementation of **clip export functionality** that allows users to save rendered clips with all effects, layers, and parameters baked in. Users can export clips via context menu in the playlist.

## Goals

- **Export rendered clips**: Save clips with all effects applied
- **Context menu integration**: Right-click on clip → Export (using existing menu)
- **One-click export**: No dialogs, immediate processing
- **Toast notifications**: Simple start/complete messages
- **Background processing**: Export without blocking UI
- **Auto-naming**: Automatic timestamp-based filenames
- **Fixed output location**: `video/exports/` folder
- **HAP Alpha format**: Fast decoding with alpha channel support (default)

## Use Cases

### 1. Effect Baking
User applies complex effect stack (color correction, transitions, overlays) and wants to export the final result for use in other software or as a pre-rendered clip for better performance.

### 2. Clip Archival
Save specific clip versions with effects applied at specific settings for later recall or documentation.

### 3. Sharing
Export clips with effects for sharing with other users or uploading to platforms.

### 4. Performance Optimization
Pre-render heavy effect chains to reduce real-time processing load during live performances.

### 5. External Workflow
Export clips for further editing in video editors (Premiere, Resolve, etc.) with effects already applied.

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (JavaScript)                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │ Playlist Context │────────▶│  Toast Message   │          │
│  │     Menu         │         │  "Exporting..."  │          │
│  │  • Export Clip   │         └──────────────────┘          │
│  └──────────┬───────┘                                        │
│             │                                                │
│             │ POST /api/export/clip                          │
│             ▼                                                │
└─────────────┼────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (Python)                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  Export Manager                      │   │
│  │  ┌────────────┐         ┌────────────────┐          │   │
│  │  │ Export Job │────────▶│ Clip Renderer  │          │   │
│  │  │  Queue     │         │ - Load clip    │          │   │
│  │  │            │         │ - Apply effects│          │   │
│  │  └────────────┘         │ - Render frames│          │   │
│  │                         └────────┬───────┘          │   │
│  │                                  │                  │   │
│  │  ┌────────────────────────────┐ │                  │   │
│  │  │      Video Encoder         │ │                  │   │
│  │  │  - FFmpeg integration      │◀┘                  │   │
│  │  │  - Format conversion       │                    │   │
│  │  │  - Codec selection         │                    │   │
│  │  └────────────┬───────────────┘                    │   │
│  └───────────────┼──────────────────────────────────────┘   │
│                  │                                          │
│  ┌───────────────▼───────────────┐                         │
│  │    WebSocket Progress         │                         │
│  │    /ws/export-progress        │                         │
│  └───────────────┬───────────────┘                         │
│                  │                                          │
└──────────────────┼──────────────────────────────────────────┘
                   │
                   ▼ Completion notification
┌─────────────────────────────────────────────────────────────┐
│                   Frontend Toast Messages                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ✅ Export complete!                                 │   │
│  │  Saved to: video/exports/export_20251219_143052.mp4 │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Steps

### Phase 1: Backend - Export Manager

#### 1.1 Create Export Manager

**File:** `src/modules/export_manager.py`

```python
"""
Export Manager
Handles clip export with effects applied.
"""

import os
import logging
import threading
import queue
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np
from typing import Optional, Dict, Any, Callable

logger = logging.getLogger(__name__)

class ExportJob:
    """Represents a single export job."""
    
    def __init__(self, job_id, clip_id, output_path, settings):
        self.job_id = job_id
        self.clip_id = clip_id
        self.output_path = output_path
        self.settings = settings
        self.status = 'queued'  # queued, processing, completed, failed, cancelled
        self.progress = 0.0  # 0.0 to 1.0
        self.current_frame = 0
        self.total_frames = 0
        self.error = None
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None


class ExportManager:
    """Manages clip export operations."""
    
    def __init__(self):
        self.jobs = {}  # job_id -> ExportJob
        self.job_queue = queue.Queue()
        self.current_job = None
        self.worker_thread = None
        self.is_running = False
        self.progress_callbacks = []  # List of callbacks for progress updates
        
    def start(self):
        """Start export worker thread."""
        if self.is_running:
            return
        
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("📦 Export manager started")
    
    def stop(self):
        """Stop export worker thread."""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("📦 Export manager stopped")
    
    def create_export(self, clip_id, output_path=None):
        """
        Create new export job with default settings.
        
        Args:
            clip_id: Clip ID to export
            output_path: Optional output file path (auto-generated if None)
        
        Returns:
            str: Job ID
        """
        # Use default settings
        settings = {
            'format': 'hap_alpha',
            'codec': 'hap',
            'fps': 'source',
            'resolution': 'source'
        }
        import uuid
        job_id = str(uuid.uuid4())
        
        job = ExportJob(job_id, clip_id, output_path, settings)
        self.jobs[job_id] = job
        self.job_queue.put(job_id)
        
        logger.info(f"📦 Created export job {job_id}: {clip_id} -> {output_path}")
        return job_id
    
    def cancel_export(self, job_id):
        """Cancel export job."""
        if job_id in self.jobs:
            job = self.jobs[job_id]
            if job.status in ['queued', 'processing']:
                job.status = 'cancelled'
                logger.info(f"📦 Cancelled export job {job_id}")
                return True
        return False
    
    def get_job_status(self, job_id):
        """Get export job status."""
        if job_id in self.jobs:
            job = self.jobs[job_id]
            return {
                'job_id': job.job_id,
                'clip_id': job.clip_id,
                'status': job.status,
                'progress': job.progress,
                'current_frame': job.current_frame,
                'total_frames': job.total_frames,
                'error': job.error,
                'output_path': job.output_path
            }
        return None
    
    def _worker_loop(self):
        """Background worker loop."""
        while self.is_running:
            try:
                # Get next job (with timeout to allow checking is_running)
                try:
                    job_id = self.job_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                if job_id not in self.jobs:
                    continue
                
                job = self.jobs[job_id]
                self.current_job = job
                
                # Process export
                self._process_export(job)
                
                self.current_job = None
                
            except Exception as e:
                logger.error(f"Error in export worker: {e}")
    
    def _process_export(self, job: ExportJob):
        """Process single export job."""
        from .clip_registry import get_clip_registry
        from .plugin_manager import get_plugin_manager
        
        try:
            job.status = 'processing'
            job.started_at = datetime.now()
            
            # Get clip from registry
            registry = get_clip_registry()
            clip_data = registry.get_clip(job.clip_id)
            
            if not clip_data:
                raise Exception(f"Clip not found: {job.clip_id}")
            
            # Get clip source path
            clip_path = clip_data.get('path')
            if not os.path.exists(clip_path):
                raise Exception(f"Clip file not found: {clip_path}")
            
            # Open video source
            cap = cv2.VideoCapture(clip_path)
            if not cap.isOpened():
                raise Exception(f"Failed to open clip: {clip_path}")
            
            # Get clip properties
            source_fps = cap.get(cv2.CAP_PROP_FPS)
            source_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            source_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Apply settings
            output_fps = source_fps if job.settings.get('fps') == 'source' else job.settings.get('fps', 30)
            
            if job.settings.get('resolution') == 'source':
                output_width, output_height = source_width, source_height
            else:
                output_width, output_height = job.settings.get('resolution', (source_width, source_height))
            
            start_frame = job.settings.get('start_frame', 0)
            end_frame = job.settings.get('end_frame', total_frames)
            
            job.total_frames = end_frame - start_frame
            
            # Prepare output writer
            writer = self._create_video_writer(
                job.output_path,
                job.settings.get('format', 'mp4'),
                job.settings.get('codec', 'h264'),
                output_fps,
                (output_width, output_height),
                job.settings.get('quality', 'high')
            )
            
            # Load effect plugins
            plugin_manager = get_plugin_manager()
            effect_instances = []
            
            for effect_data in clip_data.get('effects', []):
                plugin_id = effect_data.get('plugin_id')
                parameters = effect_data.get('parameters', {})
                
                try:
                    plugin = plugin_manager.load_plugin(plugin_id)
                    if plugin:
                        # Initialize with parameters
                        for param_name, param_value in parameters.items():
                            plugin.update_parameter(param_name, param_value)
                        effect_instances.append(plugin)
                except Exception as e:
                    logger.warning(f"Failed to load effect {plugin_id}: {e}")
            
            # Seek to start frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            # Render frames
            frame_index = start_frame
            processed_frames = 0
            
            while frame_index < end_frame and job.status == 'processing':
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_float = frame_rgb.astype(np.float32) / 255.0
                
                # Apply effects
                for effect in effect_instances:
                    try:
                        frame_float = effect.process_frame(
                            frame_float,
                            frame_count=processed_frames,
                            fps=output_fps
                        )
                    except Exception as e:
                        logger.error(f"Effect processing error: {e}")
                
                # Resize if needed
                if (output_width, output_height) != (source_width, source_height):
                    frame_float = cv2.resize(frame_float, (output_width, output_height))
                
                # Convert back to uint8
                frame_uint8 = (np.clip(frame_float, 0, 1) * 255).astype(np.uint8)
                frame_bgr = cv2.cvtColor(frame_uint8, cv2.COLOR_RGB2BGR)
                
                # Write frame
                writer.write(frame_bgr)
                
                # Update progress
                processed_frames += 1
                frame_index += 1
                job.current_frame = processed_frames
                job.progress = processed_frames / job.total_frames
                
                # Notify progress callbacks
                self._notify_progress(job)
                
            # Cleanup
            cap.release()
            writer.release()
            
            # Check if completed or cancelled
            if job.status == 'processing':
                job.status = 'completed'
                job.completed_at = datetime.now()
                logger.info(f"📦 Export completed: {job.output_path}")
            else:
                # Job was cancelled - delete partial file
                if os.path.exists(job.output_path):
                    os.remove(job.output_path)
                logger.info(f"📦 Export cancelled: {job.job_id}")
            
        except Exception as e:
            job.status = 'failed'
            job.error = str(e)
            job.completed_at = datetime.now()
            logger.error(f"📦 Export failed: {e}")
    
    def _create_video_writer(self, output_path, format_type, codec, fps, resolution, quality):
        """Create video writer with specified settings."""
        fourcc_map = {
            'h264': cv2.VideoWriter_fourcc(*'avc1'),  # H.264
            'h265': cv2.VideoWriter_fourcc(*'hev1'),  # H.265
            'prores': cv2.VideoWriter_fourcc(*'apcn'),  # ProRes
            'mjpeg': cv2.VideoWriter_fourcc(*'MJPG'),  # Motion JPEG
            'avi': cv2.VideoWriter_fourcc(*'XVID')     # Xvid
        }
        
        fourcc = fourcc_map.get(codec, cv2.VideoWriter_fourcc(*'avc1'))
        
        writer = cv2.VideoWriter(
            output_path,
            fourcc,
            fps,
            resolution
        )
        
        if not writer.isOpened():
            raise Exception(f"Failed to create video writer for {output_path}")
        
        return writer
    
    def _notify_progress(self, job: ExportJob):
        """Notify progress callbacks."""
        for callback in self.progress_callbacks:
            try:
                callback(job.job_id, job.progress, job.current_frame, job.total_frames)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
    
    def add_progress_callback(self, callback: Callable):
        """Add progress callback."""
        self.progress_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: Callable):
        """Remove progress callback."""
        if callback in self.progress_callbacks:
            self.progress_callbacks.remove(callback)


# Global instance
_export_manager = None

def get_export_manager():
    """Get global export manager instance."""
    global _export_manager
    if _export_manager is None:
        _export_manager = ExportManager()
    return _export_manager
```

#### 1.2 Create Export API

**File:** `src/modules/api_export.py`

```python
"""
Export API
REST and WebSocket endpoints for clip export.
"""

from flask import Blueprint, jsonify, request
from flask_sock import Sock
import json
import time
import logging
from .export_manager import get_export_manager
from pathlib import Path

logger = logging.getLogger(__name__)

# Create blueprint
export_bp = Blueprint('export', __name__)
sock = Sock()

@export_bp.route('/api/export/clip', methods=['POST'])
def export_clip():
    """Export clip with effects applied (default settings)."""
    try:
        data = request.get_json() or {}
        
        clip_id = data.get('clip_id')
        
        if not clip_id:
            return jsonify({'success': False, 'error': 'No clip ID provided'}), 400
        
        # Auto-generate output path: video/exports/export_TIMESTAMP.mov (HAP format)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path('video/exports')
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"export_{timestamp}.mov")
        
        # Create export job with default settings
        manager = get_export_manager()
        job_id = manager.create_export(clip_id, output_path)
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'output_path': output_path
        })
    
    except Exception as e:
        logger.error(f"Error creating export: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@export_bp.route('/api/export/<job_id>/status', methods=['GET'])
def get_export_status(job_id):
    """Get export job status."""
    try:
        manager = get_export_manager()
        status = manager.get_job_status(job_id)
        
        if status:
            return jsonify({'success': True, 'status': status})
        else:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
    
    except Exception as e:
        logger.error(f"Error getting export status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@export_bp.route('/api/export/<job_id>/cancel', methods=['POST'])
def cancel_export(job_id):
    """Cancel export job."""
    try:
        manager = get_export_manager()
        success = manager.cancel_export(job_id)
        
        return jsonify({'success': success})
    
    except Exception as e:
        logger.error(f"Error cancelling export: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@sock.route('/ws/export-progress')
def export_progress_websocket(ws):
    """WebSocket endpoint for real-time export progress."""
    logger.info("📦 Export progress WebSocket client connected")
    manager = get_export_manager()
    
    # Progress callback
    def progress_callback(job_id, progress, current_frame, total_frames):
        try:
            ws.send(json.dumps({
                'type': 'progress',
                'job_id': job_id,
                'progress': progress,
                'current_frame': current_frame,
                'total_frames': total_frames
            }))
        except:
            pass
    
    manager.add_progress_callback(progress_callback)
    
    try:
        while True:
            # Keep connection alive
            message = ws.receive(timeout=1)
            if message:
                # Handle any client messages if needed
                pass
    except Exception as e:
        logger.info(f"Export progress WebSocket closed: {e}")
    finally:
        manager.remove_progress_callback(progress_callback)
        logger.info("📦 Export progress WebSocket disconnected")

def init_export_api(app):
    """Initialize export API with Flask app."""
    app.register_blueprint(export_bp)
    sock.init_app(app)
    
    # Start export manager
    manager = get_export_manager()
    manager.start()
    
    logger.info("📦 Export API initialized")
```

### Phase 2: Frontend - Context Menu & Export Dialog

#### 2.1 Add Context Menu Option

**File:** `frontend/js/player.js` (modify existing `showPlaylistContextMenu` function)

```javascript
// Modify existing showPlaylistContextMenu function in player.js
// Add export option to existing context menu
function showPlaylistContextMenu(x, y, playlistId, index, fileItem) {
    const menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.style.left = x + 'px';
    menu.style.top = y + 'px';
    
    menu.innerHTML = `
        <div class="context-menu-item" data-action="clone">
            <span>🔄 Clone</span>
            <small>Full copy with effects & layers</small>
        </div>
        <div class="context-menu-item" data-action="duplicate">
            <span>📄 Duplicate</span>
            <small>Same file, new ID (no effects)</small>
        </div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item" data-action="copy">
            <span>📋 Copy</span>
            <small>Copy base clip (no effects)</small>
        </div>
        <div class="context-menu-item ${!hasCopiedClip ? 'disabled' : ''}" data-action="paste">
            <span>📥 Paste</span>
            <small>${hasCopiedClip ? 'Paste copied clip' : 'No clip copied'}</small>
        </div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item" data-action="export">
            <span>📦 Export Clip</span>
            <small>Save with effects applied</small>
        </div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item context-menu-item-danger" data-action="remove">
            <span>🗑️ Remove Clip</span>
            <small>Delete from playlist</small>
        </div>
    `;
    
    // Handle menu item clicks (add to existing switch statement)
    menu.addEventListener('click', async (e) => {
        const menuItem = e.target.closest('.context-menu-item');
        if (!menuItem || menuItem.classList.contains('disabled')) return;
        
        const action = menuItem.getAttribute('data-action');
        
        try {
            switch (action) {
                case 'clone':
                    await clonePlaylistItem(playlistId, index, fileItem);
                    break;
                case 'duplicate':
                    await duplicatePlaylistItem(playlistId, index, fileItem);
                    break;
                case 'copy':
                    copyPlaylistItem(playlistId, fileItem);
                    break;
                case 'paste':
                    await pastePlaylistItem(playlistId, index);
                    break;
                case 'export':
                    await exportClip(fileItem.clip_id);
                    break;
                case 'remove':
                    await removePlaylistItem(playlistId, index);
                    break;
            }
        } catch (error) {
            console.error(`Error executing ${action}:`, error);
            showToast(`Error: ${error.message}`, 'error');
        }
        
        menu.remove();
    });
    
    document.body.appendChild(menu);
}

// Export clip with one click
async function exportClip(clipId) {
    try {
        // Show toast: Starting export
        showToast('📦 Exporting clip...', 'info');
        
        const response = await fetch('/api/export/clip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ clip_id: clipId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Poll for completion
            pollExportStatus(data.job_id, data.output_path);
        } else {
            showToast('❌ Export failed: ' + data.error, 'error');
        }
    } catch (e) {
        console.error('Export error:', e);
        showToast('❌ Export failed: ' + e.message, 'error');
    }
}

// Poll export status until complete
async function pollExportStatus(jobId, outputPath) {
    const checkStatus = async () => {
        try {
            const response = await fetch(`/api/export/${jobId}/status`);
            const data = await response.json();
            
            if (data.success) {
                const status = data.status;
                
                if (status.status === 'completed') {
                    showToast(`✅ Export complete! Saved to: ${outputPath}`, 'success', 5000);
                } else if (status.status === 'failed') {
                    showToast('❌ Export failed: ' + status.error, 'error');
                } else if (status.status === 'processing') {
                    // Still processing, check again in 1 second
                    setTimeout(checkStatus, 1000);
                }
            }
        } catch (e) {
            console.error('Error checking export status:', e);
        }
    };
    
    // Start polling
    setTimeout(checkStatus, 1000);
}

// Simple toast notification
function showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Fade in
    setTimeout(() => toast.classList.add('toast-show'), 10);
    
    // Remove after duration
    setTimeout(() => {
        toast.classList.remove('toast-show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}
```

#### 2.2 Add Toast Notification Styles

**File:** `frontend/css/toast.css`

```css
.toast {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: rgba(20, 20, 30, 0.95);
    border: 1px solid #3c3c3c;
    border-radius: 8px;
    padding: 15px 20px;
    color: #e0e0e0;
    font-size: 14px;
    max-width: 400px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(10px);
    z-index: 10000;
    opacity: 0;
    transform: translateY(20px);
    transition: all 0.3s ease;
    pointer-events: none;
}

.toast-show {
    opacity: 1;
    transform: translateY(0);
    pointer-events: auto;
}

.toast-info {
    border-left: 4px solid #2196f3;
}

.toast-success {
    border-left: 4px solid #4caf50;
}

.toast-error {
    border-left: 4px solid #f44336;
}
```



## Usage

### Clip Export

1. Right-click on clip in playlist
2. Select "📦 Export Clip"
3. Toast message: "📦 Exporting clip..."
4. Export processes in background with default settings:
   - Format: HAP Alpha (DXT5 with alpha channel)
   - Resolution: Source (original)
   - Frame Rate: Source (original)
   - Location: `video/exports/export_YYYYMMDD_HHMMSS.mov`
5. Toast message on completion: "✅ Export complete! Saved to: video/exports/export_20251219_143052.mov"
6. Export runs in background, UI remains responsive

## Technical Details

### Effect Application

Export renders each frame through the same effect pipeline as live playback:
1. Load source frame
2. Convert to RGB float32 (0.0-1.0)
3. Apply effects in order (same as ClipFX)
4. Resize if needed
5. Convert back to uint8
6. Write to output file

### Default Export Settings

- **Format**: HAP Alpha (DXT5)
- **Codec**: HAP with alpha channel
- **Resolution**: Source (original clip resolution)
- **Frame Rate**: Source (original clip FPS)
- **Output**: `video/exports/export_YYYYMMDD_HHMMSS.mov`
- **Effects**: All clip effects applied in order
- **Advantages**: Fast decoding, alpha channel support, optimized for real-time playback

### Performance

- **Export speed**: Depends on effects complexity and resolution
- **Typical**: 2-5x realtime for simple effects
- **Heavy effects**: 0.5-1x realtime (slower than realtime)
- **Progress updates**: Every frame (60 fps WebSocket)
- **Background processing**: Non-blocking, UI remains responsive

## Future Enhancements

1. **Export Settings Dialog** (optional)
   - Format selection (MP4, MOV, AVI)
   - Quality presets (High, Medium, Low)
   - Resolution override
   - Frame rate override
   - Custom output path

2. **FFmpeg Integration**
   - Better codec support
   - Hardware acceleration (NVENC, QuickSync)
   - Audio track support
   - Advanced encoding options

3. **Batch Export**
   - Export multiple clips at once
   - Queue management UI
   - Priority reordering

4. **Progress Indicator**
   - Real-time progress bar in toast
   - Frame count display
   - Cancel export option

5. **Metadata Embedding**
   - Export effect list as metadata
   - Project info embedded in file
   - Watermarking support

6. **Cloud Export**
   - Export to cloud storage (S3, Dropbox, etc.)
   - Remote rendering service integration
   - Distributed export across machines

## References

- `src/modules/export_manager.py` - Export job management
- `src/modules/api_export.py` - REST API for export operations
- `frontend/js/player.js` - Export trigger and toast notifications
- `frontend/css/toast.css` - Toast notification styles
- OpenCV: Video I/O and encoding
- FFmpeg: Advanced codec support (future)
