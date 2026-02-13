"""
ArtNet Sender Module

Creates and manages stupidArtnet instances for each configured output.
Handles multi-universe DMX packetization and network transmission.
"""

import time
from typing import Dict, Optional
from stupidArtnet import StupidArtnet
from .artnet_output import ArtNetOutput
from ..core.logger import get_logger

logger = get_logger(__name__)


class ArtNetSender:
    """Manages stupidArtnet instances per output"""
    
    def __init__(self):
        """Initialize ArtNet sender"""
        self.senders: Dict[str, Dict] = {}  # output_id → {'universes': [...], 'config': {...}}
        
    def configure_output(self, output: ArtNetOutput):
        """
        Configure stupidArtnet instances for an output.
        
        Args:
            output: Output configuration
        """
        output_id = output.id
        
        # Remove existing if present
        if output_id in self.senders:
            self.remove_output(output_id)
        
        # Calculate required universes (will be determined by actual DMX data size)
        # For now, prepare configuration
        self.senders[output_id] = {
            'config': output,
            'universes': [],  # Will be created on first send
            'last_send_time': 0.0
        }
        
        logger.debug(f"ArtNet output configured: {output.name} → {output.target_ip} (universe {output.start_universe})")
    
    def send(self, output_id: str, dmx_data: bytes):
        """
        Send DMX data to an output.
        
        Args:
            output_id: Output identifier
            dmx_data: DMX bytes to send
        """
        if output_id not in self.senders:
            logger.warning(f"Cannot send to unknown output: {output_id}")
            return
        
        sender_info = self.senders[output_id]
        output_config = sender_info['config']
        
        # Check if output is active
        if not output_config.active:
            return
        
        # Calculate required universes (512 channels per universe)
        channels_needed = len(dmx_data)
        universes_needed = (channels_needed + 509) // 510  # 510 usable channels per universe
        
        # Create stupidArtnet instances if needed
        if len(sender_info['universes']) != universes_needed:
            self._create_universes(output_id, universes_needed, output_config)
        
        # Split data into universe chunks and send
        universes = sender_info['universes']
        for i, universe in enumerate(universes):
            start_idx = i * 510
            end_idx = min(start_idx + 510, channels_needed)
            
            # Extract chunk for this universe
            chunk = list(dmx_data[start_idx:end_idx])
            
            # Pad to 510 channels
            while len(chunk) < 510:
                chunk.append(0)
            
            # Send via stupidArtnet
            universe.set(chunk)
            universe.show()
        
        sender_info['last_send_time'] = time.time()
    
    def _create_universes(self, output_id: str, count: int, config: ArtNetOutput):
        """
        Create stupidArtnet universe instances.
        
        Args:
            output_id: Output identifier
            count: Number of universes needed
            config: Output configuration
        """
        sender_info = self.senders[output_id]
        
        # Clear existing universes
        sender_info['universes'].clear()
        
        # Create new universes
        for i in range(count):
            universe_num = config.start_universe + i
            
            universe = StupidArtnet(
                target_ip=config.target_ip,
                universe=universe_num,
                packet_size=510,  # Usable DMX channels
                fps=config.fps,
                even_packet_size=True,  # Even packet size for compatibility
                broadcast=False  # Direct IP transmission
            )
            
            sender_info['universes'].append(universe)
        
        logger.debug(f"Created {count} ArtNet universe(s) for {config.name} starting at universe {config.start_universe}")
    
    def remove_output(self, output_id: str):
        """
        Remove and cleanup an output.
        
        Args:
            output_id: Output identifier
        """
        if output_id not in self.senders:
            return
        
        sender_info = self.senders[output_id]
        
        # Send blackout to all universes
        for universe in sender_info['universes']:
            try:
                universe.set([0] * 510)
                universe.show()
            except Exception as e:
                logger.warning(f"Error sending blackout to universe: {e}")
        
        # Remove from registry
        del self.senders[output_id]
        logger.debug(f"Removed ArtNet output: {output_id}")
    
    def blackout_output(self, output_id: str):
        """
        Send blackout (all zeros) to an output.
        
        Args:
            output_id: Output identifier
        """
        if output_id not in self.senders:
            return
        
        sender_info = self.senders[output_id]
        
        for universe in sender_info['universes']:
            universe.set([0] * 510)
            universe.show()
    
    def blackout_all(self):
        """Send blackout to all outputs"""
        for output_id in list(self.senders.keys()):
            self.blackout_output(output_id)
    
    def update_output_config(self, output: ArtNetOutput):
        """
        Update configuration for an existing output.
        
        Args:
            output: Updated output configuration
        """
        # Just reconfigure (will recreate universes if needed)
        self.configure_output(output)
    
    def get_stats(self, output_id: str) -> Optional[Dict]:
        """
        Get statistics for an output.
        
        Args:
            output_id: Output identifier
        
        Returns:
            Dictionary with stats or None if output not found
        """
        if output_id not in self.senders:
            return None
        
        sender_info = self.senders[output_id]
        
        return {
            'universes': len(sender_info['universes']),
            'last_send_time': sender_info['last_send_time'],
            'target_ip': sender_info['config'].target_ip,
            'start_universe': sender_info['config'].start_universe,
            'active': sender_info['config'].active
        }
    
    def cleanup(self):
        """Cleanup all outputs and send final blackout"""
        output_ids = list(self.senders.keys())
        for output_id in output_ids:
            self.remove_output(output_id)
        
        logger.debug("ArtNet sender cleaned up")
