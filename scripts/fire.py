"""
Fire - Realistischer Feuer-Effekt
Flackernde Flammen in Gelb/Orange/Rot die von unten nach oben züngeln
"""
import math
import random

# Script Metadaten
SCRIPT_NAME = "Fire"
SCRIPT_FPS = 30
SCRIPT_DESCRIPTION = "Realistisches Feuer mit flackernden Flammen"

# Metadata Dictionary für Script-Listing
METADATA = {
    'name': SCRIPT_NAME,
    'description': SCRIPT_DESCRIPTION,
    'fps': SCRIPT_FPS,
    'author': 'AI Generated'
}

# Feuer-State für zeitliche Kontinuität
noise_offset = 0

def generate_frame(frame_number, width, height, time, fps=30):
    """
    Generiert einen Frame mit Feuer-Effekt.
    
    Args:
        frame_number: Aktuelle Frame-Nummer
        width: Breite des Canvas
        height: Höhe des Canvas
        time: Zeit in Sekunden
        fps: Frames pro Sekunde
    
    Returns:
        numpy.ndarray: RGB-Array mit Shape (height, width, 3)
    """
    import numpy as np
    canvas_width = width
    canvas_height = height
    global noise_offset
    
    rgb_values = []
    
    # Zeit-Parameter für Animation
    t = time if time else frame_number * 0.1
    noise_offset += 0.05
    
    # Generiere Points-Grid für das gesamte Canvas
    points = []
    step = 10  # Abstand zwischen Points
    for y in range(0, canvas_height, step):
        for x in range(0, canvas_width, step):
            points.append((x, y))
    
    for x, y in points:
        # Y-Position normalisieren (0 = unten, 1 = oben)
        norm_y = y / canvas_height
        
        # X-Position normalisieren für horizontale Variation
        norm_x = x / canvas_width
        
        # Basis-Intensität: Unten heiß, oben kälter
        # Feuer ist unten am stärksten
        base_intensity = 1.0 - (norm_y ** 0.7)
        
        # Turbulenz/Flackern mit mehreren Frequenzen
        turbulence1 = math.sin(norm_x * 8 + t * 2) * 0.3
        turbulence2 = math.sin(norm_x * 15 + t * 3 + noise_offset) * 0.2
        turbulence3 = math.sin(norm_x * 20 - t * 4) * 0.15
        
        # Vertikale "Flammen-Zungen"
        flame_wave = math.sin(norm_x * 10 + t * 1.5) * (1 - norm_y) * 0.4
        
        # Zufälliges Funkeln (Glut-Partikel)
        sparkle = random.random() * 0.1 if random.random() > 0.95 else 0
        
        # Kombiniere alle Effekte
        intensity = base_intensity + turbulence1 + turbulence2 + turbulence3 + flame_wave + sparkle
        intensity = max(0, min(1.0, intensity))
        
        # Feuer-Farbverlauf basierend auf Intensität
        if intensity > 0.8:
            # Sehr heiß: Fast weiß / helles Gelb
            r = 255
            g = int(255 * (0.8 + intensity * 0.2))
            b = int(200 * (intensity - 0.8) * 5)  # Hauch von Blau bei extremer Hitze
        elif intensity > 0.6:
            # Heiß: Helles Gelb-Orange
            r = 255
            g = int(200 + (intensity - 0.6) * 275)
            b = int(50 * (intensity - 0.6))
        elif intensity > 0.4:
            # Medium: Orange
            r = int(255)
            g = int(100 + (intensity - 0.4) * 500)
            b = 0
        elif intensity > 0.2:
            # Kühl: Dunkel-Orange / Rot
            r = int(180 + (intensity - 0.2) * 375)
            g = int((intensity - 0.2) * 500)
            b = 0
        elif intensity > 0.05:
            # Sehr kühl: Dunkles Rot / Glut
            r = int(intensity * 900)
            g = int(intensity * 200)
            b = 0
        else:
            # Schwarz / kein Feuer
            r = int(intensity * 500)
            g = 0
            b = 0
        
        # Begrenze Werte
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        
        rgb_values.append((x, y, r, g, b))
    
    # Erstelle Canvas und schreibe RGB-Werte hinein
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    
    for px, py, r, g, b in rgb_values:
        # Zeichne kleinen Block um jeden Point (damit sichtbar)
        x_start = max(0, int(px) - 5)
        x_end = min(width, int(px) + 5)
        y_start = max(0, int(py) - 5)
        y_end = min(height, int(py) + 5)
        
        if 0 <= y_start < height and 0 <= x_start < width:
            canvas[y_start:y_end, x_start:x_end] = [r, g, b]
    
    return canvas


def cleanup():
    """Optional: Cleanup beim Beenden des Scripts."""
    global noise_offset
    noise_offset = 0
