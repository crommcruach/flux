"""
JSON Schema Validator for points files
"""
from jsonschema import validate, ValidationError, Draft7Validator

# JSON Schema for points export format
POINTS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Punkte Export Schema",
    "description": "Schema for LED-mapping points with canvas information",
    "type": "object",
    "required": ["canvas", "objects"],
    "properties": {
        "canvas": {
            "type": "object",
            "description": "Canvas-Dimensionen",
            "required": ["width", "height"],
            "properties": {
                "width": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10000,
                    "description": "Canvas Breite in Pixeln"
                },
                "height": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10000,
                    "description": "Canvas height in pixels"
                }
            },
            "additionalProperties": False
        },
        "objects": {
            "type": "array",
            "description": "Liste von Objekten mit Punkten",
            "minItems": 0,
            "items": {
                "type": "object",
                "required": ["points"],
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Optionale Objekt-ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "Optionaler Objekt-Name"
                    },
                    "points": {
                        "type": "array",
                        "description": "Liste von Punkten/LEDs",
                        "minItems": 0,
                        "items": {
                            "type": "object",
                            "required": ["x", "y"],
                            "properties": {
                                "id": {
                                    "type": "integer",
                                    "description": "Optionale Punkt-ID"
                                },
                                "x": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "description": "X-Koordinate im Canvas"
                                },
                                "y": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "description": "Y-Koordinate im Canvas"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                "additionalProperties": True
            }
        }
    },
    "additionalProperties": False
}


def validate_points_json(data):
    """
    Validiert JSON-Daten gegen das Punkte-Schema.
    
    Args:
        data: Dictionary mit JSON-Daten
    
    Returns:
        tuple: (is_valid: bool, message: str, errors: list)
    """
    validator = Draft7Validator(POINTS_SCHEMA)
    errors = list(validator.iter_errors(data))
    
    if not errors:
        # Additional logical validation
        canvas = data['canvas']
        invalid_points = []
        
        for obj_idx, obj in enumerate(data['objects']):
            for point_idx, point in enumerate(obj.get('points', [])):
                if point['x'] >= canvas['width'] or point['y'] >= canvas['height']:
                    invalid_points.append({
                        'object': obj_idx,
                        'point': point_idx,
                        'x': point['x'],
                        'y': point['y'],
                        'reason': f"Point outside canvas ({canvas['width']}x{canvas['height']})"
                    })
        
        if invalid_points:
            error_msgs = [f"Objekt {p['object']}, Punkt {p['point']}: ({p['x']},{p['y']}) - {p['reason']}" 
                         for p in invalid_points[:5]]  # Erste 5 Fehler
            if len(invalid_points) > 5:
                error_msgs.append(f"... and {len(invalid_points) - 5} more points outside")
            
            return False, "Points outside canvas bounds", error_msgs
        
        # Count valid points
        total_points = sum(len(obj.get('points', [])) for obj in data['objects'])
        return True, f"✓ Valid ({total_points} points in {len(data['objects'])} objects)", []
    
    # Schema-Validierungsfehler
    error_messages = []
    for error in errors[:5]:  # Erste 5 Fehler
        path = '.'.join(str(p) for p in error.path) if error.path else 'root'
        error_messages.append(f"{path}: {error.message}")
    
    if len(errors) > 5:
        error_messages.append(f"... und {len(errors) - 5} weitere Fehler")
    
    return False, "Schema-Validierung fehlgeschlagen", error_messages


def validate_points_file(file_path):
    """
    Loads and validates a points JSON file.
    
    Args:
        file_path: Pfad zur JSON-Datei
    
    Returns:
        tuple: (is_valid: bool, message: str, errors: list, data: dict or None)
    """
    import json
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return False, f"Datei nicht gefunden: {file_path}", [], None
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON syntax: {e}", [], None
    except Exception as e:
        return False, f"Fehler beim Laden: {e}", [], None
    
    is_valid, message, errors = validate_points_json(data)
    return is_valid, message, errors, data if is_valid else None
