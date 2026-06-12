"""
Tests for HAP video source reimplementation.

Covers:
  1. VideoConverter produces correct .hap + sidecar .json
  2. VideoSource initializes from .hap (metadata, buffer shape)
  3. get_next_frame() returns a memoryview with ZERO heap allocation
  4. retrim() adjusts frame window correctly
  5. _find_best_resolution() selects the closest preset from a clip folder
  6. HapTexturePool acquire / release lifecycle (no real GPU needed)

Run with:
    python -m pytest tests/test_hap_video_source.py -v
"""

import json
import os
import struct
import tempfile
import tracemalloc
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Helpers — build a minimal .hap file without a real video
# ---------------------------------------------------------------------------

def _make_hapnpy(tmp_dir: Path, preset: str = '720p',
                 dxt_variant: str = 'bc1',
                 frame_count: int = 30,
                 fps: float = 30.0):
    """Write a synthetic .hap + sidecar JSON into tmp_dir/preset.{hap,json}."""
    width, height = 1280, 720  # 720p
    bpb = 8 if dxt_variant == 'bc1' else 16  # bytes per 4×4 block
    frame_bytes = (width // 4) * (height // 4) * bpb

    flat = np.zeros(frame_count * frame_bytes, dtype=np.uint8)
    # Write recognisable sentinel into each frame to validate seek
    for i in range(frame_count):
        flat[i * frame_bytes] = i % 256

    hap_path = tmp_dir / f"{preset}.hap"
    flat.tofile(str(hap_path))

    meta = {
        'fps': fps,
        'frame_count': frame_count,
        'width': width,
        'height': height,
        'format': 'hap_npy',
        'dxt_variant': dxt_variant,
        'frame_bytes': frame_bytes,
        'preset': preset,
    }
    json_path = tmp_dir / f"{preset}.json"
    json_path.write_text(json.dumps(meta))

    return str(hap_path), meta


# ---------------------------------------------------------------------------
# 1. Converter unit tests (no cv2 — we mock frame reading)
# ---------------------------------------------------------------------------

class TestVideoConverter:
    """Test VideoConverter core logic without a real video file."""

    def test_align4(self):
        from src.modules.content.converter import _align4
        assert _align4(0) == 0
        assert _align4(1) == 4
        assert _align4(4) == 4
        assert _align4(5) == 8
        assert _align4(1920) == 1920
        assert _align4(1921) == 1924

    def test_get_target_preset_exact(self):
        from src.modules.content.converter import get_target_preset
        assert get_target_preset(1280, 720) == '720p'
        assert get_target_preset(1920, 1080) == '1080p'
        assert get_target_preset(3840, 2160) == '2160p'

    def test_get_target_preset_upgrade(self):
        from src.modules.content.converter import get_target_preset
        # A 960×540 canvas should pick '720p' (first preset that covers it)
        assert get_target_preset(960, 540) == '720p'

    def test_converter_resolution_presets_exist(self):
        from src.modules.content.converter import RESOLUTION_PRESETS, ALL_PRESETS
        assert len(ALL_PRESETS) == 4
        for p in ALL_PRESETS:
            assert p in RESOLUTION_PRESETS
            w, h = RESOLUTION_PRESETS[p]
            assert w % 4 == 0 and h % 4 == 0, f"{p} dims not multiples of 4"

    def test_hap_convert_preset_bc1(self):
        """Full encode of a synthetic 8-frame 64×64 video using imagecodecs bc1_encode."""
        imagecodecs = pytest.importorskip('imagecodecs',
            reason='imagecodecs not installed — skip integration test')
        cv2 = pytest.importorskip('cv2',
            reason='opencv not installed — skip integration test')

        from src.modules.content.converter import VideoConverter, RESOLUTION_PRESETS
        vc = VideoConverter()

        with tempfile.TemporaryDirectory() as tmp:
            clip_folder = Path(tmp) / 'test_clip'
            clip_folder.mkdir()
            src_video = str(clip_folder / 'original.mov')

            # Create a tiny synthetic video with OpenCV
            width, height = 64, 64
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            vw = cv2.VideoWriter(src_video, fourcc, 10.0, (width, height))
            for _ in range(8):
                frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
                vw.write(frame)
            vw.release()

            # Patch RESOLUTION_PRESETS to use our tiny resolution
            custom_res = [{'name': 'test', 'width': 64, 'height': 64}]
            result = vc._hap_convert_preset(
                src_video,
                str(clip_folder),
                preset='test',
                dxt_variant='bc1',
                custom_resolution=(64, 64),
            )

            assert result.success, f"Conversion failed: {result.error}"
            hap_file = clip_folder / 'test.hap'
            sidecar = clip_folder / 'test.json'
            assert hap_file.exists(), "Missing .hap"
            assert sidecar.exists(), "Missing sidecar JSON"

            meta = json.loads(sidecar.read_text())
            assert meta['dxt_variant'] == 'bc1'
            assert meta['frame_count'] == 8
            assert meta['width'] == 64
            assert meta['height'] == 64
            expected_fbs = (64 // 4) * (64 // 4) * 8  # BC1: 8 bytes/block
            assert meta['frame_bytes'] == expected_fbs
            assert hap_file.stat().st_size == 8 * expected_fbs


# ---------------------------------------------------------------------------
# 2. VideoSource unit tests
# ---------------------------------------------------------------------------

class TestVideoSource:
    """Test VideoSource with synthetic .hap files (no GPU, no cv2)."""

    @pytest.fixture()
    def clip_dir(self, tmp_path):
        """Temporary clip folder with a 720p BC1 .hap + JSON."""
        return tmp_path

    @pytest.fixture()
    def hapnpy_path(self, clip_dir):
        path, _ = _make_hapnpy(clip_dir, preset='720p', dxt_variant='bc1',
                               frame_count=30, fps=25.0)
        return path

    # ------------------------------------------------------------------
    # Patch out registry import so tests don't need a full application
    # ------------------------------------------------------------------

    def _make_source(self, path, canvas_w=1280, canvas_h=720):
        with patch('src.modules.player.sources.video.get_clip_registry',
                   side_effect=ImportError('no registry in test')):
            from src.modules.player.sources.video import VideoSource
            src = VideoSource(path, canvas_w, canvas_h, clip_id=None)
        return src

    # ------------------------------------------------------------------

    def test_initialize_metadata(self, hapnpy_path):
        from src.modules.player.sources.video import VideoSource

        src = VideoSource.__new__(VideoSource)
        src.canvas_width, src.canvas_height = 1280, 720
        src.buffer = None
        src._mmap_ref = None
        src._trim_start = 0
        src.clip_id = None
        src._EAGER_LOAD_THRESHOLD_BYTES = 512 * 1024 * 1024
        src.video_path = hapnpy_path
        src.source_path = hapnpy_path
        src.source_type = 'video'
        src.player_name = 'test'
        src.config = {}
        src._frame_idx = 0
        src.fps = 25.0
        src.total_frames = 0
        src.width = 0
        src.height = 0
        src.dxt_variant = 'bc1'
        src.frame_bytes = 0

        ok = src.initialize()
        assert ok, "initialize() should return True"
        assert src.width == 1280
        assert src.height == 720
        assert src.fps == 25.0
        assert src.total_frames == 30
        assert src.dxt_variant == 'bc1'
        assert src.frame_bytes == (1280 // 4) * (720 // 4) * 8
        assert src.buffer is not None

    def test_get_next_frame_returns_memoryview(self, hapnpy_path):
        from src.modules.player.sources.video import VideoSource

        src = VideoSource.__new__(VideoSource)
        src.canvas_width, src.canvas_height = 1280, 720
        src.buffer = None
        src._mmap_ref = None
        src._trim_start = 0
        src.clip_id = None
        src._EAGER_LOAD_THRESHOLD_BYTES = 512 * 1024 * 1024
        src.video_path = hapnpy_path
        src.source_path = hapnpy_path
        src.source_type = 'video'
        src.player_name = 'test'
        src.config = {}
        src._frame_idx = 0
        src.fps = 25.0
        src.total_frames = 0
        src.width = 0
        src.height = 0
        src.dxt_variant = 'bc1'
        src.frame_bytes = 0
        src.current_frame = 0
        src.initialize()

        frame, duration = src.get_next_frame()
        assert isinstance(frame, memoryview), \
            f"Expected memoryview, got {type(frame)}"
        assert duration == pytest.approx(1.0 / src.fps, rel=1e-6)

    def test_get_next_frame_correct_size(self, hapnpy_path):
        from src.modules.player.sources.video import VideoSource

        src = VideoSource.__new__(VideoSource)
        src.canvas_width, src.canvas_height = 1280, 720
        src.buffer = None
        src._mmap_ref = None
        src._trim_start = 0
        src.clip_id = None
        src._EAGER_LOAD_THRESHOLD_BYTES = 512 * 1024 * 1024
        src.video_path = hapnpy_path
        src.source_path = hapnpy_path
        src.source_type = 'video'
        src.player_name = 'test'
        src.config = {}
        src._frame_idx = 0
        src.fps = 25.0
        src.total_frames = 0
        src.width = 0
        src.height = 0
        src.dxt_variant = 'bc1'
        src.frame_bytes = 0
        src.current_frame = 0
        src.initialize()

        expected_bytes = src.frame_bytes
        frame, _ = src.get_next_frame()
        assert len(frame) == expected_bytes, \
            f"Frame size mismatch: {len(frame)} != {expected_bytes}"

    def test_zero_copy_no_heap_allocation(self, hapnpy_path):
        """get_next_frame() must not allocate significant heap memory."""
        from src.modules.player.sources.video import VideoSource

        src = VideoSource.__new__(VideoSource)
        src.canvas_width, src.canvas_height = 1280, 720
        src.buffer = None
        src._mmap_ref = None
        src._trim_start = 0
        src.clip_id = None
        src._EAGER_LOAD_THRESHOLD_BYTES = 512 * 1024 * 1024
        src.video_path = hapnpy_path
        src.source_path = hapnpy_path
        src.source_type = 'video'
        src.player_name = 'test'
        src.config = {}
        src._frame_idx = 0
        src.fps = 25.0
        src.total_frames = 0
        src.width = 0
        src.height = 0
        src.dxt_variant = 'bc1'
        src.frame_bytes = 0
        src.current_frame = 0
        src.initialize()

        # Warm the buffer (OS page faults should not count against us)
        _ = src.get_next_frame()

        tracemalloc.start()
        tracemalloc.clear_traces()
        frame, _ = src.get_next_frame()
        snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        total_alloc = sum(s.size for s in snapshot.statistics('lineno'))
        assert total_alloc < 4096, \
            f"get_next_frame() allocated {total_alloc} bytes — expected <4096 (zero-copy violated)"

    def test_sentinel_per_frame(self, hapnpy_path, clip_dir):
        """Each frame starts with its index % 256 (from synthetic data)."""
        from src.modules.player.sources.video import VideoSource

        src = VideoSource.__new__(VideoSource)
        src.canvas_width, src.canvas_height = 1280, 720
        src.buffer = None
        src._mmap_ref = None
        src._trim_start = 0
        src.clip_id = None
        src._EAGER_LOAD_THRESHOLD_BYTES = 512 * 1024 * 1024
        src.video_path = hapnpy_path
        src.source_path = hapnpy_path
        src.source_type = 'video'
        src.player_name = 'test'
        src.config = {}
        src._frame_idx = 0
        src.fps = 25.0
        src.total_frames = 0
        src.width = 0
        src.height = 0
        src.dxt_variant = 'bc1'
        src.frame_bytes = 0
        src.current_frame = 0
        src.initialize()

        for expected_idx in range(min(10, src.total_frames)):
            frame, _ = src.get_next_frame()
            first_byte = bytes(frame)[0]
            assert first_byte == expected_idx % 256, \
                f"Frame {expected_idx}: first byte={first_byte}, expected={expected_idx % 256}"

    def test_retrim(self, hapnpy_path):
        """retrim() restricts playback to the specified frame window."""
        from src.modules.player.sources.video import VideoSource

        src = VideoSource.__new__(VideoSource)
        src.canvas_width, src.canvas_height = 1280, 720
        src.buffer = None
        src._mmap_ref = None
        src._trim_start = 0
        src.clip_id = None
        src._EAGER_LOAD_THRESHOLD_BYTES = 512 * 1024 * 1024
        src.video_path = hapnpy_path
        src.source_path = hapnpy_path
        src.source_type = 'video'
        src.player_name = 'test'
        src.config = {}
        src._frame_idx = 0
        src.fps = 25.0
        src.total_frames = 0
        src.width = 0
        src.height = 0
        src.dxt_variant = 'bc1'
        src.frame_bytes = 0
        src.current_frame = 0
        src.initialize()

        src.retrim(10, 19)  # frames 10..19 → 10 frames in buffer
        src.current_frame = src._trim_start  # replicate reset() behaviour

        # total_frames is intentionally unchanged (slider scale)
        assert src.total_frames == 30, \
            "total_frames must stay at full clip length after retrim()"
        # Buffer shrinks to exactly the trimmed window
        assert len(src.buffer) == 10 * src.frame_bytes, \
            f"Expected {10 * src.frame_bytes} buffer bytes, got {len(src.buffer)}"

        # First frame after retrim should have sentinel of frame 10
        frame, _ = src.get_next_frame()
        assert frame is not None, "get_next_frame() returned None after retrim+reset"
        first_byte = bytes(frame)[0]
        assert first_byte == 10, \
            f"After retrim(10,19): first byte={first_byte}, expected 10"

    def test_find_best_resolution_exact(self, tmp_path):
        """_find_best_resolution picks the matching preset from a clip folder."""
        # Create 720p and 1080p variants
        _make_hapnpy(tmp_path, preset='720p')
        _make_hapnpy(tmp_path, preset='1080p')

        from src.modules.player.sources.video import VideoSource

        src = VideoSource.__new__(VideoSource)
        src.canvas_width, src.canvas_height = 1280, 720

        result = src._find_best_resolution(str(tmp_path))
        assert result.endswith('720p.hap'), \
            f"Expected 720p.hap for 1280x720 canvas, got {result}"

    def test_find_best_resolution_missing(self, tmp_path, caplog):
        """_find_best_resolution logs an error and returns path if no .hapnpy found."""
        import logging
        from src.modules.player.sources.video import VideoSource

        src = VideoSource.__new__(VideoSource)
        src.canvas_width, src.canvas_height = 1280, 720

        with caplog.at_level(logging.ERROR):
            result = src._find_best_resolution(str(tmp_path))

        assert result == str(tmp_path), "Should return original path on failure"
        assert any('No .hap' in r.message for r in caplog.records), \
            "Expected error log about missing .hap"

    def test_initialize_rejects_npy(self, tmp_path):
        """initialize() must fail cleanly when given a .npy file."""
        npy_path = tmp_path / 'test.npy'
        npy_path.write_bytes(b'\x00' * 100)

        from src.modules.player.sources.video import VideoSource

        src = VideoSource.__new__(VideoSource)
        src.canvas_width, src.canvas_height = 1280, 720
        src.buffer = None
        src._mmap_ref = None
        src._trim_start = 0
        src.clip_id = None
        src._EAGER_LOAD_THRESHOLD_BYTES = 512 * 1024 * 1024
        src.video_path = str(npy_path)
        src.source_path = str(npy_path)
        src.source_type = 'video'
        src.player_name = 'test'
        src.config = {}
        src._frame_idx = 0
        src.fps = 25.0
        src.total_frames = 0
        src.width = 0
        src.height = 0
        src.dxt_variant = 'bc1'
        src.frame_bytes = 0

        ok = src.initialize()
        assert not ok, "initialize() must return False for .npy files"


# ---------------------------------------------------------------------------
# 3. HapTexturePool unit tests (mock wgpu)
# ---------------------------------------------------------------------------

class TestHapTexturePool:
    """Test pool acquire/release without a real GPU device."""

    @pytest.fixture(autouse=True)
    def mock_gpu(self, monkeypatch):
        """Replace wgpu.GPUDevice with a mock so tests run without a GPU."""
        mock_device = MagicMock()
        mock_texture = MagicMock()
        mock_texture.create_view.return_value = MagicMock()
        mock_device.create_texture.return_value = mock_texture

        # Patch get_device to return our mock
        monkeypatch.setattr(
            'src.modules.gpu.hap_texture.get_device',
            lambda: mock_device,
        )
        monkeypatch.setattr(
            'src.modules.gpu.hap_texture.wgpu.TextureUsage',
            MagicMock(TEXTURE_BINDING=0x1, COPY_DST=0x2),
        )
        monkeypatch.setattr(
            'src.modules.gpu.hap_texture.wgpu.TextureFormat',
            MagicMock(bc1_rgba_unorm='bc1_rgba_unorm', bc3_rgba_unorm='bc3_rgba_unorm'),
        )

    def test_acquire_returns_hap_texture(self):
        from src.modules.gpu.hap_texture import _reset_hap_pool, get_hap_texture_pool
        _reset_hap_pool()
        pool = get_hap_texture_pool()
        tex = pool.acquire(1280, 720, 'bc1')
        assert tex is not None

    def test_release_and_reacquire(self):
        from src.modules.gpu.hap_texture import _reset_hap_pool, get_hap_texture_pool
        _reset_hap_pool()
        pool = get_hap_texture_pool()

        tex1 = pool.acquire(1280, 720, 'bc1')
        pool.release(tex1)
        tex2 = pool.acquire(1280, 720, 'bc1')
        # Reusing the same object from the pool is preferred
        assert tex2 is tex1, "Pool should reuse released texture"

    def test_different_dims_separate_buckets(self):
        from src.modules.gpu.hap_texture import _reset_hap_pool, get_hap_texture_pool
        _reset_hap_pool()
        pool = get_hap_texture_pool()

        tex_720 = pool.acquire(1280, 720, 'bc1')
        tex_1080 = pool.acquire(1920, 1080, 'bc1')
        assert tex_720 is not tex_1080

    def test_release_all(self):
        from src.modules.gpu.hap_texture import _reset_hap_pool, get_hap_texture_pool
        _reset_hap_pool()
        pool = get_hap_texture_pool()

        _ = pool.acquire(1280, 720, 'bc1')
        pool.release_all()
        # Acquiring again after release_all should succeed
        tex = pool.acquire(1280, 720, 'bc1')
        assert tex is not None

    def test_singleton(self):
        from src.modules.gpu.hap_texture import _reset_hap_pool, get_hap_texture_pool
        _reset_hap_pool()
        pool_a = get_hap_texture_pool()
        pool_b = get_hap_texture_pool()
        assert pool_a is pool_b, "get_hap_texture_pool() must return the same singleton"
