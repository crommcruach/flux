"""
Globale Player-Lock - Verhindert dass mehrere Player gleichzeitig aktiv sind
Shared zwischen VideoPlayer und ScriptPlayer
"""
import threading

# GLOBALE LOCK: Verhindert dass mehrere Player gleichzeitig senden
_global_player_lock = threading.Lock()
_active_player = None
_shared_artnet_manager = None  # Shared ArtNet Manager zwischen allen Playern
