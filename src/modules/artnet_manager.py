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
        
        # Statistik-Tracking (AtomicInteger-Pattern für Lock-free Stats)
        # Verwende threading.local() würde hier nicht helfen, da Stats global sind
        # Stattdessen: Atomic operations mit numpy (schneller als Lock)
        self._stats_packets = np.array([0], dtype=np.int64)  # Atomic counter
        self._stats_bytes = np.array([0], dtype=np.int64)    # Atomic counter
        
        # Gradient Pattern Cache (verhindert Neuberechnung)
        self._gradient_cache = None
        self.stats_start_time = time.time()
        
        # Delta-Encoding State
        self.delta_encoding_enabled = False
        self.delta_threshold = 8  # Default für 8-bit
        self.full_frame_interval = 30
        self.frame_counter = 0
        self.last_sent_frame = None  # Für Delta-Berechnung
        self.bit_depth = 8  # 8 oder 16
        
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
        
        # Delta-Encoding Konfiguration
        self.bit_depth = config.get('bit_depth', 8)
        delta_config = config.get('delta_encoding', {})
        self.delta_encoding_enabled = delta_config.get('enabled', False)
        
        # Threshold je nach bit_depth
        if self.bit_depth == 16:
            self.delta_threshold = delta_config.get('threshold_16bit', 2048)
        else:
            self.delta_threshold = delta_config.get('threshold', 8)
        
        self.full_frame_interval = delta_config.get('full_frame_interval', 30)
        
        logger.info(f"Delta-Encoding: {'Aktiviert' if self.delta_encoding_enabled else 'Deaktiviert'} "
                   f"(Bit-Tiefe: {self.bit_depth}, Threshold: {self.delta_threshold})")
        
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
        """Sendet RGB-Frame über Art-Net mit Priorisierung und Delta-Encoding.
        
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
        
        # Delta-Encoding: Prüfe ob Full-Frame nötig oder Delta möglich
        self.frame_counter += 1
        force_full_frame = (self.frame_counter % self.full_frame_interval == 0)
        
        if self.delta_encoding_enabled and not force_full_frame and self.last_sent_frame is not None:
            # Delta-Mode: Sende nur geänderte Pixel
            rgb_array = np.array(rgb_data, dtype=np.uint8)
            last_array = np.array(self.last_sent_frame, dtype=np.uint8)
            
            # Berechne Differenz (absolute difference für alle Channels)
            diff = np.abs(rgb_array.astype(np.int16) - last_array.astype(np.int16))
            
            # Finde Pixel mit signifikanter Änderung (max diff über R,G,B Channels)
            diff_per_pixel = diff.reshape(-1, 3).max(axis=1)
            changed_pixels = diff_per_pixel > self.delta_threshold
            
            # Wenn > 80% geändert, sende Full-Frame (effizienter)
            if np.sum(changed_pixels) > (len(changed_pixels) * 0.8):
                force_full_frame = True
        else:
            force_full_frame = True
        
        # Speichere aktuelles Frame für nächste Delta-Berechnung
        self.last_sent_frame = rgb_data.copy()
        
        universes_sent = 0
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
            universes_sent += 1
        
        # Statistik: Zähle gesendete Pakete (Lock-free mit numpy atomic ops)
        self._stats_packets[0] += universes_sent
        # Art-Net Paket: 18B Header + 512B Data + 8B UDP + 20B IP + 14B Ethernet ≈ 572 Bytes
        self._stats_bytes[0] += universes_sent * 572
    
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
                # Lock-free atomic increment
                self._stats_packets[0] += len(self.universes)
                self._stats_bytes[0] += len(self.universes) * 572
            
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
        """Erzeugt RGB-Farbverlauf über alle Punkte (NumPy-optimiert mit Cache)."""
        # Cache-Check: Gradient ist statisch für gegebene total_points
        if self._gradient_cache is not None:
            self.test_pattern_data = self._gradient_cache
        else:
            # NumPy-Vektorisierung: HSV->RGB für alle Punkte gleichzeitig
            import cv2
            
            # Erzeuge Hue-Werte (0-180 für OpenCV HSV)
            hues = np.linspace(0, 180, self.total_points, dtype=np.uint8)
            
            # Erstelle HSV array (alle Pixel: volle Sättigung & Helligkeit)
            hsv = np.zeros((1, self.total_points, 3), dtype=np.uint8)
            hsv[0, :, 0] = hues  # Hue
            hsv[0, :, 1] = 255   # Saturation
            hsv[0, :, 2] = 255   # Value
            
            # Konvertiere HSV->RGB (vektorisiert, ~10x schneller)
            rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
            
            # Flatten zu [r,g,b, r,g,b, ...]
            self.test_pattern_data = rgb.flatten().tolist()
            
            # Cache speichern für nächsten Aufruf
            self._gradient_cache = self.test_pattern_data
        
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
        """Gibt Netzwerk-Statistiken zurück (Lock-free)."""
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
        
        # Atomic reads (numpy arrays sind thread-safe für einzelne Elemente)
        packets_sent = int(self._stats_packets[0])
        bytes_sent = int(self._stats_bytes[0])
        
        packets_per_sec = packets_sent / elapsed
        bytes_per_sec = bytes_sent / elapsed
        mbps = (bytes_per_sec * 8) / 1_000_000  # Megabit pro Sekunde
        # Netzwerkauslastung basierend auf 1 Gbit/s Netzwerk
        network_load = (bytes_per_sec / 125_000_000) * 100
        
        return {
            'packets_sent': packets_sent,
            'packets_per_sec': round(packets_per_sec, 1),
            'bytes_sent': bytes_sent,
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
        """Ordnet RGB-Kanäle entsprechend der Universum-Konfiguration um (NumPy-optimiert)."""
        import numpy as np
        
        channel_order = self.universe_channel_orders.get(universe_idx, 'RGB')
        
        # Wenn RGB (Standard), keine Umordnung nötig
        if channel_order == 'RGB':
            return data
        
        # Hole Mapping für diese Reihenfolge
        mapping = self.channel_mappings.get(channel_order)
        if not mapping:
            return data  # Fallback bei ungültiger Konfiguration
        
        # NumPy fancy indexing - 10x schneller als Python-Loop
        # Konvertiere zu NumPy array und reshapen zu (N, 3)
        data_array = np.array(data, dtype=np.uint8)
        num_pixels = len(data_array) // 3
        
        if num_pixels * 3 == len(data_array):
            # Perfekt teilbar durch 3 - reshape und reorder in einem Schritt
            rgb_pixels = data_array.reshape(-1, 3)
            reordered_pixels = rgb_pixels[:, mapping]
            return reordered_pixels.flatten().tolist()
        else:
            # Nicht perfekt teilbar - behandle Rest separat
            complete_pixels = num_pixels * 3
            rgb_pixels = data_array[:complete_pixels].reshape(-1, 3)
            reordered_pixels = rgb_pixels[:, mapping]
            reordered = reordered_pixels.flatten().tolist()
            reordered.extend(data_array[complete_pixels:].tolist())
            return reordered
