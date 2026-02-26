# Quick Test: Selective Module Debugging

## Test 1: Enable Debug via Config

Edit `config.json`:

```json
{
  "app": {
    "console_log_level": "INFO",
    "file_log_level": "DEBUG",
    "debug_modules": [
      "modules.player.core"
    ]
  }
}
```

**Start the app** - You'll see DEBUG messages only from `modules.player.core`

## Test 2: Enable Debug at Runtime (No Restart)

While app is running, in another terminal:

```powershell
# Enable debug for Art-Net modules
curl -X POST http://localhost:5000/api/debug/modules/enable `
  -H "Content-Type: application/json" `
  -d '{"modules": ["modules.artnet.*", "modules.api.artnet"]}'

# Check status
curl http://localhost:5000/api/debug/modules

# Disable when done
curl -X POST http://localhost:5000/api/debug/modules/disable `
  -H "Content-Type: application/json" `
  -d '{"modules": ["modules.artnet.*"]}'
```

## Test 3: Debug Specific Issue

**Scenario:** Art-Net output not working

```json
{
  "app": {
    "console_log_level": "WARNING",
    "debug_modules": [
      "modules.artnet.*",
      "modules.player.outputs.base"
    ]
  }
}
```

Start app → Load video → Watch console for Art-Net debug messages

## Test 4: Wildcard Pattern

**Scenario:** Debug entire API layer

```json
{
  "app": {
    "console_log_level": "INFO", 
    "debug_modules": [
      "modules.api.*"
    ]
  }
}
```

Now every API request will show DEBUG logs!

## Verify It's Working

1. **Start app** with debug_modules configured
2. **Check startup logs** - Should see: `🔍 Debug enabled for modules: ...`
3. **Trigger the module** - Use the feature that would log
4. **Check logs** - `logs/flux_*.log` should contain DEBUG messages from that module
5. **Console output** - If `console_log_level: "DEBUG"`, you'll see it in terminal too

## Common Modules to Debug

| Module | When to use |
|--------|-------------|
| `modules.player.core` | Video playback issues |
| `modules.player.outputs.*` | Output plugin problems |
| `modules.artnet.*` | Art-Net transmission issues |
| `modules.api.*` | API endpoint debugging |
| `modules.player.effects.*` | Effect not applied |
| `modules.audio.*` | Audio analyzer issues |
| `modules.session.*` | Session save/restore problems |

## Tips

- Set `console_log_level: "WARNING"` to reduce noise
- Set `file_log_level: "DEBUG"` to capture all debug to file
- Use wildcards (`.*`) for broad debugging
- Use specific names for narrow debugging
- Check `logs/flux_*.log` for full debug output
