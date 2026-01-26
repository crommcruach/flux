"""
Sequencer API - REST endpoints for audio-driven sequencer

Provides:
- Mode control (enable/disable sequencer as master)
- Audio file upload and browsing
- Playback control (play/pause/stop/seek)
- Split management (add/remove)
- Timeline data (get splits and slots)
- Clip mapping (assign clips to slots)
"""

import os
import re
from pathlib import Path
from flask import request, jsonify, send_file
from .logger import get_logger

logger = get_logger(__name__)


def _save_timeline_to_playlist(player_manager):
    """
    Helper: Save timeline to viewed playlist after any change.
    Called after timeline modifications (upload, load, split add/remove, clip mapping).
    """
    try:
        from .api_playlists import get_playlist_system
        playlist_system = get_playlist_system()
        if playlist_system:
            viewed = playlist_system.get_viewed_playlist()
            if viewed:
                # Save timeline to viewed playlist
                viewed.sequencer['timeline'] = player_manager.sequencer.timeline.to_dict()
                playlist_system._auto_save()
                logger.debug(f"💾 Saved timeline to viewed playlist '{viewed.name}'")
    except Exception as e:
        logger.warning(f"Failed to save timeline to playlist: {e}")


def register_sequencer_routes(app, player_manager, config, session_state=None):
    """Register sequencer API routes.
    
    Args:
        app: Flask app instance
        player_manager: PlayerManager with sequencer
        config: Application configuration
        session_state: SessionStateManager instance (optional)
    """
    
    # Get workspace root from Flask static folder path
    # static_folder points to: workspace_root/frontend
    workspace_root = Path(app.static_folder).parent
    
    video_dir = config.get('paths', {}).get('video_dir', 'video')
    audio_dir = config.get('paths', {}).get('sequencer_audio_dir', 'audio')
    
    # ========================================
    # SEQUENCER MODE CONTROL
    # ========================================
    
    @app.route('/api/sequencer/mode', methods=['POST'])
    def sequencer_set_mode():
        """Enable/disable sequencer mode
        
        When enabled: Sequencer = MASTER, all playlists = SLAVES
        When disabled: Normal Master/Slave via Transport
        """
        try:
            data = request.get_json() or {}
            enabled = data.get('enabled', False)
            
            if not player_manager.sequencer:
                return jsonify({
                    'success': False,
                    'error': 'Sequencer not initialized'
                }), 500
            
            # Save sequencer mode to VIEWED playlist
            try:
                from .api_playlists import get_playlist_system
                playlist_system = get_playlist_system()
                if playlist_system:
                    viewed = playlist_system.get_viewed_playlist()
                    if viewed:
                        # Always save to viewed playlist
                        viewed.sequencer['mode_active'] = enabled
                        
                        # Check if viewed playlist is active
                        is_active = viewed.id == playlist_system.active_playlist_id
                        
                        if is_active:
                            # Apply to physical players only if this is the active playlist
                            logger.info(f"✅ Applying sequencer mode={enabled} to ACTIVE playlist")
                            player_manager.set_sequencer_mode(enabled)
                        else:
                            # Just save, don't apply to players
                            logger.info(f"💾 Saved sequencer mode={enabled} to INACTIVE playlist")
                        
                        # Trigger auto-save
                        playlist_system._auto_save()
                    else:
                        # Fallback if no viewed playlist
                        player_manager.set_sequencer_mode(enabled)
                else:
                    # Fallback if playlist system not available
                    player_manager.set_sequencer_mode(enabled)
            except Exception as e:
                logger.error(f"Could not save sequencer mode to playlist: {e}", exc_info=True)
                # Fallback: apply to players directly
                player_manager.set_sequencer_mode(enabled)
            
            return jsonify({
                'success': True,
                'mode': 'master' if enabled else 'disabled',
                'enabled': enabled
            })
        except Exception as e:
            logger.error(f"Error setting sequencer mode: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/sequencer/status', methods=['GET'])
    def sequencer_get_status():
        """Get current sequencer state (mode, audio file, timeline)"""
        try:
            if not player_manager.sequencer:
                return jsonify({
                    'mode_active': False,
                    'has_audio': False
                })
            
            engine = player_manager.sequencer.engine
            timeline = player_manager.sequencer.timeline
            
            # Convert absolute path to relative path for frontend
            audio_file = None
            if engine.is_loaded and engine._file_path:
                abs_path = Path(engine._file_path)
                try:
                    # Try to make relative to workspace root
                    rel_path = abs_path.relative_to(workspace_root)
                    audio_file = str(rel_path).replace('\\', '/')
                except ValueError:
                    # Path is outside workspace, use absolute
                    audio_file = engine._file_path
            
            # Convert clip_mapping int keys to strings for JSON
            clip_mapping_json = {}
            if engine.is_loaded and timeline.clip_mapping:
                clip_mapping_json = {str(k): v for k, v in timeline.clip_mapping.items()}
            
            # Get sequencer mode from VIEWED playlist (not physical player!)
            mode_active = player_manager.sequencer_mode_active  # Default
            try:
                from .api_playlists import get_playlist_system
                playlist_system = get_playlist_system()
                if playlist_system:
                    viewed = playlist_system.get_viewed_playlist()
                    if viewed:
                        mode_active = viewed.sequencer.get('mode_active', False)  # From viewed playlist!
            except Exception as e:
                logger.warning(f"Could not get sequencer mode from viewed playlist: {e}")
            
            status = {
                'mode_active': mode_active,  # From viewed playlist!
                'has_audio': engine.is_loaded,
                'audio_file': audio_file,
                'audio_duration': engine.duration if engine.is_loaded else 0,
                'splits': timeline.splits if engine.is_loaded else [],
                'clip_mapping': clip_mapping_json,
                'is_playing': engine.is_playing if engine.is_loaded else False
            }
            
            return jsonify(status)
        except Exception as e:
            logger.error(f"Error getting sequencer status: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========================================
    # AUDIO FILE MANAGEMENT
    # ========================================
    
    @app.route('/api/sequencer/upload', methods=['POST'])
    def sequencer_upload_audio():
        """Upload audio file for sequencer (drag-and-drop)
        
        Saves to configured sequencer audio directory (default: audio/).
        """
        try:
            # Check if file was uploaded
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Validate audio file extension
            allowed_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')
            if not file.filename.lower().endswith(allowed_extensions):
                return jsonify({
                    'error': 'Invalid file type. Allowed: MP3, WAV, OGG, FLAC, M4A, AAC'
                }), 400
            
            # Create sequencer audio directory (absolute path)
            audio_path = workspace_root / audio_dir
            audio_path.mkdir(parents=True, exist_ok=True)
            
            # Sanitize filename
            safe_filename = re.sub(r'[^\w\-_\. ]', '_', file.filename)
            
            # Save file
            file_path = audio_path / safe_filename
            file.save(str(file_path))
            
            # Load into sequencer immediately (with absolute path)
            metadata = player_manager.sequencer.load_audio(str(file_path))
            
            # Save timeline to viewed playlist
            _save_timeline_to_playlist(player_manager)
            
            # Return relative path for frontend (from workspace root)
            relative_path = file_path.relative_to(workspace_root)
            
            logger.info(f"📤 Audio uploaded: {safe_filename}")
            
            return jsonify({
                'success': True,
                'path': str(relative_path).replace('\\', '/'),
                'filename': safe_filename,
                'metadata': metadata
            })
        except Exception as e:
            logger.error(f"Error uploading audio: {e}")
            return jsonify({'success': False, 'error': str(e)}), 400
    
    @app.route('/api/sequencer/browse-audio', methods=['GET'])
    def sequencer_browse_audio():
        """List available audio files for modal file browser
        
        Scans:
        - Configured sequencer audio directory (default: audio/)
        - video/ (for music files)
        """
        try:
            audio_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')
            files = []
            
            # Scan configured sequencer audio directory
            sequencer_audio_path = workspace_root / audio_dir
            if sequencer_audio_path.exists():
                for file_path in sequencer_audio_path.glob('*'):
                    if file_path.suffix.lower() in audio_extensions and file_path.is_file():
                        # Store relative path for frontend
                        rel_path = file_path.relative_to(workspace_root)
                        files.append({
                            'filename': file_path.name,
                            'path': str(rel_path).replace('\\', '/'),
                            'size': file_path.stat().st_size,
                            'folder': 'Sequencer Audio'
                        })
            
            # Scan video/ folder for music
            video_path = workspace_root / video_dir
            if video_path.exists():
                for file_path in video_path.rglob('*'):
                    if file_path.suffix.lower() in audio_extensions and file_path.is_file():
                        # Store relative path for frontend
                        rel_path = file_path.relative_to(workspace_root)
                        folder_rel = file_path.relative_to(video_path)
                        folder = f'Video/{folder_rel.parent}' if folder_rel.parent != Path('.') else 'Video'
                        files.append({
                            'filename': file_path.name,
                            'path': str(rel_path).replace('\\', '/'),
                            'size': file_path.stat().st_size,
                            'folder': folder
                        })
            
            return jsonify({
                'success': True,
                'files': sorted(files, key=lambda x: x['filename'])
            })
        except Exception as e:
            logger.error(f"Error browsing audio files: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/sequencer/load', methods=['POST'])
    def sequencer_load_audio():
        """Load audio file into sequencer from server path
        
        Used by modal file browser.
        """
        try:
            data = request.get_json() or {}
            file_path = data.get('file_path')
            
            if not file_path:
                return jsonify({'error': 'No file_path provided'}), 400
            
            # Convert to absolute path
            absolute_path = workspace_root / file_path
            if not absolute_path.exists():
                return jsonify({'error': f'File not found: {file_path}'}), 404
            
            metadata = player_manager.sequencer.load_audio(str(absolute_path))
            
            # Save timeline to viewed playlist
            _save_timeline_to_playlist(player_manager)
            
            logger.info(f"📂 Audio loaded: {os.path.basename(file_path)}")
            
            return jsonify({
                'success': True,
                'metadata': metadata
            })
        except Exception as e:
            logger.error(f"Error loading audio: {e}")
            return jsonify({'success': False, 'error': str(e)}), 400
    
    @app.route('/api/sequencer/audio/<path:file_path>', methods=['GET'])
    def sequencer_serve_audio(file_path):
        """Serve audio file to frontend
        
        Allows WaveSurfer.js to load audio from server after upload.
        Security: Only allow from configured sequencer audio dir or video/
        """
        try:
            # Construct full path (security check)
            # Check if path starts with audio_dir (with forward or backslash)
            audio_dir_fwd = audio_dir.replace('\\', '/')
            audio_dir_back = audio_dir.replace('/', '\\\\')
            if file_path.startswith(f'{audio_dir_fwd}/') or file_path.startswith(f'{audio_dir_back}\\\\'):
                full_path = workspace_root / file_path
            elif file_path.startswith('video/') or file_path.startswith('video\\'):
                full_path = workspace_root / file_path
            else:
                return jsonify({'error': 'Invalid path'}), 403
            
            if not full_path.exists():
                return jsonify({'error': 'File not found'}), 404
            
            return send_file(
                str(full_path),
                mimetype='audio/mpeg',  # Will auto-detect based on extension
                as_attachment=False
            )
        except Exception as e:
            logger.error(f"Error serving audio: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========================================
    # PLAYBACK CONTROL
    # ========================================
    
    @app.route('/api/sequencer/play', methods=['POST'])
    def sequencer_play():
        """Start sequencer playback and monitoring"""
        try:
            # Ensure sequencer mode is active before playing
            if not player_manager.sequencer_mode_active:
                player_manager.set_sequencer_mode(True)
                logger.info("🎵 Sequencer mode activated via play button")
            
            player_manager.sequencer.play()
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error starting playback: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/sequencer/pause', methods=['POST'])
    def sequencer_pause():
        """Pause sequencer playback"""
        try:
            player_manager.sequencer.pause()
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error pausing playback: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/sequencer/stop', methods=['POST'])
    def sequencer_stop():
        """Stop sequencer playback and reset"""
        try:
            player_manager.sequencer.stop()
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error stopping playback: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/sequencer/seek', methods=['POST'])
    def sequencer_seek():
        """Seek to position in audio"""
        try:
            data = request.get_json() or {}
            position = data.get('position', 0.0)
            
            player_manager.sequencer.seek(position)
            return jsonify({'success': True, 'position': position})
        except Exception as e:
            logger.error(f"Error seeking: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ========================================
    # SPLIT & TIMELINE MANAGEMENT
    # ========================================
    
    @app.route('/api/sequencer/split/add', methods=['POST'])
    def sequencer_add_split():
        """Add split point to timeline"""
        try:
            data = request.get_json() or {}
            time = data.get('time')
            
            if time is None:
                return jsonify({'error': 'No time provided'}), 400
            
            success = player_manager.sequencer.add_split(time)
            
            if success:
                # Save timeline to viewed playlist
                _save_timeline_to_playlist(player_manager)
                
                # Save session state to persist splits
                if session_state:
                    from .clip_registry import get_clip_registry
                    session_state.save_async(player_manager, get_clip_registry(), force=True)
                    logger.debug("💾 Session state saved after split add")
                
                # Return updated timeline
                timeline = player_manager.sequencer.get_timeline_data()
                return jsonify({
                    'success': True,
                    'timeline': timeline
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Split rejected (too close to existing split or boundary)'
                })
        except Exception as e:
            logger.error(f"Error adding split: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/sequencer/split/remove', methods=['POST'])
    def sequencer_remove_split():
        """Remove split point from timeline"""
        try:
            data = request.get_json() or {}
            time = data.get('time')
            
            if time is None:
                return jsonify({'error': 'No time provided'}), 400
            
            success = player_manager.sequencer.remove_split(time)
            
            if success:
                # Save timeline to viewed playlist
                _save_timeline_to_playlist(player_manager)
                
                # Save session state to persist splits
                if session_state:
                    from .clip_registry import get_clip_registry
                    session_state.save_async(player_manager, get_clip_registry(), force=True)
                    logger.debug("💾 Session state saved after split remove")
                
                # Return updated timeline
                timeline = player_manager.sequencer.get_timeline_data()
                return jsonify({
                    'success': True,
                    'timeline': timeline
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Split not found'
                })
        except Exception as e:
            logger.error(f"Error removing split: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/sequencer/timeline', methods=['GET'])
    def sequencer_get_timeline():
        """Get timeline data (splits, slots, clip mappings)"""
        try:
            timeline = player_manager.sequencer.get_timeline_data()
            return jsonify(timeline)
        except Exception as e:
            logger.error(f"Error getting timeline: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/sequencer/clip-mapping', methods=['POST'])
    def sequencer_set_clip_mapping():
        """Map slot to clip name"""
        try:
            data = request.get_json() or {}
            slot_index = data.get('slot_index')
            clip_name = data.get('clip_name')
            
            if slot_index is None or clip_name is None:
                return jsonify({'error': 'Missing slot_index or clip_name'}), 400
            
            player_manager.sequencer.set_clip_mapping(slot_index, clip_name)
            
            # Save timeline to viewed playlist
            _save_timeline_to_playlist(player_manager)
            
            # Save session state to persist clip mappings
            if session_state:
                from .clip_registry import get_clip_registry
                session_state.save_async(player_manager, get_clip_registry(), force=True)
                logger.debug("💾 Session state saved after clip mapping")
            
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error setting clip mapping: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ========================================
    # TIMELINE SAVE/LOAD
    # ========================================
    
    @app.route('/api/sequencer/save', methods=['POST'])
    def sequencer_save_timeline():
        """Save timeline to file"""
        try:
            data = request.get_json() or {}
            file_path = data.get('file_path', 'data/sequencer/timeline.json')
            
            player_manager.sequencer.timeline.save(file_path)
            
            logger.info(f"💾 Timeline saved: {file_path}")
            
            return jsonify({'success': True, 'path': file_path})
        except Exception as e:
            logger.error(f"Error saving timeline: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/sequencer/load-timeline', methods=['POST'])
    def sequencer_load_timeline():
        """Load timeline from file"""
        try:
            data = request.get_json() or {}
            file_path = data.get('file_path', 'data/sequencer/timeline.json')
            
            player_manager.sequencer.timeline.load(file_path)
            timeline = player_manager.sequencer.get_timeline_data()
            
            logger.info(f"📂 Timeline loaded: {file_path}")
            
            return jsonify({
                'success': True,
                'timeline': timeline
            })
        except Exception as e:
            logger.error(f"Error loading timeline: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
