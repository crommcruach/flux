"""
API Endpoints for log access
"""
import os
import logging
from pathlib import Path
from flask import jsonify, request


def register_log_routes(app):
    """Registers all log API routes"""
    
    @app.route('/api/logs', methods=['GET'])
    def get_logs():
        """
        Returns the current log lines.
        
        Returns:
            JSON with log lines
        """
        try:
            log_dir = Path('logs')
            
            # Find the newest log file
            if not log_dir.exists():
                return jsonify({
                    'lines': ['Log directory not found'],
                    'file': None,
                    'size': 0
                })
            
            log_files = sorted(log_dir.glob('flux_*.log'), key=lambda f: f.stat().st_mtime, reverse=True)
            
            if not log_files:
                return jsonify({
                    'lines': ['No log files found'],
                    'file': None,
                    'size': 0
                })
            
            # Read the newest log file
            latest_log = log_files[0]
            
            # Read the last 500 lines (or all if fewer)
            with open(latest_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Remove trailing newlines
                lines = [line.rstrip('\n') for line in lines]
                # Take the last 500 lines
                lines = lines[-500:]
            
            file_size_mb = latest_log.stat().st_size / (1024 * 1024)
            
            return jsonify({
                'lines': lines,
                'file': latest_log.name,
                'size': round(file_size_mb, 2),
                'total_lines': len(lines)
            })
            
        except Exception as e:
            return jsonify({
                'error': str(e),
                'lines': [f'Error loading logs: {str(e)}'],
                'file': None,
                'size': 0
            }), 500
    
    @app.route('/api/logs/files', methods=['GET'])
    def get_log_files():
        """
        Returns a list of all available log files.
        
        Returns:
            JSON with list of log files
        """
        try:
            log_dir = Path('logs')
            
            if not log_dir.exists():
                return jsonify({'files': []})
            
            log_files = sorted(log_dir.glob('flux_*.log'), key=lambda f: f.stat().st_mtime, reverse=True)
            
            files_info = []
            for log_file in log_files:
                stat = log_file.stat()
                files_info.append({
                    'name': log_file.name,
                    'size': round(stat.st_size / (1024 * 1024), 2),  # MB
                    'modified': stat.st_mtime,
                    'path': str(log_file)
                })
            
            return jsonify({'files': files_info})
            
        except Exception as e:
            return jsonify({
                'error': str(e),
                'files': []
            }), 500
    
    @app.route('/api/logs/clear', methods=['POST'])
    def clear_old_logs():
        """
        Deletes old log files (keeps the newest 5).
        
        Returns:
            JSON with confirmation
        """
        try:
            log_dir = Path('logs')
            
            if not log_dir.exists():
                return jsonify({
                    'success': True,
                    'message': 'Log directory not found',
                    'deleted': 0
                })
            
            log_files = sorted(log_dir.glob('flux_*.log'), key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Keep the newest 5, delete the rest
            files_to_delete = log_files[5:]
            deleted_count = 0
            
            for log_file in files_to_delete:
                try:
                    log_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {log_file}: {e}")
            
            return jsonify({
                'success': True,
                'message': f'{deleted_count} old log files deleted',
                'deleted': deleted_count,
                'remaining': len(log_files) - deleted_count
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'deleted': 0
            }), 500
    
    @app.route('/api/logs/js-error', methods=['POST'])
    def log_js_error():
        """
        Loggt JavaScript-Fehler aus dem Frontend.
        
        Expected JSON:
            {
                "message": "Error message",
                "source": "file.js",
                "line": 123,
                "column": 45,
                "stack": "Stack trace",
                "url": "http://localhost:5000/page.html",
                "userAgent": "Mozilla/5.0..."
            }
        
        Returns:
            JSON with confirmation
        """
        try:
            data = request.get_json()
            
            message = data.get('message', 'Unknown error')
            source = data.get('source', 'unknown')
            line = data.get('line', 0)
            column = data.get('column', 0)
            stack = data.get('stack', '')
            url = data.get('url', '')
            user_agent = data.get('userAgent', '')
            
            # Log via Python logger
            if source and line:
                error_msg += f" at {source}:{line}:{column}"
            if url:
                error_msg += f" (URL: {url})"
            
            logger.error(error_msg)
            
            # Log stack trace on separate lines
            if stack:
                for stack_line in stack.split('\n'):
                    if stack_line.strip():
                        logger.error(f"[JS STACK] {stack_line.strip()}")
            
            # User agent for debugging
            if user_agent:
                logger.debug(f"[JS ERROR] User-Agent: {user_agent}")
            
            return jsonify({
                'success': True,
                'message': 'Error logged'
            })
            
        except Exception as e:
            logger = logging.getLogger('flux')
            logger.error(f"Error logging JS error: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/logs/js-log', methods=['POST'])
    def log_js_console():
        """
        Loggt alle JavaScript-Console-Ausgaben (log, warn, error, info, debug).
        
        Expected JSON:
            {
                "level": "log|warn|error|info|debug",
                "message": "Log message",
                "args": ["arg1", "arg2", ...],
                "url": "http://localhost:5000/page.html",
                "timestamp": 1234567890.123,
                "stack": "Stack trace (optional)"
            }
        
        Returns:
            JSON with confirmation
        """
        try:
            data = request.get_json()
            
            level = data.get('level', 'log')
            message = data.get('message', '')
            args = data.get('args', [])
            url = data.get('url', '')
            timestamp = data.get('timestamp', '')
            stack = data.get('stack', '')
            
            # Log via Python logger
            logger = logging.getLogger('flux')
            
            # Combine message and args
            if args:
                full_message = f"{message} {' '.join(str(arg) for arg in args)}"
            else:
                full_message = message
            
            # Build log message
            log_msg = f"[JS {level.upper()}]"
            if url:
                # Extract only the path without domain
                from urllib.parse import urlparse
                parsed = urlparse(url)
                path = parsed.path if parsed.path else 'unknown'
                log_msg += f" [{path}]"
            log_msg += f" {full_message}"
            
            # Log with corresponding level
            if level == 'error':
                logger.error(log_msg)
                if stack:
                    for stack_line in stack.split('\n'):
                        if stack_line.strip():
                            logger.error(f"[JS STACK] {stack_line.strip()}")
            elif level == 'warn':
                logger.warning(log_msg)
            elif level == 'info':
                logger.debug(log_msg)
            elif level == 'debug':
                logger.debug(log_msg)
            else:  # log
                logger.debug(log_msg)
            
            return jsonify({
                'success': True,
                'message': 'Log sent to server'
            })
            
        except Exception as e:
            logger = logging.getLogger('flux')
            logger.error(f"Fehler beim Loggen von JS-Console: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
