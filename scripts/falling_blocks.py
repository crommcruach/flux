"""
Falling Blocks - Weiße Blöcke fallen von oben und stapeln sich
Prozedural generiert, keine Pygame-Abhängigkeit
"""
import numpy as np


class BlocksState:
    """Globaler State für gefallene Blöcke."""
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.fallen_blocks = []  # Liste von (y_position) Werten
        self.current_block_y = 0.0
        self.last_frame = 0
        self.is_full = False


# Globaler State (wird zwischen Frames beibehalten)
_state = BlocksState()


def generate_frame(frame_number, width, height, time, fps=30):
    """
    Generiert Frame mit fallenden Blöcken.
    
    Args:
        frame_number (int): Frame-Nummer
        width (int): Canvas-Breite
        height (int): Canvas-Höhe
        time (float): Zeit in Sekunden
        fps (int): FPS
    
    Returns:
        numpy.ndarray: Frame als (height, width, 3) RGB Array
    """
    global _state
    
    # Reset wenn neuer Durchlauf (zurück zu Frame 0 oder Zeit-Sprung)
    if frame_number == 0 or frame_number < _state.last_frame - 1:
        _state.reset()
    
    _state.last_frame = frame_number
    
    # Parameter
    BLOCK_HEIGHT = 30
    fall_speed = 10  # Pixel pro Frame
    
    # Schwarzer Hintergrund
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Wenn Bildschirm voll, reset
    if _state.is_full:
        _state.reset()
    
    # Zeichne alle gefallenen Blöcke
    for block_y in _state.fallen_blocks:
        if 0 <= block_y < height and block_y + BLOCK_HEIGHT <= height:
            frame[block_y:block_y + BLOCK_HEIGHT, :] = [255, 255, 255]
    
    # Bewege aktuellen Block nach unten
    _state.current_block_y += fall_speed
    
    # Prüfe ob Block gelandet ist
    block_landed = False
    
    # Unteren Rand erreicht?
    if _state.current_block_y >= height - BLOCK_HEIGHT:
        block_landed = True
        _state.current_block_y = height - BLOCK_HEIGHT
    
    # Kollision mit anderem Block?
    for fallen_y in _state.fallen_blocks:
        if abs(_state.current_block_y + BLOCK_HEIGHT - fallen_y) < fall_speed:
            block_landed = True
            _state.current_block_y = fallen_y - BLOCK_HEIGHT
            break
    
    # Block ist gelandet
    if block_landed:
        block_y_int = int(_state.current_block_y)
        if block_y_int not in _state.fallen_blocks:
            _state.fallen_blocks.append(block_y_int)
        _state.current_block_y = 0.0
        
        # Prüfe ob Bildschirm voll
        if len(_state.fallen_blocks) >= height // BLOCK_HEIGHT:
            _state.is_full = True
    
    # Zeichne aktuellen fallenden Block
    block_y_draw = int(_state.current_block_y)
    if 0 <= block_y_draw < height and block_y_draw + BLOCK_HEIGHT <= height:
        frame[block_y_draw:block_y_draw + BLOCK_HEIGHT, :] = [255, 255, 255]
    
    return frame


METADATA = {
    "name": "Falling Blocks",
    "author": "Flux",
    "description": "Weiße Blöcke fallen von oben und stapeln sich bis der Bildschirm voll ist",
    "fps": 60,
    "parameters": {
        "block_height": {"default": 30, "min": 10, "max": 100, "unit": "px"},
        "fall_speed": {"default": 10, "min": 1, "max": 50, "unit": "px/frame"}
    }
}
