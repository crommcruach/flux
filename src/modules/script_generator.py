"""
Script Generator - Führt Python-Scripts als Videoquellen aus
Lädt und führt Scripts aus dem scripts/ Ordner aus
"""
import os
import sys
import importlib.util
import numpy as np
import time as time_module
from pathlib import Path
from .logger import get_logger

logger = get_logger(__name__)


class ScriptGenerator:
    """Verwaltet und führt Python-Scripts als Frame-Generatoren aus."""
    
    def __init__(self, scripts_dir='scripts'):
        self.scripts_dir = scripts_dir
        self.loaded_script = None
        self.script_path = None
        self.script_module = None
        self.start_time = None
        self.frame_count = 0
        
    def list_scripts(self):
        """Listet alle verfügbaren Scripts auf."""
        if not os.path.exists(self.scripts_dir):
            return []
        
        scripts = []
        for file in os.listdir(self.scripts_dir):
            if file.endswith('.py') and not file.startswith('_'):
                script_path = os.path.join(self.scripts_dir, file)
                metadata = self._get_metadata(script_path)
                scripts.append({
                    'filename': file,
                    'path': script_path,
                    'name': metadata.get('name', file),
                    'description': metadata.get('description', 'Keine Beschreibung'),
                    'author': metadata.get('author', 'Unbekannt'),
                    'fps': metadata.get('fps', 30)
                })
        
        return scripts
    
    def _get_metadata(self, script_path):
        """Liest Metadata aus einem Script."""
        try:
            spec = importlib.util.spec_from_file_location("temp_module", script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return getattr(module, 'METADATA', {})
        except Exception:
            return {}
    
    def load_script(self, script_name):
        """
        Lädt ein Script.
        
        Args:
            script_name: Name der Script-Datei (mit oder ohne .py)
        
        Returns:
            bool: True wenn erfolgreich geladen
        """
        # Füge .py hinzu wenn nicht vorhanden
        if not script_name.endswith('.py'):
            script_name += '.py'
        
        script_path = os.path.join(self.scripts_dir, script_name)
        
        if not os.path.exists(script_path):
            logger.error(f"Script nicht gefunden: {script_path}")
            return False
        
        try:
            # Lade Script als Modul
            spec = importlib.util.spec_from_file_location(
                f"script_{script_name}", 
                script_path
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            
            # Prüfe ob generate_frame Funktion existiert
            if not hasattr(module, 'generate_frame'):
                logger.error(f"Fehler: Script {script_name} hat keine generate_frame() Funktion")
                return False
            
            self.script_module = module
            self.script_path = script_path
            self.loaded_script = script_name
            self.start_time = time_module.time()
            self.frame_count = 0
            
            # Zeige Metadata
            metadata = getattr(module, 'METADATA', {})
            logger.info(f"Script geladen: {metadata.get('name', script_name)}")
            if metadata.get('description'):
                logger.info(f"  {metadata['description']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Laden des Scripts: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def generate_frame(self, width, height, fps=30, frame_number=None, time=None):
        """
        Generiert ein Frame mit dem geladenen Script.
        
        Args:
            width: Canvas-Breite
            height: Canvas-Höhe
            fps: Frames pro Sekunde
            frame_number: Optional - überschreibt internen Counter
            time: Optional - überschreibt interne Zeit
        
        Returns:
            numpy.ndarray: Frame als (height, width, 3) RGB Array oder None
        """
        if not self.script_module:
            return None
        
        try:
            # Verwende externe Werte oder interne Counter
            if frame_number is None:
                frame_number = self.frame_count
                self.frame_count += 1
            
            if time is None:
                if self.start_time is None:
                    self.start_time = time_module.time()
                time = time_module.time() - self.start_time
            
            # Rufe generate_frame Funktion auf
            frame = self.script_module.generate_frame(
                frame_number=frame_number,
                width=width,
                height=height,
                time=time,
                fps=fps
            )
            
            # Validiere Frame
            if frame is None:
                return None
            
            if not isinstance(frame, np.ndarray):
                logger.warning("Warnung: generate_frame() muss numpy.ndarray zurückgeben")
                return None
            
            if frame.shape != (height, width, 3):
                logger.warning(f"Warnung: Frame hat falsche Dimensionen: {frame.shape}, erwartet: ({height}, {width}, 3)")
                return None
            
            if frame.dtype != np.uint8:
                # Konvertiere zu uint8 wenn nötig
                frame = frame.astype(np.uint8)
            
            return frame
            
        except Exception as e:
            logger.error(f"Fehler beim Generieren des Frames: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def reset(self):
        """Setzt Frame-Counter und Timer zurück."""
        self.start_time = time_module.time()
        self.frame_count = 0
    
    def is_loaded(self):
        """Prüft ob ein Script geladen ist."""
        return self.script_module is not None
    
    def get_info(self):
        """Gibt Informationen über das geladene Script zurück."""
        if not self.script_module:
            return {}
        
        metadata = getattr(self.script_module, 'METADATA', {})
        return {
            'script': self.loaded_script,
            'name': metadata.get('name', self.loaded_script),
            'description': metadata.get('description', ''),
            'author': metadata.get('author', 'Unbekannt'),
            'fps': metadata.get('fps', 30),
            'parameters': metadata.get('parameters', {}),
            'frames_generated': self.frame_count,
            'runtime': time_module.time() - self.start_time if self.start_time else 0
        }
