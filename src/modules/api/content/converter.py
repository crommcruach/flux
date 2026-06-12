"""
REST API for video converter (HAP_NPY format).
"""

from flask import Blueprint, request, jsonify
from ...content.converter import (
    get_converter,
    OutputFormat,
    ALL_PRESETS,
)
import os
import json
from pathlib import Path
import threading


converter_bp = Blueprint('converter', __name__)


def _get_video_dir() -> str:
    """Return the video directory from config.json (paths.video_dir)."""
    try:
        config_path = Path.cwd() / 'config.json'
        with open(config_path) as f:
            cfg = json.load(f)
        video_dir = (
            cfg.get('paths', {}).get('video_dir')
            or cfg.get('content', {}).get('video_dir')
            or cfg.get('video_dir')
        )
        if video_dir:
            return str(Path(video_dir).expanduser().resolve())
    except Exception:
        pass
    # Fallback: <cwd>/video
    return str(Path.cwd() / 'video')


def _resolve_path(path_str: str, try_video_dir: bool = True) -> str:
    """Resolve a potentially relative path to an absolute path."""
    path = Path(path_str)
    if path.is_absolute():
        return str(path.resolve())

    if try_video_dir:
        video_path = Path(_get_video_dir()) / path
        if video_path.exists():
            return str(video_path.resolve())

    full_path = Path.cwd() / path
    if full_path.exists():
        return str(full_path.resolve())

    if try_video_dir:
        return str((Path(_get_video_dir()) / path).resolve())
    return str(full_path.resolve())


@converter_bp.route('/api/converter/status', methods=['GET'])
def converter_status():
    """Check if converter dependencies (OpenCV + imagecodecs) are available."""
    try:
        get_converter()
        return jsonify({
            "success": True,
            "available": True,
            "format": "hap_npy",
        })
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "available": False,
            "error": str(e),
            "details": traceback.format_exc(),
        }), 200


@converter_bp.route('/api/converter/formats', methods=['GET'])
def list_formats():
    """List supported output formats."""
    return jsonify({"formats": [
        {
            "id": "hap_npy",
            "name": "HAP (BC1/BC3)",
            "description": (
                "DXT-compressed .hap — zero-copy GPU upload, ~6x RAM saving over raw frames. "
                "BC1 for RGB clips (HAP), BC3 for RGBA/alpha clips (HAP Alpha). "
                "Encoded via FFmpeg HAP codec (libsquish quality)."
            ),
        }
    ]})


@converter_bp.route('/api/converter/presets', methods=['GET'])
def list_presets():
    """List available resolution presets."""
    from ...content.converter import RESOLUTION_PRESETS
    return jsonify({
        "presets": [
            {"id": p, "label": p, "width": RESOLUTION_PRESETS[p][0], "height": RESOLUTION_PRESETS[p][1]}
            for p in ALL_PRESETS
        ]
    })


@converter_bp.route('/api/converter/info', methods=['POST'])
def get_video_info():
    """Return basic metadata for a video file."""
    data = request.json or {}
    video_path = data.get('path')
    if not video_path:
        return jsonify({"error": "Missing 'path' parameter"}), 400

    resolved = _resolve_path(video_path)
    if not os.path.exists(resolved):
        return jsonify({"error": f"Video not found: {resolved}"}), 404

    try:
        info = get_converter().get_video_info(resolved)
        return jsonify({"success": True, "info": info})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@converter_bp.route('/api/converter/upload', methods=['POST'])
def upload_file():
    """Upload a video file and start background HAP conversion for all presets."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        import re
        upload_dir = Path.cwd() / 'video' / 'uploads'
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = re.sub(r'[^\w\-_\. ]', '_', file.filename)
        file_path = upload_dir / safe_filename
        file.save(str(file_path))

        video_root = _get_video_dir()
        upload_dir = Path(video_root) / 'uploads'

        # Get selected presets and dxt_variant from form data
        presets_raw = request.form.get('presets')
        dxt_variant = request.form.get('dxt_variant', 'bc1')
        presets = json.loads(presets_raw) if presets_raw else list(ALL_PRESETS)
        custom_raw = request.form.get('custom_resolutions')
        custom_resolutions = json.loads(custom_raw) if custom_raw else []

        converting = False
        try:
            converter = get_converter()
            thread = threading.Thread(
                target=converter.convert_multi_resolution,
                kwargs=dict(
                    input_path=str(file_path),
                    presets=presets,
                    output_dir=video_root,
                    dxt_variant=dxt_variant,
                    custom_resolutions=custom_resolutions,
                ),
                daemon=True,
            )
            thread.start()
            converting = True
        except Exception as conv_err:
            print(f'Auto-conversion skipped: {conv_err}')

        base_name = os.path.splitext(safe_filename)[0]
        clip_folder = str(Path(video_root) / base_name)

        return jsonify({
            'success': True,
            'filename': safe_filename,
            'upload_path': str(file_path),
            'clip_folder': clip_folder,
            'presets': presets,
            'converting': converting,
            'message': (
                'Upload successful. Converting in background.' if converting
                else 'Upload successful (conversion skipped — check imagecodecs install).'
            ),
        })
    except Exception as e:
        import traceback
        print(f'Upload error: {traceback.format_exc()}')
        return jsonify({'error': str(e)}), 500


@converter_bp.route('/api/converter/convert/start', methods=['POST'])
def start_multi_res_conversion():
    """Start HAP conversion for an existing file on the server.

    Body:
        source_path        Path to the source video file
        presets            List of preset names (default: all)
        dxt_variant        'bc1' or 'bc3' (default: 'bc1')
        custom_resolutions List of {name, width, height} dicts (optional)
    """
    data = request.json or {}
    source_path_str = data.get('source_path')
    if not source_path_str:
        return jsonify({'error': 'Missing source_path'}), 400

    abs_path = _resolve_path(source_path_str, try_video_dir=True)
    if not os.path.exists(abs_path):
        return jsonify({'error': f'File not found: {abs_path}'}), 404

    presets = data.get('presets', list(ALL_PRESETS))
    dxt_variant = data.get('dxt_variant', 'bc1')
    custom_resolutions = data.get('custom_resolutions', [])

    base_name = os.path.splitext(os.path.basename(abs_path))[0]
    clip_folder = str(Path(os.path.dirname(abs_path)) / base_name)

    try:
        converter = get_converter()
        thread = threading.Thread(
            target=converter.convert_multi_resolution,
            kwargs=dict(
                input_path=abs_path,
                presets=presets,
                output_dir=os.path.dirname(abs_path),
                dxt_variant=dxt_variant,
                custom_resolutions=custom_resolutions,
            ),
            daemon=True,
        )
        thread.start()
        return jsonify({
            'success': True,
            'source_path': abs_path,
            'clip_folder': clip_folder,
            'presets': presets,
            'dxt_variant': dxt_variant,
            'converting': True,
            'message': 'HAP conversion started in background.',
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@converter_bp.route('/api/converter/convert/status', methods=['GET'])
def get_multi_res_status():
    """Poll conversion status for a clip folder."""
    clip_folder = request.args.get('clip_folder')
    if not clip_folder:
        return jsonify({'error': 'Missing clip_folder parameter'}), 400

    try:
        status = get_converter().get_conversion_status(clip_folder)
        return jsonify({'success': True, **status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@converter_bp.route('/api/converter/convert/resume', methods=['POST'])
def resume_multi_res():
    """Resume incomplete conversions for a clip folder."""
    data = request.json or {}
    clip_folder = data.get('clip_folder')
    presets = data.get('presets', list(ALL_PRESETS))
    dxt_variant = data.get('dxt_variant', 'bc1')
    custom_resolutions = data.get('custom_resolutions', [])

    if not clip_folder:
        return jsonify({'error': 'Missing clip_folder'}), 400

    original = os.path.join(clip_folder, 'original.mov')
    if not os.path.exists(original):
        return jsonify({'error': f'original.mov not found in {clip_folder}'}), 404

    try:
        converter = get_converter()
        status = converter.get_conversion_status(clip_folder)
        pending = [p for p in presets if status['presets'].get(p) != 'done']

        if not pending:
            return jsonify({'message': 'All presets already completed', 'status': status})

        thread = threading.Thread(
            target=converter.convert_multi_resolution,
            kwargs=dict(
                input_path=original,
                presets=pending,
                output_dir=os.path.dirname(clip_folder),
                dxt_variant=dxt_variant,
                custom_resolutions=custom_resolutions,
            ),
            daemon=True,
        )
        thread.start()
        return jsonify({'success': True, 'resuming': pending})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@converter_bp.route('/api/converter/canvas-size', methods=['GET'])
def get_canvas_size():
    """Get canvas size from config."""
    try:
        config_path = Path.cwd() / 'config.json'
        with open(config_path) as f:
            config = json.load(f)
        canvas = config.get('canvas', {})
        return jsonify({
            'success': True,
            'width': canvas.get('width', 60),
            'height': canvas.get('height', 300),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'width': 60, 'height': 300})
