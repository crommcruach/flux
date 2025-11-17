"""
API Console - Console & Command Execution Endpoints
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
        """Führt CLI-Befehl aus."""
        data = request.get_json()
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({"status": "error", "message": "Kein Befehl angegeben"}), 400
        
        # Log Command
        rest_api_instance.add_log(f"> {command}")
        
        # Command ausführen
        try:
            result = rest_api_instance._execute_command(command)
            if result:
                rest_api_instance.add_log(result)
            return jsonify({"status": "success", "output": result})
        except Exception as e:
            error_msg = f"Fehler: {str(e)}"
            rest_api_instance.add_log(error_msg)
            return jsonify({"status": "error", "message": error_msg}), 500
    
    @app.route('/api/console/clear', methods=['POST'])
    def console_clear():
        """Löscht Console Log."""
        rest_api_instance.console_log.clear()
        return jsonify({"status": "success", "message": "Console gelöscht"})
