# Browser Cache & Storage komplett löschen

## Problem
Alte Float-IDs werden noch verwendet, obwohl der Code auf UUIDs umgestellt wurde.

## Lösung

### Option 1: Inkognito-Modus (schnell)
1. Öffne Browser im Inkognito-Modus (Ctrl+Shift+N in Chrome/Edge)
2. Navigiere zu http://localhost:5000
3. Teste die Anwendung

### Option 2: DevTools Clear Storage (empfohlen)
1. Öffne DevTools (F12)
2. Gehe zu "Application" Tab
3. Im linken Menü unter "Storage" → klicke "Clear site data"
4. Bestätige mit "Clear site data"
5. Lade Seite neu (Ctrl+Shift+R für Hard Reload)

### Option 3: Manuell localStorage löschen
1. Öffne DevTools Console (F12)
2. Führe aus: `localStorage.clear(); sessionStorage.clear();`
3. Lade Seite neu (Ctrl+Shift+R)

### Option 4: Browser Cache komplett löschen
**Chrome/Edge:**
- Ctrl+Shift+Delete
- Wähle "Cached images and files"
- Zeitraum: "All time"
- Klicke "Clear data"

**Firefox:**
- Ctrl+Shift+Delete
- Wähle "Cache"
- Zeitraum: "Everything"
- Klicke "Clear Now"

## Nach dem Löschen
1. Navigiere zu http://localhost:5000
2. Öffne DevTools Console (F12)
3. Prüfe ob Migration läuft: `⚠️ Migrating ... from float ID to UUID`
4. Füge neue Clips zur Playlist hinzu
5. Console sollte zeigen: `🆔 ... clip ID: frontend=<UUID>, backend=<UUID>, using=<UUID>`
