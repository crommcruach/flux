"""
Plugin Base Class - Foundation für alle Plugins
Unterstützt: Generators, Effects, Sources, Transitions
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Any, Optional
import numpy as np


class PluginType(Enum):
    """Plugin-Typen"""
    GENERATOR = "generator"  # Erzeugt Frames (z.B. ScriptGenerator)
    EFFECT = "effect"         # Verarbeitet Frames (z.B. Blur, Color)
    SOURCE = "source"         # Frame-Quelle (z.B. Video, LiveStream)
    TRANSITION = "transition" # Übergang zwischen 2 Frames


class ParameterType(Enum):
    """Parameter-Typen für UI-Generierung"""
    FLOAT = "float"           # Slider (min, max, step)
    INT = "int"               # Integer Slider (min, max, step)
    BOOL = "bool"             # Checkbox
    SELECT = "select"         # Dropdown (options array)
    COLOR = "color"           # Color Picker (hex string)
    STRING = "string"         # Text Input
    RANGE = "range"           # Dual-Slider (min, max)


class PluginBase(ABC):
    """
    Base-Klasse für alle Plugins.
    
    Jedes Plugin muss METADATA und PARAMETERS definieren sowie die abstrakten Methoden implementieren.
    
    Beispiel-Implementierung:
    
    ```python
    from plugins import PluginBase, PluginType, ParameterType
    
    class BlurEffect(PluginBase):
        METADATA = {
            'id': 'blur',
            'name': 'Gaussian Blur',
            'description': 'Verwischt das Bild mit Gaussian Blur',
            'author': 'Flux Team',
            'version': '1.0.0',
            'type': PluginType.EFFECT
        }
        
        PARAMETERS = [
            {
                'name': 'strength',
                'label': 'Blur Stärke',
                'type': ParameterType.FLOAT,
                'default': 5.0,
                'min': 0.0,
                'max': 20.0,
                'step': 0.5,
                'description': 'Stärke des Blur-Effekts (Kernel-Größe)'
            }
        ]
        
        def initialize(self, config):
            self.strength = config.get('strength', 5.0)
        
        def process_frame(self, frame, **kwargs):
            kernel_size = int(self.strength) * 2 + 1  # Muss ungerade sein
            return cv2.GaussianBlur(frame, (kernel_size, kernel_size), 0)
        
        def update_parameter(self, name, value):
            if name == 'strength':
                self.strength = float(value)
                return True
            return False
        
        def get_parameters(self):
            return {'strength': self.strength}
    ```
    """
    
    # METADATA - Muss von Subclass definiert werden
    METADATA: Dict[str, Any] = {}
    
    # PARAMETERS - Muss von Subclass definiert werden
    PARAMETERS: List[Dict[str, Any]] = []
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialisiert Plugin mit Konfiguration.
        
        Args:
            config: Dictionary mit Parameter-Werten (Key = Parameter Name)
        """
        # Clean config from range metadata if present
        if config:
            cleaned_config = {}
            for key, val in config.items():
                # Extract _value from range metadata dicts
                if isinstance(val, dict) and '_value' in val:
                    cleaned_config[key] = val['_value']
                else:
                    cleaned_config[key] = val
            self.config = cleaned_config
        else:
            self.config = {}
        
        # B6 Performance: JSON-Caching für API-Responses
        self._cached_metadata_json = None
        self._cached_parameters_json = None
        
        self.validate_metadata()
        self.validate_parameters()
        self.initialize(self.config)
    
    def _get_param_value(self, key: str, default: Any = None) -> Any:
        """
        Helper method to extract parameter value from config.
        
        Handles triple-slider range metadata automatically:
        If value is {'_value': X, '_rangeMin': Y, '_rangeMax': Z}, returns X
        Otherwise returns the value as-is.
        
        Args:
            key: Parameter name
            default: Default value if parameter not found
            
        Returns:
            Extracted parameter value
        """
        val = self.config.get(key, default)
        # Extract actual value if it's a range metadata dict
        if isinstance(val, dict) and '_value' in val:
            return val['_value']
        return val
    
    def validate_metadata(self):
        """Validiert METADATA gegen Schema."""
        required_fields = ['id', 'name', 'type']
        for field in required_fields:
            if field not in self.METADATA:
                raise ValueError(f"Plugin {self.__class__.__name__} fehlt METADATA['{field}']")
        
        if not isinstance(self.METADATA['type'], PluginType):
            raise ValueError(f"Plugin {self.METADATA['id']}: METADATA['type'] muss PluginType Enum sein")
    
    def validate_parameters(self):
        """Validiert PARAMETERS Array gegen Schema."""
        for param in self.PARAMETERS:
            # Required fields
            if 'name' not in param or 'type' not in param:
                raise ValueError(f"Plugin {self.METADATA['id']}: Parameter fehlt 'name' oder 'type'")
            
            # Type muss ParameterType Enum sein
            if not isinstance(param['type'], ParameterType):
                raise ValueError(f"Plugin {self.METADATA['id']}: Parameter '{param['name']}' type muss ParameterType Enum sein")
            
            # Type-spezifische Validierung
            param_type = param['type']
            
            if param_type in [ParameterType.FLOAT, ParameterType.INT]:
                if 'min' not in param or 'max' not in param:
                    raise ValueError(f"Plugin {self.METADATA['id']}: Parameter '{param['name']}' vom Typ {param_type.value} benötigt 'min' und 'max'")
            
            elif param_type == ParameterType.SELECT:
                if 'options' not in param or not isinstance(param['options'], list):
                    raise ValueError(f"Plugin {self.METADATA['id']}: Parameter '{param['name']}' vom Typ SELECT benötigt 'options' Array")
            
            elif param_type == ParameterType.RANGE:
                if 'min' not in param or 'max' not in param:
                    raise ValueError(f"Plugin {self.METADATA['id']}: Parameter '{param['name']}' vom Typ RANGE benötigt 'min' und 'max'")
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]):
        """
        Initialisiert Plugin mit Parametern.
        Wird beim Laden/Start des Plugins aufgerufen.
        
        Args:
            config: Dictionary mit Parameter-Werten
        """
        pass
    
    @abstractmethod
    def update_parameter(self, name: str, value: Any) -> bool:
        """
        Aktualisiert einen Parameter zur Laufzeit.
        
        Args:
            name: Parameter-Name
            value: Neuer Wert
            
        Returns:
            True wenn Parameter existiert und aktualisiert wurde, False sonst
        """
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """
        Gibt aktuelle Parameter-Werte zurück.
        
        Returns:
            Dictionary mit {parameter_name: value}
        """
        pass
    
    def cleanup(self):
        """
        Cleanup-Methode für Plugin-Ressourcen.
        Optional überschreibbar.
        """
        pass
    
    # ========================================
    # TYPE-SPEZIFISCHE METHODEN
    # ========================================
    
    # --- EFFECT Plugins ---
    def process_frame(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """
        Verarbeitet Frame (für EFFECT Plugins).
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Zusätzliche Kontext-Daten (z.B. time, fps, frame_number)
            
        Returns:
            Verarbeitetes Frame (NumPy Array, BGR)
        """
        raise NotImplementedError(f"Plugin {self.METADATA['id']} ist vom Typ {self.METADATA['type'].value} und implementiert keine process_frame() Methode")
    
    # --- GENERATOR Plugins ---
    def generate_frame(self, width: int, height: int, frame_number: int, time: float, fps: float) -> np.ndarray:
        """
        Generiert Frame (für GENERATOR Plugins).
        
        Args:
            width: Frame-Breite
            height: Frame-Höhe
            frame_number: Aktuelle Frame-Nummer
            time: Zeit in Sekunden
            fps: Frames pro Sekunde
            
        Returns:
            Generiertes Frame (NumPy Array, BGR)
        """
        raise NotImplementedError(f"Plugin {self.METADATA['id']} ist vom Typ {self.METADATA['type'].value} und implementiert keine generate_frame() Methode")
    
    # --- SOURCE Plugins ---
    def get_frame(self) -> Optional[np.ndarray]:
        """
        Holt nächstes Frame (für SOURCE Plugins).
        
        Returns:
            Frame (NumPy Array, BGR) oder None wenn keine Frames mehr verfügbar
        """
        raise NotImplementedError(f"Plugin {self.METADATA['id']} ist vom Typ {self.METADATA['type'].value} und implementiert keine get_frame() Methode")
    
    def seek(self, frame_number: int):
        """
        Springt zu bestimmtem Frame (für SOURCE Plugins).
        
        Args:
            frame_number: Ziel-Frame-Nummer
        """
        raise NotImplementedError(f"Plugin {self.METADATA['id']} ist vom Typ {self.METADATA['type'].value} und implementiert keine seek() Methode")
    
    # --- TRANSITION Plugins ---
    def blend_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, progress: float) -> np.ndarray:
        """
        Mischt zwei Frames (für TRANSITION Plugins).
        
        Args:
            frame_a: Frame A (NumPy Array, BGR)
            frame_b: Frame B (NumPy Array, BGR)
            progress: Übergangs-Fortschritt (0.0 = nur A, 1.0 = nur B)
            
        Returns:
            Gemischtes Frame (NumPy Array, BGR)
        """
        raise NotImplementedError(f"Plugin {self.METADATA['id']} ist vom Typ {self.METADATA['type'].value} und implementiert keine blend_frames() Methode")
    
    # ========================================
    # HELPER METHODS
    # ========================================
    
    def get_parameter_schema(self) -> List[Dict[str, Any]]:
        """
        Gibt PARAMETERS Array für UI-Generierung zurück.
        
        Returns:
            Liste von Parameter-Definitionen
        """
        return self.PARAMETERS
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Gibt METADATA Dictionary zurück.
        
        Returns:
            Plugin-Metadaten
        """
        return self.METADATA
    
    def get_metadata_json(self) -> Dict[str, Any]:
        """
        Gibt METADATA Dictionary mit Enum→String Konvertierung zurück (gecacht).
        B6 Performance Optimization: Cached für API-Responses (120/min → 1/plugin-lifetime).
        
        Returns:
            Plugin-Metadaten mit serialisierten Enums
        """
        if self._cached_metadata_json is None:
            # Einmalig konvertieren
            metadata = self.METADATA.copy()
            
            # Konvertiere PluginType Enum zu String
            if 'type' in metadata and isinstance(metadata['type'], PluginType):
                metadata['type'] = metadata['type'].value
            
            self._cached_metadata_json = metadata
        
        return self._cached_metadata_json
    
    def get_parameters_json(self) -> List[Dict[str, Any]]:
        """
        Gibt PARAMETERS Array mit Enum→String Konvertierung zurück (gecacht).
        B6 Performance Optimization: Cached für API-Responses.
        
        Returns:
            Parameter-Definitionen mit serialisierten Enums
        """
        if self._cached_parameters_json is None:
            # Deep copy to avoid modifying class-level PARAMETERS
            import copy
            parameters = copy.deepcopy(self.PARAMETERS)
            
            # Konvertiere ParameterType Enum zu String
            for param in parameters:
                if 'type' in param and isinstance(param['type'], ParameterType):
                    param['type'] = param['type'].value
            
            self._cached_parameters_json = parameters
        
        return self._cached_parameters_json
    
    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.METADATA.get('id', 'unknown')} type={self.METADATA.get('type', 'unknown')}>"
