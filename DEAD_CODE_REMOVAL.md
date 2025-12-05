# Dead Code Removal Checklist

⚠️ **Markierte Stellen zur späteren Entfernung**

Diese Datei listet alle Dead Code Stellen im Backend auf, die nach erfolgreicher Migration auf das neue System entfernt werden können.

---

## 🗑️ Komplette Dateien zum Löschen

### 1. `src/modules/api_effects_deprecated.py` (198 lines)
**Status:** Ersetzt durch `api_player_unified.py`  
**Grund:** Legacy Effect Chain API für Video Player  
**Migration:** Alle Endpoints auf `/api/player/video/effects/*` umgestellt  
**Verwendung:** Nicht mehr in `rest_api.py` registriert  
**Aktion:** ✅ Datei kann gelöscht werden

### 2. `src/modules/api_artnet_effects_deprecated.py` (157 lines)
**Status:** Ersetzt durch `api_player_unified.py`  
**Grund:** Legacy Effect Chain API für Art-Net Player  
**Migration:** Alle Endpoints auf `/api/player/artnet/effects/*` umgestellt  
**Verwendung:** Nicht mehr in `rest_api.py` registriert  
**Aktion:** ✅ Datei kann gelöscht werden

### 3. `src/modules/api_clip_trim.py` (243 lines)
**Status:** Ersetzt durch Transport Effect Plugin  
**Grund:** Clip Trimming/Playback Control jetzt im Transport-Effekt  
**Migration:** Transport Plugin bietet alle Features (trim, speed, reverse, modes)  
**Verwendung:** Noch in `rest_api.py` registriert (Zeile 135, 157)  
**Abhängigkeiten:**
- `rest_api.py`: Import und Registration entfernen
- Frontend: Alte trim UI bereits auskommentiert
**Aktion:** ⚠️ Nach Verifikation löschen

---

## 🔧 Klassen zum Entfernen

### 4. `frame_source.py` - ScriptSource Klasse (Zeile 337-420)
**Status:** Ersetzt durch GeneratorSource mit Plugin-System  
**Grund:** Prozeduraler Script-Generator durch Plugin-System ersetzt  
**Migration:** Alle Generatoren sind jetzt Plugins  
**Verwendung:** Noch referenziert in:
- `api_routes.py`: register_script_routes (Zeile 765, 782, 809-810)
- `cli_handler.py`: load_script command (Zeile 197, 855, 888, 896-897)
- `dmx_controller.py`: Script loading (Zeile 227, 229, 231-232)
- `rest_api.py`: is_script check (Zeile 223-224, 429, 435-436)
- `__init__.py`: Export (Zeile 5, 16)

**Abhängigkeiten zu prüfen:**
```python
from .frame_source import ScriptSource
script_source = ScriptSource(script_name, width, height, config)
isinstance(source, ScriptSource)
```

**Aktion:** ⚠️ Alle Referenzen auf GeneratorSource umstellen, dann löschen

---

## 📦 Properties/Attribute zum Entfernen

### 5. `frame_source.py` - VideoSource trim/reverse Properties (Zeile 78-97)
**Code:**
```python
self.clip_id = clip_id
self.in_point = None
self.out_point = None
self.reverse = False
# + ClipRegistry loading logic
```
**Status:** Ersetzt durch Transport Effect Plugin  
**Grund:** Playback-Control jetzt im Effect-Layer  
**Migration:** Transport Plugin verwaltet trim/reverse  
**Aktion:** ⚠️ Nach Transport-Plugin-Verifikation entfernen

### 6. `player.py` - _legacy_source Attribute (Zeile 64-65)
**Code:**
```python
self._legacy_source = frame_source
```
**Status:** Ersetzt durch Layer-System  
**Grund:** Alle Sources jetzt in `layers[0].source`  
**Migration:** Layer-System vollständig implementiert  
**Verwendung:** Nur noch in `source` Property  
**Aktion:** ⚠️ Nach source Property Entfernung löschen

### 7. `player.py` - source Property (Zeile 1622-1644)
**Code:**
```python
@property
def source(self):
    if self.layers:
        return self.layers[0].source
    return self._legacy_source

@source.setter
def source(self, value):
    if self.layers:
        self.layers[0].source = value
    else:
        self._legacy_source = value
```
**Status:** Backward Compatibility Property  
**Grund:** Direkter Zugriff auf `layers[0].source` möglich  
**Migration:** Alle Code-Stellen auf `layers[0].source` umstellen  
**Verwendung:** Suche nach `player.source =` und `player.source`  
**Aktion:** ⚠️ Nach Referenz-Umstellung löschen

---

## 🔄 Methoden zum Entfernen

### 8. `clip_registry.py` - set_clip_trim() (Zeile 443-467)
**Status:** Ersetzt durch Transport Effect Plugin  
**Grund:** Trim-Daten jetzt in Effect-Plugin-State  
**Verwendung:** Nur noch in `api_clip_trim.py`  
**Aktion:** ✅ Mit api_clip_trim.py zusammen löschen

### 9. `clip_registry.py` - set_clip_reverse() (Zeile 469-490)
**Status:** Ersetzt durch Transport Effect Plugin  
**Grund:** Reverse-Daten jetzt in Effect-Plugin-State  
**Verwendung:** Nur noch in `api_clip_trim.py`  
**Aktion:** ✅ Mit api_clip_trim.py zusammen löschen

### 10. `clip_registry.py` - get_clip_playback_info() (Zeile 492-510)
**Status:** Ersetzt durch Transport Effect Plugin  
**Grund:** Playback-Info jetzt in Effect-Plugin-State  
**Verwendung:** Nur noch in `frame_source.py` (VideoSource.__init__)  
**Aktion:** ⚠️ Nach VideoSource trim properties Entfernung löschen

---

## 📋 Imports zum Entfernen

### 11. `rest_api.py` - api_clip_trim Import (Zeile 135)
**Code:**
```python
from .api_clip_trim import register_clip_trim_api
```
**Aktion:** ✅ Mit api_clip_trim.py zusammen löschen

### 12. `rest_api.py` - api_clip_trim Registration (Zeile 157)
**Code:**
```python
register_clip_trim_api(self.app, get_clip_registry(), self.player_manager)
```
**Aktion:** ✅ Mit api_clip_trim.py zusammen löschen

---

## 🎯 Entfernungs-Reihenfolge

### Phase 1: Sofort löschbar (keine Abhängigkeiten)
1. ✅ `api_effects_deprecated.py`
2. ✅ `api_artnet_effects_deprecated.py`

### Phase 2: Nach Verifikation (minimale Abhängigkeiten)
3. ⚠️ `api_clip_trim.py` + registrations
4. ⚠️ `clip_registry.py`: set_clip_trim, set_clip_reverse, get_clip_playback_info
5. ⚠️ `frame_source.py` (VideoSource): trim/reverse properties

### Phase 3: Nach ScriptSource Migration
6. ⚠️ `frame_source.py`: ScriptSource Klasse
7. ⚠️ Alle ScriptSource Imports in:
   - `api_routes.py`
   - `cli_handler.py`
   - `dmx_controller.py`
   - `rest_api.py`
   - `__init__.py`

### Phase 4: Nach Layer-System Migration
8. ⚠️ `player.py`: source Property (getter/setter)
9. ⚠️ `player.py`: _legacy_source Attribute
10. ⚠️ Alle `player.source` Zugriffe auf `player.layers[0].source` umstellen

---

## 🔍 Verwendungssuche

### ScriptSource Vorkommen prüfen:
```bash
grep -r "ScriptSource" src/
grep -r "from.*script_generator" src/
grep -r "script_source\s*=" src/
```

### player.source Vorkommen prüfen:
```bash
grep -r "\.source\s*=" src/
grep -r "player\.source" src/
grep -r "self\.source" src/modules/player.py
```

### api_clip_trim Vorkommen prüfen:
```bash
grep -r "register_clip_trim" src/
grep -r "from.*api_clip_trim" src/
```

---

## ✅ Abschluss-Checkliste

- [ ] Phase 1 abgeschlossen
- [ ] Phase 2 abgeschlossen
- [ ] Phase 3 abgeschlossen
- [ ] Phase 4 abgeschlossen
- [ ] Alle Tests nach jeder Phase ausführen
- [ ] Frontend Kompatibilität nach jeder Phase prüfen
- [ ] Diese Datei nach vollständiger Entfernung löschen

---

**Erstellt:** 2025-12-05  
**Zuletzt aktualisiert:** 2025-12-05  
**Status:** 🟡 In Arbeit - Markierungen gesetzt, noch nicht entfernt
