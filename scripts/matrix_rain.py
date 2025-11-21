"""
Matrix Rain - Fallende grüne "Zeichen" wie im Film Matrix
Vertikale Streifen mit unterschiedlichen Geschwindigkeiten
"""
import random
import math

# Script Metadaten
SCRIPT_NAME = "Matrix Rain"
SCRIPT_FPS = 20
SCRIPT_DESCRIPTION = "Grüner Matrix-Regen mit fallenden Zeichen"

# Metadata Dictionary für Script-Listing
METADATA = {
    'name': SCRIPT_NAME,
    'description': SCRIPT_DESCRIPTION,
    'fps': SCRIPT_FPS,
    'author': 'AI Generated'
}

# Matrix Rain State
# Für jeden X-Streifen: [position, speed, length, brightness]
rain_strips = {}
initialized = False

def init_rain_strips(canvas_width, canvas_height):
    """Initialisiert die Regen-Streifen."""
    global rain_strips, initialized
    
    # Erstelle etwa 15-25 Streifen
    num_strips = random.randint(15, 25)
    
    for i in range(num_strips):
        # Zufällige X-Position
        x_pos = random.uniform(0, canvas_width)
        
        rain_strips[i] = {
            'x': x_pos,
            'y': random.uniform(-canvas_height * 0.5, 0),  # Starte teilweise außerhalb
            'speed': random.uniform(2, 8),  # Unterschiedliche Geschwindigkeiten
            'length': random.uniform(20, 60),  # Länge des Schweifs
            'brightness': random.uniform(0.6, 1.0)  # Helligkeit
        }
    
    initialized = True

def generate_frame(frame_number, width, height, time, fps=30):
    """
    Generiert einen Frame mit Matrix-Rain-Effekt.
    
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
    global rain_strips, initialized
    
    # Initialisiere beim ersten Frame
    if not initialized:
        init_rain_strips(canvas_width, canvas_height)
    
    # Update Streifen-Positionen
    for strip_id in rain_strips:
        strip = rain_strips[strip_id]
        strip['y'] += strip['speed']
        
        # Reset wenn komplett durch
        if strip['y'] > canvas_height + strip['length']:
            strip['y'] = -strip['length']
            strip['x'] = random.uniform(0, canvas_width)
            strip['speed'] = random.uniform(2, 8)
            strip['length'] = random.uniform(20, 60)
            strip['brightness'] = random.uniform(0.6, 1.0)
    
    # Generiere Points-Grid
    points = []
    step = 10
    for y in range(0, canvas_height, step):
        for x in range(0, canvas_width, step):
            points.append((x, y))
    
    rgb_values = []
    
    for x, y in points:
        # Finde nächsten Streifen
        closest_strip = None
        min_distance = float('inf')
        
        for strip in rain_strips.values():
            # Berechne horizontale Distanz
            dx = abs(x - strip['x'])
            
            # Berechne vertikale Position relativ zum Streifen-Kopf
            dy = y - strip['y']
            
            # Prüfe ob Punkt im Streifen ist
            if dx < 15 and 0 <= dy <= strip['length']:
                distance = dx + abs(dy)
                if distance < min_distance:
                    min_distance = distance
                    closest_strip = (strip, dy)
        
        if closest_strip:
            strip, dy = closest_strip
            
            # Helligkeit basierend auf Position im Streifen
            # Kopf (dy=0) ist am hellsten, Schweif wird dunkler
            position_factor = 1.0 - (dy / strip['length'])
            
            # Horizontale Distanz-Dämpfung (schärfere Kanten)
            dx = abs(x - strip['x'])
            distance_factor = max(0, 1.0 - dx / 15)
            
            # Gesamtintensität
            intensity = position_factor * distance_factor * strip['brightness']
            
            # Kopf-Highlight (die ersten 10% sind extra hell)
            if dy < strip['length'] * 0.1:
                head_boost = (1 - dy / (strip['length'] * 0.1)) * 0.5
                intensity = min(1.0, intensity + head_boost)
            
            # Matrix-Grün (heller = mehr Weiß-Anteil)
            if intensity > 0.8:
                # Sehr hell: Fast weiß mit grünem Stich
                r = int(200 * intensity)
                g = 255
                b = int(200 * intensity)
            elif intensity > 0.5:
                # Hell: Helles Grün
                r = int(100 * intensity)
                g = int(255 * intensity)
                b = int(100 * intensity)
            else:
                # Dunkel: Dunkles Grün
                r = 0
                g = int(200 * intensity)
                b = 0
            
            # Gelegentliches Flackern für "Digital-Glitch" Effekt
            if random.random() > 0.97:
                r = int(r * 0.5)
                g = int(g * 0.5)
                b = int(b * 0.5)
            
            rgb_values.append((x, y, r, g, b))
        else:
            # Schwarzer Hintergrund mit gelegentlichem schwachem Glühen
            if random.random() > 0.98:
                # Sehr seltenes schwaches grünes Glühen
                glow = random.randint(0, 30)
                rgb_values.append((x, y, 0, glow, 0))
            else:
                rgb_values.append((x, y, 0, 0, 0))
    
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
    global rain_strips, initialized
    rain_strips = {}
    initialized = False
