# 🚀 Quick Reference: Client-to-Server Logging

## Setup (One-time)

Add this line to your HTML `<head>` **before other scripts**:
```html
<script src="js/client-logger.js"></script>
```

## Usage (Automatic)

Just use console as normal - logs are automatically sent to server:
```javascript
console.log('Message');      // → Server: INFO [JS LOG] Message
console.warn('Warning');     // → Server: WARNING [JS WARN] Warning  
console.error('Error');      // → Server: ERROR [JS ERROR] Error
console.info('Info');        // → Server: INFO [JS INFO] Info
```

## View Server Logs

```bash
# Watch all JS logs in real-time
tail -f logs/flux_*.log | grep "JS"

# View last 50 lines
tail -n 50 logs/flux_*.log | grep "JS"

# Search for specific error
grep "JS ERROR" logs/flux_*.log
```

## Control Logger (Optional)

```javascript
ClientLogger.disable();              // Stop sending logs
ClientLogger.enable();               // Resume sending logs
ClientLogger.setLevel('debug', true); // Enable debug level
ClientLogger.flush();                // Send logs immediately
```

## Test It

1. Open: `http://localhost:5000/logger-test.html`
2. Click test buttons
3. View server logs

## What Gets Logged

| Browser | Server Log |
|---------|-----------|
| `console.log('Hi')` | `INFO [JS LOG] [/page.html] Hi` |
| `console.error(err)` | `ERROR [JS ERROR] [/page.html] Error: message` |
| Uncaught errors | `ERROR [JS ERROR] + stack trace` |
| Promise rejections | `ERROR [JS ERROR] Unhandled Promise...` |

## Files

- **Client**: [frontend/js/client-logger.js](../frontend/js/client-logger.js)
- **Server**: [src/modules/api_logs.py](../src/modules/api_logs.py)
- **Docs**: [docs/CLIENT_LOGGING.md](CLIENT_LOGGING.md)
- **Test**: [frontend/logger-test.html](../frontend/logger-test.html)

## Benefits

✅ No more copy-pasting frontend errors  
✅ All logs in one place (server logs)  
✅ Automatic error capture with stack traces  
✅ Works with existing code (no changes needed)  
✅ Still logs to browser console too  

## Already Added To

- ✅ [frontend/player.html](../frontend/player.html)
- ✅ [frontend/index.html](../frontend/index.html)

Add to other HTML files as needed!
