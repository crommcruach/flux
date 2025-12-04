"""
Webcam Generator Plugin - Live video capture from local webcams
"""
import numpy as np
import cv2
from plugins import PluginBase, PluginType, ParameterType


class WebcamGenerator(PluginBase):
    """
    Webcam Generator - Erfasst Live-Video von lokalen Webcams.
    
    Ermöglicht die Verwendung von angeschlossenen USB-Webcams oder integrierten Kameras
    als Videoquelle. Unterstützt verschiedene Auflösungen und Bildwiederholraten.
    """
    
    METADATA = {
        'id': 'webcam',
        'name': 'Webcam',
        'description': 'Live-Video-Erfassung von lokalen Webcams und Kameras',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Live Sources'
    }
    
    PARAMETERS = [
        {
            'name': 'device_id',
            'label': 'Kamera ID',
            'type': ParameterType.INT,
            'default': 0,
            'min': 0,
            'max': 10,
            'step': 1,
            'description': 'Kamera-Index (0 = Standard-Webcam, 1+ = zusätzliche Kameras)'
        },
        {
            'name': 'fps',
            'label': 'FPS',
            'type': ParameterType.INT,
            'default': 30,
            'min': 1,
            'max': 60,
            'step': 1,
            'description': 'Ziel-Bildwiederholrate (Frames pro Sekunde)'
        },
        {
            'name': 'width',
            'label': 'Capture-Breite',
            'type': ParameterType.INT,
            'default': 640,
            'min': 160,
            'max': 1920,
            'step': 160,
            'description': 'Capture-Breite in Pixeln (wird auf Ausgabe-Größe skaliert)'
        },
        {
            'name': 'height',
            'label': 'Capture-Höhe',
            'type': ParameterType.INT,
            'default': 480,
            'min': 120,
            'max': 1080,
            'step': 120,
            'description': 'Capture-Höhe in Pixeln (wird auf Ausgabe-Größe skaliert)'
        },
        {
            'name': 'mirror',
            'label': 'Spiegeln',
            'type': ParameterType.BOOL,
            'default': False,
            'description': 'Video horizontal spiegeln (nützlich für Selfie-Kameras)'
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
            'name': 'contrast',
            'label': 'Kontrast',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 3.0,
            'step': 0.1,
            'description': 'Kontrastanpassung (1.0 = Normal)'
        },
        {
            'name': 'saturation',
            'label': 'Sättigung',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Farbsättigung (0.0 = Graustufen, 1.0 = Normal)'
        },
        {
            'name': 'duration',
            'label': 'Duration (seconds)',
            'type': ParameterType.INT,
            'default': 10,
            'min': 1,
            'max': 60,
            'step': 60,
            'description': 'Maximale Capture-Dauer vor Auto-Advance (1h Standard)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Webcam-Capture."""
        self.device_id = int(config.get('device_id', 0))
        self.fps = int(config.get('fps', 30))
        self.capture_width = int(config.get('width', 640))
        self.capture_height = int(config.get('height', 480))
        self.mirror = bool(config.get('mirror', False))
        self.brightness = float(config.get('brightness', 1.0))
        self.contrast = float(config.get('contrast', 1.0))
        self.saturation = float(config.get('saturation', 1.0))
        self.duration = int(config.get('duration', 10))
        
        self.cap = None
        self.last_frame = None
        self.frame_count = 0
        self.time = 0.0
        
        # Versuche Kamera zu öffnen
        self._connect()
        
        return True
    
    def _connect(self):
        """Verbindet zur Webcam."""
        try:
            # Schließe alte Verbindung falls vorhanden
            if self.cap is not None:
                self.cap.release()
            
            # Öffne Webcam
            self.cap = cv2.VideoCapture(self.device_id)
            
            if not self.cap.isOpened():
                raise Exception(f"Konnte Kamera {self.device_id} nicht öffnen")
            
            # Setze Capture-Parameter
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.capture_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.capture_height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            
            # Versuche ersten Frame zu lesen
            ret, frame = self.cap.read()
            if not ret or frame is None:
                raise Exception("Konnte keinen Frame von der Kamera lesen")
            
            self.last_frame = frame
            
            return True
            
        except Exception as e:
            if self.cap:
                self.cap.release()
                self.cap = None
            return False
    
    def _apply_adjustments(self, frame):
        """Wendet Helligkeit, Kontrast und Sättigung an."""
        # Helligkeit & Kontrast anwenden
        if self.brightness != 1.0 or self.contrast != 1.0:
            # Konvertiere zu float für Berechnungen
            frame = frame.astype(np.float32)
            
            # Kontrast (um Mittelwert 127.5)
            if self.contrast != 1.0:
                frame = ((frame - 127.5) * self.contrast) + 127.5
            
            # Helligkeit
            if self.brightness != 1.0:
                frame = frame * self.brightness
            
            # Clipping und zurück zu uint8
            frame = np.clip(frame, 0, 255).astype(np.uint8)
        
        # Sättigung anwenden
        if self.saturation != 1.0:
            # Konvertiere zu HSV
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
            
            # Sättigung anpassen (S-Kanal)
            hsv[:, :, 1] = np.clip(hsv[:, :, 1] * self.saturation, 0, 255)
            
            # Zurück zu BGR
            hsv = hsv.astype(np.uint8)
            frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        
        return frame
    
    def process_frame(self, frame, **kwargs):
        """
        Generiert Frame von Webcam.
        
        Args:
            frame: Unused (generator creates new frame)
            **kwargs: Muss 'width', 'height' enthalten
        
        Returns:
            numpy.ndarray: Frame als (height, width, 3) RGB Array
        """
        width = kwargs.get('width', 60)
        height = kwargs.get('height', 300)
        time = kwargs.get('time', self.time)
        
        self.time = time
        
        # Prüfe ob Kamera verbunden ist
        if self.cap is None or not self.cap.isOpened():
            # Versuche neu zu verbinden
            if not self._connect():
                # Erstelle Fehler-Frame
                error_frame = np.zeros((height, width, 3), dtype=np.uint8)
                cv2.putText(error_frame, "Webcam Error", (width//2 - 80, height//2),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.putText(error_frame, f"Device {self.device_id}", (width//2 - 60, height//2 + 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 1)
                return error_frame
        
        # Versuche Frame zu lesen
        if self.cap and self.cap.isOpened():
            ret, captured_frame = self.cap.read()
            
            if ret and captured_frame is not None:
                self.last_frame = captured_frame
                self.frame_count += 1
                
                # Spiegeln falls aktiviert
                if self.mirror:
                    captured_frame = cv2.flip(captured_frame, 1)
                
                # Wende Anpassungen an
                captured_frame = self._apply_adjustments(captured_frame)
                
                # Konvertiere BGR zu RGB
                captured_frame = cv2.cvtColor(captured_frame, cv2.COLOR_BGR2RGB)
                
                # Skaliere auf Zielgröße
                if captured_frame.shape[1] != width or captured_frame.shape[0] != height:
                    captured_frame = cv2.resize(captured_frame, (width, height))
                
                return captured_frame
            else:
                # Fehler beim Lesen - Verbindung verloren
                if self.cap:
                    self.cap.release()
                    self.cap = None
        
        # Verwende letzten bekannten Frame oder schwarzen Frame
        if self.last_frame is not None:
            frame = self.last_frame.copy()
            
            # Spiegeln falls aktiviert
            if self.mirror:
                frame = cv2.flip(frame, 1)
            
            # Wende Anpassungen an
            frame = self._apply_adjustments(frame)
            
            # Konvertiere BGR zu RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Skaliere auf Zielgröße
            if frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height))
            
            # Füge "Reconnecting" Overlay hinzu
            cv2.putText(frame, "Reconnecting...", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            return frame
        else:
            # Kein Frame verfügbar
            return np.zeros((height, width, 3), dtype=np.uint8)
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'device_id':
            new_id = int(value)
            if new_id != self.device_id:
                self.device_id = new_id
                # Neu verbinden mit neuer Kamera-ID
                self._connect()
            return True
        elif name == 'fps':
            self.fps = int(value)
            if self.cap:
                self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            return True
        elif name == 'width':
            self.capture_width = int(value)
            if self.cap:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.capture_width)
            return True
        elif name == 'height':
            self.capture_height = int(value)
            if self.cap:
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.capture_height)
            return True
        elif name == 'mirror':
            self.mirror = bool(value)
            return True
        elif name == 'brightness':
            self.brightness = float(value)
            return True
        elif name == 'contrast':
            self.contrast = float(value)
            return True
        elif name == 'saturation':
            self.saturation = float(value)
            return True
        elif name == 'duration':
            self.duration = int(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'device_id': self.device_id,
            'fps': self.fps,
            'width': self.capture_width,
            'height': self.capture_height,
            'mirror': self.mirror,
            'brightness': self.brightness,
            'contrast': self.contrast,
            'saturation': self.saturation,
            'duration': self.duration
        }
    
    def cleanup(self):
        """Cleanup beim Beenden."""
        if self.cap:
            try:
                self.cap.release()
                self.cap = None
            except Exception:
                pass
