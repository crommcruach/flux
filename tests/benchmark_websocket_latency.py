"""
Benchmark WebSocket vs REST latency
Tests command execution speed for WebSocket vs traditional REST API
"""
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
try:
    from socketio import Client
except ImportError:
    print("❌ python-socketio not installed")
    print("Install with: pip install python-socketio")
    sys.exit(1)


def benchmark_rest_latency(base_url='http://localhost:5000', iterations=100):
    """Benchmark REST API latency."""
    print(f"\n{'='*60}")
    print(f"REST API Latency Benchmark ({iterations} iterations)")
    print(f"{'='*60}")
    
    latencies = []
    errors = 0
    
    for i in range(iterations):
        try:
            start = time.time()
            response = requests.post(f'{base_url}/api/player/video/play', timeout=5)
            latency = (time.time() - start) * 1000  # ms
            
            if response.status_code == 200:
                latencies.append(latency)
            else:
                errors += 1
                
            if (i + 1) % 10 == 0:
                print(f"Progress: {i+1}/{iterations} requests completed...")
                
        except Exception as e:
            errors += 1
            print(f"Error on iteration {i+1}: {e}")
    
    if not latencies:
        print("❌ No successful requests!")
        return None
    
    avg = sum(latencies) / len(latencies)
    min_lat = min(latencies)
    max_lat = max(latencies)
    median_lat = sorted(latencies)[len(latencies) // 2]
    
    print(f"\nREST API Results:")
    print(f"  ✓ Successful: {len(latencies)}/{iterations}")
    print(f"  ✗ Errors: {errors}/{iterations}")
    print(f"  📊 Average: {avg:.2f}ms")
    print(f"  ⬇️  Min: {min_lat:.2f}ms")
    print(f"  ⬆️  Max: {max_lat:.2f}ms")
    print(f"  📈 Median: {median_lat:.2f}ms")
    
    return avg


def benchmark_websocket_latency(base_url='http://localhost:5000', iterations=100):
    """Benchmark WebSocket command latency."""
    print(f"\n{'='*60}")
    print(f"WebSocket Latency Benchmark ({iterations} iterations)")
    print(f"{'='*60}")
    
    sio = Client()
    latencies = []
    errors = 0
    response_times = []
    
    @sio.on('command.response', namespace='/player')
    def on_response(data):
        """Handle command response."""
        if response_times:
            end = time.time()
            latency = (end - response_times[-1]) * 1000  # ms
            latencies.append(latency)
    
    @sio.on('command.error', namespace='/player')
    def on_error(data):
        """Handle command error."""
        nonlocal errors
        errors += 1
        print(f"Command error: {data.get('error', 'Unknown')}")
    
    try:
        print("Connecting to WebSocket...")
        sio.connect(base_url, namespaces=['/player'], wait_timeout=10)
        print("✓ Connected to /player namespace")
        
        time.sleep(0.5)  # Wait for connection to stabilize
        
        for i in range(iterations):
            response_times.append(time.time())
            sio.emit('command.play', {'player_id': 'video'}, namespace='/player')
            time.sleep(0.02)  # Small delay between commands (50 commands/sec)
            
            if (i + 1) % 10 == 0:
                print(f"Progress: {i+1}/{iterations} commands sent...")
        
        # Wait for all responses
        print("Waiting for responses...")
        time.sleep(2)
        
        sio.disconnect()
        
    except Exception as e:
        print(f"❌ WebSocket connection error: {e}")
        return None
    
    if not latencies:
        print("❌ No successful responses!")
        return None
    
    avg = sum(latencies) / len(latencies)
    min_lat = min(latencies)
    max_lat = max(latencies)
    median_lat = sorted(latencies)[len(latencies) // 2]
    
    print(f"\nWebSocket Results:")
    print(f"  ✓ Successful: {len(latencies)}/{iterations}")
    print(f"  ✗ Errors: {errors}/{iterations}")
    print(f"  📊 Average: {avg:.2f}ms")
    print(f"  ⬇️  Min: {min_lat:.2f}ms")
    print(f"  ⬆️  Max: {max_lat:.2f}ms")
    print(f"  📈 Median: {median_lat:.2f}ms")
    
    return avg


def main():
    """Run benchmark tests."""
    print("\n" + "="*60)
    print("🚀 WebSocket vs REST Latency Benchmark")
    print("="*60)
    
    base_url = 'http://localhost:5000'
    iterations = 50  # Reduced for faster testing
    
    # Check if server is running
    try:
        response = requests.get(f'{base_url}/api/config/frontend', timeout=2)
        if response.status_code != 200:
            print(f"❌ Server not responding properly (status {response.status_code})")
            print(f"Make sure Flux is running on {base_url}")
            return
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        print(f"Make sure Flux is running on {base_url}")
        return
    
    print(f"✓ Server is running on {base_url}")
    
    # Run benchmarks
    rest_latency = benchmark_rest_latency(base_url, iterations)
    ws_latency = benchmark_websocket_latency(base_url, iterations)
    
    # Calculate improvement
    if rest_latency and ws_latency:
        print(f"\n{'='*60}")
        print("📊 COMPARISON")
        print(f"{'='*60}")
        improvement = rest_latency / ws_latency
        reduction_ms = rest_latency - ws_latency
        reduction_pct = ((rest_latency - ws_latency) / rest_latency) * 100
        
        print(f"REST Latency:      {rest_latency:.2f}ms")
        print(f"WebSocket Latency: {ws_latency:.2f}ms")
        print(f"\n🎯 Improvement:     {improvement:.1f}x faster")
        print(f"⚡ Reduction:       -{reduction_ms:.2f}ms ({reduction_pct:.1f}% faster)")
        
        if improvement >= 10:
            print(f"\n✅ EXCELLENT: WebSocket is {improvement:.0f}x faster than REST!")
        elif improvement >= 5:
            print(f"\n✅ GREAT: WebSocket is {improvement:.0f}x faster than REST!")
        elif improvement >= 2:
            print(f"\n✅ GOOD: WebSocket is {improvement:.0f}x faster than REST!")
        else:
            print(f"\n⚠️  MARGINAL: Only {improvement:.1f}x improvement")
    else:
        print("\n❌ Benchmark failed - check server connection")
    
    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()
