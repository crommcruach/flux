"""
Globale Player-Lock - Verhindert dass mehrere Art-Net Player gleichzeitig aktiv sind
Shared zwischen allen Player-Instanzen
"""
import threading

# GLOBALE LOCK: Verhindert dass mehrere Art-Net Player gleichzeitig senden
_global_player_lock = threading.Lock()
_active_player = None
_shared_artnet_manager = None  # Shared ArtNet Manager zwischen allen Playern
