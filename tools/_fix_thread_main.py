"""Patch _thread_main in glfw_display.py to use anchor-based context sharing."""
import os, sys

os.chdir(os.path.join(os.path.dirname(__file__), '..'))

content = open('src/modules/gpu/glfw_display.py', encoding='utf-8').read()
old_start = content.find('    def _thread_main')
marker = 'glfw.swap_interval(0)  # no vsync'
old_end_idx = content.find(marker, old_start)
old_end = content.find('\n', old_end_idx) + 1

if old_start == -1 or old_end_idx == -1:
    print('ERROR: markers not found')
    sys.exit(1)

new_block = '''\
    def _thread_main(self):
        window = None
        try:
            # _ensure_anchor() was called by get_context() on the render thread.
            # If the anchor window exists, pass it as 'share' to create_window()
            # so GLFW uses wglCreateContextAttribsARB(hdc, anchor_hglrc, attribs)
            # internally.  Creation-time sharing has no non-current precondition
            # and avoids the AMD post-wglShareLists HDC invalidation (0x7D0) bug.
            anchor = _anchor_win
            gpu_capable = anchor is not None and _PYOPENGL_AVAILABLE

            if not glfw.init():
                logger.error("GLFWDisplay: glfw.init() failed")
                return

            # GL 4.3 core required for compute shaders (GPU upload path).
            # Display shader only needs 3.3 but CPUuploader uses #version 430.
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
            glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
            glfw.window_hint(glfw.DOUBLEBUFFER, True)
            glfw.window_hint(glfw.VISIBLE, True)

            monitor = None
            w, h = self.width, self.height
            if self.fullscreen:
                monitors = glfw.get_monitors()
                if self.monitor_index < len(monitors):
                    monitor = monitors[self.monitor_index]
                    mode = glfw.get_video_mode(monitor)
                    w, h = mode.size.width, mode.size.height

            # Pass anchor as 'share' -- no wglShareLists needed.
            window = glfw.create_window(w, h, self.title, monitor, anchor)
            if not window:
                logger.error("GLFWDisplay: glfw.create_window() failed")
                return

            glfw.make_context_current(window)
            glfw.swap_interval(0)  # no vsync -- render thread controls pacing
'''

new_content = content[:old_start] + new_block + '\n' + content[old_end:]
open('src/modules/gpu/glfw_display.py', 'w', encoding='utf-8').write(new_content)
print(f'Patched: replaced {old_end - old_start} chars at pos {old_start}')
