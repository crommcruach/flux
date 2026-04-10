path = r"c:\Users\cromm\OneDrive\Dokumente\Py_artnet\src\modules\gpu\glfw_display.py"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

# ── Step 1: fix method header to import get_main_hdc ────────────────────────
old1 = '        try:\n            from .context import get_main_hglrc\n            main_hglrc = get_main_hglrc()\n            if not main_hglrc:\n                logger.info("GLFWDisplay: main HGLRC not available yet'

new1 = '        try:\n            from .context import get_main_hglrc, get_main_hdc\n            main_hglrc = get_main_hglrc()\n            main_hdc   = get_main_hdc()\n            if not main_hglrc:\n                logger.info("GLFWDisplay: main HGLRC not available yet'

if old1 in src:
    src = src.replace(old1, new1, 1)
    print("OK step 1: added get_main_hdc import + assignment")
else:
    print("FAIL step 1")
    lines = src.splitlines()
    for i, l in enumerate(lines[249:270], 250):
        print(f"  {i}: {repr(l)}")

# ── Step 2: add release/restore around wglShareLists ────────────────────────
old2 = '            result = ctypes.windll.opengl32.wglShareLists(main_hglrc, glfw_hglrc)\n            if result:'

new2 = (
    '            # wglShareLists requires BOTH contexts non-current on ALL threads.\n'
    '            # Release the main context temporarily on this thread, call\n'
    '            # wglShareLists, then restore it. The GLFW thread released its\n'
    '            # context in _thread_main() before posting the handshake request.\n'
    '            released_main = False\n'
    '            if main_hdc:\n'
    '                released_main = bool(\n'
    '                    ctypes.windll.opengl32.wglMakeCurrent(main_hdc, None)\n'
    '                )\n'
    '                if not released_main:\n'
    '                    err_rel = ctypes.windll.kernel32.GetLastError()\n'
    '                    logger.warning(\n'
    '                        "GLFWDisplay: could not release main context before "\n'
    '                        f"wglShareLists (GetLastError={err_rel:#x}) \u2014 trying anyway"\n'
    '                    )\n'
    '\n'
    '            result = ctypes.windll.opengl32.wglShareLists(main_hglrc, glfw_hglrc)\n'
    '\n'
    '            # Restore main context on this thread regardless of outcome\n'
    '            if released_main and main_hdc:\n'
    '                ctypes.windll.opengl32.wglMakeCurrent(main_hdc, main_hglrc)\n'
    '\n'
    '            if result:'
)

if old2 in src:
    src = src.replace(old2, new2, 1)
    print("OK step 2: added release/restore around wglShareLists")
else:
    print("FAIL step 2")
    lines = src.splitlines()
    for i, l in enumerate(lines[264:285], 265):
        print(f"  {i}: {repr(l)}")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("File written.")

import py_compile, sys
try:
    py_compile.compile(path, doraise=True)
    print("Syntax OK")
except py_compile.PyCompileError as e:
    print(f"Syntax ERROR: {e}")
    sys.exit(1)
