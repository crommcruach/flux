# Client-to-Server Logging Architecture

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         BROWSER                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Your JavaScript Code                                            │
│  ─────────────────────                                          │
│    console.log('Video loaded')  ──┐                             │
│    console.error('Failed')  ──────┤                             │
│    console.warn('Slow')  ─────────┤                             │
│                                    │                             │
│                                    ▼                             │
│  ┌───────────────────────────────────────────────────┐          │
│  │        client-logger.js (Interceptor)              │          │
│  ├───────────────────────────────────────────────────┤          │
│  │  ✓ Captures all console.* calls                   │          │
│  │  ✓ Still logs to browser console                  │          │
│  │  ✓ Batches logs for efficiency                    │          │
│  │  ✓ Rate limiting (max 100/min)                    │          │
│  │  ✓ Filters noise (socket.io, etc)                 │          │
│  └──────────────────┬────────────────────────────────┘          │
│                     │                                             │
│                     │ POST /api/logs/js-log                      │
│                     │ {                                           │
│                     │   "level": "log",                          │
│                     │   "message": "Video loaded",               │
│                     │   "url": "/player.html",                   │
│                     │   "timestamp": 1234567890                  │
│                     │ }                                           │
│                     │                                             │
└─────────────────────┼─────────────────────────────────────────────┘
                      │
                      │ HTTP POST
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                         SERVER                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Flask API Endpoint                                              │
│  ───────────────────                                            │
│    @app.route('/api/logs/js-log')                               │
│                     │                                             │
│                     ▼                                             │
│  ┌───────────────────────────────────────────────────┐          │
│  │         api_logs.py (Handler)                      │          │
│  ├───────────────────────────────────────────────────┤          │
│  │  ✓ Receives log data                              │          │
│  │  ✓ Formats message                                │          │
│  │  ✓ Adds metadata (URL, level)                     │          │
│  │  ✓ Routes to Python logger                        │          │
│  └──────────────────┬────────────────────────────────┘          │
│                     │                                             │
│                     ▼                                             │
│  ┌───────────────────────────────────────────────────┐          │
│  │        Python Logger (logging module)              │          │
│  ├───────────────────────────────────────────────────┤          │
│  │  logger.info('[JS LOG] Video loaded')             │          │
│  │  logger.error('[JS ERROR] Failed')                │          │
│  │  logger.warning('[JS WARN] Slow')                 │          │
│  └──────────────────┬────────────────────────────────┘          │
│                     │                                             │
│                     ▼                                             │
│  ┌───────────────────────────────────────────────────┐          │
│  │              Log Files                             │          │
│  ├───────────────────────────────────────────────────┤          │
│  │  logs/flux_20260129.log                           │          │
│  ├───────────────────────────────────────────────────┤          │
│  │  2026-01-29 10:30:15 INFO [JS LOG] Video loaded   │          │
│  │  2026-01-29 10:30:16 ERROR [JS ERROR] Failed      │          │
│  │  2026-01-29 10:30:17 WARNING [JS WARN] Slow       │          │
│  └───────────────────────────────────────────────────┘          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Console Call
```javascript
// Your code
console.log('Video loaded', videoData);
```

### 2. Interception
```javascript
// client-logger.js intercepts
- Captures: message, arguments, level, URL, timestamp
- Still shows in browser console
- Serializes data (objects → JSON)
```

### 3. Batching
```javascript
// Queued for efficient sending
Queue: [log1, log2, log3, ...]
→ Sent every 2 seconds or when batch reaches 10
→ Errors sent immediately
```

### 4. Network Request
```http
POST /api/logs/js-log HTTP/1.1
Content-Type: application/json

{
  "level": "log",
  "message": "Video loaded",
  "args": ["{"duration": 120}"],
  "url": "http://localhost:5000/player.html",
  "timestamp": 1706526615123
}
```

### 5. Server Processing
```python
# api_logs.py
@app.route('/api/logs/js-log', methods=['POST'])
def log_js_console():
    data = request.get_json()
    logger.info(f"[JS LOG] [{url}] {message}")
```

### 6. Log File
```
2026-01-29 10:30:15,123 INFO [JS LOG] [/player.html] Video loaded {"duration": 120}
```

## Error Handling Flow

### Uncaught Error
```javascript
// Error occurs
throw new Error('Video not found');

↓ Captured by window.onerror

↓ Sent to /api/logs/js-error with stack trace

↓ Logged with full context

Server log:
ERROR [JS ERROR] Uncaught Error: Video not found at player.js:145:20
ERROR [JS STACK] at loadVideo (player.js:145:20)
ERROR [JS STACK] at onClick (player.html:67:15)
```

## Performance Characteristics

| Aspect | Detail |
|--------|--------|
| **Overhead per log** | < 1ms |
| **Network requests** | ~1 every 2 seconds |
| **Batch size** | 10 logs per request |
| **Rate limit** | 100 logs/minute |
| **Queue size** | Max 100 logs |
| **Fallback** | Still logs to console if server down |

## Configuration Points

### Client-Side (client-logger.js)
```javascript
- enabled: true/false
- batchSize: 10
- batchTimeout: 2000ms
- rateLimit: 100/min
- sendLevels: { log, warn, error, info, debug }
- ignorePatterns: [regex patterns]
```

### Server-Side (api_logs.py)
```python
- Log level mapping
- Message formatting
- URL path extraction
- Stack trace parsing
```

## Security Considerations

```
Browser (Untrusted)
    ↓
    Validate input
    ↓
    Rate limit
    ↓
    Sanitize data
    ↓
Server (Trusted)
```

⚠️ Production checklist:
- [ ] Add authentication to log endpoints
- [ ] Implement server-side rate limiting
- [ ] Filter sensitive data (passwords, tokens)
- [ ] Consider disabling in production
- [ ] Monitor log file sizes

## Integration Points

### Existing Files Modified
1. **frontend/player.html** - Added script tag
2. **frontend/index.html** - Added script tag
3. **src/modules/api_logs.py** - Added endpoint

### New Files Created
1. **frontend/js/client-logger.js** - Main logger
2. **frontend/logger-test.html** - Test page
3. **docs/CLIENT_LOGGING*.md** - Documentation

## Benefits Summary

```
Before:
  User: "I got an error"
  Dev: "What error? Where? When?"
  User: "I don't know, I closed it"
  
After:
  User: "I got an error"
  Dev: *checks server logs*
  Dev: "I see it. Line 145, null pointer. Fixed."
```

No more:
- ❌ Copy-pasting errors from browser
- ❌ "Can you reproduce it?"
- ❌ Lost error messages
- ❌ Missing context

Instead:
- ✅ Automatic error capture
- ✅ Full stack traces
- ✅ Historical logs
- ✅ Complete context
