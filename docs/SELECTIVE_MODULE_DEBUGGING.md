# Selective Module Debugging

## Overview

Py_artnet now supports **selective module debugging** - you can enable DEBUG-level logging for specific modules while keeping others at INFO/WARNING level. This is useful for troubleshooting specific parts of the application without being overwhelmed by debug messages from all modules.

## Features

- ✅ **Module-specific log levels** - Enable DEBUG only where needed
- ✅ **Wildcard support** - Use patterns like `modules.player.*` to debug all player modules
- ✅ **Config-based** - Set debug modules in `config.json` (applied on startup)
- ✅ **Runtime control** - Enable/disable debug via REST API without restart
- ✅ **No performance impact** - Only enabled modules produce debug logs

## Configuration (config.json)

### Basic Setup

Add module patterns to the `debug_modules` array in `config.json`:

```json
{
  "app": {
    "console_log_level": "INFO",
    "file_log_level": "INFO",
    "debug_modules": [
      "modules.player.core",
      "modules.api.artnet"
    ]
  }
}
```

These modules will have DEBUG level enabled on startup, while all other modules remain at INFO level.

### Wildcard Patterns

You can use wildcards to enable debug for multiple modules:

```json
{
  "app": {
    "debug_modules": [
      "modules.player.*",        // All player modules
      "modules.api.*",           // All API modules
      "modules.artnet.routing*"  // All routing-related modules
    ]
  }
}
```

### Common Module Patterns

| Pattern | What it enables |
|---------|----------------|
| `modules.player.core` | Main player loop |
| `modules.player.outputs.*` | All output plugins (display, virtual, NDI) |
| `modules.player.effects.*` | Effects system |
| `modules.api.*` | All API endpoints |
| `modules.api.artnet` | Art-Net API only |
| `modules.artnet.*` | Art-Net routing and bridge |
| `modules.audio.*` | Audio analyzer and sequences |
| `modules.session.*` | Session persistence |

## Runtime Control (REST API)

### Get Current Module Debug Levels

```bash
GET /api/debug/modules
```

**Response:**
```json
{
  "success": true,
  "modules": {
    "modules.player.core": "DEBUG",
    "modules.api.artnet": "DEBUG"
  },
  "total": 2
}
```

### Enable Debug for Modules

```bash
POST /api/debug/modules/enable
Content-Type: application/json

{
  "modules": ["modules.player.effects.*", "modules.api.artnet"]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Debug enabled for 2 module(s)",
  "modules": ["modules.player.effects.*", "modules.api.artnet"],
  "current_levels": {
    "modules.player.effects.*": "DEBUG",
    "modules.api.artnet": "DEBUG"
  }
}
```

### Disable Debug for Modules

```bash
POST /api/debug/modules/disable
Content-Type: application/json

{
  "modules": ["modules.player.core"]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Debug disabled for 1 module(s)",
  "modules": ["modules.player.core"],
  "current_levels": {}
}
```

## Usage Examples

### Example 1: Debug Art-Net Issues

**Problem:** Art-Net packets not being sent correctly

**Solution:**
```json
{
  "app": {
    "debug_modules": [
      "modules.artnet.*",
      "modules.api.artnet"
    ]
  }
}
```

This will show:
- Art-Net routing decisions
- Pixel remapping operations
- Output slice calculations
- Art-Net API requests

### Example 2: Debug Player Performance Issues

**Problem:** Video playback stuttering or frame drops

**Solution:**
```json
{
  "app": {
    "debug_modules": [
      "modules.player.core",
      "modules.player.outputs.*",
      "modules.player.sources"
    ]
  }
}
```

This will show:
- Frame generation timing
- Output plugin performance
- Video decoding operations
- FPS limiting logic

### Example 3: Debug Effects Not Working

**Problem:** Effects not being applied as expected

**Solution:**
```json
{
  "app": {
    "debug_modules": [
      "modules.player.effects.*",
      "plugins.effects.*"
    ]
  }
}
```

This will show:
- Effect initialization
- Effect chain processing
- Parameter updates
- Default effects application

### Example 4: Debug via API (No Restart)

If you discover an issue while the app is running:

```bash
# Enable debug for audio analyzer
curl -X POST http://localhost:5000/api/debug/modules/enable \
  -H "Content-Type: application/json" \
  -d '{"modules": ["modules.audio.*"]}'

# Watch logs for debug output...

# Disable when done
curl -X POST http://localhost:5000/api/debug/modules/disable \
  -H "Content-Type: application/json" \
  -d '{"modules": ["modules.audio.*"]}'
```

## Best Practices

### ✅ Do's

- **Start narrow** - Enable debug for specific modules first
- **Use wildcards** - `modules.player.*` instead of listing every submodule
- **Runtime testing** - Use API to test which modules to debug
- **Document findings** - Add useful debug modules to config.json for future sessions

### ❌ Don'ts

- **Don't debug everything** - Defeats the purpose, use `console_log_level: "DEBUG"` instead
- **Don't leave debug on in production** - Remove `debug_modules` from shipped configs
- **Don't guess module names** - Check logs to see exact module paths

## Finding Module Names

Module names follow the project structure. To find the exact name:

1. **Check the file path:**
   ```
   src/modules/player/core.py → modules.player.core
   src/modules/api/artnet.py → modules.api.artnet
   plugins/effects/transition.py → plugins.effects.transition
   ```

2. **Check log output:**
   ```
   INFO | modules.player.core | Frame 1234 rendered
          ^^^^^^^^^^^^^^^^^^^
          This is the module name
   ```

3. **Use wildcards if unsure:**
   ```json
   "debug_modules": ["modules.player.*"]  // Catches all player modules
   ```

## Performance Impact

- **Minimal overhead** - Only affects enabled modules
- **File logging** - All debug messages go to log files
- **Console filtering** - Console still respects `console_log_level` setting
- **No runtime penalty** - Disabled modules don't evaluate debug statements

## Troubleshooting

### Module debug not working?

1. **Check module name** - Verify exact module path in logs
2. **Check log level** - Must have `file_log_level: "DEBUG"` in config
3. **Restart required** - Changes to `debug_modules` in config need restart
4. **Use API for instant testing** - Runtime changes don't need restart

### Too many logs?

1. **Be more specific** - Use exact module names instead of wildcards
2. **Disable when done** - Use API to disable debug after finding issue
3. **Adjust console_log_level** - Set to WARNING to reduce console output

### Module not found?

1. **Check spelling** - Module names are case-sensitive
2. **Check if module exists** - Some plugins may not be loaded
3. **Use pattern** - Try `modules.api.*` instead of specific endpoint

## Integration with Existing Debug System

This module debugging system works **alongside** the existing `DebugCategories` system:

- **Module debugging** - Controls which modules produce DEBUG logs
- **Debug categories** - Controls which types of operations are logged (transport, effects, etc.)

Both systems are independent and can be used together for maximum flexibility.

## See Also

- [DEBUG_SYSTEM.md](DEBUG_SYSTEM.md) - Original category-based debug system
- [LOGGING.md](LOGGING.md) - General logging architecture
- [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md) - Complete config.json schema
