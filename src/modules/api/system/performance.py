"""
Performance Monitoring API - Provides real-time performance metrics.
"""
from flask import jsonify, request
from ...performance.profiler import get_all_profilers
from ...core.logger import get_logger

logger = get_logger(__name__)


def register_performance_routes(app, player_manager):
    """Register performance monitoring API routes."""
    
    @app.route('/api/performance/metrics', methods=['GET'])
    def get_performance_metrics():
        """
        Get performance metrics for all players.
        
        Returns comprehensive profiling data for the entire rendering pipeline.
        """
        try:
            profilers = get_all_profilers()
            
            metrics = {}
            for player_name, profiler in profilers.items():
                metrics[player_name] = profiler.get_metrics()
            
            return jsonify({
                'success': True,
                'metrics': metrics,
                'players': list(metrics.keys())
            })
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/performance/reset', methods=['POST'])
    def reset_performance_metrics():
        """Reset performance metrics for all players."""
        try:
            data = request.get_json() or {}
            player_name = data.get('player')
            
            profilers = get_all_profilers()
            
            if player_name:
                # Reset specific player
                if player_name in profilers:
                    profilers[player_name].reset()
                    return jsonify({
                        'success': True,
                        'message': f'Reset metrics for {player_name}'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'Player {player_name} not found'
                    }), 404
            else:
                # Reset all players
                for profiler in profilers.values():
                    profiler.reset()
                return jsonify({
                    'success': True,
                    'message': 'Reset metrics for all players'
                })
        except Exception as e:
            logger.error(f"Failed to reset performance metrics: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/performance/toggle', methods=['POST'])
    def toggle_performance_profiling():
        """Enable or disable performance profiling."""
        try:
            data = request.get_json() or {}
            enabled = data.get('enabled', True)
            player_name = data.get('player')
            
            profilers = get_all_profilers()
            
            if player_name:
                # Toggle specific player
                if player_name in profilers:
                    if enabled:
                        profilers[player_name].enable()
                    else:
                        profilers[player_name].disable()
                    return jsonify({
                        'success': True,
                        'enabled': enabled,
                        'player': player_name
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'Player {player_name} not found'
                    }), 404
            else:
                # Toggle all players
                for profiler in profilers.values():
                    if enabled:
                        profiler.enable()
                    else:
                        profiler.disable()
                return jsonify({
                    'success': True,
                    'enabled': enabled,
                    'players': list(profilers.keys())
                })
        except Exception as e:
            logger.error(f"Failed to toggle performance profiling: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
