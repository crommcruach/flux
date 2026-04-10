"""
Screencapture Generator Plugin - Capture screen/window content
"""
import numpy as np
import cv2
from plugins import PluginBase, PluginType, ParameterType


class ScreencaptureGenerator(PluginBase):
    """
    Screencapture Generator - Erfasst Bildschirm- oder Fenster-Inhalte.
    
    Ermöglicht das Aufnehmen des gesamten Bildschirms, einzelner Monitore oder
    spezifischer Bereiche. Nutzt 'mss' für performante Screen-Captures.
    """
    
    METADATA = {
        'id': 'screencapture',
        'name': 'Screen Capture',
        'description': 'Erfasst Bildschirm- oder Fenster-Inhalte in Echtzeit',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Live Sources'
    }
    
    PARAMETERS = [
        {
            'name': 'monitor',
            'label': 'Monitor',
            'type': ParameterType.INT,
            'default': 1,
            'min': 0,
            'max': 10,
            'step': 1,
            'description': 'Monitor-Index (0 = alle Monitore, 1 = primärer Monitor, 2+ = weitere)'
        },
        {
            'name': 'capture_rate',
            'label': 'Capture Rate (FPS)',
            'type': ParameterType.INT,
            'default': 30,
            'min': 1,
            'max': 60,
            'step': 1,
            'description': 'Frames pro Sekunde (höhere Werte = mehr CPU-Last)'
        },
        {
            'name': 'use_region',
            'label': 'Region verwenden',
            'type': ParameterType.BOOL,
            'default': False,
            'description': 'Nur einen bestimmten Bildschirmbereich erfassen'
        },
        {
            'name': 'region_x',
            'label': 'Region X',
            'type': ParameterType.INT,
            'default': 0,
            'min': 0,
            'max': 7680,
            'step': 10,
            'description': 'X-Koordinate der Region (nur wenn "Region verwenden" aktiviert)'
        },
        {
            'name': 'region_y',
            'label': 'Region Y',
            'type': ParameterType.INT,
            'default': 0,
            'min': 0,
            'max': 4320,
            'step': 10,
            'description': 'Y-Koordinate der Region (nur wenn "Region verwenden" aktiviert)'
        },
        {
            'name': 'region_width',
            'label': 'Region Breite',
            'type': ParameterType.INT,
            'default': 1920,
            'min': 100,
            'max': 7680,
            'step': 10,
            'description': 'Breite der Region in Pixeln'
        },
        {
            'name': 'region_height',
            'label': 'Region Höhe',
            'type': ParameterType.INT,
            'default': 1080,
            'min': 100,
            'max': 4320,
            'step': 10,
            'description': 'Höhe der Region in Pixeln'
        },
        {
            'name': 'show_cursor',
            'label': 'Cursor anzeigen',
            'type': ParameterType.BOOL,
            'default': True,
            'description': 'Mauszeiger im Capture anzeigen (nicht alle Backends unterstützen dies)'
        },
        {
            'name': 'brightness',
            'label': 'Helligkeit',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Helligkeitsanpassung (1.0 = Normal)'
        },
        {
            'name': 'duration',
            'label': 'Duration (seconds)',
            'type': ParameterType.STRING,
            'default': '10',
            'description': 'Duration in seconds (1-60, affects Transport timeline)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Screen-Capture."""
        self.monitor = int(config.get('monitor', 1))
        self.capture_rate = int(config.get('capture_rate', 30))
        self.use_region = bool(config.get('use_region', False))
        self.region_x = int(config.get('region_x', 0))
        self.region_y = int(config.get('region_y', 0))
        self.region_width = int(config.get('region_width', 1920))
        self.region_height = int(config.get('region_height', 1080))
        self.show_cursor = bool(config.get('show_cursor', True))
        self.brightness = float(config.get('brightness', 1.0))
        # Duration can be string or number, convert and clamp to 1-60
        duration_val = config.get('duration', 10)
        try:
            self.duration = max(1, min(60, float(duration_val)))
        except (ValueError, TypeError):
            self.duration = 10
        
        self.sct = None
        self.last_frame = None
        self.frame_count = 0
        self.time = 0.0
        self.last_capture_time = 0.0
        self.frame_interval = 1.0 / self.capture_rate
        
        # Versuche mss zu importieren und zu initialisieren
        try:
            import mss
            self.sct = mss.mss()
            self.has_mss = True
        except ImportError:
            # Fallback: Verwende PyAutoGUI falls mss nicht verfügbar
            try:
                import pyautogui
                self.has_mss = False
                self.pyautogui = pyautogui
            except ImportError:
                # Kein Screen-Capture Backend verfügbar
                self.has_mss = False
                self.pyautogui = None
        
        return True
    
    def _get_monitor_info(self):
        """Gibt Monitor-Informationen zurück."""
        if self.has_mss and self.sct:
            # mss: Monitor 0 = alle Monitore, 1+ = einzelne Monitore
            monitors = self.sct.monitors
            if 0 <= self.monitor < len(monitors):
                return monitors[self.monitor]
            else:
                # Fallback auf primären Monitor
                return monitors[1] if len(monitors) > 1 else monitors[0]
        return None
    
    def _capture_mss(self, width, height):
        """Capture mit mss (performant)."""
        try:
            # Bestimme Capture-Region
            if self.use_region:
                # Benutzerdefinierte Region
                monitor = {
                    'left': self.region_x,
                    'top': self.region_y,
                    'width': self.region_width,
                    'height': self.region_height
                }
            else:
                # Ganzer Monitor
                monitor = self._get_monitor_info()
                if monitor is None:
                    return None
            
            # Capture Screenshot
            screenshot = self.sct.grab(monitor)
            
            # Konvertiere zu numpy array (BGRA Format)
            frame = np.array(screenshot)
            
            # Konvertiere BGRA zu RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
            
            return frame
            
        except Exception as e:
            return None
    
    def _capture_pyautogui(self, width, height):
        """Capture mit PyAutoGUI (Fallback)."""
        try:
            # Bestimme Capture-Region
            if self.use_region:
                region = (self.region_x, self.region_y, self.region_width, self.region_height)
            else:
                region = None
            
            # Screenshot aufnehmen
            screenshot = self.pyautogui.screenshot(region=region)
            
            # Konvertiere PIL Image zu numpy array
            frame = np.array(screenshot)
            
            # PIL gibt RGB zurück, keine Konvertierung nötig
            return frame
            
        except Exception as e:
            return None
    
    def _apply_brightness(self, frame):
        """Wendet Helligkeitsanpassung an."""
        if self.brightness != 1.0:
            frame = frame.astype(np.float32)
            frame = frame * self.brightness
            frame = np.clip(frame, 0, 255).astype(np.uint8)
        return frame
    
    def process_frame(self, frame, **kwargs):
        """
        Generiert Frame von Screen-Capture.
        
        Args:
            frame: Unused (generator creates new frame)
            **kwargs: Muss 'width', 'height' enthalten, optional 'time'
        
        Returns:
            numpy.ndarray: Frame als (height, width, 3) RGB Array
        """
        width = kwargs.get('width', 60)
        height = kwargs.get('height', 300)
        time = kwargs.get('time', self.time)
        
        self.time = time
        
        # Prüfe ob genug Zeit seit letztem Capture vergangen ist (Frame-Rate-Limiting)
        if time - self.last_capture_time < self.frame_interval:
            # Verwende letzten Frame
            if self.last_frame is not None:
                frame = self.last_frame.copy()
                # Skaliere auf Zielgröße
                if frame.shape[1] != width or frame.shape[0] != height:
                    frame = cv2.resize(frame, (width, height))
                return frame
            else:
                return np.zeros((height, width, 3), dtype=np.uint8)
        
        self.last_capture_time = time
        
        # Prüfe ob Capture-Backend verfügbar ist
        if not self.has_mss and self.pyautogui is None:
            # Kein Backend verfügbar - zeige Fehler
            error_frame = np.zeros((height, width, 3), dtype=np.uint8)
            cv2.putText(error_frame, "Screen Capture Error", (width//2 - 120, height//2),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(error_frame, "Install: pip install mss", (width//2 - 140, height//2 + 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 1)
            return error_frame
        
        # Capture Screen
        if self.has_mss:
            captured_frame = self._capture_mss(width, height)
        else:
            captured_frame = self._capture_pyautogui(width, height)
        
        if captured_frame is not None:
            self.last_frame = captured_frame
            self.frame_count += 1
            
            # Wende Helligkeit an
            captured_frame = self._apply_brightness(captured_frame)
            
            # Skaliere auf Zielgröße
            if captured_frame.shape[1] != width or captured_frame.shape[0] != height:
                captured_frame = cv2.resize(captured_frame, (width, height))
            
            return captured_frame
        else:
            # Fehler beim Capture - verwende letzten Frame oder schwarzen Frame
            if self.last_frame is not None:
                frame = self.last_frame.copy()
                
                # Wende Helligkeit an
                frame = self._apply_brightness(frame)
                
                # Skaliere auf Zielgröße
                if frame.shape[1] != width or frame.shape[0] != height:
                    frame = cv2.resize(frame, (width, height))
                
                # Füge "Capture Error" Overlay hinzu
                cv2.putText(frame, "Capture Error", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                return frame
            else:
                return np.zeros((height, width, 3), dtype=np.uint8)
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'monitor':
            self.monitor = int(value)
            return True
        elif name == 'capture_rate':
            self.capture_rate = int(value)
            self.frame_interval = 1.0 / max(1, self.capture_rate)
            return True
        elif name == 'use_region':
            self.use_region = bool(value)
            return True
        elif name == 'region_x':
            self.region_x = int(value)
            return True
        elif name == 'region_y':
            self.region_y = int(value)
            return True
        elif name == 'region_width':
            self.region_width = int(value)
            return True
        elif name == 'region_height':
            self.region_height = int(value)
            return True
        elif name == 'show_cursor':
            self.show_cursor = bool(value)
            # Hinweis: Nicht alle Backends unterstützen Cursor-Kontrolle
            return True
        elif name == 'brightness':
            self.brightness = float(value)
            return True
        elif name == 'duration':
            self.duration = int(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'monitor': self.monitor,
            'capture_rate': self.capture_rate,
            'use_region': self.use_region,
            'region_x': self.region_x,
            'region_y': self.region_y,
            'region_width': self.region_width,
            'region_height': self.region_height,
            'show_cursor': self.show_cursor,
            'brightness': self.brightness,
            'duration': self.duration
        }
    
    def cleanup(self):
        """Cleanup beim Beenden."""
        if self.sct:
            try:
                self.sct.close()
                self.sct = None
            except Exception:
                pass
