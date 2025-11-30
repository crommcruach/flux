#!/usr/bin/env python3
"""
Replace console.log/warn/info with debug.log/warn/info in player.js
Keeps console.error unchanged (errors should always be shown)
"""

import re
from pathlib import Path

def replace_console_calls(file_path):
    """Replace console.log/warn/info with debug wrapper calls"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
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
    
    # Count replacements
    log_count = len(re.findall(r'debug\.log\(', content))
    warn_count = len(re.findall(r'debug\.warn\(', content))
    info_count = len(re.findall(r'debug\.info\(', content))
    error_count = len(re.findall(r'console\.error\(', content))
    
    if content != original:
        # Backup original
        backup_path = file_path.with_suffix('.js.backup')
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original)
        print(f"✅ Backup created: {backup_path}")
        
        # Write modified content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Replaced console calls in {file_path}")
        print(f"   📊 debug.log: {log_count}")
        print(f"   📊 debug.warn: {warn_count}")
        print(f"   📊 debug.info: {info_count}")
        print(f"   📊 console.error: {error_count} (unchanged)")
    else:
        print(f"ℹ️ No changes needed in {file_path}")

if __name__ == '__main__':
    player_js = Path(__file__).parent / 'src' / 'static' / 'js' / 'player.js'
    
    if not player_js.exists():
        print(f"❌ File not found: {player_js}")
        exit(1)
    
    print(f"🔄 Processing {player_js}...")
    replace_console_calls(player_js)
    print("✅ Done!")
