# Adding Client Logging to Other Pages

## Quick Add (2 minutes)

### Step 1: Add Script Tag

Add this line in the `<head>` section **before any other JavaScript**:

```html
<script src="js/client-logger.js"></script>
```

### Step 2: Test

Open the page and check browser console for:
```
🚀 Client Logger initialized - Logs will be sent to server
```

### Step 3: Verify

Check server logs:
```bash
tail -f logs/flux_*.log | grep "JS"
```

Done! 🎉

---

## Detailed Instructions

### For Each HTML File

1. **Open the HTML file**
2. **Find the `<head>` section**
3. **Add the script tag as the FIRST script**

### Example: Before

```html
<head>
  <meta charset="utf-8">
  <title>My Page</title>
  <link href="css/styles.css" rel="stylesheet">
  <script src="libs/jquery.min.js"></script>
  <script src="js/mypage.js"></script>
</head>
```

### Example: After

```html
<head>
  <meta charset="utf-8">
  <title>My Page</title>
  <link href="css/styles.css" rel="stylesheet">
  
  <!-- Client Logger - MUST BE FIRST -->
  <script src="js/client-logger.js"></script>
  
  <script src="libs/jquery.min.js"></script>
  <script src="js/mypage.js"></script>
</head>
```

---

## Files to Update

### Already Updated ✅
- [x] frontend/player.html
- [x] frontend/index.html

### Recommended to Update
- [ ] frontend/artnet.html
- [ ] frontend/benchmark.html
- [ ] frontend/cli.html
- [ ] frontend/config.html
- [ ] frontend/converter.html
- [ ] frontend/editor.html
- [ ] frontend/effects.html
- [ ] frontend/fullscreen.html
- [ ] frontend/output-settings.html

### Optional (Components)
- [ ] frontend/components/modal.html
- [ ] frontend/components/search-filter.html
- [ ] frontend/components/sequence-modal.html
- [ ] frontend/components/toast.html
- [ ] frontend/components/transition-menu.html

---

## Path Considerations

### Same Directory
If HTML is in `frontend/`:
```html
<script src="js/client-logger.js"></script>
```

### Subdirectory (components/)
If HTML is in `frontend/components/`:
```html
<script src="../js/client-logger.js"></script>
```

### Root
If HTML is at root level:
```html
<script src="frontend/js/client-logger.js"></script>
```

---

## Testing Checklist

After adding to each page:

1. ✅ **Load the page**
   ```
   http://localhost:5000/your-page.html
   ```

2. ✅ **Check browser console**
   ```
   Should see: 🚀 Client Logger initialized
   ```

3. ✅ **Test a log**
   ```javascript
   console.log('Test from your-page');
   ```

4. ✅ **Check server logs**
   ```bash
   grep "Test from your-page" logs/flux_*.log
   ```

5. ✅ **Test error capture**
   ```javascript
   throw new Error('Test error');
   ```

6. ✅ **Verify error in logs**
   ```bash
   grep "Test error" logs/flux_*.log
   ```

---

## Common Issues

### Script not loading (404)?

**Problem**: 
```
GET http://localhost:5000/js/client-logger.js 404
```

**Solution**: Check the path is correct relative to HTML file location.

```html
<!-- frontend/page.html -->
<script src="js/client-logger.js"></script>  ✅

<!-- frontend/components/page.html -->
<script src="../js/client-logger.js"></script>  ✅
```

---

### Logger not initializing?

**Problem**: No "Client Logger initialized" message

**Solution 1**: Check script is loaded before other scripts
```html
<!-- WRONG -->
<script src="js/myapp.js"></script>
<script src="js/client-logger.js"></script>  ❌

<!-- RIGHT -->
<script src="js/client-logger.js"></script>  ✅
<script src="js/myapp.js"></script>
```

**Solution 2**: Check browser console for errors

---

### Logs not appearing on server?

**Problem**: Logs show in browser but not in server logs

**Checklist**:
1. Check server is running
2. Check endpoint exists:
   ```bash
   curl -X POST http://localhost:5000/api/logs/js-log \
     -H "Content-Type: application/json" \
     -d '{"level":"log","message":"test","url":"test","timestamp":123}'
   ```
3. Check logger is enabled:
   ```javascript
   console.log(ClientLogger.config.enabled);  // Should be true
   ```
4. Check browser console for network errors

---

### Too many requests?

**Problem**: Network tab shows many requests to `/api/logs/js-log`

**Solution**: Logs are batched every 2 seconds by default. This is normal.

To reduce:
```javascript
// Edit client-logger.js CONFIG
batchTimeout: 5000  // Send every 5 seconds instead
```

---

## Bulk Update Script

To add to multiple files at once, create a script:

### PowerShell Script

```powershell
# add-logger.ps1
$files = @(
    "frontend/artnet.html",
    "frontend/cli.html",
    "frontend/config.html"
)

$loggerScript = '  <!-- Client Logger - MUST BE FIRST -->`n  <script src="js/client-logger.js"></script>`n'

foreach ($file in $files) {
    $content = Get-Content $file -Raw
    
    # Find </head> tag and insert before it
    $content = $content -replace '</head>', "$loggerScript  </head>"
    
    Set-Content $file $content
    Write-Host "✅ Updated: $file"
}
```

Run:
```powershell
.\add-logger.ps1
```

---

## Verification

After updating all files:

### 1. Quick Test All Pages

```javascript
// Test script - paste in browser console on each page
console.log(`Testing ${window.location.pathname}`);
setTimeout(() => {
    console.error('Test error from ' + window.location.pathname);
}, 1000);
```

### 2. Check Server Logs

```bash
# Should see entries from all pages
tail -f logs/flux_*.log | grep "JS" | grep "Testing"
```

### 3. Visual Confirmation

Create checklist:
```
Pages tested:
✅ /player.html - Logs working
✅ /index.html - Logs working
✅ /cli.html - Logs working
⬜ /config.html - Not tested yet
```

---

## Maintenance

### Updating the Logger

When you update `client-logger.js`, all pages automatically use the new version (no cache if developing locally).

### Disabling for Specific Pages

If you want to disable for a specific page:

```html
<script src="js/client-logger.js"></script>
<script>
  // Disable for this page only
  ClientLogger.disable();
</script>
```

### Temporary Disable

In browser console:
```javascript
ClientLogger.disable();
// ... do something ...
ClientLogger.enable();
```

---

## Production Deployment

Before deploying to production:

### Option 1: Disable Completely
```html
<!-- Comment out in production -->
<!-- <script src="js/client-logger.js"></script> -->
```

### Option 2: Environment Check
```html
<script src="js/client-logger.js"></script>
<script>
  // Disable in production
  if (window.location.hostname !== 'localhost' && 
      window.location.hostname !== '127.0.0.1') {
    ClientLogger.disable();
  }
</script>
```

### Option 3: Build Process
Use a build tool to remove the script tag in production builds.

---

## Summary

1. Add `<script src="js/client-logger.js"></script>` to `<head>`
2. Make sure it's the **first** script
3. Test the page
4. Check server logs
5. Done! ✅

Need help? Check:
- [Full Documentation](CLIENT_LOGGING.md)
- [Quick Reference](CLIENT_LOGGING_QUICKREF.md)
- [Test Page](../frontend/logger-test.html)
