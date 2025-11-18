"""
Horizontal Line - Weiße horizontale Linie die von links nach rechts wandert
"""
import numpy as np


def generate_frame(frame_number, width, height, time, fps=30):
    """
    Generiert Frame mit horizontaler weißer Linie (1px breit).
    
    Args:
        frame_number (int): Frame-Nummer
        width (int): Canvas-Breite
        height (int): Canvas-Höhe
        time (float): Zeit in Sekunden
        fps (int): FPS
    
    Returns:
        numpy.ndarray: Frame als (height, width, 3) RGB Array
    """
    # Schwarzer Hintergrund
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Animation-Parameter
    speed = 150  # Pixel pro Sekunde
    
    # Berechne X-Position (von links nach rechts, dann wieder von links)
    x_pos = int((time * speed) % width)
    
    # Zeichne weiße vertikale Linie (1px breit, über gesamte Höhe)
    if 0 <= x_pos < width:
        frame[:, x_pos] = [255, 255, 255]
    
    return frame


METADATA = {
    "name": "Horizontal Line",
    "author": "Flux",
    "description": "Weiße horizontale Linie wandert von links nach rechts",
    "fps": 30,
    "parameters": {
        "speed": {"default": 150, "min": 10, "max": 500, "unit": "px/s"}
    }
}
