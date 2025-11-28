"""
LiveStream Generator Plugin - Live video from HTTP/RTSP/HLS streams
"""
import numpy as np
import cv2
from plugins import PluginBase, PluginType, ParameterType
from modules.logger import get_logger

logger = get_logger(__name__)


class LiveStreamGenerator(PluginBase):
    """
    LiveStream Generator - Erfasst Live-Video von verschiedenen Stream-Protokollen.
    
    Unterstützt RTSP, HTTP, HLS und weitere Streaming-Protokolle über FFmpeg.
    Ideal für IP-Kameras, Streaming-Server und andere Live-Videoquellen.
    """
    
    METADATA = {
        'id': 'livestream',
        'name': 'Live Stream',
        'description': 'Live-Video von HTTP/RTSP/HLS/RTMP, YouTube und anderen Streaming-Protokollen',
        'author': 'Flux Team',
        'version': '1.1.0',
        'type': PluginType.GENERATOR,
        'category': 'Live Sources'
    }
    
    PARAMETERS = [
        {
            'name': 'stream_url',
            'label': 'Stream URL',
            'type': ParameterType.STRING,
            'default': 'rtsp://localhost:8554/stream',
            'description': 'Stream-URL (RTSP, HTTP, HLS, RTMP, YouTube, etc.) - Benötigt yt-dlp für YouTube'
        },
        {
            'name': 'protocol',
            'label': 'Protokoll',
            'type': ParameterType.SELECT,
            'default': 'auto',
            'options': ['auto', 'rtsp', 'http', 'hls', 'rtmp', 'udp'],
            'description': 'Stream-Protokoll (auto = automatische Erkennung)'
        },
        {
            'name': 'reconnect_delay',
            'label': 'Reconnect Delay (s)',
            'type': ParameterType.INT,
            'default': 5,
            'min': 1,
            'max': 60,
            'step': 1,
            'description': 'Sekunden bis zur Neuverbindung bei Verbindungsverlust'
        },
        {
            'name': 'buffer_size',
            'label': 'Buffer Size',
            'type': ParameterType.INT,
            'default': 1,
            'min': 1,
            'max': 30,
            'step': 1,
            'description': 'Frame-Buffer-Größe (1 = niedrigste Latenz)'
        },
        {
            'name': 'timeout',
            'label': 'Connection Timeout (s)',
            'type': ParameterType.INT,
            'default': 10,
            'min': 1,
            'max': 60,
            'step': 1,
            'description': 'Timeout für Verbindungsversuche'
        },
        {
            'name': 'use_tcp',
            'label': 'TCP verwenden (RTSP)',
            'type': ParameterType.BOOL,
            'default': True,
            'description': 'TCP statt UDP für RTSP-Streams (zuverlässiger aber höhere Latenz)'
        },
        {
            'name': 'low_latency',
            'label': 'Low Latency Mode',
            'type': ParameterType.BOOL,
            'default': True,
            'description': 'Minimiert Latenz durch kleineren Buffer (kann zu Frame-Drops führen)'
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
            'type': ParameterType.INT,
            'default': 3600,
            'min': 5,
            'max': 86400,
            'step': 60,
            'description': 'Maximale Stream-Dauer vor Auto-Advance (1h Standard)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Stream-Verbindung."""
        # Support both 'stream_url' and 'rtsp_url' for compatibility
        self.stream_url = str(config.get('stream_url', config.get('rtsp_url', 'rtsp://localhost:8554/stream')))
        self.protocol = str(config.get('protocol', 'auto'))
        self.reconnect_delay = int(config.get('reconnect_delay', 5))
        self.buffer_size = int(config.get('buffer_size', 1))
        self.timeout = int(config.get('timeout', 10))
        self.use_tcp = bool(config.get('use_tcp', True))
        self.low_latency = bool(config.get('low_latency', True))
        self.brightness = float(config.get('brightness', 1.0))
        self.duration = int(config.get('duration', 3600))
        
        self.cap = None
        self.last_frame = None
        self.frame_count = 0
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        self.last_connection_time = None
        self.time = 0.0
        
        # Versuche zu verbinden
        self._connect()
        
        return True
    
    def _extract_youtube_url(self, url):
        """Extrahiert die echte Stream-URL von YouTube mit yt-dlp."""
        try:
            import yt_dlp
            
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info['url']
                
        except ImportError:
            logger.error("yt-dlp not installed. Install with: pip install yt-dlp")
            return None
        except Exception as e:
            logger.error(f"Failed to extract YouTube URL: {e}")
            return None
    
    def _connect(self):
        """Verbindet zum Stream."""
        try:
            import time
            current_time = time.time()
            
            # Prüfe ob Wartezeit vor Reconnect eingehalten werden soll
            if self.last_connection_time:
                elapsed = current_time - self.last_connection_time
                if elapsed < self.reconnect_delay:
                    return False
            
            self.last_connection_time = current_time
            self.connection_attempts += 1
            
            # Schließe alte Verbindung
            if self.cap is not None:
                self.cap.release()
            
            # Check if URL is YouTube and extract real stream URL
            stream_url = self.stream_url
            if 'youtube.com' in stream_url.lower() or 'youtu.be' in stream_url.lower():
                logger.info(f"Detected YouTube URL, extracting stream URL...")
                extracted_url = self._extract_youtube_url(stream_url)
                if extracted_url:
                    stream_url = extracted_url
                    logger.info(f"Successfully extracted YouTube stream URL")
                else:
                    logger.error("Failed to extract YouTube stream URL")
                    return False
            
            # Erstelle VideoCapture mit Backend-spezifischen Optionen
            if self.protocol == 'rtsp' or 'rtsp://' in stream_url.lower():
                # RTSP-spezifische Optionen
                if self.use_tcp:
                    # Erzwinge TCP für RTSP
                    import os
                    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
            
            self.cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
            
            if not self.cap.isOpened():
                raise Exception(f"Konnte Stream nicht öffnen: {self.stream_url}")
            
            # Setze Buffer-Größe für niedrige Latenz
            if self.low_latency:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
            
            # Setze Timeout (in Millisekunden)
            self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.timeout * 1000)
            self.cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.timeout * 1000)
            
            # Versuche ersten Frame zu lesen
            ret, frame = self.cap.read()
            if not ret or frame is None:
                raise Exception("Konnte ersten Frame nicht vom Stream lesen")
            
            self.last_frame = frame
            self.connection_attempts = 0  # Reset bei erfolgreicher Verbindung
            
            return True
            
        except Exception as e:
            if self.cap:
                self.cap.release()
                self.cap = None
            return False
    
    def _apply_brightness(self, frame):
        """Wendet Helligkeitsanpassung an."""
        if self.brightness != 1.0:
            frame = frame.astype(np.float32)
            frame = frame * self.brightness
            frame = np.clip(frame, 0, 255).astype(np.uint8)
        return frame
    
    def process_frame(self, frame, **kwargs):
        """
        Generiert Frame vom Stream.
        
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
        
        # Prüfe ob Neuverbindung nötig ist
        if self.cap is None or not self.cap.isOpened():
            if self.connection_attempts >= self.max_connection_attempts:
                # Zu viele Fehlversuche - zeige Fehler-Frame
                error_frame = np.zeros((height, width, 3), dtype=np.uint8)
                cv2.putText(error_frame, "Stream Connection Failed", (width//2 - 150, height//2),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
                # Zeige URL (gekürzt falls zu lang)
                url_display = self.stream_url if len(self.stream_url) <= 40 else self.stream_url[:37] + "..."
                cv2.putText(error_frame, url_display, (width//2 - 150, height//2 + 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 128), 1)
                return error_frame
            else:
                # Versuche Neuverbindung
                self._connect()
        
        # Versuche Frame vom Stream zu lesen
        if self.cap and self.cap.isOpened():
            ret, captured_frame = self.cap.read()
            
            if ret and captured_frame is not None:
                self.last_frame = captured_frame
                self.frame_count += 1
                
                # Wende Helligkeit an
                captured_frame = self._apply_brightness(captured_frame)
                
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
            
            # Wende Helligkeit an
            frame = self._apply_brightness(frame)
            
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
            # Kein Frame verfügbar - schwarzer Frame
            return np.zeros((height, width, 3), dtype=np.uint8)
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'stream_url' or name == 'rtsp_url':
            new_url = str(value)
            if new_url != self.stream_url:
                self.stream_url = new_url
                # Neu verbinden mit neuer URL
                if self.cap:
                    self.cap.release()
                    self.cap = None
                self.connection_attempts = 0
                self._connect()
            return True
        elif name == 'protocol':
            self.protocol = str(value)
            return True
        elif name == 'reconnect_delay':
            self.reconnect_delay = int(value)
            return True
        elif name == 'buffer_size':
            self.buffer_size = int(value)
            if self.cap and self.low_latency:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
            return True
        elif name == 'timeout':
            self.timeout = int(value)
            return True
        elif name == 'use_tcp':
            old_tcp = self.use_tcp
            self.use_tcp = bool(value)
            # Bei RTSP und TCP-Änderung neu verbinden
            if old_tcp != self.use_tcp and ('rtsp' in self.stream_url.lower() or self.protocol == 'rtsp'):
                if self.cap:
                    self.cap.release()
                    self.cap = None
                self.connection_attempts = 0
                self._connect()
            return True
        elif name == 'low_latency':
            self.low_latency = bool(value)
            if self.cap and self.low_latency:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
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
            'stream_url': self.stream_url,
            'rtsp_url': self.stream_url,  # Alias for compatibility
            'protocol': self.protocol,
            'reconnect_delay': self.reconnect_delay,
            'buffer_size': self.buffer_size,
            'timeout': self.timeout,
            'use_tcp': self.use_tcp,
            'low_latency': self.low_latency,
            'brightness': self.brightness,
            'duration': self.duration
        }
    
    def cleanup(self):
        """Cleanup beim Beenden."""
        if self.cap:
            try:
                # Release in separatem Thread mit Timeout um Blocking zu vermeiden
                import threading
                
                def release_cap():
                    try:
                        self.cap.release()
                    except Exception:
                        pass
                
                release_thread = threading.Thread(target=release_cap, daemon=True)
                release_thread.start()
                release_thread.join(timeout=1.0)  # Max. 1 Sekunde warten
                
                self.cap = None
            except Exception:
                self.cap = None
