"""
Clip Registry - Zentrales Management von Video-Clips mit eindeutigen IDs.

Ermöglicht:
- Eindeutige Identifikation von Clips unabhängig vom Dateinamen
- Mehrfache Verwendung desselben Videos in verschiedenen Playern
- Clip-spezifische Metadaten und Effekte
"""

import uuid
import os
from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ClipRegistry:
    """Zentrale Registry für Video-Clips mit UUID-basierter Identifikation."""
    
    def __init__(self):
        """Initialisiert die Clip-Registry."""
        # Mapping: clip_id (UUID) -> clip_data
        self.clips: Dict[str, Dict] = {}
        
        # Reverse-Mapping für schnelle Suche: (player_id, absolute_path) -> clip_id
        self._path_index: Dict[tuple, str] = {}
    
    def register_clip(
        self, 
        player_id: str, 
        absolute_path: str, 
        relative_path: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Registriert einen neuen Clip oder gibt existierende ID zurück.
        
        Args:
            player_id: ID des Players ('video' oder 'artnet')
            absolute_path: Absoluter Pfad zur Video-Datei
            relative_path: Relativer Pfad (für UI)
            metadata: Optionale Metadaten (fps, duration, etc.)
        
        Returns:
            clip_id: Eindeutige UUID für diesen Clip
        """
        # Prüfe ob Clip bereits registriert
        index_key = (player_id, absolute_path)
        if index_key in self._path_index:
            clip_id = self._path_index[index_key]
            logger.debug(f"Clip bereits registriert: {clip_id} ({os.path.basename(absolute_path)})")
            return clip_id
        
        # Erstelle neue Clip-ID
        clip_id = str(uuid.uuid4())
        
        # Speichere Clip-Daten
        self.clips[clip_id] = {
            'clip_id': clip_id,
            'player_id': player_id,
            'absolute_path': absolute_path,
            'relative_path': relative_path,
            'filename': os.path.basename(absolute_path),
            'metadata': metadata or {},
            'created_at': datetime.now().isoformat(),
            'effects': []  # Clip-spezifische Effekte
        }
        
        # Index aktualisieren
        self._path_index[index_key] = clip_id
        
        logger.info(f"✅ Clip registriert: {clip_id} → {player_id}/{os.path.basename(absolute_path)}")
        return clip_id
    
    def get_clip(self, clip_id: str) -> Optional[Dict]:
        """
        Holt Clip-Daten anhand der ID.
        
        Args:
            clip_id: Eindeutige Clip-ID
        
        Returns:
            Clip-Daten oder None wenn nicht gefunden
        """
        return self.clips.get(clip_id)
    
    def find_clip_by_path(self, player_id: str, absolute_path: str) -> Optional[str]:
        """
        Findet Clip-ID anhand von Player-ID und Pfad.
        
        Args:
            player_id: ID des Players
            absolute_path: Absoluter Pfad zur Video-Datei
        
        Returns:
            clip_id oder None wenn nicht gefunden
        """
        index_key = (player_id, absolute_path)
        return self._path_index.get(index_key)
    
    def get_clips_for_player(self, player_id: str) -> List[Dict]:
        """
        Holt alle Clips eines bestimmten Players.
        
        Args:
            player_id: ID des Players
        
        Returns:
            Liste von Clip-Daten
        """
        return [
            clip for clip in self.clips.values()
            if clip['player_id'] == player_id
        ]
    
    def unregister_clip(self, clip_id: str) -> bool:
        """
        Entfernt einen Clip aus der Registry.
        
        Args:
            clip_id: Eindeutige Clip-ID
        
        Returns:
            True wenn erfolgreich entfernt
        """
        if clip_id not in self.clips:
            return False
        
        clip_data = self.clips[clip_id]
        index_key = (clip_data['player_id'], clip_data['absolute_path'])
        
        # Entferne aus beiden Datenstrukturen
        del self.clips[clip_id]
        if index_key in self._path_index:
            del self._path_index[index_key]
        
        logger.info(f"🗑️ Clip unregistriert: {clip_id}")
        return True
    
    def add_effect_to_clip(self, clip_id: str, effect_data: Dict) -> bool:
        """
        Fügt einen Effekt zu einem Clip hinzu.
        
        Args:
            clip_id: Eindeutige Clip-ID
            effect_data: Effekt-Daten (plugin_id, parameters, etc.)
        
        Returns:
            True wenn erfolgreich hinzugefügt
        """
        if clip_id not in self.clips:
            logger.error(f"Clip nicht gefunden: {clip_id}")
            return False
        
        self.clips[clip_id]['effects'].append(effect_data)
        logger.debug(f"Effekt zu Clip hinzugefügt: {clip_id} → {effect_data.get('plugin_id')}")
        return True
    
    def get_clip_effects(self, clip_id: str) -> List[Dict]:
        """
        Holt alle Effekte eines Clips.
        
        Args:
            clip_id: Eindeutige Clip-ID
        
        Returns:
            Liste von Effekt-Daten
        """
        if clip_id not in self.clips:
            return []
        
        return self.clips[clip_id].get('effects', [])
    
    def remove_effect_from_clip(self, clip_id: str, effect_index: int) -> bool:
        """
        Entfernt einen Effekt von einem Clip.
        
        Args:
            clip_id: Eindeutige Clip-ID
            effect_index: Index des zu entfernenden Effekts
        
        Returns:
            True wenn erfolgreich entfernt
        """
        if clip_id not in self.clips:
            return False
        
        effects = self.clips[clip_id]['effects']
        if 0 <= effect_index < len(effects):
            removed = effects.pop(effect_index)
            logger.debug(f"Effekt von Clip entfernt: {clip_id} → {removed.get('plugin_id')}")
            return True
        
        return False
    
    def clear_clip_effects(self, clip_id: str) -> bool:
        """
        Entfernt alle Effekte von einem Clip.
        
        Args:
            clip_id: Eindeutige Clip-ID
        
        Returns:
            True wenn erfolgreich
        """
        if clip_id not in self.clips:
            return False
        
        self.clips[clip_id]['effects'] = []
        logger.debug(f"Alle Effekte von Clip entfernt: {clip_id}")
        return True
    
    def update_clip_metadata(self, clip_id: str, metadata: Dict) -> bool:
        """
        Aktualisiert Metadaten eines Clips.
        
        Args:
            clip_id: Eindeutige Clip-ID
            metadata: Neue/aktualisierte Metadaten
        
        Returns:
            True wenn erfolgreich
        """
        if clip_id not in self.clips:
            return False
        
        self.clips[clip_id]['metadata'].update(metadata)
        return True


# Globale Singleton-Instanz
_clip_registry: Optional[ClipRegistry] = None


def get_clip_registry() -> ClipRegistry:
    """
    Singleton-Getter für ClipRegistry.
    
    Returns:
        Globale ClipRegistry-Instanz
    """
    global _clip_registry
    if _clip_registry is None:
        _clip_registry = ClipRegistry()
        logger.info("📋 ClipRegistry initialisiert")
    return _clip_registry
