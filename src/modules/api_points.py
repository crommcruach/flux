"""
API Points - Points Management Endpoints

WICHTIG: Verwende NIEMALS print() Statements in API-Funktionen!
Dies verursacht "write() before start_response" Fehler in Flask/Werkzeug.
Nutze stattdessen immer den Logger.
"""
from flask import jsonify, request
import os


def register_points_routes(app, player, data_dir):
    """Registriert Points-Management Endpunkte."""
    
    @app.route('/api/points/list', methods=['GET'])
    def list_points():
        """Listet alle verfügbaren Points-Dateien auf."""
        try:
            if not os.path.exists(data_dir):
                return jsonify({"status": "error", "message": "Data-Verzeichnis nicht gefunden"}), 404
            
            json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
            current_file = os.path.basename(player.points_json_path)
            
            files_info = []
            for filename in sorted(json_files):
                filepath = os.path.join(data_dir, filename)
                file_size = os.path.getsize(filepath)
                is_current = (filename == current_file)
                
                files_info.append({
                    "filename": filename,
                    "size": file_size,
                    "is_current": is_current,
                    "path": filepath
                })
            
            return jsonify({
                "status": "success",
                "files": files_info,
                "current": current_file,
                "total": len(files_info)
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/points/switch', methods=['POST'])
    def switch_points():
        """Wechselt zu anderer Points-Datei."""
        try:
            data = request.get_json()
            filename = data.get('filename')
            
            if not filename:
                return jsonify({"status": "error", "message": "Kein Dateiname angegeben"}), 400
            
            filepath = os.path.join(data_dir, filename)
            
            if not os.path.exists(filepath):
                return jsonify({"status": "error", "message": f"Datei nicht gefunden: {filename}"}), 404
            
            # Validiere JSON vor dem Wechsel
            from .validator import validate_points_file
            is_valid, message, errors, _ = validate_points_file(filepath)
            
            if not is_valid:
                return jsonify({
                    "status": "error",
                    "message": "Ungültige Points-Datei",
                    "validation_errors": errors
                }), 400
            
            # Lade neue Points
            was_playing = player.is_playing
            if was_playing:
                player.stop()
            
            player.load_points(filepath)
            
            if was_playing:
                player.start()
            
            return jsonify({
                "status": "success",
                "message": f"Points gewechselt zu: {filename}",
                "filename": filename,
                "was_playing": was_playing
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/points/reload', methods=['POST'])
    def reload_points():
        """Lädt aktuelle Points-Datei neu."""
        try:
            current_path = player.points_json_path
            
            # Validiere vor Reload
            from .validator import validate_points_file
            is_valid, message, errors, _ = validate_points_file(current_path)
            
            if not is_valid:
                return jsonify({
                    "status": "error",
                    "message": "Ungültige Points-Datei",
                    "validation_errors": errors
                }), 400
            
            was_playing = player.is_playing
            if was_playing:
                player.stop()
            
            player.load_points(current_path)
            
            if was_playing:
                player.start()
            
            return jsonify({
                "status": "success",
                "message": "Points neu geladen",
                "filename": os.path.basename(current_path),
                "was_playing": was_playing
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/points/validate', methods=['POST'])
    def validate_points():
        """Validiert eine Points-Datei."""
        try:
            data = request.get_json()
            filename = data.get('filename')
            
            if not filename:
                return jsonify({"status": "error", "message": "Kein Dateiname angegeben"}), 400
            
            filepath = os.path.join(data_dir, filename)
            
            if not os.path.exists(filepath):
                return jsonify({"status": "error", "message": f"Datei nicht gefunden: {filename}"}), 404
            
            from .validator import validate_points_file
            is_valid, message, errors, data = validate_points_file(filepath)
            
            result = {
                "status": "success" if is_valid else "error",
                "is_valid": is_valid,
                "message": message,
                "filename": filename
            }
            
            if errors:
                result["validation_errors"] = errors
            
            if is_valid and data:
                result["info"] = {
                    "canvas_width": data.get('canvas', {}).get('width'),
                    "canvas_height": data.get('canvas', {}).get('height'),
                    "objects_count": len(data.get('objects', []))
                }
            
            return jsonify(result)
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/points/current', methods=['GET'])
    def current_points():
        """Gibt aktuell geladene Points-Datei zurück."""
        return jsonify({
            "status": "success",
            "filename": os.path.basename(player.points_json_path),
            "path": player.points_json_path,
            "total_points": player.total_points,
            "canvas_width": player.canvas_width,
            "canvas_height": player.canvas_height
        })
