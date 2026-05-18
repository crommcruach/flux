"""Check each generator plugin for GPU shader vs CPU implementation"""
import os, re

gen_dir = 'plugins/generators'
results = {}
for fname in sorted(os.listdir(gen_dir)):
    if not fname.endswith('.py') or fname == '__init__.py':
        continue
    content = open(os.path.join(gen_dir, fname), encoding='utf-8').read()
    has_get_shader = 'def get_shader' in content
    # Look for get_shader returning actual WGSL (triple-quote string or var)
    returns_none  = bool(re.search(r'def get_shader[^:]*:.*?return\s+None', content, re.DOTALL))
    # Is there a wgsl string (look for @fragment or @vertex in content)
    has_wgsl      = '@fragment' in content or '@vertex' in content or 'wgsl' in content.lower()
    has_numpy_gen = bool(re.search(r'np\.|numpy', content))
    results[fname] = {
        'has_get_shader': has_get_shader,
        'returns_none':   returns_none,
        'has_wgsl':       has_wgsl,
        'has_numpy':      has_numpy_gen,
    }

print(f'{"File":<25} {"get_shader":<12} {"has_WGSL":<10} {"ret_None":<10} {"numpy"}')
print('-' * 68)
for f, r in results.items():
    gpu = r['has_get_shader'] and r['has_wgsl'] and not r['returns_none']
    tag = "GPU" if gpu else "CPU"
    print(f'[{tag}] {f:<23} {str(r["has_get_shader"]):<12} {str(r["has_wgsl"]):<10} {str(r["returns_none"]):<10} {str(r["has_numpy"])}')
