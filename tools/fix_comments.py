"""
Fix missing # in comment lines.
Uses the Python AST parser to find exact error lines,
then applies targeted fixes.
"""
import ast
import re
import sys

filepath = sys.argv[1] if len(sys.argv) > 1 else 'src/modules/api/app.py'

with open(filepath, 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

CODE_STARTERS = [
    r'^(self|from|import|if|elif|else:|else\s*:|for|while|try:|except|finally:|raise|return|yield|pass|break|continue|with|async|await|def|class)\b',
    r'^[a-z_]\w*\s*[=(]',
    r'^[a-z_]\w*\.',
    r'^[a-z_]\w*\[',
    r'^[A-Z][A-Za-z0-9_]*\(',
    r'^[A-Z][A-Za-z0-9_]*\[',
    r'^["' + "'" + r'({[\-@_\*!~]',
    r'^#',
    r'^[0-9]',
    r'^(True|False|None)\b',
    r'^"""',
    r"^'''",
    r'^\)',
    r'^\]',
    r'^\}',
]

def is_code(content):
    return any(re.match(p, content) for p in CODE_STARTERS)

for iteration in range(200):
    full_code = ''.join(lines)
    try:
        ast.parse(full_code)
        print(f"OK after {iteration} fixes.")
        break
    except SyntaxError as e:
        lineno = e.lineno
        if not lineno or lineno > len(lines):
            print(f"Cannot fix: {e}")
            sys.exit(1)
        bad_line = lines[lineno - 1]
        stripped = bad_line.rstrip('\n\r')
        content = stripped.lstrip()
        indent = len(stripped) - len(content)
        if not content:
            print(f"Blank line {lineno} error - stopping")
            sys.exit(1)
        print(f"  [{lineno}] {stripped!r}")
        m = re.match(r'^(\s*\S.*\S|\s*\S)\s{3,}(\S[^\n\r]*)$', stripped) if is_code(content) else None
        if m and not m.group(2).startswith('#'):
            lines[lineno - 1] = m.group(1) + '    # ' + m.group(2) + '\n'
            print(f"       -> inline comment")
        else:
            new_indent = max(0, indent - 2)
            lines[lineno - 1] = ' ' * new_indent + '# ' + content + '\n'
            print(f"       -> standalone comment")
else:
    print("Still errors after 200 iterations")
    sys.exit(1)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print(f"Saved: {filepath}")
