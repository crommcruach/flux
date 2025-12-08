"""
Static Picture Generator Plugin - Display static images
"""
import numpy as np
import cv2
import os
import json
from plugins import PluginBase, PluginType, ParameterType


class StaticPictureGenerator(PluginBase):
    """
    Static Picture Generator - Zeigt ein statisches Bild an.
    
    Lädt und zeigt ein statisches Bild (PNG, JPG, BMP, TIFF, etc.)
    für eine konfigurierbare Dauer an.
    """
    
    METADATA = {
        'id': 'static_picture',
        'name': 'Statisches Bild',
        'description': 'Zeigt ein statisches Bild (PNG, JPG, BMP, TIFF, etc.) an',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Live Sources'
    }
    
    PARAMETERS = [
        {
            'name': 'image_path',
            'label': 'Bild-Datei',
            'type': ParameterType.STRING,
            'default': '',
            'description': 'Relativer Pfad zur Bilddatei (z.B. kanal_1/image.png) - sucht in video_dir und video_sources'
        },
        {
            'name': 'duration',
            'label': 'Duration (seconds)',
            'type': ParameterType.INT,
            'default': 30,
            'min': 1,
            'max': 60,
            'step': 5,
            'description': 'Anzeigedauer in Sekunden (für Playlist Auto-Advance)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Generator mit Parametern."""
        self.image_path = config.get('image_path', '')
        self.duration = int(config.get('duration', 10))
        self.time = 0.0
        self.image = None
        self.image_loaded = False
        
        # Lade Suchpfade aus config.json
        self._load_search_paths()
        
        # Versuche Bild zu laden, falls Pfad angegeben
        if self.image_path:
            self._load_image()
    
    def _load_search_paths(self):
        """Lädt die Suchpfade aus config.json."""
        self.search_paths = ['video']  # Default fallback
        
        try:
            config_path = 'config.json'
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    app_config = json.load(f)
                    
                paths_config = app_config.get('paths', {})
                video_dir = paths_config.get('video_dir', 'video')
                video_sources = paths_config.get('video_sources', [])
                
                # Haupt video_dir ist immer dabei
                self.search_paths = [video_dir]
                
                # Zusätzliche video_sources hinzufügen
                if isinstance(video_sources, list):
                    self.search_paths.extend([s for s in video_sources if s and os.path.exists(s)])
                    
                print(f"🔍 Bild-Suchpfade: {', '.join(self.search_paths)}")
        except Exception as e:
            print(f"⚠️ Konnte config.json nicht laden, verwende Default 'video': {e}")
    
    def _resolve_image_path(self, relative_path):
        """
        Löst relativen Pfad auf, indem in allen konfigurierten Verzeichnissen gesucht wird.
        
        Args:
            relative_path: Relativer Pfad (z.B. "kanal_1/image.png")
            
        Returns:
            Absoluter Pfad oder None wenn nicht gefunden
        """
        # Validiere Input - keine leeren/whitespace Pfade
        if not relative_path or not relative_path.strip():
            return None
        
        relative_path = relative_path.strip()
        
        # Falls schon absolut und existiert, direkt zurückgeben
        if os.path.isabs(relative_path) and os.path.exists(relative_path):
            return relative_path
        
        # Suche in allen konfigurierten Verzeichnissen
        for search_dir in self.search_paths:
            full_path = os.path.join(search_dir, relative_path)
            if os.path.exists(full_path):
                print(f"✅ Bild gefunden: {full_path}")
                return full_path
        
        return None
    
    def _load_image(self):
        """Lädt das Bild von der Festplatte."""
        try:
            # Löse Pfad auf
            resolved_path = self._resolve_image_path(self.image_path)
            
            if not resolved_path:
                print(f"⚠️ Bilddatei nicht gefunden: {self.image_path}")
                print(f"   Gesucht in: {', '.join(self.search_paths)}")
                self.image_loaded = False
                return
            
            # Lade Bild mit OpenCV (unterstützt viele Formate: PNG, JPG, BMP, TIFF, WebP, etc.)
            # Verwende imdecode mit numpy für bessere Unicode-Unterstützung
            try:
                # Lese Datei als Bytes (umgeht Windows Unicode-Probleme)
                with open(resolved_path, 'rb') as f:
                    file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
                img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            except Exception as read_error:
                print(f"❌ Fehler beim Lesen der Datei: {read_error}")
                img = None
            
            if img is None:
                print(f"❌ Konnte Bild nicht laden: {resolved_path}")
                print(f"   Unterstützte Formate: PNG, JPG, JPEG, BMP, TIFF, TIF, WebP")
                self.image_loaded = False
                return
            
            # Konvertiere von BGR (OpenCV) zu RGB (Flux)
            self.image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            self.image_loaded = True
            print(f"✅ Bild geladen: {resolved_path} ({self.image.shape[1]}x{self.image.shape[0]} px)")
            
        except Exception as e:
            print(f"❌ Fehler beim Laden des Bildes: {e}")
            self.image_loaded = False
    
    def process_frame(self, frame, **kwargs):
        """
        Gibt das statische Bild zurück.
        
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
        
        # Falls kein Bild geladen, zeige schwarzes Frame
        if not self.image_loaded or self.image is None:
            return np.zeros((height, width, 3), dtype=np.uint8)
        
        # Skaliere Bild auf Output-Größe
        try:
            # Verwende INTER_LINEAR für bessere Qualität
            resized = cv2.resize(self.image, (width, height), interpolation=cv2.INTER_LINEAR)
            return resized.astype(np.uint8)
            
        except Exception as e:
            print(f"❌ Fehler beim Skalieren des Bildes: {e}")
            return np.zeros((height, width, 3), dtype=np.uint8)
    
    def update_parameter(self, name, value):
        """Aktualisiert einen Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'image_path':
            self.image_path = str(value)
            # Lade neues Bild
            self._load_image()
            return True
        elif name == 'duration':
            self.duration = max(5, min(600, int(value)))
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'image_path': self.image_path,
            'duration': self.duration
        }
    
    def cleanup(self):
        """Cleanup beim Beenden."""
        self.image = None
        self.image_loaded = False
