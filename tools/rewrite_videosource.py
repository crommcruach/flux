"""Replace VideoSource class in sources.py with clean .npy-only implementation."""
import os

src_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modules', 'player', 'sources.py')
src_path = os.path.normpath(src_path)

with open(src_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find exact line indices (0-based)
vs_start = next(i for i, l in enumerate(lines) if 'class VideoSource(FrameSource):' in l)
gs_start = next(i for i, l in enumerate(lines) if 'class GeneratorSource(FrameSource):' in l)

print(f"VideoSource: lines {vs_start+1}-{gs_start} → replacing with clean .npy implementation")

new_class = '''\
class VideoSource(FrameSource):
    """Video file as frame source via memory-mapped .npy arrays."""

    def __init__(self, video_path, canvas_width, canvas_height, config=None, clip_id=None, player_name='video'):
        super().__init__(canvas_width, canvas_height, config)
        self.video_path = self._find_best_resolution(video_path)
        self.source_path = self.video_path
        self.source_type = 'video'
        self.clip_id = clip_id
        self.player_name = player_name
        self.frames = None  # np.memmap loaded in initialize()

    def _find_best_resolution(self, path: str) -> str:
        """Resolve clip folder to the best-matching .npy file."""
        if not os.path.isdir(path):
            return path

        from ..content.converter import ALL_PRESETS, get_target_preset
        target = get_target_preset(self.canvas_width, self.canvas_height)
        start_idx = ALL_PRESETS.index(target)
        ordered = ALL_PRESETS[start_idx:] + ALL_PRESETS[:start_idx][::-1]

        for preset in ordered:
            candidate = os.path.join(path, f"{preset}.npy")
            if os.path.exists(candidate):
                logger.debug(f"[NpySource] {os.path.basename(path)} -> {preset}.npy")
                return candidate

        logger.error(f"[NpySource] No .npy found in clip folder: {path}")
        return path

    def initialize(self):
        if self.frames is not None:
            return True

        if not os.path.exists(self.video_path):
            logger.error(f"[NpySource] File not found: {self.video_path}")
            return False

        try:
            self.frames = np.load(self.video_path, mmap_mode='r')
            self.total_frames = self.frames.shape[0]

            meta_path = self.video_path[:-4] + '.json'
            if os.path.exists(meta_path):
                import json as _json
                with open(meta_path) as f:
                    meta = _json.load(f)
                self.fps = float(meta.get('fps', DEFAULT_FPS))
            else:
                self.fps = DEFAULT_FPS

            if self.clip_id:
                from .clips.registry import get_clip_registry
                clip = get_clip_registry().get_clip(self.clip_id)
                if clip:
                    clip['total_frames'] = self.total_frames

            logger.info(
                f"[NpySource] {os.path.basename(self.video_path)} "
                f"{self.total_frames} frames @ {self.fps:.1f}fps"
            )
            return True
        except Exception as e:
            logger.error(f"[NpySource] Failed to load {self.video_path}: {e}")
            return False

    def get_next_frame(self):
        if self.frames is None or self.current_frame >= self.total_frames:
            return None, 0
        frame = self.frames[self.current_frame].copy()
        self.current_frame += 1
        return frame, 1.0 / self.fps

    def reset(self):
        self.current_frame = 0

    def cleanup(self):
        self.frames = None

    def get_source_name(self):
        return os.path.basename(self.video_path) if self.video_path else "Unknown"


'''

result = lines[:vs_start] + [new_class] + lines[gs_start:]

with open(src_path, 'w', encoding='utf-8') as f:
    f.writelines(result)

# Verify
with open(src_path, 'r', encoding='utf-8') as f:
    content = f.read()

vs_start_c = content.index('class VideoSource')
gs_start_c = content.index('class GeneratorSource')
cls = content[vs_start_c:gs_start_c]

checks = {
    'self.cap removed': 'self.cap' not in cls,
    'self.gif removed': 'self.gif' not in cls,
    'VideoCapture removed': 'VideoCapture' not in cls,
    'threading removed': 'threading.Lock' not in cls,
    'self.frames present': 'self.frames' in cls,
    'single get_next_frame': cls.count('def get_next_frame') == 1,
    'single initialize': cls.count('def initialize') == 1,
}

all_ok = all(checks.values())
for k, v in checks.items():
    status = 'OK' if v else 'FAIL'
    print(f"  [{status}] {k}")

print()
print("RESULT:", "CLEAN" if all_ok else "FAIL")
