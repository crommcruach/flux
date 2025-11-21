"""
Art-Net Manager - Verwaltet Art-Net Ausgabe und Testmuster
"""
import time
import threading
import numpy as np
from stupidArtnet import StupidArtnet
from .logger import get_logger

logger = get_logger(__name__)


class ArtNetManager:
    """Verwaltet Art-Net Universen und Testmuster mit Priorität."""
    
    def __init__(self, target_ip, start_universe, total_points, channels_per_universe=3):
        self.target_ip = target_ip
        self.start_universe = start_universe
        self.total_points = total_points
        self.channels_per_universe = channels_per_universe
        self.last_frame = None  # Für DMX Monitor
        
        # Berechne benötigte Universen
        total_channels = total_points * 3  # RGB
        self.required_universes = (total_channels + channels_per_universe - 1) // channels_per_universe
        
        self.universes = []
        self.universe_channel_orders = {}  # Universe-Index -> channel_order (z.B. "GRB")
        self.is_active = False
        
        # Priorisierung: Test > Replay > Video
        self.test_mode = False  # True wenn Testmuster aktiv (höchste Priorität)
        self.replay_mode = False  # True wenn Replay aktiv (überschreibt Video)
        self.test_pattern_data = None  # Gespeicherte Testmuster-Daten
        self.test_thread = None  # Thread für kontinuierliches Testmuster-Senden
        self.test_thread_running = False
        
        # Statistik-Tracking
        self.packets_sent = 0
        self.bytes_sent = 0
        self.stats_start_time = time.time()
        self.stats_lock = threading.Lock()
        
        # RGB-Kanal-Mapping: Definiert Reihenfolge für jede Permutation
        self.channel_mappings = {
            'RGB': [0, 1, 2],  # Standard: R=0, G=1, B=2
            'GRB': [1, 0, 2],  # G=0, R=1, B=2
            'BGR': [2, 1, 0],  # B=0, G=1, R=2
            'RBG': [0, 2, 1],  # R=0, B=1, G=2
            'GBR': [1, 2, 0],  # G=0, B=1, R=2
            'BRG': [2, 0, 1]   # B=0, R=1, G=2
        }
        
    def start(self, artnet_config=None):
        """Startet Art-Net Universen."""
        if self.is_active:
            return
        
        # Lade Werte aus config oder verwende defaults
        config = artnet_config or {}
        # Höhere FPS für flüssigere Ausgabe (wird von show() überschrieben)
        self.artnet_fps = config.get('fps', 60)
        fps = self.artnet_fps
        even_packet = config.get('even_packet', True)
        broadcast = config.get('broadcast', True)
        
        # Lade Universe-spezifische Kanal-Reihenfolgen
        universe_configs = config.get('universe_configs', {})
        default_order = universe_configs.get('default', 'RGB')
        
        # Konfiguriere Kanal-Reihenfolge pro Universum
        for i in range(self.required_universes):
            universe_num = str(self.start_universe + i)
            channel_order = universe_configs.get(universe_num, default_order)
            self.universe_channel_orders[i] = channel_order.upper()
        
        logger.debug("Starte Art-Net...")
        for i in range(self.required_universes):
            universe = StupidArtnet(
                self.target_ip, 
                self.start_universe + i, 
                self.channels_per_universe, 
                fps,
                even_packet,
                broadcast
            )
            # WICHTIG: start() nicht aufrufen - wir senden manuell mit show()
            # Der interne Thread von stupidArtnet kann Flackern verursachen
            self.universes.append(universe)
            logger.debug(f"  Art-Net Universum {self.start_universe + i} initialisiert (manueller Modus)")
        self.is_active = True
    
    def stop(self):
        """Stoppt Art-Net und sendet finalen Blackout."""
        if not self.is_active:
            return
        
        # Stoppe Test-Thread falls aktiv
        self._stop_test_thread()
        
        # Sende finalen Blackout (direkt, ohne Thread)
        logger.debug("Sende finalen Blackout...")
        zero_data = [0] * self.channels_per_universe
        for universe in self.universes:
            universe.set(zero_data)
            universe.show()
        
        time.sleep(0.1)
        
        # Kein universe.stop() nötig da wir keinen Thread gestartet haben
        
        self.universes = []
        self.is_active = False
        logger.debug("Art-Net gestoppt")
    
    def send_frame(self, rgb_data, source='video'):
        """Sendet RGB-Frame über Art-Net mit Priorisierung.
        
        Args:
            rgb_data: DMX-Daten
            source: 'video', 'replay', oder 'test'
        
        Priorität: test > replay > video
        """
        if not self.is_active:
            return
        
        # Test hat höchste Priorität - blockiert alles
        if self.test_mode:
            return
        
        # Replay blockiert Video
        if self.replay_mode and source == 'video':
            return
        
        # Speichere für DMX Monitor (was tatsächlich gesendet wird)
        self.last_frame = rgb_data
        
        for universe_idx, universe in enumerate(self.universes):
            start_channel = universe_idx * self.channels_per_universe
            end_channel = min(start_channel + self.channels_per_universe, len(rgb_data))
            universe_data = rgb_data[start_channel:end_channel]
            
            # Wende Kanal-Umordnung für dieses Universum an
            universe_data = self._reorder_channels(universe_data, universe_idx)
            
            if len(universe_data) < self.channels_per_universe:
                universe_data.extend([0] * (self.channels_per_universe - len(universe_data)))
            
            # Setze Daten UND sende sofort (flush=True umgeht FPS-Limiting)
            universe.set(universe_data)
            universe.show()  # Explizit senden ohne FPS-Wartezeit
        
        # Statistik: Zähle gesendete Pakete
        with self.stats_lock:
            self.packets_sent += len(self.universes)
            # Art-Net Paket: 18B Header + 512B Data + 8B UDP + 20B IP + 14B Ethernet ≈ 572 Bytes
            self.bytes_sent += len(self.universes) * 572
    
    def _stop_test_thread(self):
        """Stoppt den Test-Thread."""
        if self.test_thread and self.test_thread_running:
            self.test_thread_running = False
            if self.test_thread.is_alive():
                self.test_thread.join(timeout=1.0)
            self.test_thread = None
    
    def _test_pattern_loop(self):
        """Thread-Funktion: Sendet Testmuster kontinuierlich (~40 Hz)."""
        while self.test_thread_running and self.is_active:
            if self.test_pattern_data:
                # Speichere für DMX Monitor
                self.last_frame = self.test_pattern_data
                
                for universe_idx, universe in enumerate(self.universes):
                    start_channel = universe_idx * self.channels_per_universe
                    end_channel = min(start_channel + self.channels_per_universe, len(self.test_pattern_data))
                    universe_data = self.test_pattern_data[start_channel:end_channel]
                    
                    # Wende Kanal-Umordnung für dieses Universum an
                    universe_data = self._reorder_channels(universe_data, universe_idx)
                    
                    if len(universe_data) < self.channels_per_universe:
                        universe_data.extend([0] * (self.channels_per_universe - len(universe_data)))
                    
                    universe.set(universe_data)
                    universe.show()
                
                # Statistik: Zähle gesendete Pakete
                with self.stats_lock:
                    self.packets_sent += len(self.universes)
                    self.bytes_sent += len(self.universes) * 572
            
            time.sleep(0.025)  # 40 Hz Refresh-Rate
    
    def blackout(self):
        """Sendet Blackout (alle Kanäle auf 0)."""
        if not self.is_active:
            return
        
        # Stoppe alten Test-Thread
        self._stop_test_thread()
        
        # Setze Blackout-Daten und starte Thread
        self.test_mode = True
        self.test_pattern_data = [0] * (self.total_points * 3)
        
        self.test_thread_running = True
        self.test_thread = threading.Thread(target=self._test_pattern_loop, daemon=True)
        self.test_thread.start()
        
        logger.info("Blackout gesendet")
    
    def test_pattern(self, color='red'):
        """Sendet Testmuster (hat Vorrang vor Video)."""
        if not self.is_active:
            logger.warning("Art-Net nicht aktiv!")
            return
        
        # Stoppe alten Test-Thread
        self._stop_test_thread()
        
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
            logger.warning(f"Unbekannte Farbe! Verfügbar: {', '.join(colors.keys())}, gradient")
            return
        
        r, g, b = colors[color]
        self.test_pattern_data = [r, g, b] * self.total_points
        
        # Starte Thread für kontinuierliches Senden
        self.test_thread_running = True
        self.test_thread = threading.Thread(target=self._test_pattern_loop, daemon=True)
        self.test_thread.start()
        
        logger.info(f"Testmuster '{color}' gesendet (Video gestoppt)")
    
    def _gradient_pattern(self):
        """Erzeugt RGB-Farbverlauf über alle Punkte."""
        self.test_pattern_data = []
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
            
            self.test_pattern_data.extend([r, g, b])
        
        # Starte Thread für kontinuierliches Senden
        self.test_thread_running = True
        self.test_thread = threading.Thread(target=self._test_pattern_loop, daemon=True)
        self.test_thread.start()
        
        logger.debug(f"RGB-Gradient Testmuster gesendet ({self.total_points} Punkte, Video gestoppt)")
    
    def resume_video_mode(self):
        """Deaktiviert Test- und Replay-Modus, erlaubt Video-Wiedergabe."""
        self._stop_test_thread()
        self.test_mode = False
        self.replay_mode = False
        self.test_pattern_data = None
        logger.debug("Video-Modus aktiviert")
    
    def get_active_mode(self):
        """Gibt den aktuellen aktiven Modus zurück."""
        if self.test_mode:
            return "Test"
        elif self.replay_mode:
            return "Replay"
        else:
            return "Video"
    
    def set_fps(self, fps):
        """Setzt Art-Net FPS für alle Universen."""
        if not self.is_active:
            return
        fps = max(1, min(60, int(fps)))  # Limit 1-60 FPS (realistisch für LED-Strips)
        self.artnet_fps = fps
        for universe in self.universes:
            universe.fps = fps
        logger.debug(f"Art-Net FPS auf {fps} gesetzt")
    
    def get_fps(self):
        """Gibt aktuelle Art-Net FPS zurück."""
        return getattr(self, 'artnet_fps', 60)
    
    def get_network_stats(self):
        """Gibt Netzwerk-Statistiken zurück."""
        with self.stats_lock:
            elapsed = time.time() - self.stats_start_time
            if elapsed < 0.1:  # Verhindere Division durch 0
                return {
                    'packets_sent': 0,
                    'packets_per_sec': 0,
                    'bytes_sent': 0,
                    'bytes_per_sec': 0,
                    'mbps': 0.0,
                    'network_load_percent': 0.0
                }
            
            packets_per_sec = self.packets_sent / elapsed
            bytes_per_sec = self.bytes_sent / elapsed
            mbps = (bytes_per_sec * 8) / 1_000_000  # Megabit pro Sekunde
            # Netzwerkauslastung basierend auf 1 Gbit/s Netzwerk
            network_load = (bytes_per_sec / 125_000_000) * 100
            
            return {
                'packets_sent': self.packets_sent,
                'packets_per_sec': round(packets_per_sec, 1),
                'bytes_sent': self.bytes_sent,
                'bytes_per_sec': round(bytes_per_sec, 1),
                'mbps': round(mbps, 2),
                'network_load_percent': round(network_load, 2)
            }
    
    def reset_stats(self):
        """Setzt Statistiken zurück."""
        with self.stats_lock:
            self.packets_sent = 0
            self.bytes_sent = 0
            self.stats_start_time = time.time()
    
    def _reorder_channels(self, data, universe_idx):
        """Ordnet RGB-Kanäle entsprechend der Universum-Konfiguration um."""
        channel_order = self.universe_channel_orders.get(universe_idx, 'RGB')
        
        # Wenn RGB (Standard), keine Umordnung nötig
        if channel_order == 'RGB':
            return data
        
        # Hole Mapping für diese Reihenfolge
        mapping = self.channel_mappings.get(channel_order)
        if not mapping:
            return data  # Fallback bei ungültiger Konfiguration
        
        # Erstelle neues Array mit umgeordneten Kanälen
        reordered = []
        for i in range(0, len(data), 3):
            if i + 2 < len(data):
                # Lese RGB aus Original-Daten
                rgb = [data[i], data[i+1], data[i+2]]
                # Schreibe in neuer Reihenfolge
                reordered.extend([rgb[mapping[0]], rgb[mapping[1]], rgb[mapping[2]]])
            else:
                # Rest beibehalten falls nicht vollständig
                reordered.extend(data[i:])
                break
        
        return reordered
