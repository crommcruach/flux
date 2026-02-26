"""
Playlist Manager - Handles playlist navigation and autoplay
"""
from ...core.logger import get_logger, debug_playback, debug_layers

logger = get_logger(__name__)


class PlaylistManager:
    """Manages playlist state, navigation, and autoplay logic."""
    
    def __init__(self):
        """Initialize PlaylistManager."""
        self.playlist = []  # List of video paths or generator:id strings
        self.playlist_index = -1  # Current index in playlist
        self.playlist_params = {}  # Dict: generator_id -> parameters (for autoplay)
        self.playlist_ids = []  # List of UUIDs matching playlist order (same index)
        self.autoplay = True  # Automatically play next item
        self.loop_playlist = False  # Loop back to start when end is reached
        
    def set_playlist(self, items, ids=None):
        """
        Set playlist items.
        
        Args:
            items: List of video paths or 'generator:id' strings
            ids: Optional list of clip UUIDs matching items order
        """
        self.playlist = items
        self.playlist_ids = ids if ids else []
        self.playlist_index = -1
        logger.debug(f"Playlist set: {len(items)} items")
        
    def get_current_item(self):
        """
        Get current playlist item.
        
        Returns:
            str: Current item path or None if no valid index
        """
        if self.playlist and 0 <= self.playlist_index < len(self.playlist):
            return self.playlist[self.playlist_index]
        return None
    
    def get_current_clip_id(self):
        """
        Get current clip UUID.
        
        Returns:
            str: Current clip UUID or None
        """
        if isinstance(self.playlist_ids, list) and 0 <= self.playlist_index < len(self.playlist_ids):
            return self.playlist_ids[self.playlist_index]
        return None
    
    def get_next_index(self):
        """
        Calculate next playlist index.
        
        Returns:
            int or None: Next index, or None if end reached and no loop
        """
        if not self.playlist:
            return None
            
        next_index = self.playlist_index + 1
        
        # Check if at end
        if next_index >= len(self.playlist):
            if self.loop_playlist:
                return 0  # Loop back to start
            else:
                return None  # End reached
        
        return next_index
    
    def advance(self, player_name=""):
        """
        Advance to next item in playlist.
        
        Args:
            player_name: Name for logging
            
        Returns:
            tuple: (next_item, next_clip_id) or (None, None) if end reached
        """
        next_index = self.get_next_index()
        
        if next_index is None:
            debug_playback(logger, f"📋 [{player_name}] End of playlist reached")
            return None, None
        
        self.playlist_index = next_index
        
        # Get next item
        next_item = self.playlist[next_index]
        
        # Get clip_id if available
        next_clip_id = None
        if isinstance(self.playlist_ids, list) and next_index < len(self.playlist_ids):
            next_clip_id = self.playlist_ids[next_index]
        
        if next_index == 0:
            debug_playback(logger, f"🔁 [{player_name}] Playlist loop - back to first item")
        else:
            debug_playback(logger, f"⏭️ [{player_name}] Autoplay: Loading next item ({next_index + 1}/{len(self.playlist)}): {next_item}")
        
        return next_item, next_clip_id
    
    def set_index(self, index):
        """
        Set current playlist index.
        
        Args:
            index: New playlist index
            
        Returns:
            bool: True if valid index, False otherwise
        """
        if not self.playlist or index < 0 or index >= len(self.playlist):
            logger.warning(f"Invalid playlist index: {index} (size: {len(self.playlist) if self.playlist else 0})")
            return False
        
        self.playlist_index = index
        return True
    
    def get_item_at(self, index):
        """
        Get item at specific index.
        
        Args:
            index: Playlist index
            
        Returns:
            tuple: (item, clip_id) or (None, None) if invalid
        """
        if not self.playlist or index < 0 or index >= len(self.playlist):
            return None, None
        
        item = self.playlist[index]
        
        # Get clip_id if available
        clip_id = None
        if isinstance(self.playlist_ids, list) and index < len(self.playlist_ids):
            clip_id = self.playlist_ids[index]
        
        return item, clip_id
    
    def get_generator_parameters(self, generator_id, plugin_manager=None, clip_registry=None, current_source=None):
        """
        Get parameters for generator with priority fallback.
        
        Priority:
        1. ClipRegistry (stored parameters from playlist)
        2. playlist_params (user runtime modifications)
        3. Current generator parameters (if same generator)
        4. Default parameters from plugin
        
        Args:
            generator_id: Generator plugin ID
            plugin_manager: PluginManager instance (optional)
            clip_registry: ClipRegistry instance (optional)
            current_source: Current source to check for parameter reuse
            
        Returns:
            dict: Parameters or None
        """
        parameters = None
        
        # 1. Check clip registry
        if clip_registry:
            clip_id = self.get_current_clip_id()
            if clip_id and clip_id in clip_registry.clips:
                clip_meta = clip_registry.clips[clip_id].get('metadata', {})
                if clip_meta.get('parameters'):
                    parameters = clip_meta['parameters'].copy()
                    debug_playback(logger, f"🌟 Using ClipRegistry parameters: {parameters}")
                    return parameters
        
        # 2. Check playlist_params
        if generator_id in self.playlist_params:
            parameters = self.playlist_params[generator_id].copy()
            debug_playback(logger, f"🌟 Using playlist_params: {parameters}")
            return parameters
        
        # 3. Reuse current generator parameters if same generator
        if current_source:
            from ..sources import GeneratorSource
            if isinstance(current_source, GeneratorSource) and current_source.generator_id == generator_id:
                parameters = current_source.parameters.copy()
                # Store for future use
                self.playlist_params[generator_id] = parameters.copy()
                debug_playback(logger, f"🌟 Reusing and storing modified parameters: {parameters}")
                return parameters
        
        # 4. Fallback to defaults
        if plugin_manager:
            param_list = plugin_manager.get_plugin_parameters(generator_id)
            parameters = {p['name']: p['default'] for p in param_list}
            debug_playback(logger, f"🌟 Using default parameters: {parameters}")
            return parameters
        
        return None
    
    def should_autoplay(self, is_slave=False):
        """
        Check if autoplay should proceed.
        
        Args:
            is_slave: True if player is in slave mode
            
        Returns:
            bool: True if should autoplay, False if should loop current
        """
        # Slaves loop current clip, don't autoplay
        if is_slave:
            return False
        
        # Master or standalone: use autoplay setting
        return self.autoplay and len(self.playlist) > 0
    
    def clear(self):
        """Clear playlist and reset state."""
        self.playlist.clear()
        self.playlist_ids.clear()
        self.playlist_params.clear()
        self.playlist_index = -1
        logger.debug("Playlist cleared")
