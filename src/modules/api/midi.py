"""
MIDI API — Mappings, Profiles, Clock, SocketIO
All MIDI-related REST endpoints + real-time clock broadcast.
"""
from flask import Blueprint, jsonify, request, make_response
import json
import copy
import threading
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

midi_bp = Blueprint('midi', __name__)

PROFILES_FILE = Path('config/midi_profiles.json')

# ── Profile persistence ───────────────────────────────────────────────────────

def _load_profiles():
    if PROFILES_FILE.exists():
        return json.loads(PROFILES_FILE.read_text(encoding='utf-8'))
    return {
        'active_profile': 'Default',
        'profiles': [{'name': 'Default', 'description': '', 'mappings': {}}]
    }


def _save_profiles(data):
    PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILES_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def _active_mappings():
    data   = _load_profiles()
    active = data.get('active_profile', 'Default')
    for p in data.get('profiles', []):
        if p['name'] == active:
            return p.get('mappings', {})
    return {}


def _save_active_mappings(mappings):
    data   = _load_profiles()
    active = data.get('active_profile', 'Default')
    for p in data.get('profiles', []):
        if p['name'] == active:
            p['mappings'] = mappings
    _save_profiles(data)


# ── Pattern matching ──────────────────────────────────────────────────────────

def matches_pattern(path: str, pattern: str) -> bool:
    """Return True when path matches a wildcard pattern (e.g. '*.brightness')."""
    pp = pattern.split('.')
    lp = path.split('.')
    if len(pp) != len(lp):
        return False
    return all(p == '*' or p == l for p, l in zip(pp, lp))


# ── Mappings CRUD ─────────────────────────────────────────────────────────────

@midi_bp.route('/api/midi/mappings', methods=['GET'])
def get_mappings():
    mappings = _active_mappings()
    result = [
        {
            'midi':   k,
            'type':   v['type'],
            'number': v['number'],
            'path':   v['path'],
            'mode':   v.get('mode', 'local'),
            'name':   v.get('name', ''),
        }
        for k, v in mappings.items()
    ]
    return jsonify({'success': True, 'mappings': result})


@midi_bp.route('/api/midi/mappings', methods=['POST'])
def add_mapping():
    d           = request.get_json() or {}
    midi_type   = d.get('midi_type', 'cc')
    midi_number = d.get('midi_number')
    path        = d.get('parameter_path')
    if midi_number is None or not path:
        return jsonify({'success': False, 'error': 'midi_number and parameter_path required'}), 400
    key      = f"{midi_type}:{midi_number}"
    mappings = _active_mappings()
    mappings[key] = {
        'type':       midi_type,
        'number':     midi_number,
        'path':       path,
        'min':        d.get('min_value', 0),
        'max':        d.get('max_value', 100),
        'mode':       d.get('mapping_mode', 'local'),
        'channel':    d.get('midi_channel', 1),
        'value_mode': d.get('value_mode', 'absolute'),
        'invert':     bool(d.get('invert', False)),
        'use_14bit':  bool(d.get('use_14bit', False)),
        'name':       d.get('name', path),
    }
    _save_active_mappings(mappings)
    return jsonify({'success': True})


@midi_bp.route('/api/midi/mappings/<midi_type>/<int:midi_number>', methods=['DELETE'])
def delete_mapping(midi_type, midi_number):
    key      = f"{midi_type}:{midi_number}"
    mappings = _active_mappings()
    if key not in mappings:
        return jsonify({'success': False, 'error': 'Mapping not found'}), 404
    del mappings[key]
    _save_active_mappings(mappings)
    return jsonify({'success': True})


# ── Profiles CRUD ─────────────────────────────────────────────────────────────

@midi_bp.route('/api/midi/profiles', methods=['GET'])
def get_profiles():
    data   = _load_profiles()
    active = data.get('active_profile')
    result = [
        {
            'name':          p['name'],
            'description':   p.get('description', ''),
            'mapping_count': len(p.get('mappings', {})),
            'is_active':     p['name'] == active,
        }
        for p in data.get('profiles', [])
    ]
    return jsonify({'success': True, 'profiles': result, 'active': active})


@midi_bp.route('/api/midi/profiles', methods=['POST'])
def create_profile():
    d    = request.get_json() or {}
    name = d.get('name')
    if not name:
        return jsonify({'success': False, 'error': 'name required'}), 400
    data = _load_profiles()
    if any(p['name'] == name for p in data['profiles']):
        return jsonify({'success': False, 'error': 'Profile already exists'}), 409
    data['profiles'].append({'name': name, 'description': d.get('description', ''), 'mappings': {}})
    _save_profiles(data)
    return jsonify({'success': True})


@midi_bp.route('/api/midi/profiles/switch', methods=['POST'])
def switch_profile():
    name = (request.get_json() or {}).get('name')
    data = _load_profiles()
    if not any(p['name'] == name for p in data['profiles']):
        return jsonify({'success': False, 'error': 'Profile not found'}), 404
    data['active_profile'] = name
    _save_profiles(data)
    return jsonify({'success': True, 'active_profile': name})


@midi_bp.route('/api/midi/profiles/duplicate', methods=['POST'])
def duplicate_profile():
    d        = request.get_json() or {}
    source   = d.get('source')
    new_name = d.get('name')
    data     = _load_profiles()
    src      = next((p for p in data['profiles'] if p['name'] == source), None)
    if not src:
        return jsonify({'success': False, 'error': 'Source not found'}), 404
    new_profile        = copy.deepcopy(src)
    new_profile['name'] = new_name
    data['profiles'].append(new_profile)
    _save_profiles(data)
    return jsonify({'success': True})


@midi_bp.route('/api/midi/profiles/<name>/export', methods=['GET'])
def export_profile(name):
    data    = _load_profiles()
    profile = next((p for p in data['profiles'] if p['name'] == name), None)
    if not profile:
        return jsonify({'success': False, 'error': 'Not found'}), 404
    r = make_response(json.dumps(profile, indent=2))
    r.headers['Content-Type']        = 'application/json'
    r.headers['Content-Disposition'] = f'attachment; filename={name}.midi_profile.json'
    return r


@midi_bp.route('/api/midi/profiles/import', methods=['POST'])
def import_profile():
    profile = request.get_json()
    if not profile or 'name' not in profile:
        return jsonify({'success': False, 'error': 'Invalid profile data'}), 400
    data = _load_profiles()
    if any(p['name'] == profile['name'] for p in data['profiles']):
        profile = copy.deepcopy(profile)
        profile['name'] += ' (imported)'
    data['profiles'].append(profile)
    _save_profiles(data)
    return jsonify({'success': True, 'profile': profile['name']})


@midi_bp.route('/api/midi/profiles/<name>', methods=['DELETE'])
def delete_profile(name):
    if name == 'Default':
        return jsonify({'success': False, 'error': 'Cannot delete Default profile'}), 400
    data = _load_profiles()
    data['profiles'] = [p for p in data['profiles'] if p['name'] != name]
    if data.get('active_profile') == name:
        data['active_profile'] = 'Default'
    _save_profiles(data)
    return jsonify({'success': True})


# ── MIDI Clock REST ───────────────────────────────────────────────────────────

@midi_bp.route('/api/midi/devices', methods=['GET'])
def get_midi_devices():
    from ..midi_clock import get_midi_clock_manager
    mgr = get_midi_clock_manager()
    return jsonify({
        'success':        True,
        'input_devices':  mgr.get_input_devices(),
        'output_devices': mgr.get_output_devices(),
    })


@midi_bp.route('/api/midi/clock/connect-input', methods=['POST'])
def clock_connect_input():
    from ..midi_clock import get_midi_clock_manager
    d   = request.get_json() or {}
    mgr = get_midi_clock_manager()
    ok  = mgr.connect_input(d.get('device'))
    return jsonify({'success': ok, 'device': mgr.input_device_name})


@midi_bp.route('/api/midi/clock/disconnect-input', methods=['POST'])
def clock_disconnect_input():
    from ..midi_clock import get_midi_clock_manager
    get_midi_clock_manager().disconnect_input()
    return jsonify({'success': True})


@midi_bp.route('/api/midi/clock/connect-output', methods=['POST'])
def clock_connect_output():
    from ..midi_clock import get_midi_clock_manager
    d   = request.get_json() or {}
    mgr = get_midi_clock_manager()
    ok  = mgr.connect_output(d.get('device'), d.get('bpm', 120.0))
    return jsonify({'success': ok, 'device': mgr.output_device_name})


@midi_bp.route('/api/midi/clock/disconnect-output', methods=['POST'])
def clock_disconnect_output():
    from ..midi_clock import get_midi_clock_manager
    get_midi_clock_manager().disconnect_output()
    return jsonify({'success': True})


@midi_bp.route('/api/midi/clock/start', methods=['POST'])
def clock_send_start():
    from ..midi_clock import get_midi_clock_manager
    get_midi_clock_manager().send_start()
    return jsonify({'success': True})


@midi_bp.route('/api/midi/clock/continue', methods=['POST'])
def clock_send_continue():
    from ..midi_clock import get_midi_clock_manager
    get_midi_clock_manager().send_continue()
    return jsonify({'success': True})


@midi_bp.route('/api/midi/clock/stop', methods=['POST'])
def clock_send_stop():
    from ..midi_clock import get_midi_clock_manager
    get_midi_clock_manager().send_stop()
    return jsonify({'success': True})


@midi_bp.route('/api/midi/clock/set-bpm', methods=['POST'])
def clock_set_bpm():
    from ..midi_clock import get_midi_clock_manager
    d   = request.get_json() or {}
    mgr = get_midi_clock_manager()
    mgr.set_output_bpm(d.get('bpm', 120.0))
    return jsonify({'success': True, 'bpm': mgr.output_bpm})


@midi_bp.route('/api/midi/clock/status', methods=['GET'])
def clock_status():
    from ..midi_clock import get_midi_clock_manager
    return jsonify({'success': True, 'status': get_midi_clock_manager().get_status()})


# ── Initialisation ────────────────────────────────────────────────────────────

def _start_clock_broadcast(socketio_instance):
    """Push MIDI clock status to all clients at 20 Hz."""
    from ..midi_clock import get_midi_clock_manager

    def _loop():
        while True:
            try:
                socketio_instance.emit('midi_clock_update', get_midi_clock_manager().get_status())
            except Exception:
                pass
            time.sleep(0.05)

    threading.Thread(target=_loop, daemon=True, name="midi-clock-broadcast").start()


def init_midi_api(app, socketio_instance):
    """Register the MIDI blueprint and start the clock broadcast thread."""
    app.register_blueprint(midi_bp)
    _start_clock_broadcast(socketio_instance)

    # Register the midi_input SocketIO event handler
    @socketio_instance.on('midi_input')
    def handle_midi_input(data):
        """Browser sends raw MIDI CC; backend resolves mapping and broadcasts midi_apply."""
        midi_type   = data.get('type', 'cc')
        midi_number = data.get('number')
        value       = data.get('value', 0)
        key         = f"{midi_type}:{midi_number}"
        mapping     = _active_mappings().get(key)
        if not mapping:
            return
        socketio_instance.emit('midi_apply', {
            'type':   midi_type,
            'number': midi_number,
            'value':  value,
            'path':   mapping['path'],
            'mode':   mapping.get('mode', 'local'),
            'min':    mapping.get('min', 0),
            'max':    mapping.get('max', 100),
        })

    logger.info("MIDI API initialized")
