"""
API Console - Console & Command Execution Endpoints

WICHTIG: Verwende NIEMALS print() Statements in API-Funktionen!
Dies verursacht "write() before start_response" Fehler in Flask/Werkzeug.
Nutze stattdessen immer den Logger:
    from .logger import get_logger
    logger = get_logger(__name__)
    logger.info("Message")
"""
from flask import jsonify, request


def register_console_routes(app, rest_api_instance):
    """Registriert Console-Management Endpunkte."""
    
    @app.route('/api/console/log', methods=['GET'])
    def console_log():
        """Gibt Console Log zurück."""
        lines = int(request.args.get('lines', 100))
        log_lines = list(rest_api_instance.console_log)[-lines:]
        return jsonify({
            "log": log_lines,
            "total": len(rest_api_instance.console_log)
        })
    
    @app.route('/api/console/command', methods=['POST'])
    def console_command():
        """Führt CLI-Befehl aus (in separatem Thread um Print-Statements zu isolieren)."""
        import threading
        import io
        import sys
        
        data = request.get_json()
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({"status": "error", "message": "Kein Befehl angegeben"}), 400
        
        # Log Command
        rest_api_instance.add_log(f"> {command}")
        
        # Führe Command in separatem Thread aus (verhindert Print-Probleme)
        result_container = {'result': None, 'error': None, 'done': False}
        
        def execute_in_thread():
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            try:
                # Umleite stdout/stderr zu StringIO
                sys.stdout = io.StringIO()
                sys.stderr = io.StringIO()
                
                result = rest_api_instance._execute_command(command)
                
                # Hole captured output
                stdout_output = sys.stdout.getvalue()
                stderr_output = sys.stderr.getvalue()
                
                # Kombiniere Ergebnis mit captured output
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
            error_msg = f"Fehler: {result_container['error']}"
            rest_api_instance.add_log(error_msg)
            return jsonify({"status": "error", "message": error_msg}), 500
        
        result = result_container['result']
        if result:
            rest_api_instance.add_log(result)
        return jsonify({"status": "success", "output": result or "Befehl ausgeführt"})
    
    @app.route('/api/console/clear', methods=['POST'])
    def console_clear():
        """Löscht Console Log."""
        rest_api_instance.console_log.clear()
        return jsonify({"status": "success", "message": "Console gelöscht"})
