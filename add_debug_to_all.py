#!/usr/bin/env python3
"""
Add debug logging system to all JS files
"""

import re
from pathlib import Path

# Debug system code to inject
DEBUG_SYSTEM = """
// ========================================
// DEBUG LOGGING SYSTEM
// ========================================

let DEBUG_LOGGING = true; // Default: enabled

// Debug logger wrapper functions
const debug = {
    log: (...args) => { if (DEBUG_LOGGING) console.log(...args); },
    info: (...args) => { if (DEBUG_LOGGING) console.info(...args); },
    warn: (...args) => { if (DEBUG_LOGGING) console.warn(...args); },
    error: (...args) => console.error(...args), // Errors always shown
    group: (...args) => { if (DEBUG_LOGGING) console.group(...args); },
    groupEnd: () => { if (DEBUG_LOGGING) console.groupEnd(); },
    table: (...args) => { if (DEBUG_LOGGING) console.table(...args); }
};

// Load debug setting from config
async function loadDebugConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        DEBUG_LOGGING = config.frontend?.debug_logging ?? true;
        console.log(`🐛 Debug logging: ${DEBUG_LOGGING ? 'ENABLED' : 'DISABLED'}`);
    } catch (error) {
        console.error('❌ Failed to load debug config, using default (enabled):', error);
        DEBUG_LOGGING = true;
    }
}

// Runtime toggle function (accessible from browser console)
window.toggleDebug = function(enable) {
    DEBUG_LOGGING = enable ?? !DEBUG_LOGGING;
    console.log(`🐛 Debug logging ${DEBUG_LOGGING ? 'ENABLED' : 'DISABLED'}`);
    return DEBUG_LOGGING;
};
"""

def has_debug_system(content):
    """Check if file already has debug system"""
    return 'DEBUG LOGGING SYSTEM' in content or 'const debug = {' in content

def inject_debug_system(content):
    """Inject debug system after imports or at start"""
    
    # Check if file already has debug system
    if has_debug_system(content):
        return content, False
    
    # Find injection point (after imports or at start)
    import_match = re.search(r'^((?:import .+?;\s*)+)', content, re.MULTILINE)
    
    if import_match:
        # Inject after imports
        imports_end = import_match.end()
        new_content = content[:imports_end] + '\n' + DEBUG_SYSTEM + '\n' + content[imports_end:]
    else:
        # Inject at start (check for comments first)
        comment_match = re.search(r'^(/\*\*[\s\S]*?\*/\s*)', content)
        if comment_match:
            comment_end = comment_match.end()
            new_content = content[:comment_end] + '\n' + DEBUG_SYSTEM + '\n' + content[comment_end:]
        else:
            new_content = DEBUG_SYSTEM + '\n' + content
    
    return new_content, True

def replace_console_calls(content):
    """Replace console.log/warn/info with debug wrapper calls"""
    
    original = content
    
    # Replace console.log with debug.log
    content = re.sub(r'\bconsole\.log\(', 'debug.log(', content)
    
    # Replace console.warn with debug.warn
    content = re.sub(r'\bconsole\.warn\(', 'debug.warn(', content)
    
    # Replace console.info with debug.info
    content = re.sub(r'\bconsole\.info\(', 'debug.info(', content)
    
    # Replace console.group with debug.group
    content = re.sub(r'\bconsole\.group\(', 'debug.group(', content)
    
    # Replace console.groupEnd with debug.groupEnd
    content = re.sub(r'\bconsole\.groupEnd\(\)', 'debug.groupEnd()', content)
    
    # Replace console.table with debug.table
    content = re.sub(r'\bconsole\.table\(', 'debug.table(', content)
    
    return content, content != original

def process_file(file_path):
    """Process a single JS file"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Step 1: Inject debug system if not present
    content, injected = inject_debug_system(content)
    
    # Step 2: Replace console calls
    content, replaced = replace_console_calls(content)
    
    if content != original:
        # Backup original
        backup_path = file_path.with_suffix('.js.backup')
        if not backup_path.exists():  # Don't overwrite existing backup
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original)
            print(f"   💾 Backup: {backup_path.name}")
        
        # Write modified content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Count results
        log_count = len(re.findall(r'debug\.log\(', content))
        warn_count = len(re.findall(r'debug\.warn\(', content))
        info_count = len(re.findall(r'debug\.info\(', content))
        error_count = len(re.findall(r'console\.error\(', content))
        
        print(f"✅ {file_path.name}")
        if injected:
            print(f"   ➕ Debug system injected")
        if replaced:
            print(f"   📊 debug.log: {log_count}, debug.warn: {warn_count}, debug.info: {info_count}")
            print(f"   📊 console.error: {error_count} (unchanged)")
        
        return True
    else:
        print(f"ℹ️  {file_path.name} - No changes needed")
        return False

if __name__ == '__main__':
    base_path = Path(__file__).parent / 'src' / 'static' / 'js'
    
    # Files to process
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
    
    print("🔄 Processing JS files with debug logging system...\n")
    
    modified_count = 0
    for file_path in files:
        if file_path.exists():
            if process_file(file_path):
                modified_count += 1
            print()
        else:
            print(f"⚠️  {file_path.name} - File not found\n")
    
    print(f"✅ Done! Modified {modified_count} file(s)")
