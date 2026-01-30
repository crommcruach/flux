# Client-to-Server Logging Implementation

## ✅ What Was Implemented

A complete client-side logging system that pipes all JavaScript console logs to the server for centralized debugging.

## 📁 Files Created/Modified

### New Files:
1. **[frontend/js/client-logger.js](../frontend/js/client-logger.js)**
   - Main client-side logger script
   - Intercepts all console.* calls
   - Batches and sends logs to server
   - Rate limiting and filtering

2. **[docs/CLIENT_LOGGING.md](CLIENT_LOGGING.md)**
   - Complete documentation
   - Usage examples
   - Configuration guide
   - Troubleshooting

3. **[frontend/logger-test.html](../frontend/logger-test.html)**
   - Interactive test page
   - Test all log types
   - View server logs
   - Control logger settings

### Modified Files:
1. **[src/modules/api_logs.py](../src/modules/api_logs.py)**
   - Added `/api/logs/js-log` endpoint
   - Handles all log levels (log, warn, error, info, debug)
   - Logs to Python logging system

2. **[frontend/player.html](../frontend/player.html)**
   - Added client-logger.js script
   - Example integration

3. **[frontend/index.html](../frontend/index.html)**
   - Added client-logger.js script
   - Example integration

## 🚀 How to Use

### Quick Start

1. **Server is already configured** - no backend changes needed!

2. **Add to your HTML files** (already done for player.html and index.html):
   ```html
   <script src="js/client-logger.js"></script>
   ```

3. **That's it!** All console logs will now appear in server logs:
   ```javascript
   console.log('Hello');  // Appears in server logs
   console.error('Oops'); // Appears in server logs with stack trace
   ```

### Test It

1. Start your server:
   ```bash
   python src/main.py
   ```

2. Open the test page:
   ```
   http://localhost:5000/logger-test.html
   ```

3. Click the test buttons and watch server logs:
   ```bash
   tail -f logs/flux_*.log | grep "JS"
   ```

## 📊 What Gets Logged

### Browser Console:
```javascript
console.log('Video loaded:', { duration: 120 });
console.error('Failed to load', error);
```

### Server Logs:
```
2026-01-29 10:30:15,123 INFO [JS LOG] [/player.html] Video loaded: {"duration": 120}
2026-01-29 10:30:16,234 ERROR [JS ERROR] [/player.html] Failed to load Error: Network timeout
```

## 🎯 Features

✅ **Automatic**: No code changes needed  
✅ **Non-invasive**: Logs still appear in browser console  
✅ **Efficient**: Batched sending, rate limiting  
✅ **Smart**: Filters noise (socket.io, favicon 404s)  
✅ **Complete**: Captures errors, warnings, info, debug  
✅ **Stack traces**: Errors include full stack trace  

## ⚙️ Configuration

Edit `client-logger.js` to customize:

```javascript
const CONFIG = {
    enabled: true,          // Toggle on/off
    batchSize: 10,          // Logs per batch
    batchTimeout: 2000,     // Send after 2 seconds
    rateLimit: 100,         // Max logs per minute
    sendLevels: {
        log: true,
        warn: true,
        error: true,
        debug: false        // Enable if needed
    }
};
```

## 🎮 Runtime Control

Control via browser console:

```javascript
// Disable/enable
ClientLogger.disable();
ClientLogger.enable();

// Control specific levels
ClientLogger.setLevel('debug', true);

// Flush immediately
ClientLogger.flush();

// View config
console.log(ClientLogger.config);
```

## 📈 Benefits

1. **No more copy-pasting errors** from browser to chat
2. **Historical logs** - even after closing browser
3. **Production debugging** - see what users experience
4. **Centralized** - all logs in one place
5. **Context** - URL, timestamp, stack trace included

## 🔧 Troubleshooting

### Logs not appearing?

1. Check if script loaded:
   ```javascript
   console.log(ClientLogger);
   ```

2. Check server endpoint:
   ```bash
   curl -X POST http://localhost:5000/api/logs/js-log \
     -H "Content-Type: application/json" \
     -d '{"level":"log","message":"test","url":"test","timestamp":123}'
   ```

3. Check server logs for errors:
   ```bash
   grep "js-log\|JS LOG\|JS ERROR" logs/flux_*.log
   ```

### Too many logs?

- Increase `rateLimit` in config
- Add patterns to `ignorePatterns`
- Disable debug level: `ClientLogger.setLevel('debug', false)`

## 🔐 Security

⚠️ **Important for Production**:

- Consider disabling in production OR
- Add authentication to log endpoints
- Filter sensitive data before logging
- Implement server-side rate limiting

Example production disable:
```javascript
if (window.location.hostname !== 'localhost') {
    ClientLogger.disable();
}
```

## 📝 Example Output

### Before (manual error reporting):
```
User: "I got an error: Uncaught TypeError: Cannot read property 'duration' of undefined"
You: "What line? What file? What were you doing?"
```

### After (automatic logging):
```
Server logs:
2026-01-29 10:30:15,123 ERROR [JS ERROR] [/player.html] Uncaught TypeError: Cannot read property 'duration' of undefined at player.js:145:20
[JS STACK] at loadVideo (player.js:145:20)
[JS STACK] at HTMLButtonElement.onclick (player.html:67:15)
```

## 🎉 Summary

You now have automatic client-to-server logging! No more manually posting frontend errors. Just check your server logs to see everything that happens in the browser.

## 📚 Additional Resources

- Full Documentation: [CLIENT_LOGGING.md](CLIENT_LOGGING.md)
- Test Page: `http://localhost:5000/logger-test.html`
- Server Code: [api_logs.py](../src/modules/api_logs.py)
- Client Code: [client-logger.js](../frontend/js/client-logger.js)

## 🔄 Next Steps

1. Test the logger with the test page
2. Add `<script src="js/client-logger.js"></script>` to other HTML files
3. Monitor server logs while using the application
4. Adjust configuration based on your needs
5. Consider production deployment strategy
