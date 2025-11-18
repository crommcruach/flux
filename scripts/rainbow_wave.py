"""
Rainbow Wave - Beispiel Shader
Erzeugt eine horizontale Regenbogen-Welle die sich bewegt
"""
import numpy as np


def hsv_to_rgb_vectorized(h, s, v):
    """
    Schnelle HSV zu RGB Konvertierung mit NumPy (vektorisiert).
    
    Args:
        h: Hue (0-1)
        s: Saturation (0-1) 
        v: Value (0-1)
    
    Returns:
        tuple: (r, g, b) als NumPy Arrays (0-1)
    """
    i = (h * 6.0).astype(int)
    f = (h * 6.0) - i
    
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    
    i = i % 6
    
    # Erstelle RGB Arrays
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    
    return r, g, b


def generate_frame(frame_number, width, height, time, fps=30):
    """
    Generiert ein einzelnes Frame.
    
    Args:
        frame_number (int): Aktuelle Frame-Nummer (startet bei 0)
        width (int): Canvas-Breite in Pixeln
        height (int): Canvas-Höhe in Pixeln
        time (float): Verstrichene Zeit in Sekunden
        fps (int): Frames pro Sekunde
    
    Returns:
        numpy.ndarray: Frame als (height, width, 3) RGB Array (uint8)
    """
    # Animation-Parameter
    speed = 2.0  # Geschwindigkeit der Welle
    wave_length = 60  # Wellenlänge in Pixeln
    
    # Berechne Hue-Offset basierend auf Zeit
    offset = (time * speed) % 1.0
    
    # Erstelle X-Koordinaten-Array
    x_coords = np.arange(width, dtype=np.float32)
    
    # Berechne Hue für jede Spalte (0-1 Range)
    hue = (x_coords / wave_length + offset) % 1.0
    
    # Konvertiere HSV zu RGB (vektorisiert!)
    r, g, b = hsv_to_rgb_vectorized(hue, 1.0, 1.0)
    
    # Skaliere zu 0-255 und konvertiere zu uint8
    frame_row = np.stack([r * 255, g * 255, b * 255], axis=-1).astype(np.uint8)
    
    # Wiederhole für alle Zeilen (Broadcasting)
    frame = np.tile(frame_row, (height, 1, 1))
    
    return frame


# Metadata (optional)
METADATA = {
    "name": "Rainbow Wave",
    "author": "Flux",
    "description": "Horizontale Regenbogen-Welle",
    "fps": 30,
    "parameters": {
        "speed": {"default": 2.0, "min": 0.1, "max": 10.0},
        "wave_length": {"default": 60, "min": 10, "max": 200}
    }
}
