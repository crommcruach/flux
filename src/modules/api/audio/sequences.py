"""
Sequence API Routes

REST API endpoints for Dynamic Parameter Sequences.
"""

from flask import jsonify, request
import logging
import threading
from ...core.logger import get_logger
from ...session.state import get_session_state
from ...player.clips.registry import get_clip_registry

logger = get_logger(__name__)


def register_sequence_routes(app, sequence_manager, audio_analyzer, player_manager, socketio=None):
    """
    Register sequence management API routes
    
    Args:
        app: Flask application
        sequence_manager: SequenceManager instance
        audio_analyzer: AudioAnalyzer instance
        player_manager: PlayerManager instance for session state saving
        socketio: SocketIO instance for audio feature streaming
    """
    
    # Audio feature streaming thread
    _streaming_thread = None
    _streaming_active = False
    
    def audio_feature_streamer():
        """Background thread that emits audio features via WebSocket"""
        import time
        nonlocal _streaming_active
        
        logger.debug("Audio feature streaming thread started")
        
        while _streaming_active:
            try:
                if audio_analyzer and audio_analyzer.is_running() and socketio:
                    features = audio_analyzer.get_features()
                    # Emit to all connected clients
                    socketio.emit('audio_features', {
                        'features': features,
                        'running': True
                    })
                
                # Stream at ~40 FPS for smooth visualization
                time.sleep(0.025)
            except Exception as e:
                logger.error(f"Error in audio streaming: {e}")
                time.sleep(0.1)
        
        logger.debug("Audio feature streaming thread stopped")
    
    def start_audio_streaming():
        """Start the audio feature streaming thread"""
        nonlocal _streaming_thread, _streaming_active
        
        if _streaming_thread and _streaming_thread.is_alive():
            return
        
        _streaming_active = True
        _streaming_thread = threading.Thread(target=audio_feature_streamer, daemon=True)
        _streaming_thread.start()
        logger.debug("Audio feature streaming started")
    
    def stop_audio_streaming():
        """Stop the audio feature streaming thread"""
        nonlocal _streaming_thread, _streaming_active
        
        _streaming_active = False
        if _streaming_thread:
            _streaming_thread.join(timeout=1.0)
            _streaming_thread = None
        logger.debug("Audio feature streaming stopped")
    
    # Start streaming if SocketIO is available
    if socketio:
        import atexit
        start_audio_streaming()
        atexit.register(stop_audio_streaming)
    
    @app.route('/api/sequences', methods=['GET'])
    def get_sequences():
        """Get all sequences"""
        try:
            sequences = sequence_manager.get_all()
            return jsonify({
                'sequences': [seq.serialize() for seq in sequences],
                'count': len(sequences)
            })
        except Exception as e:
            logger.error(f"Error getting sequences: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/sequences/<sequence_id>', methods=['GET'])
    def get_sequence(sequence_id):
        """Get sequence by ID"""
        try:
            sequence = sequence_manager.get(sequence_id)
            if not sequence:
                return jsonify({'error': 'Sequence not found'}), 404
            
            return jsonify(sequence.serialize())
        except Exception as e:
            logger.error(f"Error getting sequence {sequence_id}: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/sequences', methods=['POST'])
    def create_sequence():
        """Create a new sequence"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            seq_type = data.get('type')
            target = data.get('target_parameter')
            config = data.get('config', {})
            
            if not seq_type or not target:
                return jsonify({'error': 'Missing type or target_parameter'}), 400
            
            # Import sequence classes
            from modules.audio.sequences.audio import AudioSequence
            from modules.audio.sequences.lfo import LFOSequence
            from modules.audio.sequences.timeline import TimelineSequence
            from modules.audio.sequences.bpm import BPMSequence
            
            # Create sequence based on type
            if seq_type == 'audio':
                # Map frontend direction names to backend mode names (for backward compatibility)
                mode_mapping = {
                    'rise-from-min': 'rise-from-min',
                    'rise-from-max': 'rise-from-max',
                    'beat-forward': 'beat-forward',
                    'beat-backward': 'beat-backward',
                    # Legacy mappings
                    'raise': 'rise-from-min',
                    'lower': 'rise-from-max',
                    'attack_release': 'rise-from-min',
                    'inverted_attack_release': 'rise-from-max'
                }
                raw_mode = config.get('mode', config.get('direction', 'rise-from-min'))
                mode = mode_mapping.get(raw_mode, 'rise-from-min')
                
                # Log received config for debugging
                logger.info(f"🎵 Creating AudioSequence: raw_mode={raw_mode}, mapped_mode={mode}, band={config.get('band')}, config={config}")
                
                sequence = AudioSequence(
                    sequence_id=data.get('id'),
                    target_parameter=target,
                    audio_analyzer=audio_analyzer,
                    feature=config.get('feature', 'rms'),
                    min_value=config.get('min_value', 0.0),
                    max_value=config.get('max_value', 1.0),
                    smoothing=config.get('smoothing', 0.1),
                    invert=config.get('invert', False),
                    band=config.get('band', 'bass'),
                    mode=mode,
                    attack_release=config.get('attack_release', 0.5)
                )
            
            elif seq_type == 'lfo':
                sequence = LFOSequence(
                    sequence_id=data.get('id'),
                    target_parameter=target,
                    waveform=config.get('waveform', 'sine'),
                    frequency=config.get('frequency', 1.0),
                    amplitude=config.get('amplitude', 1.0),
                    offset=config.get('offset', 0.0),
                    phase=config.get('phase', 0.0),
                    min_value=config.get('min_value', 0.0),
                    max_value=config.get('max_value', 1.0)
                )
            
            elif seq_type == 'timeline':
                sequence = TimelineSequence(
                    sequence_id=data.get('id'),
                    target_parameter=target,
                    loop_mode=config.get('loop_mode', 'once'),
                    duration=config.get('duration', 5.0),
                    playback_state=config.get('playback_state', 'pause'),
                    speed=config.get('speed', 1.0),
                    min_value=config.get('min_value', 0.0),
                    max_value=config.get('max_value', 100.0)
                )
            
            elif seq_type == 'bpm':
                sequence = BPMSequence(
                    sequence_id=data.get('id'),
                    target_parameter=target,
                    audio_analyzer=audio_analyzer,
                    beat_division=config.get('beat_division', 8),
                    clip_duration=config.get('clip_duration', 10.0),
                    playback_state=config.get('playback_state', 'forward'),
                    loop_mode=config.get('loop_mode', 'loop'),
                    speed=config.get('speed', 1.0),
                    min_value=config.get('min_value', 0.0),
                    max_value=config.get('max_value', 100.0)
                )
            
            else:
                return jsonify({'error': f'Unknown sequence type: {seq_type}'}), 400
            
            # Remove any existing sequences for this parameter (only one sequence per parameter allowed)
            # IMPORTANT: Also check for sequences with similar UIDs in case of format changes or typos
            # Parse the target UID to extract key components
            existing_sequences = []
            target_clip_id = None
            target_effect_idx = None
            target_param_name = None
            
            # Try to parse the target UID to get components
            if target.startswith('param_clip_'):
                parts = target.split('_')
                try:
                    if 'effect' in parts:
                        clip_idx = parts.index('clip') + 1
                        effect_idx_pos = parts.index('effect') + 1
                        # Reconstruct clip UUID (might contain hyphens)
                        clip_end = effect_idx_pos - 1
                        target_clip_id = '_'.join(parts[clip_idx:clip_end])
                        target_effect_idx = int(parts[effect_idx_pos])
                        target_param_name = '_'.join(parts[effect_idx_pos + 1:])
                except (ValueError, IndexError) as e:
                    logger.warning(f"Could not parse target UID {target}: {e}")
            
            # Find existing sequences by exact match OR by matching clip_id + effect_idx + param_name
            for s in sequence_manager.get_all():
                if s.target_parameter == target:
                    # Exact match
                    existing_sequences.append(s)
                elif target_clip_id and target_effect_idx is not None and target_param_name:
                    # Check if this sequence targets the same parameter even with different UID format
                    s_uid = s.target_parameter
                    if s_uid.startswith('param_clip_'):
                        s_parts = s_uid.split('_')
                        try:
                            if 'effect' in s_parts:
                                s_clip_idx = s_parts.index('clip') + 1
                                s_effect_idx_pos = s_parts.index('effect') + 1
                                s_clip_end = s_effect_idx_pos - 1
                                s_clip_id = '_'.join(s_parts[s_clip_idx:s_clip_end])
                                s_effect_idx = int(s_parts[s_effect_idx_pos])
                                s_param_name = '_'.join(s_parts[s_effect_idx_pos + 1:])
                                
                                # Match if all components are identical
                                if (s_clip_id == target_clip_id and 
                                    s_effect_idx == target_effect_idx and 
                                    s_param_name == target_param_name):
                                    existing_sequences.append(s)
                                    logger.info(f"🔍 Found sequence with different UID format: {s_uid} -> matches {target}")
                        except (ValueError, IndexError):
                            pass
            
            if existing_sequences:
                logger.info(f"🗑️ Removing {len(existing_sequences)} existing sequence(s) for {target}")
                for existing_seq in existing_sequences:
                    logger.debug(f"   Deleting: {existing_seq.id} (UID: {existing_seq.target_parameter})")
                    sequence_manager.delete(existing_seq.id)
            
            # Parse UID to extract clip_id, effect_index, layer_index
            # Expected formats:
            # - param_clip_{clip_id}_effect_{effect_index}_{param_name}
            # - param_clip_{clip_id}_layer_{layer_idx}_effect_{effect_idx}_{param_name}
            clip_id = None
            effect_index = None
            layer_index = None
            param_name = None
            
            if target.startswith('param_clip_'):
                parts = target.split('_')
                try:
                    if 'layer' in parts:
                        # Layer-level effect: param_clip_{clip}_layer_{layer}_effect_{effect}_{param}
                        clip_idx = parts.index('clip') + 1
                        layer_idx_pos = parts.index('layer') + 1
                        effect_idx_pos = parts.index('effect') + 1
                        
                        clip_id = '_'.join(parts[clip_idx:layer_idx_pos-1])  # Reconstruct UUID
                        layer_index = int(parts[layer_idx_pos])
                        effect_index = int(parts[effect_idx_pos])
                        param_name = '_'.join(parts[effect_idx_pos+1:])
                    elif 'effect' in parts:
                        # Clip-level effect: param_clip_{clip}_effect_{effect}_{param}
                        clip_idx = parts.index('clip') + 1
                        effect_idx_pos = parts.index('effect') + 1
                        
                        clip_id = '_'.join(parts[clip_idx:effect_idx_pos-1])  # Reconstruct UUID
                        effect_index = int(parts[effect_idx_pos])
                        param_name = '_'.join(parts[effect_idx_pos+1:])
                except (ValueError, IndexError) as e:
                    logger.warning(f"Could not parse new UID format: {target}, error: {e}")
            
            # Store sequence config in clip_registry (NEW ARCHITECTURE)
            if clip_id and effect_index is not None and param_name:
                clip_registry = get_clip_registry()
                sequence_config = {
                    'sequence_id': sequence.id,
                    'type': seq_type,
                    'enabled': True,
                    **config  # Include all config parameters
                }
                
                success = clip_registry.add_sequence_to_effect(
                    clip_id, 
                    effect_index, 
                    param_name, 
                    sequence_config,
                    layer_index
                )
                
                if success:
                    logger.info(f"📦 Stored sequence in clip_registry: clip {clip_id[:8]}..., effect {effect_index}, param {param_name}")
                else:
                    logger.warning(f"⚠️ Could not store sequence in clip_registry (clip or effect not found)")
            else:
                logger.warning(f"⚠️ Could not parse UID to store in clip_registry: {target}")
            
            # Add to manager (for immediate activation)
            sequence_id = sequence_manager.create(sequence)
            logger.info(f"✅ Created sequence: {sequence_id} ({seq_type}) -> {target}")
            
            # Save session state to persist sequences
            session_state = get_session_state()
            logger.info(f"💾 Saving session state with {len(sequence_manager.sequences)} sequences...")
            session_state.save_async(player_manager, get_clip_registry(), force=True)
            logger.info(f"✅ Session state saved successfully")
            
            return jsonify({
                'message': 'Sequence created successfully',
                'sequence': sequence.serialize()
            }), 201
        
        except Exception as e:
            logger.error(f"Error creating sequence: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/sequences/<sequence_id>', methods=['PUT'])
    def update_sequence(sequence_id):
        """Update sequence configuration"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            sequence = sequence_manager.get(sequence_id)
            if not sequence:
                return jsonify({'error': 'Sequence not found'}), 404
            
            # Update sequence properties
            config = data.get('config', {})
            
            # Log the received config for debugging
            logger.info(f"📝 Updating sequence {sequence_id} with config: {config}")
            
            # Handle BPM-specific updates with proper setters
            if sequence.type == 'bpm':
                if 'beat_division' in config:
                    sequence.set_beat_division(config['beat_division'])
                if 'playback_state' in config:
                    sequence.set_playback_state(config['playback_state'])
                if 'loop_mode' in config:
                    sequence.set_loop_mode(config['loop_mode'])
                if 'speed' in config:
                    sequence.set_speed(config['speed'])
                # Handle other properties generically
                for key, value in config.items():
                    if key not in ['beat_division', 'playback_state', 'loop_mode', 'speed'] and hasattr(sequence, key):
                        setattr(sequence, key, value)
            else:
                # Generic update for other sequence types
                for key, value in config.items():
                    if hasattr(sequence, key):
                        setattr(sequence, key, value)
            
            # Save session state to persist changes
            session_state = get_session_state()
            session_state.save_async(player_manager, get_clip_registry(), force=True)
            
            logger.info(f"Updated sequence: {sequence_id}")
            return jsonify({
                'message': 'Sequence updated successfully',
                'sequence': sequence.serialize()
            })
        
        except Exception as e:
            logger.error(f"Error updating sequence {sequence_id}: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/sequences/<sequence_id>', methods=['DELETE'])
    def delete_sequence(sequence_id):
        """Delete a sequence"""
        try:
            # Get sequence info before deletion for cleanup
            sequence = sequence_manager.get(sequence_id)
            if not sequence:
                return jsonify({'error': 'Sequence not found'}), 404
            
            target_parameter = sequence.target_parameter
            
            # Parse UID to remove from clip_registry
            clip_id = None
            effect_index = None
            layer_index = None
            param_name = None
            
            if target_parameter.startswith('param_clip_'):
                parts = target_parameter.split('_')
                try:
                    if 'layer' in parts:
                        clip_idx = parts.index('clip') + 1
                        layer_idx_pos = parts.index('layer') + 1
                        effect_idx_pos = parts.index('effect') + 1
                        
                        clip_id = '_'.join(parts[clip_idx:layer_idx_pos-1])
                        layer_index = int(parts[layer_idx_pos])
                        effect_index = int(parts[effect_idx_pos])
                        param_name = '_'.join(parts[effect_idx_pos+1:])
                    elif 'effect' in parts:
                        clip_idx = parts.index('clip') + 1
                        effect_idx_pos = parts.index('effect') + 1
                        
                        clip_id = '_'.join(parts[clip_idx:effect_idx_pos-1])
                        effect_index = int(parts[effect_idx_pos])
                        param_name = '_'.join(parts[effect_idx_pos+1:])
                except (ValueError, IndexError) as e:
                    logger.warning(f"Could not parse UID for deletion: {target_parameter}, error: {e}")
            
            # Remove from clip_registry (NEW ARCHITECTURE)
            if clip_id and effect_index is not None and param_name:
                clip_registry = get_clip_registry()
                clip_registry.remove_sequence_from_effect(clip_id, effect_index, param_name, layer_index)
                logger.debug(f"Removed sequence from clip_registry: clip {clip_id[:8]}..., effect {effect_index}, param {param_name}")
            
            # Delete the sequence from active pool
            success = sequence_manager.delete(sequence_id)
            
            if not success:
                return jsonify({'error': 'Failed to delete sequence'}), 500
            
            # Save session state to persist deletion
            session_state = get_session_state()
            session_state.save_async(player_manager, get_clip_registry(), force=True)
            
            # Notify all clients that sequence was deleted
            socketio.emit('sequence_deleted', {
                'sequence_id': sequence_id,
                'parameter': target_parameter
            })
            
            logger.info(f"Deleted sequence: {sequence_id} (target: {target_parameter})")
            return jsonify({'message': 'Sequence deleted successfully'})
        
        except Exception as e:
            logger.error(f"Error deleting sequence {sequence_id}: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/sequences/<sequence_id>/toggle', methods=['POST'])
    def toggle_sequence(sequence_id):
        """Toggle sequence enabled state"""
        try:
            enabled = sequence_manager.toggle(sequence_id)
            
            if enabled is None:
                return jsonify({'error': 'Sequence not found'}), 404
            
            logger.info(f"Toggled sequence {sequence_id}: enabled={enabled}")
            return jsonify({
                'message': 'Sequence toggled successfully',
                'enabled': enabled
            })
        
        except Exception as e:
            logger.error(f"Error toggling sequence {sequence_id}: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/sequences/target/<path:target_parameter>', methods=['GET'])
    def get_sequences_by_target(target_parameter):
        """Get all sequences for a specific parameter"""
        try:
            sequences = sequence_manager.get_by_target(target_parameter)
            return jsonify({
                'target_parameter': target_parameter,
                'sequences': [seq.serialize() for seq in sequences],
                'count': len(sequences)
            })
        except Exception as e:
            logger.error(f"Error getting sequences for target: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    # Audio Analyzer Routes
    
    @app.route('/api/audio/devices', methods=['GET'])
    def get_audio_devices():
        """List available audio input devices"""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            # Filter for input devices and format response
            input_devices = []
            for idx, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    input_devices.append({
                        'index': idx,
                        'name': device['name'],
                        'channels': device['max_input_channels'],
                        'default_samplerate': device['default_samplerate']
                    })
            return jsonify({'devices': input_devices})
        except Exception as e:
            logger.error(f"Error listing audio devices: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/audio/start', methods=['POST'])
    def start_audio_analyzer():
        """Start audio analyzer"""
        try:
            # Use silent=True to avoid errors with missing Content-Type header
            data = request.get_json(silent=True) or {}
            device = data.get('device') if data else None
            source = data.get('source') if data else None
            
            if device is not None:
                audio_analyzer.set_device(device)
                logger.info(f"Audio device set to: {device}")
            
            # Set audio source if provided
            if source:
                audio_analyzer.config['audio_source'] = source
                logger.info(f"Audio source set to: {source}")
            
            # Start the analyzer (this now has comprehensive error handling)
            audio_analyzer.start()
            
            # Verify it started successfully
            if not audio_analyzer._running:
                # If still not running after start() completes, it should have raised an error
                # but just in case, provide a fallback message
                raise RuntimeError("Audio analyzer failed to start. Check logs for details.")
            
            logger.info(f"Audio analyzer started successfully: device={device}, source={source}")
            return jsonify({'message': 'Audio analyzer started successfully'})
        except RuntimeError as e:
            # Expected errors from start() method
            logger.error(f"Could not start audio analyzer: {e}")
            return jsonify({'error': str(e)}), 500
        except Exception as e:
            logger.error(f"Unexpected error starting audio analyzer: {e}", exc_info=True)
            return jsonify({'error': f'Unexpected error: {str(e)}'}), 500
    
    @app.route('/api/audio/stop', methods=['POST'])
    def stop_audio_analyzer():
        """Stop audio analyzer"""
        try:
            audio_analyzer.stop()
            logger.info("Audio analyzer stopped")
            return jsonify({'message': 'Audio analyzer stopped successfully'})
        except Exception as e:
            logger.error(f"Error stopping audio analyzer: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/audio/features', methods=['GET'])
    def get_audio_features():
        """Get current audio features"""
        try:
            features = audio_analyzer.get_features()
            return jsonify({
                'features': features,
                'running': audio_analyzer.is_running()
            })
        except Exception as e:
            logger.error(f"Error getting audio features: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/audio/gain', methods=['POST'])
    def set_audio_gain():
        """Set audio gain"""
        try:
            data = request.get_json(silent=True) or {}
            gain = data.get('gain', 1.0)
            
            # Store gain in audio analyzer config
            audio_analyzer.config['gain'] = float(gain)
            logger.info(f"Audio gain set to: {gain}")
            
            return jsonify({'message': 'Audio gain updated', 'gain': gain})
        except Exception as e:
            logger.error(f"Error setting audio gain: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/audio/config', methods=['POST'])
    def set_audio_config():
        """Set audio analyzer configuration"""
        try:
            data = request.get_json(silent=True) or {}
            
            # Update config with provided values
            if 'gain' in data:
                audio_analyzer.config['gain'] = float(data['gain'])
            if 'device' in data:
                audio_analyzer.config['device'] = data['device']
            if 'deviceName' in data:
                audio_analyzer.config['deviceName'] = data['deviceName']
            if 'beat_sensitivity' in data:
                audio_analyzer.config['beat_sensitivity'] = float(data['beat_sensitivity'])
                logger.info(f"Beat sensitivity set to: {data['beat_sensitivity']}")
            
            logger.info(f"Audio config updated: {data}")
            return jsonify({'message': 'Audio config updated', 'config': audio_analyzer.config})
        except Exception as e:
            logger.error(f"Error setting audio config: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/audio/status', methods=['GET'])
    def get_audio_status():
        """Get audio analyzer status"""
        try:
            return jsonify({
                'running': audio_analyzer.is_running(),
                'device': audio_analyzer.device,
                'sample_rate': audio_analyzer.sample_rate
            })
        except Exception as e:
            logger.error(f"Error getting audio status: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    logger.debug("Sequence API routes registered")
