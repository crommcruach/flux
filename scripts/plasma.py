"""
Plasma Effect - Klassischer Demo-Effekt
Erzeugt organische, fließende Farbmuster
"""
import numpy as np


def hsv_to_rgb_vectorized(h, s, v):
    """Schnelle HSV zu RGB Konvertierung (vektorisiert)."""
    i = (h * 6.0).astype(int)
    f = (h * 6.0) - i
    
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    
    i = i % 6
    
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    
    return r, g, b


def generate_frame(frame_number, width, height, time, fps=30):
    """
    Generiert einen Plasma-Effekt Frame.
    
    Args:
        frame_number (int): Aktuelle Frame-Nummer
        width (int): Canvas-Breite
        height (int): Canvas-Höhe
        time (float): Zeit in Sekunden
        fps (int): FPS
    
    Returns:
        numpy.ndarray: Frame als (height, width, 3) RGB Array
    """
    # Plasma-Parameter
    speed = 0.5
    
    # Erstelle Koordinaten-Meshgrid (einmalig für alle Pixel)
    x = np.arange(width, dtype=np.float32)
    y = np.arange(height, dtype=np.float32)
    X, Y = np.meshgrid(x, y)
    
    # Berechne alle 4 Sinus-Wellen parallel (NumPy Broadcasting!)
    v1 = np.sin(X / 16.0 + time * speed)
    v2 = np.sin(Y / 8.0 + time * speed)
    v3 = np.sin((X + Y) / 16.0 + time * speed)
    v4 = np.sin(np.sqrt(X*X + Y*Y) / 8.0 + time * speed)
    
    # Kombiniere Wellen
    plasma = (v1 + v2 + v3 + v4) / 4.0
    
    # Normalisiere zu 0-1
    plasma = (plasma + 1.0) / 2.0
    
    # Konvertiere zu Hue
    hue = (plasma + time * 0.1) % 1.0
    
    # HSV zu RGB (vektorisiert für gesamtes Bild!)
    r, g, b = hsv_to_rgb_vectorized(hue, 1.0, 1.0)
    
    # Stack zu RGB und konvertiere zu uint8
    frame = np.stack([r * 255, g * 255, b * 255], axis=-1).astype(np.uint8)
    
    return frame


METADATA = {
    "name": "Plasma Effect",
    "author": "Flux",
    "description": "Klassischer Plasma-Effekt mit überlagerten Sinus-Wellen",
    "fps": 30
}
