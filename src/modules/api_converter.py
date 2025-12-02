"""
REST API für Video Converter
"""

from flask import Blueprint, request, jsonify
from .video_converter import (
    get_converter, 
    OutputFormat, 
    ResizeMode, 
    ConversionJob
)
import os
from pathlib import Path
import threading


converter_bp = Blueprint('converter', __name__)

# Active conversion jobs (thread-safe)
active_jobs = {}
jobs_lock = threading.Lock()


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
    formats = [
        {
            "id": fmt.value,
            "name": fmt.name,
            "description": _get_format_description(fmt)
        }
        for fmt in OutputFormat
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
    
    # Create job
    job = ConversionJob(
        input_path=data['input_path'],
        output_path=data['output_path'],
        format=output_format,
        target_size=target_size,
        resize_mode=resize_mode,
        optimize_loop=data.get('optimize_loop', False),
        fps=data.get('fps')
    )
    
    # Convert (synchronous for now, could be async)
    try:
        converter = get_converter()
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
        OutputFormat.H264: "H.264 (libx264) - Software encoding, universal compatibility",
        OutputFormat.H264_NVENC: "H.264 (NVENC) - Hardware encoding (NVIDIA GPU required)"
    }
    return descriptions.get(fmt, "")
