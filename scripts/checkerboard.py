"""
Checkerboard - Schwarz-weißes Schachbrettmuster
Konfigurierbare Anzahl von Spalten und Reihen
"""
import numpy as np


def generate_frame(frame_number, width, height, time, fps=30, canvas=None, columns=8, rows=8):
    """
    Generiert ein Schachbrettmuster.
    
    Args:
        frame_number (int): Frame-Nummer
        width (int): Breite in Pixeln
        height (int): Höhe in Pixeln
        time (float): Zeit in Sekunden
        fps (int): FPS
        canvas (numpy.ndarray): Wiederverwendbares Canvas (optional)
        columns (int): Anzahl der Spalten (Standard: 8)
        rows (int): Anzahl der Reihen (Standard: 8)
    
    Returns:
        numpy.ndarray: Frame als (height, width, 3) RGB Array
    """
    # Nutze Canvas wenn vorhanden (Performance)
    if canvas is None:
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
    else:
        canvas.fill(0)  # Reset to black
    
    # Berechne Größe der einzelnen Felder
    cell_width = width / columns
    cell_height = height / rows
    
    # Zeichne Schachbrettmuster
    for row in range(rows):
        for col in range(columns):
            # Bestimme Farbe: Weiß wenn (row + col) gerade, sonst schwarz
            if (row + col) % 2 == 0:
                color = [255, 255, 255]  # Weiß
            else:
                color = [0, 0, 0]  # Schwarz (optional, da Canvas bereits schwarz ist)
                continue  # Skip schwarze Felder (Performance)
            
            # Berechne Pixel-Koordinaten
            x_start = int(col * cell_width)
            x_end = int((col + 1) * cell_width)
            y_start = int(row * cell_height)
            y_end = int((row + 1) * cell_height)
            
            # Zeichne Feld
            canvas[y_start:y_end, x_start:x_end] = color
    
    return canvas


METADATA = {
    "name": "Schachbrett",
    "author": "Flux",
    "description": "Schwarz-weißes Schachbrettmuster mit konfigurierbaren Spalten und Reihen",
    "fps": 30,
    "parameters": {
        "columns": {
            "default": 8,
            "min": 1,
            "max": 64,
            "type": "int",
            "description": "Anzahl der Spalten"
        },
        "rows": {
            "default": 8,
            "min": 1,
            "max": 64,
            "type": "int",
            "description": "Anzahl der Reihen"
        }
    }
}
