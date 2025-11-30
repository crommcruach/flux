#!/usr/bin/env python3
"""
Fix recursive debug calls in all JS files
"""

import re
from pathlib import Path

BUGGY_DEBUG = """const debug = {
    log: (...args) => { if (DEBUG_LOGGING) debug.log(...args); },
    info: (...args) => { if (DEBUG_LOGGING) debug.info(...args); },
    warn: (...args) => { if (DEBUG_LOGGING) debug.warn(...args); },
    error: (...args) => console.error(...args), // Errors always shown
    group: (...args) => { if (DEBUG_LOGGING) debug.group(...args); },
    groupEnd: () => { if (DEBUG_LOGGING) debug.groupEnd(); },
    table: (...args) => { if (DEBUG_LOGGING) debug.table(...args); }
};"""

FIXED_DEBUG = """const debug = {
    log: (...args) => { if (DEBUG_LOGGING) console.log(...args); },
    info: (...args) => { if (DEBUG_LOGGING) console.info(...args); },
    warn: (...args) => { if (DEBUG_LOGGING) console.warn(...args); },
    error: (...args) => console.error(...args), // Errors always shown
    group: (...args) => { if (DEBUG_LOGGING) console.group(...args); },
    groupEnd: () => { if (DEBUG_LOGGING) console.groupEnd(); },
    table: (...args) => { if (DEBUG_LOGGING) console.table(...args); }
};"""

BUGGY_LOADCONFIG = """        DEBUG_LOGGING = config.frontend?.debug_logging ?? true;
        debug.log(`🐛 Debug logging: ${DEBUG_LOGGING ? 'ENABLED' : 'DISABLED'}`);"""

FIXED_LOADCONFIG = """        DEBUG_LOGGING = config.frontend?.debug_logging ?? true;
        console.log(`🐛 Debug logging: ${DEBUG_LOGGING ? 'ENABLED' : 'DISABLED'}`);"""

BUGGY_TOGGLE = """window.toggleDebug = function(enable) {
    DEBUG_LOGGING = enable ?? !DEBUG_LOGGING;
    debug.log(`🐛 Debug logging ${DEBUG_LOGGING ? 'ENABLED' : 'DISABLED'}`);
    return DEBUG_LOGGING;
};"""

FIXED_TOGGLE = """window.toggleDebug = function(enable) {
    DEBUG_LOGGING = enable ?? !DEBUG_LOGGING;
    console.log(`🐛 Debug logging ${DEBUG_LOGGING ? 'ENABLED' : 'DISABLED'}`);
    return DEBUG_LOGGING;
};"""

def fix_file(file_path):
    """Fix recursive debug calls in a file"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Fix recursive debug object
    content = content.replace(BUGGY_DEBUG, FIXED_DEBUG)
    
    # Fix loadDebugConfig
    content = content.replace(BUGGY_LOADCONFIG, FIXED_LOADCONFIG)
    
    # Fix toggleDebug
    content = content.replace(BUGGY_TOGGLE, FIXED_TOGGLE)
    
    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Fixed: {file_path.name}")
        return True
    else:
        print(f"ℹ️  OK: {file_path.name}")
        return False

if __name__ == '__main__':
    base_path = Path(__file__).parent / 'src' / 'static' / 'js'
    
    # Files to fix
    files = [
        base_path / 'editor.js',
        base_path / 'controls.js',
        base_path / 'effects.js',
        base_path / 'artnet.js',
        base_path / 'cli.js',
        base_path / 'common.js',
        base_path / 'config.js',
        base_path / 'components' / 'effects-tab.js',
        base_path / 'components' / 'sources-tab.js',
        base_path / 'components' / 'files-tab.js',
    ]
    
    print("🔧 Fixing recursive debug calls...\n")
    
    fixed_count = 0
    for file_path in files:
        if file_path.exists():
            if fix_file(file_path):
                fixed_count += 1
        else:
            print(f"⚠️  {file_path.name} - File not found")
    
    print(f"\n✅ Fixed {fixed_count} file(s)")
