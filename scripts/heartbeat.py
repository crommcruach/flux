"""
Heartbeat - Pulsierendes Herz-Effekt
Rote Wellen pulsieren vom Zentrum nach außen wie ein schlagendes Herz
"""
import math
import time

# Script Metadaten
SCRIPT_NAME = "Heartbeat"
SCRIPT_FPS = 30
SCRIPT_DESCRIPTION = "Pulsierendes Herz - rote Wellen vom Zentrum"

# Metadata Dictionary für Script-Listing
METADATA = {
    'name': SCRIPT_NAME,
    'description': SCRIPT_DESCRIPTION,
    'fps': SCRIPT_FPS,
    'author': 'AI Generated'
}

def generate_frame(frame_number, width, height, time, fps=30):
    """
    Generiert einen Frame mit Heartbeat-Effekt.
    
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
    rgb_values = []
    
    # Zentrum des Canvas
    center_x = canvas_width / 2
    center_y = canvas_height / 2
    
    # Heartbeat-Parameter
    beat_speed = 0.15  # Geschwindigkeit des Herzschlags
    beats_per_cycle = 2  # Zwei Schläge pro Zyklus (lub-dub)
    
    # Zeitbasierte Animation
    t = frame_number * beat_speed
    
    # Erzeuge Doppel-Puls Effekt (lub-dub)
    # Erster Schlag (stärker)
    pulse1 = math.sin(t * math.pi * 2) ** 2
    # Zweiter Schlag (schwächer, zeitversetzt)
    pulse2 = 0.6 * math.sin((t + 0.15) * math.pi * 2) ** 2
    
    # Kombiniere beide Pulse
    pulse = max(pulse1, pulse2)
    
    # Wellen-Ausbreitung vom Zentrum
    wave_position = (t % 1.0) * max(canvas_width, canvas_height)
    
    # Generiere Points-Grid
    points = []
    step = 10
    for y in range(0, canvas_height, step):
        for x in range(0, canvas_width, step):
            points.append((x, y))
    
    for x, y in points:
        # Berechne Distanz vom Zentrum
        dx = x - center_x
        dy = y - center_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        # Normalisiere Distanz (0 = Zentrum, 1 = Rand)
        max_distance = math.sqrt(center_x**2 + center_y**2)
        norm_distance = distance / max_distance
        
        # Wellen-Effekt: Helligkeit basiert auf Distanz zur aktuellen Welle
        wave_diff = abs(distance - wave_position)
        wave_intensity = max(0, 1 - wave_diff / 50) * pulse
        
        # Basis-Glühen vom Zentrum (immer präsent)
        center_glow = max(0, 1 - norm_distance * 1.5) * 0.3
        
        # Kombiniere Effekte
        intensity = min(1.0, wave_intensity + center_glow)
        
        # Rot-Töne für Herz-Effekt
        if intensity > 0.7:
            # Helles Rot/Pink für intensive Bereiche
            r = int(255 * intensity)
            g = int(50 * intensity)
            b = int(80 * intensity)
        elif intensity > 0.3:
            # Mittleres Rot
            r = int(220 * intensity)
            g = int(20 * intensity)
            b = int(40 * intensity)
        else:
            # Dunkles Rot / fast schwarz
            r = int(180 * intensity)
            g = 0
            b = int(20 * intensity)
        
        rgb_values.append((x, y, r, g, b))
    
    # Erstelle Canvas und schreibe RGB-Werte hinein
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    
    for px, py, r, g, b in rgb_values:
        # Zeichne kleinen Block um jeden Point
        x_start = max(0, int(px) - 5)
        x_end = min(width, int(px) + 5)
        y_start = max(0, int(py) - 5)
        y_end = min(height, int(py) + 5)
        
        if 0 <= y_start < height and 0 <= x_start < width:
            canvas[y_start:y_end, x_start:x_end] = [r, g, b]
    
    return canvas


def cleanup():
    """Optional: Cleanup beim Beenden des Scripts."""
    pass
