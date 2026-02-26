"""
API Endpoints für Log-Zugriff
"""
import os
import logging
from pathlib import Path
from flask import jsonify, request


def register_log_routes(app):
    """Registriert alle Log-API-Routen"""
    
    @app.route('/api/logs', methods=['GET'])
    def get_logs():
        """
        Gibt die aktuellen Log-Zeilen zurück.
        
        Returns:
            JSON mit Log-Zeilen
        """
        try:
            log_dir = Path('logs')
            
            # Finde die neueste Log-Datei
            if not log_dir.exists():
                return jsonify({
                    'lines': ['Log-Verzeichnis nicht gefunden'],
                    'file': None,
                    'size': 0
                })
            
            log_files = sorted(log_dir.glob('flux_*.log'), key=lambda f: f.stat().st_mtime, reverse=True)
            
            if not log_files:
                return jsonify({
                    'lines': ['Keine Log-Dateien gefunden'],
                    'file': None,
                    'size': 0
                })
            
            # Lese die neueste Log-Datei
            latest_log = log_files[0]
            
            # Lese die letzten 500 Zeilen (oder alle, falls weniger)
            with open(latest_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Entferne Newlines am Ende
                lines = [line.rstrip('\n') for line in lines]
                # Nehme die letzten 500 Zeilen
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
                'lines': [f'Fehler beim Laden der Logs: {str(e)}'],
                'file': None,
                'size': 0
            }), 500
    
    @app.route('/api/logs/files', methods=['GET'])
    def get_log_files():
        """
        Gibt eine Liste aller verfügbaren Log-Dateien zurück.
        
        Returns:
            JSON mit Liste der Log-Dateien
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
        Löscht alte Log-Dateien (behält die neuesten 5).
        
        Returns:
            JSON mit Bestätigung
        """
        try:
            log_dir = Path('logs')
            
            if not log_dir.exists():
                return jsonify({
                    'success': True,
                    'message': 'Log-Verzeichnis nicht gefunden',
                    'deleted': 0
                })
            
            log_files = sorted(log_dir.glob('flux_*.log'), key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Behalte die neuesten 5, lösche den Rest
            files_to_delete = log_files[5:]
            deleted_count = 0
            
            for log_file in files_to_delete:
                try:
                    log_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"Fehler beim Löschen von {log_file}: {e}")
            
            return jsonify({
                'success': True,
                'message': f'{deleted_count} alte Log-Dateien gelöscht',
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
            JSON mit Bestätigung
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
            
            # Logging über den Python Logger
            logger = logging.getLogger('flux')
            
            error_msg = f"[JS ERROR] {message}"
            if source and line:
                error_msg += f" at {source}:{line}:{column}"
            if url:
                error_msg += f" (URL: {url})"
            
            logger.error(error_msg)
            
            # Stack trace in separaten Zeilen loggen
            if stack:
                for stack_line in stack.split('\n'):
                    if stack_line.strip():
                        logger.error(f"[JS STACK] {stack_line.strip()}")
            
            # User Agent für Debugging
            if user_agent:
                logger.debug(f"[JS ERROR] User-Agent: {user_agent}")
            
            return jsonify({
                'success': True,
                'message': 'Error logged'
            })
            
        except Exception as e:
            logger = logging.getLogger('flux')
            logger.error(f"Fehler beim Loggen von JS-Error: {str(e)}")
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
            JSON mit Bestätigung
        """
        try:
            data = request.get_json()
            
            level = data.get('level', 'log')
            message = data.get('message', '')
            args = data.get('args', [])
            url = data.get('url', '')
            timestamp = data.get('timestamp', '')
            stack = data.get('stack', '')
            
            # Logging über den Python Logger
            logger = logging.getLogger('flux')
            
            # Kombiniere Message und Args
            if args:
                full_message = f"{message} {' '.join(str(arg) for arg in args)}"
            else:
                full_message = message
            
            # Baue Log-Message
            log_msg = f"[JS {level.upper()}]"
            if url:
                # Extrahiere nur den Pfad ohne Domain
                from urllib.parse import urlparse
                parsed = urlparse(url)
                path = parsed.path if parsed.path else 'unknown'
                log_msg += f" [{path}]"
            log_msg += f" {full_message}"
            
            # Logge mit entsprechendem Level
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
