"""
Art-Net Manager - Verwaltet Art-Net Ausgabe und Testmuster
"""
import time
import numpy as np
from stupidArtnet import StupidArtnet


class ArtNetManager:
    """Verwaltet Art-Net Universen und Testmuster mit Priorität."""
    
    def __init__(self, target_ip, start_universe, total_points, channels_per_universe=510):
        self.target_ip = target_ip
        self.start_universe = start_universe
        self.total_points = total_points
        self.channels_per_universe = channels_per_universe
        
        # Berechne benötigte Universen
        total_channels = total_points * 3  # RGB
        self.required_universes = (total_channels + channels_per_universe - 1) // channels_per_universe
        
        self.universes = []
        self.is_active = False
        self.test_mode = False  # True wenn Testmuster aktiv
        
    def start(self, artnet_config=None):
        """Startet Art-Net Universen."""
        if self.is_active:
            return
        
        # Lade Werte aus config oder verwende defaults
        config = artnet_config or {}
        fps = config.get('fps', 30)
        even_packet = config.get('even_packet', True)
        broadcast = config.get('broadcast', True)
        
        print("Starte Art-Net...")
        for i in range(self.required_universes):
            universe = StupidArtnet(
                self.target_ip, 
                self.start_universe + i, 
                self.channels_per_universe, 
                fps,
                even_packet,
                broadcast
            )
            universe.start()
            self.universes.append(universe)
            print(f"  Art-Net Universum {self.start_universe + i} gestartet")
        
        self.is_active = True
    
    def stop(self):
        """Stoppt Art-Net und sendet Blackout."""
        if not self.is_active:
            return
        
        print("Stoppe Art-Net...")
        self.blackout()
        time.sleep(0.1)
        
        for universe in self.universes:
            universe.stop()
        
        self.universes = []
        self.is_active = False
    
    def send_frame(self, rgb_data):
        """Sendet RGB-Frame über Art-Net (nur wenn kein Testmuster aktiv)."""
        if not self.is_active or self.test_mode:
            return
        
        for universe_idx, universe in enumerate(self.universes):
            start_channel = universe_idx * self.channels_per_universe
            end_channel = min(start_channel + self.channels_per_universe, len(rgb_data))
            universe_data = rgb_data[start_channel:end_channel]
            
            if len(universe_data) < self.channels_per_universe:
                universe_data.extend([0] * (self.channels_per_universe - len(universe_data)))
            
            universe.set(universe_data)
    
    def blackout(self):
        """Sendet Blackout (alle Kanäle auf 0)."""
        if not self.is_active:
            return
        
        zero_data = [0] * self.channels_per_universe
        for universe in self.universes:
            universe.set(zero_data)
        
        self.test_mode = False
        print("Blackout gesendet")
    
    def test_pattern(self, color='red'):
        """Sendet Testmuster (hat Vorrang vor Video)."""
        if not self.is_active:
            print("Art-Net nicht aktiv!")
            return
        
        self.test_mode = True
        
        # Spezielle Muster
        if color == 'gradient':
            self._gradient_pattern()
            return
        
        colors = {
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
            'white': (255, 255, 255),
            'yellow': (255, 255, 0),
            'cyan': (0, 255, 255),
            'magenta': (255, 0, 255)
        }
        
        if color not in colors:
            print(f"Unbekannte Farbe! Verfügbar: {', '.join(colors.keys())}, gradient")
            return
        
        r, g, b = colors[color]
        test_data = [r, g, b] * self.total_points
        
        for universe_idx, universe in enumerate(self.universes):
            start_channel = universe_idx * self.channels_per_universe
            end_channel = min(start_channel + self.channels_per_universe, len(test_data))
            universe_data = test_data[start_channel:end_channel]
            
            if len(universe_data) < self.channels_per_universe:
                universe_data.extend([0] * (self.channels_per_universe - len(universe_data)))
            
            universe.set(universe_data)
        
        print(f"Testmuster '{color}' gesendet (Video pausiert)")
    
    def _gradient_pattern(self):
        """Erzeugt RGB-Farbverlauf über alle Punkte."""
        test_data = []
        for i in range(self.total_points):
            # Position im Verlauf (0.0 bis 1.0)
            pos = i / max(self.total_points - 1, 1)
            
            # RGB-Gradient: Rot -> Gelb -> Grün -> Cyan -> Blau -> Magenta -> Rot
            if pos < 1/6:  # Rot -> Gelb
                r, g, b = 255, int(255 * (pos * 6)), 0
            elif pos < 2/6:  # Gelb -> Grün
                r, g, b = int(255 * (1 - (pos - 1/6) * 6)), 255, 0
            elif pos < 3/6:  # Grün -> Cyan
                r, g, b = 0, 255, int(255 * ((pos - 2/6) * 6))
            elif pos < 4/6:  # Cyan -> Blau
                r, g, b = 0, int(255 * (1 - (pos - 3/6) * 6)), 255
            elif pos < 5/6:  # Blau -> Magenta
                r, g, b = int(255 * ((pos - 4/6) * 6)), 0, 255
            else:  # Magenta -> Rot
                r, g, b = 255, 0, int(255 * (1 - (pos - 5/6) * 6))
            
            test_data.extend([r, g, b])
        
        for universe_idx, universe in enumerate(self.universes):
            start_channel = universe_idx * self.channels_per_universe
            end_channel = min(start_channel + self.channels_per_universe, len(test_data))
            universe_data = test_data[start_channel:end_channel]
            
            if len(universe_data) < self.channels_per_universe:
                universe_data.extend([0] * (self.channels_per_universe - len(universe_data)))
            
            universe.set(universe_data)
        
        print(f"RGB-Gradient Testmuster gesendet ({self.total_points} Punkte, Video pausiert)")
    
    def resume_video_mode(self):
        """Deaktiviert Testmuster-Modus, erlaubt Video-Wiedergabe."""
        self.test_mode = False
        print("Video-Modus aktiviert")
