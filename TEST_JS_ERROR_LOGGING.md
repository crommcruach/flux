# JavaScript Error Logging - Dokumentation

## Übersicht

JavaScript-Fehler werden jetzt automatisch in die Python-Log-Datei geschrieben.

## Implementierung

### Backend (Python)

**Neuer API-Endpoint:** `POST /api/logs/js-error`

**Datei:** `src/modules/api_logs.py`

```python
@app.route('/api/logs/js-error', methods=['POST'])
def log_js_error():
    """
    Loggt JavaScript-Fehler aus dem Frontend.
    
    Expected JSON:
        {
            "message": "Error message",
            "source": "file.js",
            "line": 123,
            "column": 45,
            "stack": "Stack trace",
            "url": "http://localhost:5000/page.html",
            "userAgent": "Mozilla/5.0..."
        }
    """
```

**Log-Format:**
```
[JS ERROR] Uncaught TypeError: Cannot read property 'foo' of undefined at script.js:42:15 (URL: http://localhost:5000/controls.html)
[JS STACK] at function1 (script.js:42:15)
[JS STACK] at function2 (script.js:67:8)
```

### Frontend (JavaScript)

**Datei:** `src/static/js/common.js`

**Neue Funktion:** `initErrorLogging()`

```javascript
export function initErrorLogging() {
    // Global error handler
    window.addEventListener('error', (event) => {
        // Loggt zu Backend
    });
    
    // Unhandled promise rejection handler
    window.addEventListener('unhandledrejection', (event) => {
        // Loggt Promise-Rejections
    });
}
```

**Integration:**
- `controls.js` - ✅ Initialisiert
- `cli.js` - ✅ Initialisiert  
- `editor.js` - ✅ Initialisiert

## Was wird geloggt?

### 1. Uncaught Errors
```javascript
// Beispiel: Undefinierter Variable-Zugriff
console.log(undefinedVariable.foo);
// → [JS ERROR] undefinedVariable is not defined at controls.js:123:45
```

### 2. Unhandled Promise Rejections
```javascript
// Beispiel: Fetch ohne Error-Handling
fetch('/api/broken')
    .then(res => res.json())
    .then(data => data.process());
// → [JS ERROR] data.process is not a function (promise-rejection)
```

### 3. Stack Traces
Vollständige Stack Traces werden in separaten Zeilen geloggt:
```
[JS STACK] at handleClick (controls.js:156:12)
[JS STACK] at HTMLButtonElement.<anonymous> (controls.js:45:8)
```

### 4. Context-Informationen
- **URL:** Aktuelle Seite (z.B. `/controls.html`)
- **User-Agent:** Browser-Info
- **Timestamp:** Fehler-Zeitpunkt
- **Source:** Quelldatei und Zeile

## Testing

### Manueller Test im Browser Console:

```javascript
// Test 1: Einfacher Error
throw new Error('Test error from console');

// Test 2: Undefined Variable
console.log(thisVariableDoesNotExist);

// Test 3: Promise Rejection
Promise.reject('Test rejection');

// Test 4: Null Reference
let obj = null;
console.log(obj.property);
```

### Log-Datei prüfen:

```powershell
# Zeige neueste Log-Einträge
Get-Content .\logs\flux_*.log -Tail 20
```

## Vorteile

✅ **Automatisches Error-Tracking** - Keine manuelle Fehlersuche mehr  
✅ **Zentrale Log-Datei** - Backend & Frontend Fehler an einem Ort  
✅ **Stack Traces** - Vollständige Fehleranalyse möglich  
✅ **User-Context** - Browser, URL, Zeitpunkt bekannt  
✅ **Promise-Support** - Auch async Fehler werden erfasst  
✅ **Keine Duplikation** - Shared error handler in common.js  

## Datenschutz

**Keine sensitiven Daten:**
- Keine User-Inputs werden geloggt
- Nur technische Error-Informationen
- User-Agent für Browser-Debugging
- Lokale Log-Dateien (nicht extern)

## Performance

**Minimal Overhead:**
- Error-Logging nur bei Fehlern (nicht im Normal-Betrieb)
- Async POST-Request (blockiert nicht)
- Keine Console-Spam (nur 1 Log pro Error)
- Throttling bei mehreren gleichen Errors möglich

## Zukünftige Erweiterungen

### Mögliche Features:
1. **Error-Deduplizierung** - Gleiche Fehler nur 1x pro Minute loggen
2. **Error-Counter** - Wie oft trat der Fehler auf?
3. **Source Maps** - Minified Code zu Original-Code mappen
4. **Error-Kategorien** - Kritisch, Warning, Info
5. **Email-Alerts** - Bei kritischen Fehlern
6. **Error-Dashboard** - Web-UI für Error-Analyse

## Troubleshooting

### Errors werden nicht geloggt?

**Prüfen:**
1. Browser Console - Erscheinen Fehler dort?
2. Network Tab - Wird `/api/logs/js-error` aufgerufen?
3. Backend Log - Erscheinen `[JS ERROR]` Einträge?
4. `initErrorLogging()` wird aufgerufen?

### Zu viele Logs?

**Lösung: Throttling hinzufügen**
```javascript
let lastErrorTime = 0;
const ERROR_THROTTLE = 5000; // 5 Sekunden

if (Date.now() - lastErrorTime > ERROR_THROTTLE) {
    logErrorToBackend(error, source);
    lastErrorTime = Date.now();
}
```

## Beispiel Log-Output

```
2025-11-22 14:23:45,123 - flux - ERROR - [JS ERROR] Cannot read property 'data' of null at controls.js:156:12 (URL: http://localhost:5000/controls.html)
2025-11-22 14:23:45,124 - flux - ERROR - [JS STACK] at updateStatus (controls.js:156:12)
2025-11-22 14:23:45,124 - flux - ERROR - [JS STACK] at HTMLDocument.<anonymous> (controls.js:45:8)
2025-11-22 14:23:45,125 - flux - DEBUG - [JS ERROR] User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0
```

## Fazit

JavaScript-Fehler werden jetzt zuverlässig in die Backend-Logs geschrieben. Das erleichtert das Debugging erheblich, da alle Fehler zentral verfügbar sind.
