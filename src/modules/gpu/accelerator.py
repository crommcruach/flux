"""
GPU Accelerator stub — CPU-only fallback for Phase 1.

The original OpenCL UMat accelerator was archived to archive/legacy_cpu_pipeline_phase1.py.
Effect plugins (blur, transform, distortion, ...) still call get_gpu_accelerator() during
Phase 1. They will be migrated to GLSL shaders in Phase 2 at which point this stub and
all call sites are removed.

All operations delegate directly to CPU OpenCV — no OpenCL, no UMat.
"""
import cv2


class _CPUAccelerator:
    enabled = False   # plugins guard GPU paths with `if self.gpu.enabled:`
    backend = "CPU"   # main.py startup log reads _gpu.backend

    def resize(self, frame, size, interpolation=cv2.INTER_LINEAR):
        return cv2.resize(frame, size, interpolation=interpolation)

    def warpAffine(self, frame, M, size, flags=cv2.INTER_LINEAR,
                   borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0)):
        return cv2.warpAffine(frame, M, size, flags=flags,
                              borderMode=borderMode, borderValue=borderValue)

    def warpPerspective(self, frame, M, size, flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0)):
        return cv2.warpPerspective(frame, M, size, flags=flags,
                                   borderMode=borderMode, borderValue=borderValue)

    def gaussian_blur(self, frame, ksize, sigma=0):
        k = (ksize, ksize) if ksize > 0 else (0, 0)
        return cv2.GaussianBlur(frame, k, sigma)

    def remap(self, frame, map_x, map_y,
              interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT):
        return cv2.remap(frame, map_x, map_y, interpolation, borderMode=borderMode)


_instance = _CPUAccelerator()


def get_gpu_accelerator(_config=None):
    return _instance
