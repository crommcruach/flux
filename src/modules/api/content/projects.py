"""
API endpoints for project management (save/load projects)
"""
import os
import json
from flask import request, jsonify, send_file
from pathlib import Path
from datetime import datetime
from ...core.logger import debug_api


def register_project_routes(app, logger):
    """Register all project-related API routes"""
    
    # Point to root/projects folder (4 levels up from src/modules/api/content/)
    PROJECTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'projects'
    PROJECTS_DIR.mkdir(exist_ok=True)
    
    @app.route('/api/projects', methods=['GET'])
    def list_projects():
        """List all saved projects"""
        try:
            projects = []
            for file in PROJECTS_DIR.glob('*.json'):
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        projects.append({
                            'filename': file.name,
                            'projectName': data.get('projectName', file.stem),
                            'savedAt': data.get('savedAt', ''),
                            'shapeCount': len(data.get('shapes', [])),
                            'size': file.stat().st_size
                        })
                except Exception as e:
                    logger.warning(f"Could not read project file {file.name}: {e}")
                    continue
            
            # Sort by savedAt descending (newest first)
            projects.sort(key=lambda x: x['savedAt'], reverse=True)
            
            return jsonify({
                'success': True,
                'projects': projects,
                'count': len(projects)
            })
        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/projects/save', methods=['POST'])
    def save_project():
        """Save a project to the PROJECTS folder"""
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            project_name = data.get('projectName', 'Mein Projekt')
            
            # Create safe filename
            safe_name = ''.join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in project_name)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{safe_name}_{timestamp}.json"
            
            filepath = PROJECTS_DIR / filename
            
            # Add metadata
            data['savedAt'] = datetime.now().isoformat()
            data['version'] = data.get('version', '1.0')
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            debug_api(logger, f"Project saved: {filename}")
            
            return jsonify({
                'success': True,
                'filename': filename,
                'path': str(filepath),
                'message': f'Projekt "{project_name}" gespeichert'
            })
        except Exception as e:
            logger.error(f"Error saving project: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/projects/load/<filename>', methods=['GET'])
    def load_project(filename):
        """Load a project from the PROJECTS folder"""
        try:
            # Security: prevent path traversal
            if '..' in filename or '/' in filename or '\\' in filename:
                return jsonify({'success': False, 'error': 'Invalid filename'}), 400
            
            filepath = PROJECTS_DIR / filename
            
            if not filepath.exists():
                return jsonify({'success': False, 'error': 'Project not found'}), 404
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            debug_api(logger, f"Project loaded: {filename}")
            
            return jsonify({
                'success': True,
                'data': data
            })
        except Exception as e:
            logger.error(f"Error loading project: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/projects/delete/<filename>', methods=['DELETE'])
    def delete_project(filename):
        """Delete a project from the PROJECTS folder"""
        try:
            # Security: prevent path traversal
            if '..' in filename or '/' in filename or '\\' in filename:
                return jsonify({'success': False, 'error': 'Invalid filename'}), 400
            
            filepath = PROJECTS_DIR / filename
            
            if not filepath.exists():
                return jsonify({'success': False, 'error': 'Project not found'}), 404
            
            filepath.unlink()
            
            debug_api(logger, f"Project deleted: {filename}")
            
            return jsonify({
                'success': True,
                'message': f'Projekt "{filename}" gelöscht'
            })
        except Exception as e:
            logger.error(f"Error deleting project: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/projects/download/<filename>', methods=['GET'])
    def download_project(filename):
        """Download a project file"""
        try:
            # Security: prevent path traversal
            if '..' in filename or '/' in filename or '\\' in filename:
                return jsonify({'success': False, 'error': 'Invalid filename'}), 400
            
            filepath = PROJECTS_DIR / filename
            
            if not filepath.exists():
                return jsonify({'success': False, 'error': 'Project not found'}), 404
            
            return send_file(
                filepath,
                mimetype='application/json',
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            logger.error(f"Error downloading project: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    debug_api(logger, "Project API routes registered")
