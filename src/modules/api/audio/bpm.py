"""
BPM Detection API
REST endpoints for BPM detection control
"""

from flask import Blueprint, jsonify, request
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Create blueprint
bpm_bp = Blueprint('bpm', __name__)

# Global reference to audio analyzer (will be set by main.py)
_audio_analyzer = None
_sequence_manager = None


def set_audio_analyzer(analyzer):
    """Set the audio analyzer instance"""
    global _audio_analyzer
    _audio_analyzer = analyzer


def set_sequence_manager(manager):
    """Set the sequence manager instance"""
    global _sequence_manager
    _sequence_manager = manager


@bpm_bp.route('/api/bpm/start', methods=['POST'])
def start_bpm_detection():
    """Enable BPM detection"""
    try:
        if _audio_analyzer is None:
            return jsonify({'success': False, 'error': 'Audio analyzer not initialized'}), 500
        
        _audio_analyzer.enable_bpm_detection(True)
        
        # Start audio analyzer if not running
        if not _audio_analyzer.is_running():
            _audio_analyzer.start()
        
        return jsonify({
            'success': True,
            'status': _audio_analyzer.get_bpm_status()
        })
    
    except Exception as e:
        logger.error(f"Error starting BPM detection: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bpm_bp.route('/api/bpm/pause', methods=['POST'])
def pause_bpm_detection():
    """Pause BPM detection (keep running but don't update)"""
    try:
        if _audio_analyzer is None:
            return jsonify({'success': False, 'error': 'Audio analyzer not initialized'}), 500
        
        _audio_analyzer.enable_bpm_detection(False)
        
        return jsonify({
            'success': True,
            'status': _audio_analyzer.get_bpm_status()
        })
    
    except Exception as e:
        logger.error(f"Error pausing BPM detection: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bpm_bp.route('/api/bpm/stop', methods=['POST'])
def stop_bpm_detection():
    """Stop BPM detection and audio analyzer"""
    try:
        if _audio_analyzer is None:
            return jsonify({'success': False, 'error': 'Audio analyzer not initialized'}), 500
        
        _audio_analyzer.enable_bpm_detection(False)
        _audio_analyzer.stop()
        
        return jsonify({
            'success': True,
            'status': _audio_analyzer.get_bpm_status()
        })
    
    except Exception as e:
        logger.error(f"Error stopping BPM detection: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bpm_bp.route('/api/bpm/manual', methods=['POST'])
def set_manual_bpm():
    """Set manual BPM value"""
    try:
        if _audio_analyzer is None:
            return jsonify({'success': False, 'error': 'Audio analyzer not initialized'}), 500
        
        data = request.get_json()
        bpm = data.get('bpm')
        
        if bpm is None:
            return jsonify({'success': False, 'error': 'BPM value required'}), 400
        
        try:
            bpm = float(bpm)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid BPM value'}), 400
        
        if not (20 <= bpm <= 300):
            return jsonify({'success': False, 'error': 'BPM must be between 20 and 300'}), 400
        
        _audio_analyzer.set_manual_bpm(bpm)
        
        return jsonify({
            'success': True,
            'status': _audio_analyzer.get_bpm_status()
        })
    
    except Exception as e:
        logger.error(f"Error setting manual BPM: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bpm_bp.route('/api/bpm/tap', methods=['POST'])
def tap_tempo():
    """Record a tap for tap tempo"""
    try:
        if _audio_analyzer is None:
            return jsonify({'success': False, 'error': 'Audio analyzer not initialized'}), 500
        
        bpm = _audio_analyzer.tap_tempo()
        status = _audio_analyzer.get_bpm_status()
        
        return jsonify({
            'success': True,
            'bpm': bpm,
            'tap_count': status['tap_count'],
            'status': status
        })
    
    except Exception as e:
        logger.error(f"Error in tap tempo: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bpm_bp.route('/api/bpm/resync', methods=['POST'])
def resync_bpm():
    """Resync all BPM sequences to current beat"""
    try:
        if _audio_analyzer is None:
            return jsonify({'success': False, 'error': 'Audio analyzer not initialized'}), 500
        
        if _sequence_manager is None:
            return jsonify({'success': False, 'error': 'Sequence manager not initialized'}), 500
        
        # Reset all BPM sequences to sync to current beat
        synced_count = 0
        for sequence in _sequence_manager.get_all():
            if sequence.type == 'bpm':
                sequence.reset()  # Reset to start from current beat
                synced_count += 1
                logger.info(f"Resynced BPM sequence: {sequence.id}")
        
        logger.info(f"🔄 Resynced {synced_count} BPM sequences to current beat")
        
        return jsonify({
            'success': True,
            'synced_count': synced_count,
            'status': _audio_analyzer.get_bpm_status()
        })
    
    except Exception as e:
        logger.error(f"Error resyncing BPM sequences: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bpm_bp.route('/api/bpm/status', methods=['GET'])
def get_bpm_status():
    """Get current BPM status"""
    try:
        if _audio_analyzer is None:
            return jsonify({'success': False, 'error': 'Audio analyzer not initialized'}), 500
        
        status = _audio_analyzer.get_bpm_status()
        
        return jsonify({
            'success': True,
            'status': status
        })
    
    except Exception as e:
        logger.error(f"Error getting BPM status: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
