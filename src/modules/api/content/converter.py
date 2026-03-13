"""
REST API für Video Converter
"""

from flask import Blueprint, request, jsonify
from ...content.converter import (
    get_converter,
    OutputFormat,
    ResizeMode,
    ConversionJob,
    ALL_PRESETS,
)
import os
from pathlib import Path
import threading


converter_bp = Blueprint('converter', __name__)

# Active conversion jobs (thread-safe)
active_jobs = {}
jobs_lock = threading.Lock()


def _resolve_path(path_str: str, try_video_dir: bool = True) -> str:
    """
    Resolve a path to absolute path.
    If relative, try multiple locations:
    1. Relative to video/ directory (for files from FilesTab) if try_video_dir=True
    2. Relative to current working directory
    """
    path = Path(path_str)
    if path.is_absolute():
        return str(path.resolve())
    
    # For FilesTab files, try video directory first
    if try_video_dir:
        video_path = Path.cwd() / 'video' / path
        if video_path.exists():
            return str(video_path.resolve())
    
    # Try relative to current working directory
    full_path = Path.cwd() / path
    if full_path.exists():
        return str(full_path.resolve())
    
    # If try_video_dir was True and neither worked, still prefer video path for error message
    if try_video_dir:
        return str((Path.cwd() / 'video' / path).resolve())
    
    # Otherwise return the cwd-relative path
    return str(full_path.resolve())


@converter_bp.route('/api/converter/status', methods=['GET'])
def converter_status():
    """Check if converter is available and working"""
    try:
        converter = get_converter()
        return jsonify({
            "success": True,
            "ffmpeg_available": True,
            "ffmpeg_path": converter.ffmpeg_path,
            "ffprobe_path": converter.ffprobe_path
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Converter status error: {error_details}")
        return jsonify({
            "success": False,
            "ffmpeg_available": False,
            "error": str(e),
            "details": error_details
        }), 200  # Return 200 instead of 500 so frontend can handle it


@converter_bp.route('/api/converter/formats', methods=['GET'])
def list_formats():
    """Liste aller unterstützten Output-Formate"""
    hap_formats = [OutputFormat.HAP, OutputFormat.HAP_ALPHA, OutputFormat.HAP_Q]
    formats = [
        {
            "id": fmt.value,
            "name": fmt.name,
            "description": _get_format_description(fmt)
        }
        for fmt in hap_formats
    ]
    return jsonify({"formats": formats})


@converter_bp.route('/api/converter/info', methods=['POST'])
def get_video_info():
    """Hole Informationen über ein Video"""
    data = request.json
    video_path = data.get('path')
    
    if not video_path:
        return jsonify({"error": "Missing 'path' parameter"}), 400
    
    if not os.path.exists(video_path):
        return jsonify({"error": f"Video not found: {video_path}"}), 404
    
    try:
        converter = get_converter()
        info = converter.get_video_info(video_path)
        return jsonify({"success": True, "info": info})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@converter_bp.route('/api/converter/convert', methods=['POST'])
def convert_video():
    """
    Konvertiere ein einzelnes Video
    
    Body:
    {
        "input_path": "path/to/video.mp4",
        "output_path": "path/to/output.mov",
        "format": "hap",
        "target_size": [60, 300],
        "resize_mode": "fit",
        "optimize_loop": false,
        "fps": 30
    }
    """
    data = request.json
    
    # Validate required fields
    required = ['input_path', 'output_path', 'format']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    # Parse parameters
    try:
        format_str = data['format']
        output_format = OutputFormat(format_str)
    except ValueError:
        return jsonify({"error": f"Invalid format: {format_str}"}), 400
    
    resize_mode = ResizeMode.NONE
    if 'resize_mode' in data:
        try:
            resize_mode = ResizeMode(data['resize_mode'])
        except ValueError:
            return jsonify({"error": f"Invalid resize_mode: {data['resize_mode']}"}), 400
    
    target_size = None
    if 'target_size' in data and data['target_size'] is not None:
        target_size = tuple(data['target_size'])
        if len(target_size) != 2:
            return jsonify({"error": "target_size must be [width, height]"}), 400
    
    # Resolve paths to absolute
    input_path = _resolve_path(data['input_path'], try_video_dir=True)
    output_path = _resolve_path(data['output_path'], try_video_dir=False)
    
    # Debug logging
    print(f"🔍 Path resolution:")
    print(f"  Original input: {data['input_path']}")
    print(f"  Resolved input: {input_path}")
    print(f"  File exists: {Path(input_path).exists()}")
    
    # Check if input file exists
    if not Path(input_path).exists():
        return jsonify({
            "error": f"Input file not found: {input_path}",
            "original_path": data['input_path']
        }), 404
    
    # Ensure output directory exists
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create job
    job = ConversionJob(
        input_path=input_path,
        output_path=output_path,
        format=output_format,
        target_size=target_size,
        resize_mode=resize_mode,
        optimize_loop=data.get('optimize_loop', False),
        fps=data.get('fps')
    )
    
    # Convert (synchronous for now, could be async)
    try:
        converter = get_converter()
    except RuntimeError as e:
        # FFmpeg not available or initialization failed
        return jsonify({
            "error": f"Video converter initialization failed: {str(e)}",
            "hint": "Please install FFmpeg: https://ffmpeg.org/download.html"
        }), 500
    except Exception as e:
        return jsonify({
            "error": f"Converter error: {str(e)}"
        }), 500
    
    try:
        result = converter.convert(job)
        
        if result.success:
            return jsonify({
                "success": True,
                "result": {
                    "output_path": result.output_path,
                    "duration": result.duration,
                    "input_size_mb": result.input_size_mb,
                    "output_size_mb": result.output_size_mb,
                    "compression_ratio": result.compression_ratio
                }
            })
        else:
            return jsonify({"error": result.error}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@converter_bp.route('/api/converter/batch', methods=['POST'])
def batch_convert():
    """
    Batch-Convert mehrere Videos
    
    Body:
    {
        "input_pattern": "kanal_1/*.mp4",
        "output_dir": "kanal_1_converted",
        "format": "hap",
        "target_size": [60, 300],
        "resize_mode": "fit",
        "optimize_loop": false
    }
    """
    data = request.json
    
    # Validate required fields
    required = ['input_pattern', 'output_dir', 'format']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    # Parse parameters
    try:
        format_str = data['format']
        output_format = OutputFormat(format_str)
    except ValueError:
        return jsonify({"error": f"Invalid format: {format_str}"}), 400
    
    resize_mode = ResizeMode.NONE
    if 'resize_mode' in data:
        try:
            resize_mode = ResizeMode(data['resize_mode'])
        except ValueError:
            return jsonify({"error": f"Invalid resize_mode: {data['resize_mode']}"}), 400
    
    target_size = None
    if 'target_size' in data and data['target_size'] is not None:
        target_size = tuple(data['target_size'])
        if len(target_size) != 2:
            return jsonify({"error": "target_size must be [width, height]"}), 400
    
    # Batch convert (synchronous for now)
    try:
        converter = get_converter()
        results = converter.batch_convert(
            input_pattern=data['input_pattern'],
            output_dir=data['output_dir'],
            format=output_format,
            target_size=target_size,
            resize_mode=resize_mode,
            optimize_loop=data.get('optimize_loop', False)
        )
        
        # Format results
        results_data = []
        success_count = 0
        for result in results:
            if result.success:
                success_count += 1
            results_data.append({
                "success": result.success,
                "input_path": result.input_path,
                "output_path": result.output_path,
                "error": result.error,
                "duration": result.duration,
                "input_size_mb": result.input_size_mb,
                "output_size_mb": result.output_size_mb,
                "compression_ratio": result.compression_ratio
            })
        
        return jsonify({
            "success": True,
            "total": len(results),
            "successful": success_count,
            "failed": len(results) - success_count,
            "results": results_data
        })
        
    except ValueError as e:
        # Handle "No files found" error
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        # Log full error for debugging
        import traceback
        error_details = traceback.format_exc()
        print(f"Converter error: {error_details}")
        return jsonify({"error": str(e), "details": error_details}), 500


@converter_bp.route('/api/converter/upload', methods=['POST'])
def upload_file():
    """Upload a video file and automatically convert it to all resolution presets."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Save to video/uploads/
        import re
        upload_dir = Path.cwd() / 'video' / 'uploads'
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = re.sub(r'[^\w\-_\. ]', '_', file.filename)
        file_path = upload_dir / safe_filename
        file.save(str(file_path))

        # Derive clip folder location: video/<basename>/
        video_root = str(Path.cwd() / 'video')

        # Start background conversion (all presets, auto-resume safe)
        try:
            converter = get_converter()
            thread = threading.Thread(
                target=converter.convert_multi_resolution,
                args=(str(file_path), ALL_PRESETS, OutputFormat.HAP_ALPHA, video_root),
                daemon=True,
            )
            thread.start()
            converting = True
        except Exception as conv_err:
            # FFmpeg not available — still return success for the upload
            print(f'Auto-conversion skipped (FFmpeg unavailable): {conv_err}')
            converting = False

        import os
        base_name = os.path.splitext(safe_filename)[0]
        clip_folder = str(Path(video_root) / base_name)

        return jsonify({
            'success': True,
            'filename': safe_filename,
            'upload_path': str(file_path),
            'clip_folder': clip_folder,
            'presets': ALL_PRESETS,
            'converting': converting,
            'message': 'Upload successful. Converting to all resolutions in background.' if converting else 'Upload successful (conversion skipped).'
        })
    except Exception as e:
        import traceback
        print(f'Upload error: {traceback.format_exc()}')
        return jsonify({'error': str(e)}), 500


@converter_bp.route('/api/converter/convert/status', methods=['GET'])
def get_multi_res_status():
    """Poll conversion status for a clip folder."""
    clip_folder = request.args.get('clip_folder')
    if not clip_folder:
        return jsonify({'error': 'Missing clip_folder parameter'}), 400

    try:
        converter = get_converter()
        status = converter.get_conversion_status(clip_folder)
        return jsonify({'success': True, **status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@converter_bp.route('/api/converter/convert/resume', methods=['POST'])
def resume_multi_res():
    """Resume incomplete conversions for a clip folder."""
    data = request.json or {}
    clip_folder = data.get('clip_folder')
    presets = data.get('presets', ALL_PRESETS)

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
            args=(original, pending, OutputFormat.HAP_ALPHA, os.path.dirname(clip_folder)),
            daemon=True,
        )
        thread.start()
        return jsonify({'success': True, 'resuming': pending})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@converter_bp.route('/api/converter/convert/start', methods=['POST'])
def start_multi_res_conversion():
    """Start multi-resolution conversion for an existing file already on the server."""
    data = request.json or {}
    source_path_str = data.get('source_path')
    if not source_path_str:
        return jsonify({'error': 'Missing source_path parameter'}), 400

    abs_path = _resolve_path(source_path_str, try_video_dir=True)
    if not os.path.exists(abs_path):
        return jsonify({'error': f'File not found: {abs_path}'}), 404

    base_name = os.path.splitext(os.path.basename(abs_path))[0]
    clip_folder = str(Path(os.path.dirname(abs_path)) / base_name)

    try:
        converter = get_converter()
        thread = threading.Thread(
            target=converter.convert_multi_resolution,
            args=(abs_path, ALL_PRESETS, OutputFormat.HAP_ALPHA, os.path.dirname(abs_path)),
            daemon=True,
        )
        thread.start()
        return jsonify({
            'success': True,
            'source_path': abs_path,
            'clip_folder': clip_folder,
            'presets': ALL_PRESETS,
            'converting': True,
            'message': 'Multi-resolution conversion started in background.',
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@converter_bp.route('/api/converter/canvas-size', methods=['GET'])
def get_canvas_size():
    """Hole Canvas-Größe aus Config"""
    try:
        # Load config from config.json
        import json
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config.json")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        canvas = config.get('canvas', {})
        width = canvas.get('width', 60)
        height = canvas.get('height', 300)
        
        return jsonify({
            "success": True,
            "canvas": {
                "width": width,
                "height": height
            }
        })
    except Exception as e:
        # Return default canvas size on error
        return jsonify({
            "success": True,
            "canvas": {
                "width": 60,
                "height": 300
            }
        })


def _get_format_description(fmt: OutputFormat) -> str:
    """Beschreibung für Output-Format"""
    descriptions = {
        OutputFormat.HAP: "HAP (DXT1) - Fast decoding, lower quality",
        OutputFormat.HAP_ALPHA: "HAP Alpha (DXT5) - Fast decoding with alpha channel",
        OutputFormat.HAP_Q: "HAP Q (BC7) - Highest quality HAP variant",
    }
    return descriptions.get(fmt, "")
