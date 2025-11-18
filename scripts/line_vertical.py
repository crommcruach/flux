"""
Vertical Line - Weiße vertikale Linie die von oben nach unten wandert
"""
import numpy as np


def generate_frame(frame_number, width, height, time, fps=30):
    """
    Generiert Frame mit vertikaler weißer Linie (1px breit).
    
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
    speed = 100  # Pixel pro Sekunde
    
    # Berechne Y-Position (von oben nach unten, dann wieder von oben)
    y_pos = int((time * speed) % height)
    
    # Zeichne weiße horizontale Linie (1px hoch, über gesamte Breite)
    if 0 <= y_pos < height:
        frame[y_pos, :] = [255, 255, 255]
    
    return frame


METADATA = {
    "name": "Vertical Line",
    "author": "Flux",
    "description": "Weiße vertikale Linie wandert von oben nach unten",
    "fps": 30,
    "parameters": {
        "speed": {"default": 100, "min": 10, "max": 500, "unit": "px/s"}
    }
}
