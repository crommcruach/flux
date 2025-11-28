# Debug Logging System

## Übersicht

Das Debug-Logging-System ermöglicht es, Browser-Console-Ausgaben zentral zu steuern. Fehler (`console.error`) werden immer angezeigt, während Debug-Ausgaben (`debug.log`, `debug.warn`, `debug.info`) über die Konfiguration gesteuert werden können.

## Konfiguration

### config.json

```json
{
  "frontend": {
    "debug_logging": true,
    "_debug_logging_comment": "Enable/disable console.log debug output in browser console (true/false)"
  }
}
```

**Optionen:**
- `true`: Debug-Ausgaben werden angezeigt (Standard)
- `false`: Debug-Ausgaben werden unterdrückt (nur Fehler werden angezeigt)

## Verwendung

### Im Code

Statt `console.log()`, `console.warn()`, `console.info()` verwenden wir die `debug`-Wrapper:

```javascript
// Alte Methode (deprecated)
console.log('🎬 Video geladen:', videoPath);
console.warn('⚠️ Warnung:', message);

// Neue Methode
debug.log('🎬 Video geladen:', videoPath);
debug.warn('⚠️ Warnung:', message);

// Fehler werden IMMER angezeigt
console.error('❌ Fehler:', error);
// oder
debug.error('❌ Fehler:', error);
```

### Verfügbare Debug-Funktionen

- `debug.log(...)` - Normal log (wenn DEBUG_LOGGING = true)
- `debug.info(...)` - Info log (wenn DEBUG_LOGGING = true)
- `debug.warn(...)` - Warning log (wenn DEBUG_LOGGING = true)
- `debug.error(...)` - Error log (IMMER angezeigt)
- `debug.group(...)` - Console group (wenn DEBUG_LOGGING = true)
- `debug.groupEnd()` - Console group end (wenn DEBUG_LOGGING = true)
- `debug.table(...)` - Console table (wenn DEBUG_LOGGING = true)

## Laufzeit-Kontrolle

Debug-Logging kann zur Laufzeit über die Browser-Console umgeschaltet werden:

```javascript
// Debug-Logging aktivieren
toggleDebug(true);

// Debug-Logging deaktivieren
toggleDebug(false);

// Debug-Logging umschalten (toggle)
toggleDebug();
```

## Migration

Alle `console.log/warn/info` Aufrufe in allen JavaScript-Dateien wurden automatisch durch `debug.log/warn/info` ersetzt:

### Betroffene Dateien (11)
- `player.js`
- `controls.js`
- `editor.js`
- `effects.js`
- `artnet.js`
- `cli.js`
- `common.js`
- `config.js`
- `components/effects-tab.js`
- `components/sources-tab.js`
- `components/files-tab.js`

### Migration-Statistik
- ✅ 208 × `console.log()` → `debug.log()`
- ✅ 26 × `console.warn()` → `debug.warn()`
- ⚠️ 166 × `console.error()` (unverändert - Fehler immer anzeigen)

### Backups
Für jede modifizierte Datei wurde ein Backup erstellt (`.js.backup`)

## Vorteile

1. **Zentrale Steuerung**: Debug-Ausgaben können global ein-/ausgeschaltet werden
2. **Performance**: Weniger Console-Ausgaben in Produktion
3. **Übersichtlichkeit**: Nur relevante Logs werden angezeigt
4. **Flexibilität**: Kann zur Laufzeit umgeschaltet werden
5. **Fehlertoleranz**: Kritische Fehler werden immer angezeigt

## Beispiel

### Debug aktiviert (Standard)
```
🐛 Debug logging: ENABLED
🎬 Loading video: test.mp4
✅ Video loaded successfully
📊 FPS: 30
```

### Debug deaktiviert
```
🐛 Debug logging: DISABLED
❌ Error: File not found (nur Fehler werden angezeigt)
```
