"""
API endpoints for output routing system
Manages video outputs, slices, and monitor detection
"""

from flask import jsonify, request
import logging
import base64
import cv2
import time

from ...player.outputs.monitor_utils import get_available_monitors, get_monitor_by_index

logger = logging.getLogger(__name__)


def register_output_routes(app, player_manager):
    """Register output routing API endpoints"""
    
    # ========================================
    # Debug / Status
    # ========================================
    
    @app.route('/api/outputs/debug/status', methods=['GET'])
    def get_output_manager_status():
        """Debug endpoint to check output manager status"""
        try:
            video_player = player_manager.get_player('video')
            artnet_player = player_manager.get_player('artnet')
            
            status = {
                'video_player': {
                    'exists': video_player is not None,
                    'output_manager': video_player.output_manager is not None if video_player else False,
                    'player_name': video_player.player_name if video_player else None,
                    'enable_artnet': getattr(video_player, 'enable_artnet', None) if video_player else None
                },
                'artnet_player': {
                    'exists': artnet_player is not None,
                    'output_manager': artnet_player.output_manager is not None if artnet_player else False,
                    'player_name': artnet_player.player_name if artnet_player else None,
                    'enable_artnet': getattr(artnet_player, 'enable_artnet', None) if artnet_player else None
                }
            }
            
            # Try to import modules
            import_status = {}
            try:
                from .outputs import OutputManager
                import_status['OutputManager'] = 'OK'
            except Exception as e:
                import_status['OutputManager'] = f'FAILED: {e}'
            
            try:
                import cv2
                import_status['cv2'] = 'OK'
            except Exception as e:
                import_status['cv2'] = f'FAILED: {e}'
            
            try:
                import screeninfo
                import_status['screeninfo'] = 'OK'
            except Exception as e:
                import_status['screeninfo'] = f'FAILED: {e}'
            
            status['imports'] = import_status
            
            return jsonify({
                'success': True,
                'status': status
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # ========================================
    # Monitor Detection
    # ========================================
    
    @app.route('/api/monitors', methods=['GET'])
    def get_monitors():
        """Get available display monitors"""
        try:
            monitors = get_available_monitors()
            return jsonify({
                'success': True,
                'monitors': monitors,
                'count': len(monitors)
            })
        except Exception as e:
            logger.error(f"Failed to get monitors: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/outputs/types', methods=['GET'])
    def get_output_types():
        """Get available output types with their default configurations"""
        try:
            # Get monitors for display type
            monitors = get_available_monitors()
            
            output_types = {
                'display': {
                    'name': 'Display/Monitor',
                    'description': 'Physical display output (OpenCV window)',
                    'icon': '🖥️',
                    'requires_monitor': True,
                    'available_monitors': monitors,
                    'default_config': {
                        'type': 'display',
                        'source': 'canvas',
                        'slice': 'full',
                        'fullscreen': True,
                        'fps': 30
                    },
                    'configurable_fields': {
                        'monitor_index': {
                            'type': 'select',
                            'label': 'Monitor',
                            'options': [
                                {'value': i, 'label': f"{m['name']} ({m['width']}x{m['height']})"}
                                for i, m in enumerate(monitors)
                            ],
                            'required': True
                        },
                        'resolution': {
                            'type': 'resolution',
                            'label': 'Resolution',
                            'from_monitor': True,
                            'required': False
                        },
                        'fullscreen': {
                            'type': 'checkbox',
                            'label': 'Fullscreen',
                            'default': True
                        },
                        'window_title': {
                            'type': 'text',
                            'label': 'Window Title',
                            'default': 'Flux Output'
                        }
                    }
                },
                'virtual': {
                    'name': 'Virtual Output',
                    'description': 'Memory-only output for preview/testing (no display)',
                    'icon': '💾',
                    'requires_monitor': False,
                    'default_config': {
                        'type': 'virtual',
                        'source': 'canvas',
                        'slice': 'full',
                        'resolution': [1920, 1080],
                        'fps': 30
                    },
                    'configurable_fields': {
                        'name': {
                            'type': 'text',
                            'label': 'Name',
                            'default': 'Virtual Output',
                            'required': True
                        },
                        'resolution': {
                            'type': 'resolution',
                            'label': 'Resolution',
                            'presets': [
                                {'value': [3840, 2160], 'label': '4K (3840x2160)'},
                                {'value': [2560, 1440], 'label': '1440p (2560x1440)'},
                                {'value': [1920, 1080], 'label': '1080p (1920x1080)'},
                                {'value': [1280, 720], 'label': '720p (1280x720)'},
                                {'value': [640, 360], 'label': '360p (640x360)'}
                            ],
                            'custom': True,
                            'required': True
                        }
                    }
                },
                'ndi': {
                    'name': 'NDI Network',
                    'description': 'NDI network video output (requires NDI library)',
                    'icon': '📡',
                    'requires_monitor': False,
                    'available': False,
                    'reason': 'NDI library not installed',
                    'default_config': {
                        'type': 'ndi',
                        'source': 'canvas',
                        'slice': 'full',
                        'resolution': [1920, 1080],
                        'fps': 30
                    },
                    'configurable_fields': {
                        'ndi_name': {
                            'type': 'text',
                            'label': 'NDI Source Name',
                            'default': 'Flux NDI Output',
                            'required': True
                        },
                        'resolution': {
                            'type': 'resolution',
                            'label': 'Resolution',
                            'presets': [
                                {'value': [1920, 1080], 'label': '1080p (1920x1080)'},
                                {'value': [1280, 720], 'label': '720p (1280x720)'}
                            ],
                            'required': True
                        }
                    }
                },
                'spout': {
                    'name': 'Spout GPU',
                    'description': 'Spout GPU texture sharing (Windows only)',
                    'icon': '🎨',
                    'requires_monitor': False,
                    'available': False,
                    'reason': 'Spout library not installed or not on Windows',
                    'default_config': {
                        'type': 'spout',
                        'source': 'canvas',
                        'slice': 'full',
                        'resolution': [1920, 1080],
                        'fps': 60
                    },
                    'configurable_fields': {
                        'spout_name': {
                            'type': 'text',
                            'label': 'Spout Sender Name',
                            'default': 'Flux Spout Output',
                            'required': True
                        },
                        'resolution': {
                            'type': 'resolution',
                            'label': 'Resolution',
                            'presets': [
                                {'value': [1920, 1080], 'label': '1080p (1920x1080)'},
                                {'value': [1280, 720], 'label': '720p (1280x720)'}
                            ],
                            'required': True
                        }
                    }
                }
            }
            
            return jsonify({
                'success': True,
                'types': output_types
            })
        
        except Exception as e:
            logger.error(f"Failed to get output types: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # ========================================
    # Output Management
    # ========================================
    
    @app.route('/api/outputs/<player>', methods=['GET'])
    def get_outputs(player):
        """Get all outputs for player (video/artnet)"""
        try:
            player_obj = player_manager.get_player(player)
            if not player_obj:
                return jsonify({
                    'success': False,
                    'error': f'Player {player} not found'
                }), 404
            
            if not hasattr(player_obj, 'output_manager') or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            state = player_obj.output_manager.get_state()
            
            return jsonify({
                'success': True,
                'outputs': state['outputs'],
                'enabled_outputs': state['enabled_outputs']
            })
        
        except Exception as e:
            logger.error(f"Failed to get outputs: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/outputs/<player>/<output_id>/enable', methods=['POST'])
    def enable_output(player, output_id):
        """Enable specific output"""
        try:
            player_obj = player_manager.get_player(player)
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            success = player_obj.output_manager.enable_output(output_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Output {output_id} enabled'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to enable output {output_id}'
                }), 400
        
        except Exception as e:
            logger.error(f"Failed to enable output: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/outputs/<player>/<output_id>/disable', methods=['POST'])
    def disable_output(player, output_id):
        """Disable specific output"""
        try:
            player_obj = player_manager.get_player(player)
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            success = player_obj.output_manager.disable_output(output_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Output {output_id} disabled'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to disable output {output_id}'
                }), 400
        
        except Exception as e:
            logger.error(f"Failed to disable output: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/outputs/<player>', methods=['POST'])
    def create_output(player):
        """Create a new output dynamically"""
        try:
            data = request.get_json()
            
            # Required fields
            output_id = data.get('output_id')
            
            # Config can be at top level or in 'config' object
            config = data.get('config', {})
            output_type = config.get('type') or data.get('type', 'virtual')
            
            if not output_id:
                return jsonify({
                    'success': False,
                    'error': 'Missing output_id'
                }), 400
            
            logger.info(f"📦 Creating output '{output_id}' of type '{output_type}' with config: {config}")
            
            player_obj = player_manager.get_player(player)
            if not player_obj:
                logger.error(f"Player '{player}' not found. Available players: {list(player_manager.players.keys())}")
                return jsonify({
                    'success': False,
                    'error': f'Player "{player}" not found'
                }), 404
            
            if not player_obj.output_manager:
                logger.error(f"Output manager not available for player '{player}'. Output manager is None. Check if opencv-python and screeninfo are installed.")
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available. Make sure opencv-python and screeninfo are installed.'
                }), 404
            
            # Check if output already exists
            if output_id in player_obj.output_manager.outputs:
                return jsonify({
                    'success': False,
                    'error': f'Output {output_id} already exists'
                }), 400
            
            # VALIDATION: Check for duplicate monitor usage (display outputs only)
            if output_type == 'display':
                monitor_index = config.get('monitor_index')
                if monitor_index is not None:
                    # Check if any existing output is using this monitor
                    for existing_id, existing_output in player_obj.output_manager.outputs.items():
                        if existing_output.config.get('type') == 'display':
                            if existing_output.config.get('monitor_index') == monitor_index:
                                return jsonify({
                                    'success': False,
                                    'error': f'Monitor {monitor_index} is already in use by output "{existing_id}"'
                                }), 400
            
            # Build output config from request config
            output_config = {
                'type': output_type,
                'source': config.get('source', 'canvas'),
                'slice': config.get('slice', 'full'),
                'resolution': config.get('resolution', [1920, 1080]),
                'fps': config.get('fps', 30),
                'enabled': config.get('enabled', False)
            }
            
            # Add type-specific fields
            if output_type == 'virtual':
                output_config['name'] = config.get('name', f'Virtual Output {output_id}')
            elif output_type == 'display':
                output_config['monitor_index'] = config.get('monitor_index', 0)
                output_config['fullscreen'] = config.get('fullscreen', True)
                output_config['window_title'] = config.get('window_title', f'Flux {output_id}')
                logger.info(f"🖥️ Display output config: monitor={output_config['monitor_index']}, fullscreen={output_config['fullscreen']}, title='{output_config['window_title']}'")
            
            # Create and register output
            from ...player.outputs.plugins import DisplayOutput, VirtualOutput
            
            logger.info(f"🏗️ Creating {output_type} output '{output_id}' with config: {output_config}")
            
            if output_type == 'virtual':
                output = VirtualOutput(output_id, output_config)
            elif output_type == 'display':
                output = DisplayOutput(output_id, output_config)
            else:
                return jsonify({
                    'success': False,
                    'error': f'Unsupported output type: {output_type}'
                }), 400
            
            logger.info(f"📝 Registering output '{output_id}'...")
            player_obj.output_manager.register_output(output_id, output)
            
            # Auto-enable display outputs to show window immediately
            if output_type == 'display' or output_config.get('enabled'):
                logger.info(f"⚡ Enabling output '{output_id}'...")
                success = player_obj.output_manager.enable_output(output_id)
                if not success:
                    logger.error(f"❌ Failed to enable output {output_id}")
                    return jsonify({
                        'success': False,
                        'error': f'Output created but failed to enable'
                    }), 500
                else:
                    logger.info(f"✅ Output {output_id} enabled and window opened")
            
            logger.info(f"🎉 Output '{output_id}' created successfully!")
            
            return jsonify({
                'success': True,
                'message': f'Output {output_id} created',
                'output_id': output_id,
                'config': output_config
            })
        
        except Exception as e:
            logger.error(f"Failed to create output: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/outputs/<player>/<output_id>', methods=['DELETE'])
    def delete_output(player, output_id):
        """Delete an output (all outputs are dynamic now)"""
        try:
            player_obj = player_manager.get_player(player)
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            success = player_obj.output_manager.unregister_output(output_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Output {output_id} deleted'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Output {output_id} not found'
                }), 404
        
        except Exception as e:
            logger.error(f"Failed to delete output: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/outputs/<player>/<output_id>/source', methods=['PUT'])
    def set_output_source(player, output_id):
        """Set output source (canvas/clip/layer)"""
        try:
            data = request.get_json()
            source = data.get('source')
            
            if not source:
                return jsonify({
                    'success': False,
                    'error': 'Missing source parameter'
                }), 400
            
            player_obj = player_manager.get_player(player)
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            success = player_obj.output_manager.set_output_source(output_id, source)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Output {output_id} source set to {source}'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to set source for output {output_id}'
                }), 400
        
        except Exception as e:
            logger.error(f"Failed to set output source: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/outputs/<player>/<output_id>/slice', methods=['PUT'])
    def set_output_slice(player, output_id):
        """Set slice for output"""
        try:
            data = request.get_json()
            slice_id = data.get('slice_id')
            
            if not slice_id:
                return jsonify({
                    'success': False,
                    'error': 'Missing slice_id parameter'
                }), 400
            
            player_obj = player_manager.get_player(player)
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            success = player_obj.output_manager.set_output_slice(output_id, slice_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Output {output_id} slice set to {slice_id}'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to set slice for output {output_id}'
                }), 400
        
        except Exception as e:
            logger.error(f"Failed to set output slice: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/outputs/<player>/<output_id>/composition', methods=['PUT'])
    def set_output_composition(player, output_id):
        """Set composition (multiple slices) for output"""
        try:
            data = request.get_json()
            composition = data.get('composition')
            
            if not composition:
                return jsonify({
                    'success': False,
                    'error': 'Missing composition parameter'
                }), 400
            
            player_obj = player_manager.get_player(player)
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            success = player_obj.output_manager.set_output_composition(output_id, composition)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Output {output_id} composition set with {len(composition.get("slices", []))} slices'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to set composition for output {output_id}'
                }), 400
        
        except Exception as e:
            logger.error(f"Failed to set output composition: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/outputs/<player>/statistics', methods=['GET'])
    def get_output_statistics(player):
        """Get output statistics"""
        try:
            player_obj = player_manager.get_player(player)
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            stats = player_obj.output_manager.get_statistics()
            
            return jsonify({
                'success': True,
                'statistics': stats
            })
        
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # ========================================
    # Slice Management
    # ========================================
    
    @app.route('/api/slices', methods=['GET'])
    def get_slices():
        """Get all slice definitions"""
        try:
            # Get from video player by default
            player_obj = player_manager.get_player('video')
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            slice_list = player_obj.output_manager.slice_manager.get_slice_list()
            
            return jsonify({
                'success': True,
                'slices': {s['id']: s for s in slice_list},
                'canvas': {
                    'width': player_obj.output_manager.canvas_width,
                    'height': player_obj.output_manager.canvas_height
                }
            })
        
        except Exception as e:
            logger.error(f"Failed to get slices: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/slices', methods=['POST'])
    def create_slice():
        """Create new slice definition"""
        try:
            data = request.get_json()
            
            # Required fields
            slice_id = data.get('slice_id')
            if not slice_id:
                return jsonify({
                    'success': False,
                    'error': 'Missing slice_id'
                }), 400
            
            player_obj = player_manager.get_player('video')
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            # Add slice
            player_obj.output_manager.add_slice(slice_id, data)
            
            return jsonify({
                'success': True,
                'message': f'Slice {slice_id} created'
            })
        
        except Exception as e:
            logger.error(f"Failed to create slice: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/slices/<slice_id>', methods=['PUT'])
    def update_slice(slice_id):
        """Update slice definition"""
        try:
            data = request.get_json()
            
            player_obj = player_manager.get_player('video')
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            # Update slice
            player_obj.output_manager.update_slice(slice_id, data)
            
            return jsonify({
                'success': True,
                'message': f'Slice {slice_id} updated'
            })
        
        except Exception as e:
            logger.error(f"Failed to update slice: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/slices/<slice_id>', methods=['DELETE'])
    def delete_slice(slice_id):
        """Delete slice definition"""
        try:
            player_obj = player_manager.get_player('video')
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            success = player_obj.output_manager.slice_manager.remove_slice(slice_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Slice {slice_id} deleted'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to delete slice {slice_id}'
                }), 400
        
        except Exception as e:
            logger.error(f"Failed to delete slice: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/slices/import', methods=['POST'])
    def import_slices():
        """Import slices from JSON (from frontend export)"""
        try:
            data = request.get_json()
            slices = data.get('slices', {})
            
            player_obj = player_manager.get_player('video')
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            # Import each slice
            count = 0
            for slice_id, slice_data in slices.items():
                if slice_id == 'full':
                    continue  # Skip default full slice
                
                player_obj.output_manager.add_slice(slice_id, slice_data)
                count += 1
            
            return jsonify({
                'success': True,
                'message': f'Imported {count} slices',
                'count': count
            })
        
        except Exception as e:
            logger.error(f"Failed to import slices: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/slices/export', methods=['GET'])
    def export_slices():
        """Export slices to JSON"""
        try:
            player_obj = player_manager.get_player('video')
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            slice_list = player_obj.output_manager.slice_manager.get_slice_list()
            
            return jsonify({
                'success': True,
                'slices': {s['id']: s for s in slice_list},
                'canvas': {
                    'width': player_obj.output_manager.canvas_width,
                    'height': player_obj.output_manager.canvas_height
                }
            })
        
        except Exception as e:
            logger.error(f"Failed to export slices: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # ========================================
    # Session State Integration
    # ========================================
    
    @app.route('/api/outputs/state', methods=['GET'])
    def get_output_state():
        """Get complete output state (for session save)"""
        try:
            player_obj = player_manager.get_player('video')
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            state = player_obj.output_manager.get_state()
            
            return jsonify({
                'success': True,
                'state': state
            })
        
        except Exception as e:
            logger.error(f"Failed to get output state: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/outputs/state', methods=['POST'])
    def set_output_state():
        """Restore complete output state (for session load)"""
        try:
            data = request.get_json()
            state = data.get('state', {})
            
            player_obj = player_manager.get_player('video')
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            player_obj.output_manager.set_state(state)
            
            return jsonify({
                'success': True,
                'message': 'Output state restored'
            })
        
        except Exception as e:
            logger.error(f"Failed to set output state: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # ========================================
    # Preview/Debug
    # ========================================
    
    @app.route('/api/outputs/<player>/preview/<output_id>', methods=['GET'])
    def get_output_preview(player, output_id):
        """Get preview image of specific output (base64 JPEG)"""
        try:
            player_obj = player_manager.get_player(player)
            if not player_obj or not player_obj.output_manager:
                return jsonify({
                    'success': False,
                    'error': 'Output manager not available'
                }), 404
            
            # Get output to check if it's virtual
            if output_id not in player_obj.output_manager.outputs:
                return jsonify({
                    'success': False,
                    'error': f'Output {output_id} not found'
                }), 404
            
            output = player_obj.output_manager.outputs[output_id]
            
            # For virtual outputs, get stored frame directly
            if output.config.get('type') == 'virtual':
                from ..outputs.plugins import VirtualOutput
                if isinstance(output, VirtualOutput):
                    frame = output.get_latest_frame()
                    
                    if frame is None:
                        return jsonify({
                            'success': False,
                            'error': 'No frame available yet (virtual output not receiving frames)'
                        }), 404
                else:
                    frame = None
            else:
                # For non-virtual outputs, get processed frame
                frame = player_obj.output_manager._get_frame_for_output(output)
            
            if frame is None:
                return jsonify({
                    'success': False,
                    'error': 'No frame available'
                }), 404
            
            # Encode as JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            
            return jsonify({
                'success': True,
                'image': f'data:image/jpeg;base64,{image_base64}',
                'timestamp': time.time(),
                'output_type': output.config.get('type', 'display'),
                'resolution': output.config.get('resolution', [1920, 1080])
            })
        
        except Exception as e:
            logger.error(f"Failed to get output preview: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
