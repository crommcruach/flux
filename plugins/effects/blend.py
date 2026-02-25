"""
Blend Effect Plugin - Composites multiple layers with different blend modes
"""
import numpy as np
import cv2
from plugins import PluginBase, PluginType, ParameterType


class BlendEffect(PluginBase):
    """
    Blend Effect - Composite Modus für Layer-basierte Komposition.
    
    Unterstützt Standard-Blend-Modi aus der Bildverarbeitung:
    - Normal: Standard-Alpha-Blending
    - Multiply: Dunkelt ab (Farben multiplizieren)
    - Screen: Hellt auf (invertierte Multiplikation)
    - Add: Addiert Farben (Dodge)
    - Subtract: Subtrahiert Farben
    - Overlay: Kombiniert Multiply und Screen
    - Mask: Nutzt Overlay-Luminanz als Alpha-Maske (weiß = sichtbar, schwarz = transparent)
    """
    
    METADATA = {
        'id': 'blend',
        'name': 'Blend Mode',
        'description': 'Layer-Komposition mit verschiedenen Blend-Modi',
        'author': 'Flux Team',
        'version': '1.1.0',
        'type': PluginType.EFFECT,
        'category': 'Komposition'
    }
    
    BLEND_MODES = ['normal', 'multiply', 'screen', 'add', 'subtract', 'overlay', 'mask']
    
    PARAMETERS = [
        {
            'name': 'blend_mode',
            'label': 'Blend Mode',
            'type': ParameterType.SELECT,
            'default': 'normal',
            'options': BLEND_MODES,
            'description': 'Blend-Modus für Layer-Komposition'
        },
        {
            'name': 'opacity',
            'label': 'Opacity',
            'type': ParameterType.FLOAT,
            'default': 100.0,
            'min': 0.0,
            'max': 100.0,
            'step': 1.0,
            'description': 'Layer-Opazität in Prozent (100% = vollständig sichtbar)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Blend-Modus und Opazität."""
        self.blend_mode = config.get('blend_mode', 'normal')
        self.opacity = config.get('opacity', 100.0)
        
        # Validiere Blend-Modus
        if self.blend_mode not in self.BLEND_MODES:
            raise ValueError(f"Invalid blend mode: {self.blend_mode}. Must be one of {self.BLEND_MODES}")
    
    def process_frame(self, frame, overlay=None, **kwargs):
        """
        Wendet Blend-Modus auf Frame an.
        
        Args:
            frame: Basis-Frame (NumPy Array, RGB, uint8) - "Background"
            overlay: Overlay-Frame (NumPy Array, RGB/RGBA, uint8) - "Foreground"
                     Falls None, wird nur Opacity angewendet
            **kwargs: Zusätzliche Parameter
            
        Returns:
            Komponiertes Frame mit angewendetem Blend-Modus
        """
        # Wenn kein Overlay vorhanden, nur Opacity anwenden
        if overlay is None:
            return self._apply_opacity(frame)
        
        # PERFORMANCE: Extract alpha channel from RGBA overlay (from mask effect)
        overlay_alpha = None
        if len(overlay.shape) == 3 and overlay.shape[2] == 4:
            overlay_alpha = overlay[:, :, 3].astype(np.float32) / 255.0  # Normalize to 0-1
            overlay = overlay[:, :, :3]  # Extract RGB only
        
        # OPTIMIZATION: Fast path for normal mode at 100% opacity (zero-copy)
        if self.blend_mode == 'normal' and self.opacity >= 100.0 and overlay_alpha is None:
            # Ensure same dimensions
            if frame.shape != overlay.shape:
                return cv2.resize(overlay, (frame.shape[1], frame.shape[0]))
            return overlay  # Direct return, no processing needed (saves 3-5ms)
        
        # OPTIMIZATION: Fast path for normal mode with opacity (skip float32 conversion)
        if self.blend_mode == 'normal' and overlay_alpha is None:
            # Ensure same dimensions
            if frame.shape != overlay.shape:
                overlay = cv2.resize(overlay, (frame.shape[1], frame.shape[0]))
            # Use cv2.addWeighted directly on uint8 (MUCH faster than float32 conversion)
            opacity_factor = self.opacity / 100.0
            return cv2.addWeighted(frame, 1.0 - opacity_factor, overlay, opacity_factor, 0)
        
        # Stelle sicher, dass beide Frames gleiche Dimensionen haben
        # OPTIMIZATION: Cache resize to avoid redundant operations
        if frame.shape != overlay.shape:
            # Most expensive operation in blend - only do when needed
            overlay = cv2.resize(overlay, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR)
            # Also resize alpha if present
            if overlay_alpha is not None:
                overlay_alpha = cv2.resize(overlay_alpha, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR)
        
        # OPTIMIZATION: For opacity >= 100%, skip opacity blending step
        opacity_factor = self.opacity / 100.0
        
        # Konvertiere zu float32 für präzise Berechnungen (nur einmal!)
        # PERFORMANCE: Use in-place division to save memory allocation
        base_float = frame.astype(np.float32)
        base_float *= (1.0 / 255.0)
        over_float = overlay.astype(np.float32)
        over_float *= (1.0 / 255.0)
        
        # Wende Blend-Modus an
        if self.blend_mode == 'multiply':
            blended = self._blend_multiply(base_float, over_float)
        elif self.blend_mode == 'screen':
            blended = self._blend_screen(base_float, over_float)
        elif self.blend_mode == 'add':
            blended = self._blend_add(base_float, over_float)
        elif self.blend_mode == 'subtract':
            blended = self._blend_subtract(base_float, over_float)
        elif self.blend_mode == 'overlay':
            blended = self._blend_overlay(base_float, over_float)
        elif self.blend_mode == 'mask':
            blended = self._blend_mask(base_float, over_float)
        else:
            # Fallback zu Normal (should not happen)
            blended = over_float
        
        # PERFORMANCE: Apply overlay alpha channel if present (from mask effect)
        if overlay_alpha is not None:
            # Expand alpha to 3 channels for RGB multiplication
            alpha_3ch = np.stack([overlay_alpha, overlay_alpha, overlay_alpha], axis=2)
            # Blend using alpha: result = base * (1 - alpha) + blended * alpha
            blended = base_float * (1.0 - alpha_3ch) + blended * alpha_3ch
        
        # Wende Opacity an BEFORE converting back to uint8 (saves one conversion)
        if opacity_factor < 1.0:
            # Mix on float32 for precision
            blended = base_float * (1.0 - opacity_factor) + blended * opacity_factor
        
        # Clip und konvertiere zurück zu uint8 (nur einmal!)
        return np.clip(blended * 255.0, 0, 255).astype(np.uint8)
    
    def _apply_opacity(self, frame):
        """Wendet nur Opacity an (kein Overlay)."""
        if self.opacity >= 100.0:
            return frame
        
        opacity_factor = self.opacity / 100.0
        frame_float = frame.astype(np.float32)
        frame_float *= opacity_factor
        return np.clip(frame_float, 0, 255).astype(np.uint8)
    
    def _blend_normal(self, base, over):
        """Normal Blend: Standard-Alpha-Blending (over ersetzt base)."""
        return over
    
    def _blend_multiply(self, base, over):
        """Multiply Blend: Dunkelt ab (Farben multiplizieren)."""
        return base * over
    
    def _blend_screen(self, base, over):
        """Screen Blend: Hellt auf (1 - (1-base) * (1-over))."""
        return 1.0 - (1.0 - base) * (1.0 - over)
    
    def _blend_add(self, base, over):
        """Add Blend (Linear Dodge): Addiert Farben."""
        return np.minimum(base + over, 1.0)
    
    def _blend_subtract(self, base, over):
        """Subtract Blend: Subtrahiert Farben."""
        return np.maximum(base - over, 0.0)
    
    def _blend_overlay(self, base, over):
        """
        Overlay Blend: Kombiniert Multiply und Screen.
        Wenn base < 0.5: 2 * base * over
        Wenn base >= 0.5: 1 - 2 * (1-base) * (1-over)
        """
        # Maske für base < 0.5
        mask = base < 0.5
        
        # Multiply für dunkle Bereiche (< 0.5)
        multiply = 2.0 * base * over
        
        # Screen für helle Bereiche (>= 0.5)
        screen = 1.0 - 2.0 * (1.0 - base) * (1.0 - over)
        
        # Kombiniere basierend auf Maske
        return np.where(mask, multiply, screen)
    
    def _blend_mask(self, base, over):
        """
        Mask Blend: Nutzt Overlay-Luminanz als Alpha-Maske.
        Weiß (1.0) = base vollständig sichtbar
        Schwarz (0.0) = base transparent (schwarz)
        """
        # Konvertiere Overlay zu Graustufen (Luminanz)
        # Verwende Standard-RGB-zu-Grau-Konversion: 0.299*R + 0.587*G + 0.114*B
        if len(over.shape) == 3 and over.shape[2] == 3:
            luminance = 0.299 * over[:, :, 0] + 0.587 * over[:, :, 1] + 0.114 * over[:, :, 2]
            # Erweitere zu 3 Kanälen für Broadcasting
            mask = np.stack([luminance, luminance, luminance], axis=2)
        else:
            # Falls bereits Graustufen
            mask = over
        
        # Wende Maske auf Base an: base * mask
        return base * mask
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if name == 'blend_mode':
            if value in self.BLEND_MODES:
                self.blend_mode = value
                return True
            return False
        elif name == 'opacity':
            self.opacity = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'blend_mode': self.blend_mode,
            'opacity': self.opacity
        }
