"""
AMD Readback Optimization Test — OGL 4.6 + GL_ARB_buffer_storage
=================================================================
Tests whether OGL 4.6 + persistent mapped PBOs + glGetTexImage provides
true async GPU→CPU readback on this AMD driver.

The critical insight from test_amd_readback_opt.py:
- glReadPixels is BROKEN (returns zeros) regardless of FBO format
- glGetTexImage (via texture.read()) WORKS but takes ~60ms at 1080p
- When GL_PIXEL_PACK_BUFFER is bound, glGetTexImage writes INTO the PBO
  instead of to CPU memory — this is a DIFFERENT code path from glReadPixels

Strategy: OGL 4.6 + glBufferStorage (persistent) + glGetTexImage via PBO
  Frame N:   glGetTexImage → PBO  (async DMA, GPU→PBO)
  Frame N+1: fence sync + read PBO  (zero stall if GPU finished)

If this works: layer_composition readback drops from ~60ms to ~1ms in steady state.

Run:
    python tests/gpu/test_amd_readback_pbo.py
"""

import ctypes
import sys
import time
import numpy as np

# Require PyOpenGL for raw GL calls
try:
    import OpenGL.GL as gl
    from OpenGL.GL import glGetTexImage, glBindBuffer, glGenBuffers, glDeleteBuffers
    from OpenGL.GL import glBufferStorage, glMapBufferRange, glUnmapBuffer
    from OpenGL.GL import glFenceSync, glClientWaitSync, glDeleteSync
    from OpenGL.GL import GL_PIXEL_PACK_BUFFER, GL_UNSIGNED_BYTE, GL_FLOAT
    from OpenGL.GL import GL_MAP_READ_BIT, GL_MAP_PERSISTENT_BIT, GL_MAP_COHERENT_BIT
    from OpenGL.GL import GL_SYNC_GPU_COMMANDS_COMPLETE, GL_SYNC_FLUSH_COMMANDS_BIT
    from OpenGL.GL import GL_ALREADY_SIGNALED, GL_CONDITION_SATISFIED, GL_TIMEOUT_EXPIRED
    from OpenGL.GL import GL_TEXTURE_2D, GL_RGB, GL_RGBA
    PYOPENGL = True
except ImportError:
    PYOPENGL = False
    print("PyOpenGL not found — install with: pip install PyOpenGL")
    sys.exit(1)


def _make_test_frame(w, h):
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:, :, 2] = np.linspace(0, 255, w, dtype=np.uint8)
    frame[:, :, 1] = np.linspace(0, 255, h, dtype=np.uint8).reshape(h, 1)
    frame[:, :, 0] = 128
    return frame


def _timeit(fn, rounds=10, warmup=3):
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    return float(np.mean(times)), float(np.min(times)), float(np.max(times))


def run_test(width=1920, height=1080):
    import moderngl

    # ── Create OGL 4.6 context (driver supports it) ─────────────────────────
    try:
        ctx = moderngl.create_standalone_context(require=460)
        print(f"[ctx] OpenGL {ctx.version_code//100}.{(ctx.version_code%100)//10}")
    except Exception as e:
        print(f"[ctx] Failed to get OGL 4.6: {e} — falling back to default")
        ctx = moderngl.create_standalone_context()

    has_buf_storage = 'GL_ARB_buffer_storage' in ctx.extensions
    print(f"[ctx] GL_ARB_buffer_storage: {'✅' if has_buf_storage else '❌'}")

    # ── Float32 texture (keep working path) ─────────────────────────────────
    f32_tex = ctx.texture((width, height), 3, dtype='f4')
    frame = _make_test_frame(width, height)
    upload_buf = np.empty((height, width, 3), dtype=np.float32)
    np.multiply(frame[:, :, ::-1], 1.0 / 255.0, out=upload_buf)
    f32_tex.write(upload_buf.tobytes())

    tex_id = f32_tex.glo   # native GL texture ID

    # ── A) Baseline: texture.read() (current path) ──────────────────────────
    def baseline():
        raw = f32_tex.read()
        arr = np.frombuffer(raw, dtype=np.float32).reshape(height, width, 3)
        return (arr * 255).astype(np.uint8)

    mean_a, min_a, max_a = _timeit(baseline)
    print(f"\n[A] Baseline texture.read() float32:  mean={mean_a:.1f}ms  min={min_a:.1f}ms  max={max_a:.1f}ms")

    # ── B) PBO + glGetTexImage (single buffer, synchronous check) ────────────
    # First test: does glGetTexImage→PBO return correct data at all?
    nbytes_f32 = width * height * 3 * 4   # float32, RGB
    pbo = (ctypes.c_uint * 1)()
    glGenBuffers(1, pbo)
    pbo_id = pbo[0]

    glBindBuffer(GL_PIXEL_PACK_BUFFER, pbo_id)
    gl.glBufferData(GL_PIXEL_PACK_BUFFER, nbytes_f32, None, gl.GL_STREAM_READ)

    # Trigger transfer
    gl.glBindTexture(GL_TEXTURE_2D, tex_id)
    glGetTexImage(GL_TEXTURE_2D, 0, GL_RGB, GL_FLOAT, ctypes.c_void_p(0))  # NULL → write to pbo

    # Sync: wait for DMA to complete (synchronous check)
    gl.glFinish()

    # Map and read back
    ptr = glMapBufferRange(GL_PIXEL_PACK_BUFFER, 0, nbytes_f32, GL_MAP_READ_BIT)
    if ptr:
        arr = np.frombuffer((ctypes.c_float * (nbytes_f32 // 4)).from_address(ptr), dtype=np.float32).copy()
        glUnmapBuffer(GL_PIXEL_PACK_BUFFER)
        glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)

        if arr.max() < 0.001:
            print("[B] ❌ PBO+glGetTexImage: map returned all zeros — path broken on this driver")
            # Clean up and report
            glDeleteBuffers(1, pbo)
            ctx.release()
            return
        else:
            result_bgr = arr.reshape(height, width, 3)[::-1, :, ::-1]
            result_u8  = (result_bgr * 255).clip(0, 255).astype(np.uint8)
            diff = np.abs(result_u8.astype(np.int32) - frame.astype(np.int32))
            print(f"[B] PBO+glGetTexImage correctness: max_diff={diff.max()}  mean_diff={diff.mean():.2f}")
            if diff.max() <= 2:
                print("[B] ✅ Data correct — PBO path works!")
            else:
                print("[B] ⚠️  Large pixel diff — check conversion")
    else:
        print("[B] ❌ glMapBufferRange returned NULL")
        glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)
        glDeleteBuffers(1, pbo)
        ctx.release()
        return

    glDeleteBuffers(1, pbo)

    # ── C) Persistent mapped PBO (GL_ARB_buffer_storage) ────────────────────
    if not has_buf_storage:
        print("[C] GL_ARB_buffer_storage not available, skipping persistent PBO test")
        ctx.release()
        return

    persist_pbo = (ctypes.c_uint * 1)()
    glGenBuffers(1, persist_pbo)
    persist_id = persist_pbo[0]

    flags = GL_MAP_READ_BIT | GL_MAP_PERSISTENT_BIT | GL_MAP_COHERENT_BIT

    glBindBuffer(GL_PIXEL_PACK_BUFFER, persist_id)
    glBufferStorage(GL_PIXEL_PACK_BUFFER, nbytes_f32, None, flags)
    mapped_ptr = glMapBufferRange(GL_PIXEL_PACK_BUFFER, 0, nbytes_f32, flags)

    if not mapped_ptr:
        print("[C] ❌ glMapBufferRange (persistent) returned NULL")
        glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)
        glDeleteBuffers(1, persist_pbo)
        ctx.release()
        return

    print("[C] ✅ Persistent PBO mapped successfully")

    # Create numpy view directly on the mapped GPU memory (zero-copy)
    mapped_arr = np.frombuffer(
        (ctypes.c_float * (nbytes_f32 // 4)).from_address(mapped_ptr),
        dtype=np.float32
    )

    # ── Double-buffer async scheme ──────────────────────────────────────────
    # Frame N:   glGetTexImage → PBO (async DMA initiated, CPU continues)
    # Frame N+1: wait on fence + read mapped pointer (near-zero stall if done)

    fence = None

    def initiate_async_readback():
        nonlocal fence
        # Invalidate previous fence
        if fence is not None:
            glDeleteSync(fence)
        gl.glBindTexture(GL_TEXTURE_2D, tex_id)
        glGetTexImage(GL_TEXTURE_2D, 0, GL_RGB, GL_FLOAT, ctypes.c_void_p(0))
        fence = glFenceSync(GL_SYNC_GPU_COMMANDS_COMPLETE, 0)

    def wait_and_read():
        if fence is None:
            return None
        # Wait at most 0.5s for GPU to finish
        result = glClientWaitSync(fence, GL_SYNC_FLUSH_COMMANDS_BIT, 500_000_000)
        if result in (GL_ALREADY_SIGNALED, GL_CONDITION_SATISFIED):
            arr = mapped_arr.reshape(height, width, 3)[::-1, :, ::-1].copy()
            return (arr * 255).clip(0, 255).astype(np.uint8)
        return None  # timeout

    # Warm up — initiate then immediately wait (still synchronous, just testing path)
    initiate_async_readback()
    result_c = wait_and_read()

    if result_c is None:
        print("[C] ❌ Fence sync timed out — persistent PBO path broken")
    else:
        diff_c = np.abs(result_c.astype(np.int32) - frame.astype(np.int32))
        print(f"[C] Persistent PBO correctness: max_diff={diff_c.max()}  mean_diff={diff_c.mean():.2f}")
        if diff_c.max() <= 2:
            print("[C] ✅ Data correct")
        else:
            print(f"[C] ⚠️  Large pixel diff {diff_c.max()}")

    # Time synchronous mode (initiate + wait in same iteration)
    def full_round_trip():
        initiate_async_readback()
        return wait_and_read()

    mean_c_sync, min_c_sync, _ = _timeit(full_round_trip)
    print(f"\n[C] Persistent PBO synchronous (initiate+wait): mean={mean_c_sync:.1f}ms  min={min_c_sync:.1f}ms")

    # Time async mode (double-buffer: previous frame's data)
    # Initiate N, then read N-1 (data already in PBO from previous call)
    initiate_async_readback()  # prime the pump

    def async_round_trip():
        """Read previous frame's PBO, then initiate next frame's transfer."""
        result = wait_and_read()           # read data from previous initiate
        initiate_async_readback()          # kick off next transfer
        return result

    mean_c_async, min_c_async, _ = _timeit(async_round_trip)
    print(f"[C] Persistent PBO async (double-buffer):       mean={mean_c_async:.1f}ms  min={min_c_async:.1f}ms")

    speedup_sync  = mean_a / mean_c_sync  if mean_c_sync  > 0 else 0
    speedup_async = mean_a / mean_c_async if mean_c_async > 0 else 0
    print(f"\n     Baseline:                {mean_a:.1f}ms")
    print(f"     Persistent PBO (sync):   {mean_c_sync:.1f}ms  ({speedup_sync:.1f}x)")
    print(f"     Persistent PBO (async):  {mean_c_async:.1f}ms  ({speedup_async:.1f}x)")

    glDeleteSync(fence)
    glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)
    glDeleteBuffers(1, persist_pbo)
    ctx.release()


if __name__ == '__main__':
    print("=" * 60)
    print("AMD OGL 4.6 + Persistent PBO Readback Test")
    print("=" * 60)
    print("\n--- 1080p ---")
    run_test(1920, 1080)
    print("\n--- 720p ---")
    run_test(1280, 720)
    print("\nDone.")
