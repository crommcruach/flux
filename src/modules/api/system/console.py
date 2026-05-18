"""
API Console - Console & Command Execution Endpoints

IMPORTANT: NEVER use print() statements in API functions!
This causes "write() before start_response" errors in Flask/Werkzeug.
Always use the logger instead:
    from ...core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Message")
"""
from flask import jsonify, request


def register_console_routes(app, rest_api_instance):
    """Registriert Console-Management Endpunkte."""
    
    @app.route('/api/console/log', methods=['GET'])
    def console_log():
        """Returns console log."""
        lines = int(request.args.get('lines', 100))
        log_lines = list(rest_api_instance.console_log)[-lines:]
        return jsonify({
            "log": log_lines,
            "total": len(rest_api_instance.console_log)
        })
    
    @app.route('/api/console/command', methods=['POST'])
    def console_command():
        """Executes a CLI command (in a separate thread to isolate print statements)."""
        import threading
        import io
        import sys
        
        data = request.get_json()
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({"status": "error", "message": "No command specified"}), 400
        
        # Log Command
        rest_api_instance.add_log(f"> {command}")
        
        # Execute command in a separate thread (prevents print problems)
        result_container = {'result': None, 'error': None, 'done': False}
        
        def execute_in_thread():
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            try:
                # Redirect stdout/stderr to StringIO
                sys.stdout = io.StringIO()
                sys.stderr = io.StringIO()
                
                result = rest_api_instance._execute_command(command)
                
                # Hole captured output
                stdout_output = sys.stdout.getvalue()
                stderr_output = sys.stderr.getvalue()
                
                # Combine result with captured output
                if stdout_output or stderr_output:
                    result = (result or '') + '\n' + stdout_output + stderr_output
                
                result_container['result'] = result
            except Exception as e:
                result_container['error'] = str(e)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                result_container['done'] = True
        
        # Starte Thread und warte
        thread = threading.Thread(target=execute_in_thread, daemon=True)
        thread.start()
        thread.join(timeout=10.0)
        
        # Verarbeite Ergebnis
        if result_container['error']:
            error_msg = f"Error: {result_container['error']}"
            rest_api_instance.add_log(error_msg)
            return jsonify({"status": "error", "message": error_msg}), 500
        
        result = result_container['result']
        if result:
            rest_api_instance.add_log(result)
        return jsonify({"status": "success", "output": result or "Command executed"})
    
    @app.route('/api/console/clear', methods=['POST'])
    def console_clear():
        """Clears console log."""
        rest_api_instance.console_log.clear()
        return jsonify({"status": "success", "message": "Console cleared"})
    
    @app.route('/api/console/help', methods=['GET'])
    def console_help():
        """Returns CLI help (dynamically from utils.print_help)."""
        import io
        import sys
        from ...core.utils import print_help
        
        # Capture print_help() output
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        try:
            print_help()
            help_text = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        
        # Parse help text in strukturierte Daten
        sections = []
        current_section = None
        current_commands = []
        
        for line in help_text.split('\n'):
            line_stripped = line.strip()
            
            # Skip separators
            if line_stripped.startswith('==='):
                continue
            
            # Section headers (emoji + text)
            if line_stripped and any(emoji in line_stripped for emoji in ['📹', '🎬', '📍', '⚙️', '🌐', '🔌', 'ℹ️', '⏺️', '💾', '🎨', '🔧']):
                if current_section:
                    sections.append({
                        'title': current_section,
                        'commands': current_commands
                    })
                current_section = line_stripped
                current_commands = []
            
            # Command lines (indented)
            elif line.startswith('  ') and line_stripped and not line_stripped.startswith('💡'):
                # Parse command and description
                parts = line_stripped.split('-', 1)
                if len(parts) == 2:
                    cmd = parts[0].strip()
                    desc = parts[1].strip()
                    current_commands.append({'command': cmd, 'description': desc})
        
        # Add last section
        if current_section and current_commands:
            sections.append({
                'title': current_section,
                'commands': current_commands
            })
        
        return jsonify({
            "help_text": help_text,
            "sections": sections
        })
