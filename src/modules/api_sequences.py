"""
Sequence API Routes

REST API endpoints for Dynamic Parameter Sequences.
"""

from flask import jsonify, request
import logging
import threading
from .logger import get_logger
from .session_state import get_session_state
from .clip_registry import get_clip_registry

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
        
        logger.info("Audio feature streaming thread started")
        
        while _streaming_active:
            try:
                if audio_analyzer.is_running() and socketio:
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
        
        logger.info("Audio feature streaming thread stopped")
    
    def start_audio_streaming():
        """Start the audio feature streaming thread"""
        nonlocal _streaming_thread, _streaming_active
        
        if _streaming_thread and _streaming_thread.is_alive():
            return
        
        _streaming_active = True
        _streaming_thread = threading.Thread(target=audio_feature_streamer, daemon=True)
        _streaming_thread.start()
        logger.info("Audio feature streaming started")
    
    def stop_audio_streaming():
        """Stop the audio feature streaming thread"""
        nonlocal _streaming_thread, _streaming_active
        
        _streaming_active = False
        if _streaming_thread:
            _streaming_thread.join(timeout=1.0)
            _streaming_thread = None
        logger.info("Audio feature streaming stopped")
    
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
            from .sequences import AudioSequence, LFOSequence, TimelineSequence
            
            # Create sequence based on type
            if seq_type == 'audio':
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
                    direction=config.get('direction', 'rise_from_min'),
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
                    keyframes=config.get('keyframes', []),
                    interpolation=config.get('interpolation', 'linear'),
                    loop_mode=config.get('loop_mode', 'once'),
                    duration=config.get('duration', 10.0)
                )
            
            else:
                return jsonify({'error': f'Unknown sequence type: {seq_type}'}), 400
            
            # Add to manager
            sequence_id = sequence_manager.create(sequence)
            logger.info(f"✅ Created sequence: {sequence_id} ({seq_type}) -> {target}")
            
            # Save session state to persist sequences
            session_state = get_session_state()
            logger.info(f"💾 Saving session state with {len(sequence_manager.sequences)} sequences...")
            session_state.save(player_manager, get_clip_registry(), force=True)
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
            
            for key, value in config.items():
                if hasattr(sequence, key):
                    setattr(sequence, key, value)
            
            # Save session state to persist changes
            session_state = get_session_state()
            session_state.save(player_manager, get_clip_registry(), force=True)
            
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
            success = sequence_manager.delete(sequence_id)
            
            if not success:
                return jsonify({'error': 'Sequence not found'}), 404
            
            # Save session state to persist deletion
            session_state = get_session_state()
            session_state.save(player_manager, get_clip_registry(), force=True)
            
            logger.info(f"Deleted sequence: {sequence_id}")
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
            from .sequences import AudioAnalyzer
            devices = AudioAnalyzer.list_devices()
            return jsonify({'devices': devices})
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
            
            # Set audio source if provided
            if source:
                audio_analyzer.config['audio_source'] = source
                logger.info(f"Audio source set to: {source}")
            
            audio_analyzer.start()
            
            logger.info(f"Audio analyzer started: device={device}, source={source}")
            return jsonify({'message': 'Audio analyzer started successfully'})
        except Exception as e:
            logger.error(f"Error starting audio analyzer: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
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
    
    logger.info("Sequence API routes registered")
