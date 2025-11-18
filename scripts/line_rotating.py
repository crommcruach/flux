"""
Rotating Line - Weiße Linie rotiert um Canvas-Mittelpunkt
"""
import numpy as np
import math


def generate_frame(frame_number, width, height, time, fps=30):
    """
    Generiert Frame mit rotierender weißer Linie vom Mittelpunkt aus.
    
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
    rotation_speed = 0.5  # Umdrehungen pro Sekunde
    
    # Mittelpunkt
    center_x = width / 2
    center_y = height / 2
    
    # Berechne Winkel (in Radiant)
    angle = (time * rotation_speed * 2 * math.pi) % (2 * math.pi)
    
    # Berechne Endpunkt der Linie (längste Diagonale)
    line_length = max(width, height) * 1.5  # Länger als Canvas-Diagonale
    end_x = center_x + math.cos(angle) * line_length
    end_y = center_y + math.sin(angle) * line_length
    
    # Bresenham-Algorithmus für 1px breite Linie (NumPy-optimiert)
    # Berechne alle Punkte auf der Linie
    x0, y0 = int(center_x), int(center_y)
    x1, y1 = int(end_x), int(end_y)
    
    # Verwende NumPy für effiziente Linien-Zeichnung
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    
    x, y = x0, y0
    points = []
    
    # Sammle alle Punkte der Linie
    while True:
        if 0 <= x < width and 0 <= y < height:
            points.append((y, x))
        
        if x == x1 and y == y1:
            break
        
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
        
        # Sicherheits-Abbruch wenn Linie zu lang wird
        if len(points) > line_length * 2:
            break
    
    # Zeichne alle Punkte auf einmal (schnell!)
    if points:
        ys, xs = zip(*points)
        frame[ys, xs] = [255, 255, 255]
    
    return frame


METADATA = {
    "name": "Rotating Line",
    "author": "Flux",
    "description": "Weiße Linie rotiert um Canvas-Mittelpunkt",
    "fps": 30,
    "parameters": {
        "rotation_speed": {"default": 0.5, "min": 0.1, "max": 5.0, "unit": "rot/s"}
    }
}
