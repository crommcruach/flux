# Client-Side Logging System

## Overview

The client-side logging system automatically pipes all JavaScript console logs to the server, making debugging much easier since you don't have to manually copy frontend errors.

## Features

✅ **Automatic Log Capture**: Intercepts all `console.log()`, `console.warn()`, `console.error()`, `console.info()`, and `console.debug()` calls  
✅ **Error Tracking**: Automatically captures uncaught errors and unhandled promise rejections  
✅ **Batched Sending**: Groups logs together to reduce network overhead  
✅ **Rate Limiting**: Prevents log spam from overwhelming the server  
✅ **Smart Filtering**: Ignores noisy logs (socket.io messages, favicon 404s, etc.)  
✅ **Zero Configuration**: Works out of the box  

## Setup

### 1. Include the Script

Add this line to your HTML files **before** any other JavaScript files:

```html
<script src="js/client-logger.js"></script>
```

**Important**: This script must load before other scripts to capture all logs.

### Example for player.html:

```html
<head>
  <meta charset="utf-8" />
  <title>Flux Player</title>
  
  <!-- Client Logger - MUST BE FIRST -->
  <script src="js/client-logger.js"></script>
  
  <!-- Other scripts -->
  <script src="js/session-loader.js" defer></script>
  <script src="js/menu-loader.js" defer></script>
  <!-- etc... -->
</head>
```

### 2. Server-Side Endpoint

The server endpoint is already configured at:
- `/api/logs/js-log` - For console logs
- `/api/logs/js-error` - For errors

See [api_logs.py](../src/modules/api_logs.py) for implementation.

## Usage

### Automatic Logging

Once included, all console calls are automatically sent to the server:

```javascript
console.log('This will appear in server logs');
console.warn('Warning message');
console.error('Error message');
console.info('Info message');
```

**Server log output:**
```
2026-01-29 10:30:15,123 INFO [JS LOG] [/player.html] This will appear in server logs
2026-01-29 10:30:16,234 WARNING [JS WARN] [/player.html] Warning message
2026-01-29 10:30:17,345 ERROR [JS ERROR] [/player.html] Error message
```

### Complex Objects

The logger automatically serializes objects:

```javascript
console.log('User data:', { name: 'John', age: 30 });
console.error('Failed request:', new Error('Network timeout'));
```

### Manual Control

You can control the logger via the global `ClientLogger` API:

```javascript
// Disable logging
ClientLogger.disable();

// Re-enable logging
ClientLogger.enable();

// Disable specific log levels
ClientLogger.setLevel('debug', false);  // Don't send debug logs
ClientLogger.setLevel('error', true);   // Send error logs

// Manually flush logs to server immediately
ClientLogger.flush();

// Access configuration
console.log(ClientLogger.config);
```

## Configuration

Edit `client-logger.js` to customize behavior:

```javascript
const CONFIG = {
    enabled: true,              // Enable/disable logging
    batchSize: 10,              // Logs per batch
    batchTimeout: 2000,         // Send batch after 2 seconds
    maxQueueSize: 100,          // Max logs to queue
    rateLimit: 100,             // Max logs per minute
    sendLevels: {
        log: true,
        info: true,
        warn: true,
        error: true,
        debug: false            // Set to true for debug logs
    },
    ignorePatterns: [
        /socket\.io/i,          // Ignore socket.io messages
        /favicon\.ico/i         // Ignore favicon 404s
    ]
};
```

## Viewing Logs

### Option 1: Server Log Files

All client logs appear in your server logs:

```bash
tail -f logs/flux_YYYYMMDD.log | grep "JS"
```

### Option 2: Web Interface

Access logs via the REST API:

```javascript
fetch('/api/logs')
  .then(r => r.json())
  .then(data => console.log(data.lines));
```

### Option 3: CLI Page

Visit `http://localhost:5000/cli.html` to see live logs in the web console.

## Performance Impact

- **Minimal**: Logs are batched and rate-limited
- **Network**: ~1 request every 2 seconds (adjustable)
- **Overhead**: <1ms per log call
- **Fallback**: If server is unreachable, logs still appear in browser console

## Troubleshooting

### Logs not appearing on server?

1. Check browser console for errors
2. Verify script is loaded: `console.log(ClientLogger)`
3. Check if logging is enabled: `ClientLogger.config.enabled`
4. Test endpoint manually:
   ```javascript
   fetch('/api/logs/js-log', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({
           level: 'log',
           message: 'Test',
           url: window.location.href,
           timestamp: Date.now()
       })
   }).then(r => r.json()).then(console.log);
   ```

### Too many logs?

1. Increase `rateLimit` in config
2. Add patterns to `ignorePatterns`
3. Disable specific levels: `ClientLogger.setLevel('debug', false)`

### Logs missing context?

The logger includes:
- Full message and arguments
- URL of the page
- Timestamp
- Stack trace (for errors)

## Security Considerations

- ⚠️ **Production**: Consider disabling in production or filtering sensitive data
- ⚠️ **Rate Limiting**: Server should implement additional rate limiting
- ⚠️ **Authentication**: Consider adding auth to log endpoints for production

## Disable in Production

To disable client logging in production, either:

**Option 1: Remove the script tag**
```html
<!-- <script src="js/client-logger.js"></script> -->
```

**Option 2: Disable programmatically**
```javascript
if (window.location.hostname !== 'localhost') {
    ClientLogger.disable();
}
```

**Option 3: Server-side control**
Only include the script tag when in development mode.

## Integration with Existing Code

The logger is completely transparent - your existing code doesn't need any changes. All `console.*` calls will automatically be captured and sent to the server while still appearing in the browser console.

## Examples

### Debugging a Video Player

```javascript
// All these logs will appear on server
console.log('🎬 Loading video:', videoPath);
console.log('📊 Video metadata:', metadata);
console.warn('⚠️ Slow loading time:', loadTime);
console.error('❌ Failed to load video:', error);
```

**Server logs:**
```
INFO [JS LOG] [/player.html] 🎬 Loading video: /videos/test.mp4
INFO [JS LOG] [/player.html] 📊 Video metadata: {"duration": 120, "fps": 30}
WARNING [JS WARN] [/player.html] ⚠️ Slow loading time: 5234
ERROR [JS ERROR] [/player.html] ❌ Failed to load video: NetworkError
```

### Error Tracking

```javascript
try {
    riskyOperation();
} catch (error) {
    console.error('Operation failed:', error);
    // Automatically sent to server with stack trace
}
```

## API Reference

### ClientLogger.enable()
Enable log sending to server.

### ClientLogger.disable()
Disable log sending to server (logs still appear in browser console).

### ClientLogger.setLevel(level, enabled)
Enable/disable specific log level.
- `level`: 'log', 'info', 'warn', 'error', 'debug'
- `enabled`: boolean

### ClientLogger.flush()
Immediately send all queued logs to server.

### ClientLogger.config
Access configuration object.

## Related Files

- Frontend: [client-logger.js](js/client-logger.js)
- Backend: [api_logs.py](../src/modules/api_logs.py)
- Documentation: This file

## Future Enhancements

Possible improvements:
- [ ] Session tracking (group logs by user session)
- [ ] Performance metrics (timing data)
- [ ] Network request logging
- [ ] User action tracking
- [ ] Source map support for minified code
- [ ] Log search/filter in web UI
- [ ] Real-time log streaming via WebSocket
