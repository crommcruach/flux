path = r'c:\Users\cromm\OneDrive\Dokumente\Py_artnet\src\modules\gpu\glfw_display.py'
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

changed = False

# Step 1: rename method signature
old_sig = '    def _try_wgl_share(self, window) -> bool:'
new_sig = '    def _do_wgl_share_main_thread(self, glfw_hglrc: int) -> bool:'
if old_sig in src:
    src = src.replace(old_sig, new_sig, 1)
    print('OK step 1: renamed _try_wgl_share -> _do_wgl_share_main_thread')
    changed = True
else:
    print('FAIL step 1: method def not found')

# Step 2: remove get_wgl_context call (glfw_hglrc is now passed directly)
# There are two possible variants depending on encoding of the em-dash
for old_check in [
    '            glfw_hglrc = glfw.get_wgl_context(window)\n            if not glfw_hglrc:\n                logger.warning("GLFWDisplay: glfw.get_wgl_context() returned 0")\n                return False',
]:
    if old_check in src:
        new_check = '            if not glfw_hglrc:\n                logger.warning("GLFWDisplay: GLFW HGLRC is 0 - cannot share")\n                return False'
        src = src.replace(old_check, new_check, 1)
        print('OK step 2: replaced get_wgl_context block')
        changed = True
        break
else:
    print('NOTE step 2: get_wgl_context block not found or already replaced')

if changed:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(src)
    print('File written.')
else:
    print('No changes made.')

# Verify
import py_compile, sys
try:
    py_compile.compile(path, doraise=True)
    print('Syntax OK')
except py_compile.PyCompileError as e:
    print(f'Syntax ERROR: {e}')
    sys.exit(1)
