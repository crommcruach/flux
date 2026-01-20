"""
Heartbeat monitor to detect silent crashes
Logs to file every 5 seconds so we can see when the app dies
"""
import threading
import time
from datetime import datetime
import os

class HeartbeatMonitor:
    def __init__(self, log_file='logs/heartbeat.log'):
        self.log_file = log_file
        self.running = False
        self.thread = None
        self.counter = 0
        
        # Ensure logs directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Clear old heartbeat log
        with open(log_file, 'w') as f:
            f.write(f"=== Heartbeat Monitor Started at {datetime.now()} ===\n")
            f.flush()
    
    def start(self):
        """Start heartbeat monitoring"""
        self.running = True
        self.thread = threading.Thread(target=self._heartbeat_loop, daemon=False, name="HeartbeatMonitor")
        self.thread.start()
        print(f"💓 Heartbeat monitor started, logging to {self.log_file}")
    
    def stop(self):
        """Stop heartbeat monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
    
    def _heartbeat_loop(self):
        """Background thread that writes heartbeat every 5 seconds"""
        while self.running:
            try:
                self.counter += 1
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                message = f"[{timestamp}] Heartbeat #{self.counter} - App is alive\n"
                
                # Write and flush immediately
                with open(self.log_file, 'a') as f:
                    f.write(message)
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk
                
                # Also print to console
                print(f"💓 Heartbeat #{self.counter}")
                
                time.sleep(5)
                
            except Exception as e:
                print(f"Heartbeat error: {e}")
                time.sleep(5)
        
        # Final message
        try:
            with open(self.log_file, 'a') as f:
                f.write(f"=== Heartbeat Monitor Stopped at {datetime.now()} ===\n")
                f.flush()
        except:
            pass

# Global instance
_monitor = None

def start_heartbeat():
    global _monitor
    _monitor = HeartbeatMonitor()
    _monitor.start()

def stop_heartbeat():
    global _monitor
    if _monitor:
        _monitor.stop()
