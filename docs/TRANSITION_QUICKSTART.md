# 🎬 Transition System - Quick Start Guide

## Schnellstart (2 Minuten)

### 1. Server starten

```powershell
cd c:\Users\cromm\Documents\flux
python src\main.py
```

### 2. Player öffnen

Öffne Browser: `http://localhost:5001/player`

### 3. Transition aktivieren

1. **Klicke auf ⚡ Button** (neben Video-Playlist)
2. **Aktiviere Checkbox:** "Enable Transitions"
3. **Wähle Settings:**
   - Effect: `Fade`
   - Duration: `1.0s` (oder nach Belieben)
   - Easing: `Ease In-Out` (smoothest)

### 4. Clips laden

1. Ziehe 2-3 Videos in die **Video-Playlist**
2. Aktiviere **Autoplay** (🔁 Button)
3. Klicke **Play** (▶️)

### 5. Transition genießen! 🎉

Die Clips wechseln nun smooth mit Fade-Übergang!

---

## API Testing (1 Minute)

### Verfügbare Transitions abrufen

```bash
curl http://localhost:5001/api/transitions/list
```

**Response:**
```json
{
  "success": true,
  "transitions": [
    {
      "id": "fade",
      "name": "Fade",
      "description": "Smooth crossfade transition between frames",
      "parameters": {
        "duration": {"type": "float", "default": 1.0, "min": 0.1, "max": 5.0},
        "easing": {"type": "select", "default": "ease_in_out", "options": [...]}
      }
    }
  ],
  "count": 1
}
```

### Transition für Video-Player aktivieren

```bash
curl -X POST http://localhost:5001/api/player/video/transition/config \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "effect": "fade",
    "duration": 1.5,
    "easing": "ease_in_out"
  }'
```

**Response:**
```json
{
  "success": true,
  "player_id": "video",
  "config": {
    "enabled": true,
    "effect": "fade",
    "duration": 1.5,
    "easing": "ease_in_out"
  }
}
```

### Status abrufen

```bash
curl http://localhost:5001/api/player/video/transition/status
```

---

## Easing-Funktionen Vergleich

| Easing | Beschreibung | Use Case |
|--------|-------------|----------|
| **linear** | Gleichmäßige Geschwindigkeit | Technische Übergänge, Loops |
| **ease_in** | Langsam → Schnell | Erscheinen, Fade-In |
| **ease_out** | Schnell → Langsam | Verschwinden, Fade-Out |
| **ease_in_out** | Langsam → Schnell → Langsam | Smootheste Übergänge! ⭐ |

**Tipp:** Für Film-ähnliche Übergänge nutze `ease_in_out` mit `1.0-1.5s` Duration.

---

## Tipps & Tricks

### 🎨 Kreative Transitions

**Schnelle Cuts (MTV-Style):**
```javascript
{
  "enabled": true,
  "effect": "fade",
  "duration": 0.2,
  "easing": "linear"
}
```

**Cinematische Übergänge:**
```javascript
{
  "enabled": true,
  "effect": "fade",
  "duration": 2.0,
  "easing": "ease_in_out"
}
```

**Techno/Club Visuals:**
```javascript
{
  "enabled": true,
  "effect": "fade",
  "duration": 0.1,
  "easing": "ease_in"
}
```

### ⚡ Performance

**Optimale Settings für Live-Performance:**
- Duration: `0.5-1.0s`
- Easing: `linear` (am schnellsten)
- Resolution: 1920x1080 oder niedriger

**High-Quality Recording:**
- Duration: `1.5-2.0s`
- Easing: `ease_in_out`
- Resolution: 4K möglich

### 🔧 Debugging

**Browser Console (F12):**
```javascript
// Prüfe ob Transition-Menü geladen ist
console.log(window.createTransitionMenu);

// Zeige aktuelle Config
console.log(transitionMenus.video.getConfig());

// Manuell öffnen
transitionMenus.video.open();
```

**Server Logs:**
```bash
# Transition aktiviert
✅ video transition config updated: enabled=True, effect=fade, duration=1.5s, easing=ease_in_out

# Transition startet
⚡ [Video Player] Transition started: fade

# Transition abgeschlossen
✅ [Video Player] Transition complete (45 frames)
```

---

## Häufige Fehler

### ❌ "Transition plugin 'fade' not found"

**Ursache:** Plugin nicht registriert

**Lösung:**
```bash
# Prüfe Plugin-Manager
$env:PYTHONPATH="src"
python -c "from modules.plugin_manager import get_plugin_manager; from plugins.plugin_base import PluginType; pm = get_plugin_manager(); print(pm.list_plugins(PluginType.TRANSITION))"
```

### ❌ UI zeigt keine Transitions

**Ursache:** Template nicht geladen

**Lösung:**
1. Hard-Refresh: `Ctrl+F5`
2. Prüfe Network-Tab: `/static/components/transition-menu.html` geladen?
3. Prüfe Console: JavaScript-Fehler?

### ❌ Transitions ruckeln

**Ursache:** CPU-Überlast

**Lösung:**
1. Reduziere Duration auf `0.5s`
2. Nutze `linear` Easing
3. Reduziere Clip-Auflösung
4. Schließe andere Anwendungen

---

## Nächste Schritte

### Mehr Transitions erstellen

Siehe: `docs/TRANSITION_SYSTEM.md` - "Creating Custom Transitions"

### Integration mit Effects

Kombiniere Transitions mit Effect-Plugins für kreative Looks!

### Automation

Nutze API für automatisierte Transition-Sequenzen:
```python
import requests

transitions = [
    {"effect": "fade", "duration": 1.0},
    {"effect": "wipe_left", "duration": 0.5},
    {"effect": "dissolve", "duration": 1.5}
]

for i, trans in enumerate(transitions):
    requests.post(
        "http://localhost:5001/api/player/video/transition/config",
        json={"enabled": True, **trans}
    )
    time.sleep(30)  # Switch every 30 seconds
```

---

## Support

**Dokumentation:**
- `docs/TRANSITION_SYSTEM.md` - Technische Details
- `docs/TRANSITION_FRONTEND_INTEGRATION.md` - Frontend-Implementierung
- `docs/PLUGIN_SYSTEM.md` - Plugin-Entwicklung

**Tests:**
```bash
cd c:\Users\cromm\Documents\flux
$env:PYTHONPATH="src"
python tests\test_fade_transition.py
```

**Issues?** Check `logs/flux.log`

---

**Viel Spaß mit smooth Transitions! 🎬✨**
