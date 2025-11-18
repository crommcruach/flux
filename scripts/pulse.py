"""
Pulsing Colors - Einfache pulsierende Farbwechsel
Perfekt zum Testen
"""
import numpy as np
import colorsys
import math


def generate_frame(frame_number, width, height, time, fps=30):
    """
    Einfaches pulsierendes Farbfeld.
    
    Args:
        frame_number (int): Frame-Nummer
        width (int): Breite
        height (int): Höhe
        time (float): Zeit in Sekunden
        fps (int): FPS
    
    Returns:
        numpy.ndarray: Frame als (height, width, 3) RGB Array
    """
    # Berechne pulsierende Helligkeit (0.3 - 1.0)
    brightness = 0.65 + 0.35 * math.sin(time * 2)
    
    # Rotiere durch Farben
    hue = (time * 0.2) % 1.0
    
    # Konvertiere zu RGB
    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, brightness)
    
    # Erstelle Frame mit einzelner Farbe
    frame = np.full((height, width, 3), 
                    [int(r * 255), int(g * 255), int(b * 255)], 
                    dtype=np.uint8)
    
    return frame


METADATA = {
    "name": "Pulsing Colors",
    "author": "Flux",
    "description": "Einfache pulsierende Farbfläche",
    "fps": 30
}
