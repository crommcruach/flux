"""Check all plugins (effects, generators, transitions) for GPU vs CPU"""
import os, re

categories = {
    'effects':     'plugins/effects',
    'generators':  'plugins/generators',
    'transitions': 'plugins/transitions',
}

for cat, plugin_dir in categories.items():
    files = [f for f in sorted(os.listdir(plugin_dir)) 
             if f.endswith('.py') and f != '__init__.py']
    if not files:
        print(f'\n{cat.upper()}: (empty)')
        continue
    
    print(f'\n{cat.upper()}:')
    print(f'  {"File":<28} {"get_shader":<12} {"WGSL":<8} {"ret_None":<10} Status')
    print(f'  {"-"*65}')
    
    cpu_files = []
    for fname in files:
        path = os.path.join(plugin_dir, fname)
        content = open(path, encoding='utf-8').read()
        has_get_shader = 'def get_shader' in content
        returns_none   = bool(re.search(r'def get_shader[^:]*:[^}]*?return\s+None', content, re.DOTALL))
        has_wgsl       = '@fragment' in content or '@vertex' in content
        
        if has_get_shader and has_wgsl and not returns_none:
            status = 'GPU'
        elif not has_get_shader:
            status = 'NO_SHADER'
        else:
            status = 'CPU_FALLBACK'
        
        print(f'  [{status:<12}] {fname:<25} {str(has_get_shader):<12} {str(has_wgsl):<8} {str(returns_none)}')
        if status != 'GPU':
            cpu_files.append(fname)
    
    if cpu_files:
        print(f'\n  -> Would archive: {cpu_files}')
    else:
        print(f'\n  -> All GPU, nothing to archive.')
