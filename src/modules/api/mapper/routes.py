"""
LED Visual Mapper API Routes
Sequential LED illumination for webcam-based position detection
"""
from flask import jsonify, request, current_app
from . import mapper_bp
import threading
import time
import logging
import socket

logger = logging.getLogger(__name__)


def get_local_ip_for_target(target_ip):
    """
    Determine which local network interface will be used to reach the target IP.
    
    Args:
        target_ip: Target IP address (e.g., "192.168.1.2")
        
    Returns:
        str: Local IP address that will be used as source
    """
    try:
        # Create a UDP socket (doesn't actually send data)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((target_ip, 6454))  # Art-Net port
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.warning(f"Could not determine local IP for target {target_ip}: {e}")
        return None


def get_all_local_ips():
    """Get all local IP addresses on this machine."""
    ips = []
    try:
        hostname = socket.gethostname()
        # Get all IP addresses for this host
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ip not in ips and not ip.startswith('::'):  # Skip IPv6 for now
                ips.append(ip)
    except Exception as e:
        logger.warning(f"Could not enumerate local IPs: {e}")
    return ips

# Store active mapping tasks
_active_tasks = {}
_task_counter = 0
_task_lock = threading.Lock()


def get_channels_per_led(color_type):
    """Calculate DMX channels per LED based on type."""
    channel_map = {
        'rgb': 3,
        'rgbw': 4,
        'rgbww': 5,
        'rgbwwcw': 6
    }
    return channel_map.get(color_type, 3)


@mapper_bp.route('/simple-test', methods=['POST'])
def simple_artnet_test():
    """
    Simple Art-Net test - just send a packet with all channels at 255.
    For debugging Art-Net network issues.
    
    Request JSON:
        target_ip: str - Target IP address
        universe: int - Universe number (default 0)
        broadcast: bool - Use broadcast mode (default false)
    
    Returns:
        success: bool
        message: str - Debug info
    """
    data = request.get_json()
    target_ip = data.get('target_ip', '192.168.1.2')
    universe = data.get('universe', 0)
    use_broadcast = data.get('broadcast', False)
    
    try:
        from stupidArtnet import StupidArtnet
        import socket as sock_module
        
        # Log socket info
        hostname = sock_module.gethostname()
        local_ips = get_all_local_ips()
        source_ip = get_local_ip_for_target(target_ip)
        
        logger.info(f"=== Simple Art-Net Test ===")
        logger.info(f"Hostname: {hostname}")
        logger.info(f"All local IPs: {local_ips}")
        logger.info(f"Source IP for {target_ip}: {source_ip}")
        logger.info(f"Target: {target_ip}, Universe: {universe}, Broadcast: {use_broadcast}")
        
        # Create Art-Net instance
        actual_target = target_ip
        if use_broadcast:
            ip_parts = target_ip.split('.')
            actual_target = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"
            logger.info(f"Broadcast mode: using {actual_target}")
        
        artnet = StupidArtnet(
            target_ip=actual_target,
            universe=universe,
            packet_size=510,
            fps=30,
            even_packet_size=True,
            broadcast=use_broadcast,
            source_address=('0.0.0.0', 6454)  # Bind to source port 6454
        )
        
        logger.info(f"StupidArtnet created: {artnet}")
        artnet.start()
        logger.info(f"StupidArtnet started")
        
        # Send test packet (all channels at 255)
        test_data = [255] * 510
        artnet.set(test_data)
        logger.info(f"Data set in buffer")
        artnet.show()
        logger.info(f"Packet sent via show()")
        
        # Wait a bit
        time.sleep(2)
        
        # Turn off
        artnet.set([0] * 510)
        artnet.show()
        logger.info(f"Blackout sent")
        
        artnet.stop()
        logger.info(f"StupidArtnet stopped")
        
        return jsonify({
            'success': True,
            'message': f'Test packet sent to {actual_target}:{universe}',
            'hostname': hostname,
            'local_ips': local_ips,
            'source_ip': source_ip,
            'actual_target': actual_target
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Simple Art-Net test failed: {e}\n{error_detail}")
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': error_detail
        }), 500


@mapper_bp.route('/start-sequence', methods=['POST'])
def start_mapping_sequence():
    """
    Initialize LED mapping sequence with user configuration.
    
    Request JSON:
        artnet_ip: str - Art-Net controller IP address
        universe: int - Art-Net universe number
        color_type: str - LED type (rgb, rgbw, rgbww, rgbwwcw)
        led_count: int - Number of LEDs to map
        start_address: int - Starting DMX address (1-512)
        delay_ms: int - Delay between LEDs in milliseconds (optional, default 800)
    
    Returns:
        success: bool
        task_id: str - Background task identifier
        led_count: int - Number of LEDs in sequence
    """
    data = request.get_json()
    
    # Configuration from modal
    artnet_ip = data.get('artnet_ip')
    universe = data.get('universe', 0)
    color_type = data.get('color_type', 'rgb')
    led_count = data.get('led_count')
    start_address = data.get('start_address', 1)
    delay_ms = data.get('delay_ms', 800)
    use_broadcast = data.get('use_broadcast', False)  # Option to use broadcast mode for debugging
    
    # Validate required parameters
    if not artnet_ip or not led_count:
        return jsonify({
            'success': False, 
            'error': 'Missing required parameters: artnet_ip and led_count'
        }), 400
    
    # Validate IP format
    import re
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', artnet_ip):
        return jsonify({
            'success': False,
            'error': 'Invalid IP address format'
        }), 400
    
    # Validate ranges
    if not (1 <= led_count <= 500):
        return jsonify({
            'success': False,
            'error': 'LED count must be between 1 and 500'
        }), 400
    
    if not (1 <= start_address <= 512):
        return jsonify({
            'success': False,
            'error': 'Start address must be between 1 and 512'
        }), 400
    
    try:
        # Create mapping configuration
        mapping_config = {
            'artnet_ip': artnet_ip,
            'universe': universe,
            'color_type': color_type,
            'led_count': led_count,
            'start_address': start_address,
            'channels_per_led': get_channels_per_led(color_type),
            'delay_ms': delay_ms,
            'use_broadcast': use_broadcast
        }
        
        # Start background task
        task_id = _start_background_task(mapping_config)
        
        logger.info(f"Started LED mapping sequence: {led_count} LEDs to {artnet_ip}:{universe}")
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'led_count': led_count
        })
        
    except Exception as e:
        logger.error(f"Failed to start mapping sequence: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@mapper_bp.route('/test-single-led', methods=['POST'])
def test_single_led():
    """
    Test/retry a single LED (for manual retry during mapping).
    
    Request JSON:
        led_index: int - LED index to test
        config: dict - Mapping configuration (from original sequence)
    
    Returns:
        success: bool
        dmx_address: int - DMX address used
    """
    data = request.get_json()
    
    led_index = data.get('led_index')
    config = data.get('config')
    
    if led_index is None or not config:
        return jsonify({
            'success': False,
            'error': 'Missing led_index or config'
        }), 400
    
    try:
        # Import stupidArtnet
        from stupidArtnet import StupidArtnet
        
        channels_per_led = get_channels_per_led(config['color_type'])
        dmx_address = config['start_address'] + (led_index * channels_per_led) - 1  # 0-indexed
        
        # Determine target IP
        artnet_ip = config['artnet_ip']
        use_broadcast = config.get('use_broadcast', False)
        target_ip = artnet_ip
        
        if use_broadcast:
            ip_parts = artnet_ip.split('.')
            target_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"
        
        # Initialize Art-Net with source port 6454
        artnet = StupidArtnet(
            target_ip=target_ip,
            universe=config['universe'],
            packet_size=510,
            fps=30,
            even_packet_size=True,
            broadcast=use_broadcast,
            source_address=('0.0.0.0', 6454)  # Bind to source port 6454
        )
        artnet.start()
        
        try:
            # Build DMX packet
            dmx_data = [0] * 510
            
            # Set LED to full white
            if config['color_type'] == 'rgb':
                dmx_data[dmx_address] = 255      # R
                dmx_data[dmx_address + 1] = 255  # G
                dmx_data[dmx_address + 2] = 255  # B
            elif config['color_type'] == 'rgbw':
                dmx_data[dmx_address] = 255      # R
                dmx_data[dmx_address + 1] = 255  # G
                dmx_data[dmx_address + 2] = 255  # B
                dmx_data[dmx_address + 3] = 255  # W
            elif config['color_type'] in ['rgbww', 'rgbwwcw']:
                # Set all channels to full
                for i in range(channels_per_led):
                    if dmx_address + i < 510:
                        dmx_data[dmx_address + i] = 255
            
            # Send via stupidArtnet (CRITICAL: must call both .set() AND .show())
            artnet.set(dmx_data)
            artnet.show()  # Actually transmits the packet
            
            logger.info(f"Test LED #{led_index} at DMX address {dmx_address + 1} - packet transmitted")
            
            return jsonify({
                'success': True,
                'dmx_address': dmx_address + 1  # Return 1-indexed for display
            })
            
        finally:
            # Turn off LED
            artnet.set([0] * 510)
            artnet.show()
            artnet.stop()
        
    except Exception as e:
        logger.error(f"Failed to test LED: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@mapper_bp.route('/network-diagnostics', methods=['POST'])
def network_diagnostics():
    """
    Get network diagnostic information for Art-Net troubleshooting.
    
    Request JSON:
        target_ip: str - Target IP to test routing for
    
    Returns:
        local_ips: list - All local IP addresses
        source_ip: str - Source IP that will be used for target
        hostname: str - Machine hostname
        target_reachable: bool - Whether target is reachable (ping test)
    """
    data = request.get_json()
    target_ip = data.get('target_ip', '192.168.1.2')
    
    try:
        import platform
        import subprocess
        
        # Get all local IPs
        local_ips = get_all_local_ips()
        
        # Get source IP for target
        source_ip = get_local_ip_for_target(target_ip)
        
        # Get hostname
        hostname = socket.gethostname()
        
        # Test if target is reachable (quick ping)
        target_reachable = False
        try:
            if platform.system().lower() == 'windows':
                # Windows ping: -n 1 (count), -w 1000 (timeout 1s)
                result = subprocess.run(['ping', '-n', '1', '-w', '1000', target_ip], 
                                       capture_output=True, timeout=2)
            else:
                # Linux/Mac ping: -c 1 (count), -W 1 (timeout 1s)
                result = subprocess.run(['ping', '-c', '1', '-W', '1', target_ip], 
                                       capture_output=True, timeout=2)
            target_reachable = (result.returncode == 0)
        except Exception as ping_error:
            logger.warning(f"Ping test failed: {ping_error}")
        
        return jsonify({
            'success': True,
            'local_ips': local_ips,
            'source_ip': source_ip,
            'hostname': hostname,
            'target_ip': target_ip,
            'target_reachable': target_reachable,
            'platform': platform.system()
        })
        
    except Exception as e:
        logger.error(f"Network diagnostics failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@mapper_bp.route('/stop-sequence', methods=['POST'])
def stop_sequence():
    """
    Stop an active mapping sequence.
    
    Request JSON:
        task_id: str - Task identifier to stop
    
    Returns:
        success: bool
    """
    data = request.get_json()
    task_id = data.get('task_id')
    
    if not task_id:
        return jsonify({'success': False, 'error': 'Missing task_id'}), 400
    
    with _task_lock:
        if task_id in _active_tasks:
            _active_tasks[task_id]['stop'] = True
            logger.info(f"Stopping mapping task {task_id}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Task not found'}), 404


def _start_background_task(config):
    """Start background task for LED sequence."""
    global _task_counter
    
    with _task_lock:
        _task_counter += 1
        task_id = f"mapper_{_task_counter}"
        
        # Create task control structure
        _active_tasks[task_id] = {
            'stop': False,
            'config': config
        }
    
    # Get current Flask app instance
    app = current_app._get_current_object()
    
    # Start thread with app context
    thread = threading.Thread(
        target=_mapping_sequence_task,
        args=(task_id, config, app),
        daemon=True
    )
    thread.start()
    
    return task_id


def _mapping_sequence_task(task_id, config, app):
    """
    Background task: sequentially light each LED for detection.
    Emits SocketIO events to notify frontend.
    """
    # Run inside Flask app context
    with app.app_context():
        try:
            # Import stupidArtnet
            logger.info(f"Task {task_id}: Importing stupidArtnet library...")
            from stupidArtnet import StupidArtnet
            logger.info(f"Task {task_id}: stupidArtnet imported successfully")
            
            artnet_ip = config['artnet_ip']
            universe = config['universe']
            led_count = config['led_count']
            start_address = config['start_address']
            channels_per_led = config['channels_per_led']
            color_type = config['color_type']
            delay_ms = config['delay_ms']
            use_broadcast = config.get('use_broadcast', False)
            
            logger.info(f"Task {task_id}: Starting sequence of {led_count} LEDs")
            logger.info(f"Task {task_id}: Art-Net Config - IP: {artnet_ip}, Universe: {universe}, Type: {color_type}")
            logger.info(f"Task {task_id}: DMX Config - Start Address: {start_address}, Channels/LED: {channels_per_led}")
            logger.info(f"Task {task_id}: Network Mode - Broadcast: {use_broadcast}")
            
            # Log network interface information
            local_ips = get_all_local_ips()
            source_ip = get_local_ip_for_target(artnet_ip)
            logger.info(f"Task {task_id}: Network Diagnostics - All local IPs: {local_ips}")
            logger.info(f"Task {task_id}: Network Diagnostics - Source IP for target {artnet_ip}: {source_ip}")
            
            # Determine target IP (use broadcast address if broadcast mode enabled)
            target_ip = artnet_ip
            broadcast_enabled = use_broadcast
            
            if use_broadcast:
                # Calculate broadcast address from target IP (assume /24 network)
                ip_parts = artnet_ip.split('.')
                target_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"
                logger.info(f"Task {task_id}: Broadcast mode enabled - using broadcast address {target_ip}")
            
            logger.info(f"Task {task_id}: Creating Art-Net sender...")
            logger.info(f"Task {task_id}:   → Target IP: {target_ip}")
            logger.info(f"Task {task_id}:   → Universe: {universe}")
            logger.info(f"Task {task_id}:   → Broadcast: {broadcast_enabled}")
            logger.info(f"Task {task_id}:   → Port: 6454 (Art-Net default)")
            
            # Initialize Art-Net sender with source port 6454
            artnet = StupidArtnet(
                target_ip=target_ip,
                universe=universe,
                packet_size=510,  # 510 usable DMX channels
                fps=30,           # 30 fps refresh rate
                even_packet_size=True,  # Even packet size for compatibility
                broadcast=broadcast_enabled,  # Use broadcast if enabled
                source_address=('0.0.0.0', 6454)  # Bind to source port 6454
            )
            artnet.start()
            logger.info(f"Task {task_id}: Art-Net sender started successfully")
            
            try:
                for led_index in range(led_count):
                    # Check if stopped
                    with _task_lock:
                        if _active_tasks.get(task_id, {}).get('stop'):
                            logger.info(f"Task {task_id}: Stopped by user")
                            break
                    
                    # Calculate DMX address for this LED
                    dmx_address = start_address + (led_index * channels_per_led) - 1  # 0-indexed
                    
                    # Validate DMX address fits within packet
                    if dmx_address + channels_per_led > 510:
                        logger.error(f"Task {task_id}: LED #{led_index + 1} DMX address {dmx_address + 1} exceeds packet size (510 channels)")
                        continue
                    
                    # Create DMX packet (all zeros except current LED) - 510 channels to match packet_size
                    dmx_data = [0] * 510
                    
                    # Set LED to full white (or all channels to full)
                    if color_type == 'rgb':
                        dmx_data[dmx_address] = 255      # R
                        dmx_data[dmx_address + 1] = 255  # G
                        dmx_data[dmx_address + 2] = 255  # B
                        logger.info(f"Task {task_id}: LED #{led_index + 1}/{led_count} - DMX {dmx_address + 1}-{dmx_address + 3}: RGB(255,255,255)")
                    elif color_type == 'rgbw':
                        dmx_data[dmx_address] = 255      # R
                        dmx_data[dmx_address + 1] = 255  # G
                        dmx_data[dmx_address + 2] = 255  # B
                        dmx_data[dmx_address + 3] = 255  # W
                        logger.info(f"Task {task_id}: LED #{led_index + 1}/{led_count} - DMX {dmx_address + 1}-{dmx_address + 4}: RGBW(255,255,255,255)")
                    elif color_type in ['rgbww', 'rgbwwcw']:
                        # Set all channels to full
                        for i in range(channels_per_led):
                            if dmx_address + i < 510:  # 510 channels max
                                dmx_data[dmx_address + i] = 255
                        logger.info(f"Task {task_id}: LED #{led_index + 1}/{led_count} - DMX {dmx_address + 1}-{dmx_address + channels_per_led}: ALL(255) ({color_type})")
                    
                    # Send to Art-Net (CRITICAL: must call both .set() AND .show())
                    artnet.set(dmx_data)
                    artnet.show()  # Actually transmits the packet over network
                    logger.info(f"Task {task_id}: ✓ Art-Net packet transmitted to {artnet_ip}:{universe}")
                    
                    # Get socketio from current app
                    socketio = current_app.extensions.get('socketio')
                    
                    # Notify frontend that LED is now active
                    if socketio:
                        socketio.emit('mapper:led_active', {
                            'led_index': led_index,
                            'total': led_count,
                            'dmx_address': dmx_address + 1,  # 1-indexed for display
                            'task_id': task_id
                        })
                        logger.info(f"Task {task_id}: SocketIO event 'mapper:led_active' emitted")
                    
                    # Wait for detection
                    logger.info(f"Task {task_id}: Waiting {delay_ms}ms for detection...")
                    time.sleep(delay_ms / 1000.0)
                    
                    # Turn off LED before next one
                    artnet.set([0] * 510)  # Match packet_size=510
                    artnet.show()
                    logger.info(f"Task {task_id}: LED #{led_index + 1} turned OFF")
                    time.sleep(0.1)  # Brief pause between LEDs
                
                # Sequence complete
                socketio = current_app.extensions.get('socketio')
                if socketio:
                    socketio.emit('mapper:sequence_complete', {
                        'total_leds': led_count,
                        'task_id': task_id
                    })
                    logger.info(f"Task {task_id}: SocketIO event 'mapper:sequence_complete' emitted")
                
                logger.info(f"Task {task_id}: ✓ Sequence complete - {led_count} LEDs cycled")
                
            finally:
                # Turn off all LEDs
                logger.info(f"Task {task_id}: Turning off all LEDs and stopping Art-Net...")
                artnet.set([0] * 510)
                artnet.show()
                artnet.stop()
                logger.info(f"Task {task_id}: Art-Net sender stopped")
                
        except Exception as e:
            import traceback
            logger.error(f"Task {task_id}: ❌ Error in mapping sequence: {e}")
            logger.error(f"Task {task_id}: Traceback: {traceback.format_exc()}")
            socketio = current_app.extensions.get('socketio')
            if socketio:
                socketio.emit('mapper:error', {
                    'task_id': task_id,
                    'error': str(e)
                })
                logger.error(f"Task {task_id}: SocketIO event 'mapper:error' emitted")
        
        finally:
            # Clean up task
            with _task_lock:
                if task_id in _active_tasks:
                    del _active_tasks[task_id]
