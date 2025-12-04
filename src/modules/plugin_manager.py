"""
Plugin Manager - Lädt, verwaltet und validiert Plugins
"""
import os
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Optional, Type
from plugins import PluginBase, PluginType
from plugins.plugin_base import ParameterType
from .logger import get_logger

logger = get_logger(__name__)


class PluginManager:
    """
    Verwaltet alle Plugins und stellt Registry zur Verfügung.
    
    Features:
    - Plugin Discovery (automatisches Scannen von plugins/ Ordner)
    - Plugin Loading & Validation
    - Plugin Registry (ID -> Instance Mapping)
    - Parameter Validation
    """
    
    def __init__(self, plugins_dir: str = None):
        """
        Initialisiert PluginManager.
        
        Args:
            plugins_dir: Pfad zum plugins/ Ordner (None = auto-detect)
        """
        # Auto-detect plugins directory
        if plugins_dir is None:
            # Check if we're in src/ directory
            if Path('plugins').exists():
                plugins_dir = 'plugins'
            else:
                plugins_dir = 'src/plugins'
        
        self.plugins_dir = Path(plugins_dir)
        self.registry: Dict[str, Type[PluginBase]] = {}  # ID -> Plugin Class
        self.instances: Dict[str, PluginBase] = {}       # ID -> Plugin Instance
        
        # Discover Plugins beim Initialisieren
        self.discover_plugins()
    
    def discover_plugins(self):
        """
        Scannt plugins/ Ordner nach Plugin-Klassen.
        Lädt alle Python-Module und registriert PluginBase-Subklassen.
        """
        logger.info(f"Plugin Discovery gestartet: {self.plugins_dir.absolute()}")
        
        if not self.plugins_dir.exists():
            logger.warning(f"Plugins-Ordner nicht gefunden: {self.plugins_dir.absolute()}")
            return
        
        # Durchsuche alle Subordner (effects/, generators/, sources/, transitions/)
        for category_dir in self.plugins_dir.iterdir():
            if not category_dir.is_dir():
                continue
            
            if category_dir.name.startswith('_'):
                continue  # Skip __pycache__, __init__.py
            
            # Durchsuche alle .py Dateien im Kategorie-Ordner
            for plugin_file in category_dir.glob('*.py'):
                if plugin_file.name.startswith('_'):
                    continue  # Skip __init__.py
                
                # Import Module
                module_path = f"plugins.{category_dir.name}.{plugin_file.stem}"
                try:
                    # Check if module is already imported and reload it
                    import sys
                    if module_path in sys.modules:
                        module = importlib.reload(sys.modules[module_path])
                    else:
                        module = importlib.import_module(module_path)
                    
                    # Finde alle PluginBase-Subklassen im Modul
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, PluginBase) and obj is not PluginBase:
                            try:
                                self.register_plugin(obj)
                                logger.debug(f"Plugin geladen: {obj.METADATA.get('id', 'unknown')} ({module_path})")
                            except Exception as reg_err:
                                import traceback
                                logger.error(f"Fehler beim Registrieren von {obj.__name__}: {reg_err}")
                                traceback.print_exc()
                
                except Exception as e:
                    import traceback
                    logger.error(f"Fehler beim Laden von {module_path}: {e}")
                    traceback.print_exc()
    
    def register_plugin(self, plugin_class: Type[PluginBase]):
        """
        Registriert Plugin-Klasse in Registry.
        
        Args:
            plugin_class: Plugin-Klasse (muss von PluginBase erben)
        """
        # Validiere METADATA
        if not hasattr(plugin_class, 'METADATA') or 'id' not in plugin_class.METADATA:
            raise ValueError(f"Plugin {plugin_class.__name__} hat keine METADATA['id']")
        
        plugin_id = plugin_class.METADATA['id']
        
        # Prüfe auf Duplikate
        if plugin_id in self.registry:
            logger.warning(f"Plugin mit ID '{plugin_id}' existiert bereits - überschreibe mit {plugin_class.__name__}")
        
        self.registry[plugin_id] = plugin_class
        logger.debug(f"Registered '{plugin_id}' in registry (total: {len(self.registry)})")
    
    def load_plugin(self, plugin_id: str, config: Optional[Dict] = None) -> Optional[PluginBase]:
        """
        Lädt Plugin und erstellt NEUE Instanz.
        
        WICHTIG: Erstellt jedes Mal eine neue Instanz, da Effekte 
        mehrfach mit unterschiedlichen Configs in Chains verwendet werden können.
        
        Args:
            plugin_id: Plugin-ID aus METADATA
            config: Konfiguration (Parameter-Werte)
            
        Returns:
            Plugin-Instanz oder None wenn nicht gefunden
        """
        if plugin_id not in self.registry:
            logger.warning(f"Plugin '{plugin_id}' nicht gefunden in Registry")
            return None
        
        try:
            plugin_class = self.registry[plugin_id]
            # Erstelle NEUE Instanz (nicht cachen, da Effekte mehrfach verwendbar)
            instance = plugin_class(config=config)
            logger.debug(f"Plugin '{plugin_id}' erfolgreich geladen")
            return instance
        except Exception as e:
            import traceback
            logger.error(f"Fehler beim Laden von Plugin '{plugin_id}': {e}")
            traceback.print_exc()
            return None
    
    def get_plugin(self, plugin_id: str) -> Optional[PluginBase]:
        """
        Holt Plugin-Instanz aus Registry.
        
        Args:
            plugin_id: Plugin-ID
            
        Returns:
            Plugin-Instanz oder None wenn nicht geladen
        """
        return self.instances.get(plugin_id)
    
    def list_plugins(self, plugin_type: Optional[PluginType] = None) -> List[Dict]:
        """
        Listet alle verfügbaren Plugins auf.
        
        Args:
            plugin_type: Optional - Filtert nach Plugin-Typ
            
        Returns:
            Liste von Plugin-Metadaten
        """
        logger.debug(f"list_plugins called. Registry has {len(self.registry)} plugins")
        
        result = []
        for plugin_id, plugin_class in self.registry.items():
            try:
                metadata = plugin_class.METADATA.copy()
                
                # Filter by type
                if plugin_type and metadata.get('type') != plugin_type:
                    continue
                
                # Konvertiere PluginType Enum zu String für JSON-Serialisierung
                if 'type' in metadata and isinstance(metadata['type'], PluginType):
                    metadata['type'] = metadata['type'].value
                
                result.append(metadata)
            except Exception as e:
                logger.error(f"Error processing plugin {plugin_id}: {e}")
                import traceback
                traceback.print_exc()
        
        logger.debug(f"Returning {len(result)} plugins from list_plugins")
        return result
    
    def get_plugin_metadata(self, plugin_id: str) -> Optional[Dict]:
        """
        Gibt METADATA eines Plugins zurück.
        B6 Performance: Nutzt gecachte JSON-Version (keine redundanten Enum-Conversions).
        
        Args:
            plugin_id: Plugin-ID
            
        Returns:
            METADATA Dictionary oder None
        """
        if plugin_id not in self.registry:
            return None
        
        # B6: Nutze gecachte JSON-Version (Enum→String bereits konvertiert)
        # Erstelle temporäre Instanz nur für Metadata-Zugriff (lightweight)
        try:
            temp_instance = self.registry[plugin_id]()
            return temp_instance.get_metadata_json()
        except:
            # Fallback: Manuelle Konvertierung (falls __init__ fehlschlägt)
            metadata = self.registry[plugin_id].METADATA.copy()
            if 'type' in metadata and isinstance(metadata['type'], PluginType):
                metadata['type'] = metadata['type'].value
            return metadata
    
    def get_plugin_parameters(self, plugin_id: str) -> Optional[List[Dict]]:
        """
        Gibt PARAMETERS eines Plugins zurück (für UI-Generierung).
        B6 Performance: Nutzt gecachte JSON-Version (keine redundanten Enum-Conversions).
        
        Args:
            plugin_id: Plugin-ID
            
        Returns:
            PARAMETERS Array oder None
        """
        if plugin_id not in self.registry:
            return None
        
        # B6: Nutze gecachte JSON-Version (Enum→String bereits konvertiert & deep-copied)
        try:
            temp_instance = self.registry[plugin_id]()
            return temp_instance.get_parameters_json()
        except:
            # Fallback: Manuelle Konvertierung (falls __init__ fehlschlägt)
            import copy
            parameters = copy.deepcopy(self.registry[plugin_id].PARAMETERS)
            for param in parameters:
                if 'type' in param and isinstance(param['type'], ParameterType):
                    param['type'] = param['type'].value
            return parameters
    
    def validate_parameter_value(self, plugin_id: str, param_name: str, value) -> bool:
        """
        Validiert Parameter-Wert gegen Schema.
        
        Args:
            plugin_id: Plugin-ID
            param_name: Parameter-Name
            value: Wert zum Validieren
            
        Returns:
            True wenn valide, False sonst
        """
        if plugin_id not in self.registry:
            return False
        
        # Finde Parameter-Definition
        param_def = None
        for param in self.registry[plugin_id].PARAMETERS:
            if param['name'] == param_name:
                param_def = param
                break
        
        if not param_def:
            return False  # Parameter existiert nicht
        
        # Type-spezifische Validierung
        param_type = param_def['type']
        
        if param_type == ParameterType.FLOAT:
            try:
                v = float(value)
                return param_def['min'] <= v <= param_def['max']
            except:
                return False
        
        elif param_type == ParameterType.INT:
            try:
                v = int(value)
                return param_def['min'] <= v <= param_def['max']
            except:
                return False
        
        elif param_type == ParameterType.BOOL:
            return isinstance(value, bool)
        
        elif param_type == ParameterType.SELECT:
            return value in param_def['options']
        
        elif param_type == ParameterType.COLOR:
            # Einfache Hex-Color Validierung
            return isinstance(value, str) and (value.startswith('#') and len(value) in [7, 9])
        
        elif param_type == ParameterType.STRING:
            return isinstance(value, str)
        
        elif param_type == ParameterType.RANGE:
            try:
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    return False
                min_val, max_val = float(value[0]), float(value[1])
                return (param_def['min'] <= min_val <= param_def['max'] and
                        param_def['min'] <= max_val <= param_def['max'] and
                        min_val <= max_val)
            except:
                return False
        
        return False
    
    def unload_plugin(self, plugin_id: str):
        """
        Entlädt Plugin-Instanz und ruft cleanup() auf.
        
        Args:
            plugin_id: Plugin-ID
        """
        if plugin_id in self.instances:
            instance = self.instances[plugin_id]
            instance.cleanup()
            del self.instances[plugin_id]
            logger.info(f"Plugin '{plugin_id}' entladen")
    
    def reload_plugins(self):
        """
        Lädt alle Plugins neu (für Development).
        """
        # Entlade alle Instanzen
        for plugin_id in list(self.instances.keys()):
            self.unload_plugin(plugin_id)
        
        # Leere Registry
        self.registry.clear()
        
        # Discover neu
        self.discover_plugins()
        logger.info("Alle Plugins neu geladen")
    
    def get_stats(self) -> Dict:
        """
        Gibt Statistiken über geladene Plugins zurück.
        
        Returns:
            Dictionary mit Plugin-Statistiken
        """
        return {
            'total_plugins': len(self.registry),
            'loaded_instances': len(self.instances),
            'by_type': {
                plugin_type.value: len([p for p in self.registry.values() 
                                       if p.METADATA.get('type') == plugin_type])
                for plugin_type in PluginType
            }
        }
    
    def __repr__(self):
        return f"<PluginManager plugins={len(self.registry)} instances={len(self.instances)}>"


# Globale PluginManager-Instanz
_plugin_manager = None

def get_plugin_manager() -> PluginManager:
    """
    Singleton-Getter für PluginManager.
    
    Returns:
        Globale PluginManager-Instanz
    """
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager
