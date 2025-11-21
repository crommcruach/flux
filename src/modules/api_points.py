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
    
    @app.route('/api/points/preview/<filename>', methods=['GET'])
    def preview_points(filename):
        """Generiert Vorschau-Bild der Punkte-Positionen."""
        from flask import Response
        import numpy as np
        import cv2
        import io
        
        try:
            filepath = os.path.join(data_dir, filename)
            
            if not os.path.exists(filepath):
                return jsonify({"status": "error", "message": f"Datei nicht gefunden: {filename}"}), 404
            
            # Lade Points-Daten
            from .points_loader import PointsLoader
            points_data = PointsLoader.load_points(filepath, validate_bounds=False)
            
            canvas_width = points_data['canvas_width']
            canvas_height = points_data['canvas_height']
            point_coords = points_data['point_coords']
            
            # Berechne Thumbnail-Größe (max 400px)
            max_size = 400
            if canvas_width > canvas_height:
                thumb_width = max_size
                thumb_height = int(canvas_height * (max_size / canvas_width))
            else:
                thumb_height = max_size
                thumb_width = int(canvas_width * (max_size / canvas_height))
            
            # Erstelle schwarzes Bild
            preview = np.zeros((thumb_height, thumb_width, 3), dtype=np.uint8)
            
            # Skalierungsfaktoren
            scale_x = thumb_width / canvas_width
            scale_y = thumb_height / canvas_height
            
            # Punkte-Radius (größer für bessere Sichtbarkeit in Thumbnail)
            radius = max(3, int(min(thumb_width, thumb_height) * 0.015))
            
            # Zeichne Punkte in Magenta
            magenta = (255, 0, 255)  # BGR Format
            for point in point_coords:
                x = int(point[0] * scale_x)
                y = int(point[1] * scale_y)
                cv2.circle(preview, (x, y), radius, magenta, -1)  # Gefüllter Kreis
            
            # Konvertiere zu PNG
            _, buffer = cv2.imencode('.png', preview)
            io_buf = io.BytesIO(buffer)
            
            return Response(io_buf.getvalue(), mimetype='image/png')
            
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
