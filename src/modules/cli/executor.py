"""
Command executor — maps parsed argparse namespaces to backend API calls
and formats the results for the terminal.

Each `_cmd_<domain>_<action>` function receives the parsed Namespace and
calls `api_call()`.  It prints output and returns None.
"""
from __future__ import annotations

import json
import sys
import time
from argparse import Namespace
from typing import Callable

from .api_client import api_call
from .colors import colorize, print_status, print_table
from .errors import CLIError

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _players_for(args: Namespace) -> list[str]:
    """Expand 'all' to ['video', 'artnet'], else return single-item list."""
    p = getattr(args, 'player', 'video') or 'video'
    return ['video', 'artnet'] if p == 'all' else [p]


def _cast_value(raw: str):
    """Try to cast a string value to int, float, or bool; fallback to str."""
    if raw.lower() == 'true':
        return True
    if raw.lower() == 'false':
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _ok(r: dict) -> bool:
    return r.get('success', True)  # treat missing 'success' key as ok


def _require_ok(r: dict, context: str = ''):
    if not _ok(r):
        msg = r.get('error') or r.get('message') or 'Unknown API error'
        raise CLIError(f"{context}: {msg}" if context else msg)


# ──────────────────────────────────────────────────────────────────────────────
# player
# ──────────────────────────────────────────────────────────────────────────────

def _cmd_player_play(args: Namespace):
    for pid in _players_for(args):
        r = api_call('POST', f'/api/player/{pid}/play')
        if _ok(r):
            print_status('success', f"Player '{pid}' playing")
        else:
            print_status('error', f"Player '{pid}': {r.get('error', 'failed')}")


def _cmd_player_pause(args: Namespace):
    for pid in _players_for(args):
        r = api_call('POST', f'/api/player/{pid}/pause')
        if _ok(r):
            print_status('success', f"Player '{pid}' paused")
        else:
            print_status('error', f"Player '{pid}': {r.get('error', 'failed')}")


def _cmd_player_stop(args: Namespace):
    for pid in _players_for(args):
        r = api_call('POST', f'/api/player/{pid}/stop')
        if _ok(r):
            print_status('success', f"Player '{pid}' stopped")
        else:
            print_status('error', f"Player '{pid}': {r.get('error', 'failed')}")


def _cmd_player_clear(args: Namespace):
    for pid in _players_for(args):
        r = api_call('POST', f'/api/player/{pid}/clear')
        if _ok(r):
            print_status('success', f"Player '{pid}' cleared")
        else:
            print_status('error', f"Player '{pid}': {r.get('error', 'failed')}")


def _cmd_player_next(args: Namespace):
    for pid in _players_for(args):
        r = api_call('POST', f'/api/player/{pid}/next')
        if _ok(r):
            clip = r.get('current_clip', r.get('clip', ''))
            print_status('success', f"Player '{pid}' → next" + (f": {clip}" if clip else ''))
        else:
            print_status('error', f"Player '{pid}': {r.get('error', 'failed')}")


def _cmd_player_prev(args: Namespace):
    for pid in _players_for(args):
        r = api_call('POST', f'/api/player/{pid}/previous')
        if _ok(r):
            clip = r.get('current_clip', r.get('clip', ''))
            print_status('success', f"Player '{pid}' → prev" + (f": {clip}" if clip else ''))
        else:
            print_status('error', f"Player '{pid}': {r.get('error', 'failed')}")


def _cmd_player_status(args: Namespace):
    for pid in _players_for(args):
        r = api_call('GET', f'/api/player/{pid}/status')
        _require_ok(r, f"player status ({pid})")

        if getattr(args, 'json', False):
            print(json.dumps(r, indent=2))
            continue

        state = colorize('playing', 'green') if r.get('is_playing') else (
            colorize('paused', 'yellow') if r.get('is_paused') else colorize('stopped', 'red')
        )
        clip = r.get('current_video') or colorize('(none)', 'dim')
        frame = r.get('current_frame', 0)
        total = r.get('total_frames', 0)
        progress = f"{frame}/{total}" if total else str(frame)
        playlist_len = len(r.get('playlist', []))

        print(f"\n{colorize(pid, 'cyan', bold=True)} player")
        print(f"  {'state':<16} {state}")
        print(f"  {'clip':<16} {clip}")
        print(f"  {'frame':<16} {progress}")
        print(f"  {'playlist':<16} {playlist_len} clip(s) @ index {r.get('playlist_index', -1)}")
        print(f"  {'loop':<16} {r.get('loop', False)}")
        print(f"  {'autoplay':<16} {r.get('autoplay', False)}")
        print()


def _cmd_player_set(args: Namespace):
    """Set brightness, speed, loop, or autoplay via effect-parameter API."""
    value = _cast_value(args.value)

    # Map param names to the API endpoint / effect plugin / param name
    PARAM_MAP = {
        # param → (effect_plugin_id, effect_param_name)  for effect-based params
        'brightness': ('color', 'brightness'),
        'speed':      ('transport', 'speed'),
        'loop':       None,    # handled via player settings
        'autoplay':   None,
    }

    for pid in _players_for(args):
        mapping = PARAM_MAP.get(args.param)

        if args.param == 'loop':
            r = api_call('POST', f'/api/player/{pid}/settings',
                         data={'loop': bool(value)})
        elif args.param == 'autoplay':
            r = api_call('POST', f'/api/player/{pid}/settings',
                         data={'autoplay': bool(value)})
        elif mapping:
            plugin_id, param_name = mapping
            # Use the player-level effects parameter endpoint
            # First find the effect index
            effects_r = api_call('GET', f'/api/player/{pid}/effects')
            effects = effects_r.get('effects', [])
            idx = next((i for i, e in enumerate(effects) if e.get('plugin_id') == plugin_id), None)
            if idx is None:
                print_status('error', f"Player '{pid}': no '{plugin_id}' effect in chain — cannot set {args.param}")
                continue
            r = api_call('PUT', f'/api/player/{pid}/effects/{idx}/parameter',
                         data={'name': param_name, 'value': value})
        else:
            print_status('error', f"Unknown param '{args.param}'")
            return

        if _ok(r):
            print_status('success', f"Player '{pid}': {args.param} = {value}")
        else:
            print_status('error', f"Player '{pid}': {r.get('error', 'failed')}")


def _cmd_player_sync(args: Namespace):
    r = api_call('GET', '/api/player/sync_status')
    _require_ok(r, 'player sync')
    if getattr(args, 'json', False):
        print(json.dumps(r, indent=2))
        return
    master = r.get('master_playlist') or colorize('(none)', 'dim')
    slaves = ', '.join(r.get('slaves', [])) or colorize('(none)', 'dim')
    print(f"\n{colorize('Sync status', 'cyan', bold=True)}")
    print(f"  {'master':<20} {master}")
    print(f"  {'slaves':<20} {slaves}")
    if r.get('master_clip_index') is not None:
        print(f"  {'master clip idx':<20} {r['master_clip_index']}")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# clip
# ──────────────────────────────────────────────────────────────────────────────

def _cmd_clip_load(args: Namespace):
    for pid in _players_for(args):
        r = api_call('POST', f'/api/player/{pid}/clip/load',
                     data={'path': args.path, 'type': 'video'})
        if _ok(r):
            print_status('success', f"Loaded '{args.path}' into player '{pid}' (clip_id: {r.get('clip_id', '?')})")
        else:
            print_status('error', f"Player '{pid}': {r.get('error', 'failed')}")


def _cmd_clip_current(args: Namespace):
    for pid in _players_for(args):
        r = api_call('GET', f'/api/player/{pid}/status')
        _require_ok(r, f"clip current ({pid})")
        if getattr(args, 'json', False):
            print(json.dumps({'player': pid, 'clip': r.get('current_video'), 'clip_id': r.get('clip_id')}, indent=2))
            continue
        clip = r.get('current_video') or colorize('(none)', 'dim')
        clip_id = r.get('clip_id', '')
        print(f"{colorize(pid, 'cyan')}: {clip}" + (f"  {colorize(clip_id[:8], 'dim')}" if clip_id else ''))


# ──────────────────────────────────────────────────────────────────────────────
# effect
# ──────────────────────────────────────────────────────────────────────────────

def _cmd_effect_list(args: Namespace):
    for pid in _players_for(args):
        r = api_call('GET', f'/api/player/{pid}/effects')
        _require_ok(r, f"effect list ({pid})")
        effects = r.get('effects', [])

        if getattr(args, 'json', False):
            print(json.dumps({'player': pid, 'effects': effects}, indent=2))
            continue

        print(f"\n{colorize(pid, 'cyan', bold=True)} effects ({len(effects)})")
        if not effects:
            print(f"  {colorize('(none)', 'dim')}")
        else:
            for i, e in enumerate(effects):
                enabled = '' if e.get('enabled', True) else colorize(' [disabled]', 'dim')
                params = e.get('params', e.get('parameters', {}))
                param_str = '  '.join(f"{k}={v}" for k, v in params.items()) if params else ''
                print(f"  [{i}] {colorize(e.get('plugin_id', '?'), 'yellow')}{enabled}"
                      + (f"  {colorize(param_str, 'dim')}" if param_str else ''))
        print()


def _cmd_effect_add(args: Namespace):
    for pid in _players_for(args):
        r = api_call('POST', f'/api/player/{pid}/effects/add',
                     data={'plugin_id': args.plugin_id})
        if _ok(r):
            idx = r.get('index', '?')
            print_status('success', f"Player '{pid}': added '{args.plugin_id}' at slot {idx}")
        else:
            print_status('error', f"Player '{pid}': {r.get('error') or r.get('message', 'failed')}")


def _cmd_effect_remove(args: Namespace):
    for pid in _players_for(args):
        r = api_call('DELETE', f'/api/player/{pid}/effects/{args.index}')
        if _ok(r):
            print_status('success', f"Player '{pid}': removed effect at slot {args.index}")
        else:
            print_status('error', f"Player '{pid}': {r.get('error') or r.get('message', 'failed')}")


def _cmd_effect_set(args: Namespace):
    value = _cast_value(args.value)
    for pid in _players_for(args):
        r = api_call('PUT', f'/api/player/{pid}/effects/{args.index}/parameter',
                     data={'name': args.param, 'value': value})
        if _ok(r):
            print_status('success', f"Player '{pid}': effect[{args.index}].{args.param} = {value}")
        else:
            print_status('error', f"Player '{pid}': {r.get('error') or r.get('message', 'failed')}")


def _cmd_effect_toggle(args: Namespace):
    for pid in _players_for(args):
        r = api_call('POST', f'/api/player/{pid}/effects/{args.index}/toggle')
        if _ok(r):
            enabled = r.get('enabled')
            state = colorize('enabled', 'green') if enabled else colorize('disabled', 'yellow')
            print_status('success', f"Player '{pid}': effect[{args.index}] {state}")
        else:
            print_status('error', f"Player '{pid}': {r.get('error') or r.get('message', 'failed')}")


def _cmd_effect_clear(args: Namespace):
    if not getattr(args, 'confirm', False):
        try:
            resp = input(f"Remove ALL effects from player '{getattr(args, 'player', 'video')}'? [y/N] ")
            if resp.strip().lower() not in ('y', 'yes'):
                print(colorize('Cancelled.', 'yellow'))
                return
        except (EOFError, KeyboardInterrupt):
            print()
            return

    for pid in _players_for(args):
        r = api_call('POST', f'/api/player/{pid}/effects/clear')
        if _ok(r):
            print_status('success', f"Player '{pid}': all effects cleared")
        else:
            print_status('error', f"Player '{pid}': {r.get('error') or r.get('message', 'failed')}")


# ──────────────────────────────────────────────────────────────────────────────
# session
# ──────────────────────────────────────────────────────────────────────────────

def _cmd_session_save(args: Namespace):
    r = api_call('POST', '/api/session/save', data={'name': args.name})
    if _ok(r):
        print_status('success', f"Session saved as '{r.get('filename', args.name)}'")
    else:
        print_status('error', r.get('error', 'failed'))


def _cmd_session_load(args: Namespace):
    r = api_call('POST', '/api/session/restore', data={'filename': args.filename})
    if _ok(r):
        print_status('success', f"Session '{args.filename}' restored")
    else:
        print_status('error', r.get('error', 'failed'))


def _cmd_session_list(args: Namespace):
    r = api_call('GET', '/api/session/list')
    _require_ok(r, 'session list')
    sessions = r.get('sessions', [])
    if not sessions:
        print(colorize('No saved sessions.', 'dim'))
        return
    print_table(['Filename', 'Saved at', 'Size', 'Video', 'ArtNet'], [
        [s.get('filename', '?'), s.get('created', ''), s.get('size', ''),
         s.get('video_count', ''), s.get('artnet_count', '')]
        for s in sessions
    ])


def _cmd_session_snapshot(args: Namespace):
    r = api_call('POST', '/api/session/snapshot')
    if _ok(r):
        print_status('success', f"Snapshot saved: {r.get('filename', '?')}")
    else:
        print_status('error', r.get('error', 'failed'))


def _cmd_session_status(args: Namespace):
    r = api_call('GET', '/api/session/state')
    _require_ok(r, 'session status')
    if getattr(args, 'json', False):
        print(json.dumps(r, indent=2))
        return
    state = r.get('state', {})
    print(f"\n{colorize('Session state', 'cyan', bold=True)}")
    for key in sorted(state.keys()):
        val = state[key]
        if isinstance(val, dict):
            print(f"  {colorize(key, 'yellow')}: ({len(val)} entries)")
        elif isinstance(val, list):
            print(f"  {colorize(key, 'yellow')}: [{len(val)} items]")
        else:
            print(f"  {colorize(key, 'yellow')}: {val}")
    print()


def _cmd_session_delete(args: Namespace):
    if not getattr(args, 'confirm', False):
        try:
            resp = input(f"Delete session '{args.filename}'? [y/N] ")
            if resp.strip().lower() not in ('y', 'yes'):
                print(colorize('Cancelled.', 'yellow'))
                return
        except (EOFError, KeyboardInterrupt):
            print()
            return
    r = api_call('POST', '/api/session/delete', data={'filename': args.filename})
    if _ok(r):
        print_status('success', f"Deleted '{args.filename}'")
    else:
        print_status('error', r.get('error', 'failed'))


# ──────────────────────────────────────────────────────────────────────────────
# config
# ──────────────────────────────────────────────────────────────────────────────

def _dotget(d: dict, key: str):
    """Traverse a nested dict with a dot-separated key."""
    parts = key.split('.')
    for p in parts:
        if not isinstance(d, dict) or p not in d:
            return None
        d = d[p]
    return d


def _dotset(d: dict, key: str, value) -> dict:
    """Return a copy of d with value set at dot-separated key."""
    import copy
    d = copy.deepcopy(d)
    parts = key.split('.')
    node = d
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    node[parts[-1]] = value
    return d


def _cmd_config_get(args: Namespace):
    r = api_call('GET', '/api/config')
    val = _dotget(r, args.key)
    if val is None:
        print_status('error', f"Key '{args.key}' not found in config")
    else:
        print(f"{colorize(args.key, 'cyan')} = {json.dumps(val)}")


def _cmd_config_set(args: Namespace):
    current = api_call('GET', '/api/config')
    value = _cast_value(args.value)
    updated = _dotset(current, args.key, value)
    r = api_call('POST', '/api/config', data=updated)
    if r.get('status') == 'success' or _ok(r):
        print_status('success', f"{args.key} = {json.dumps(value)}")
    else:
        print_status('error', r.get('message') or r.get('error', 'failed'))


def _cmd_config_list(args: Namespace):
    r = api_call('GET', '/api/config')
    if getattr(args, 'json', False):
        print(json.dumps(r, indent=2))
        return

    def _flat(d, prefix=''):
        for k, v in d.items():
            full = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                yield from _flat(v, full)
            else:
                yield full, v

    rows = [(k, json.dumps(v)) for k, v in _flat(r)]
    print_table(['Key', 'Value'], rows)


def _cmd_config_reload(args: Namespace):
    print_status('error', 'Config reload endpoint does not exist. '
                 'Use \'config set <key> <value>\' to change a setting, '
                 'or restart the app to reload config.json from disk.')


# ──────────────────────────────────────────────────────────────────────────────
# content
# ──────────────────────────────────────────────────────────────────────────────

def _walk_tree(nodes: list, indent: int = 0):
    """Recursively print a files/tree response node list."""
    prefix = '  ' * indent
    for node in nodes:
        ntype = node.get('type', 'file')
        name = node.get('name', node.get('path', '?'))
        if ntype == 'folder':
            print(colorize(f"{prefix}{name}/", 'blue'))
            _walk_tree(node.get('children', []), indent + 1)
        else:
            size = node.get('size_human', '')
            line = f"{prefix}{name}"
            if size:
                line += f"  {colorize(size, 'dim')}"
            print(line)


def _cmd_content_list(args: Namespace):
    params = {}
    if getattr(args, 'path', ''):
        params['path'] = args.path

    r = api_call('GET', '/api/files/tree', params=params if params else None)
    _require_ok(r, 'content list')

    if getattr(args, 'json', False):
        print(json.dumps(r, indent=2))
        return

    tree = r.get('tree', [])
    if not tree:
        print(colorize('(empty)', 'dim'))
        return

    _walk_tree(tree)


# ──────────────────────────────────────────────────────────────────────────────
# debug
# ──────────────────────────────────────────────────────────────────────────────

def _cmd_debug_enable(args: Namespace):
    module = getattr(args, 'module', '') or ''
    r = api_call('GET', '/api/config')
    level = r.get('app', {}).get('console_log_level', 'INFO')
    debug_modules = r.get('app', {}).get('debug_modules', [])

    if module and module not in debug_modules:
        debug_modules = list(debug_modules) + [module]

    updated = _dotset(r, 'app.console_log_level', 'DEBUG')
    updated = _dotset(updated, 'app.debug_modules', debug_modules)
    r2 = api_call('POST', '/api/config', data=updated)
    if r2.get('status') == 'success' or _ok(r2):
        msg = 'Debug logging enabled'
        if module:
            msg += f" for module '{module}'"
        print_status('success', msg)
    else:
        print_status('error', r2.get('message') or r2.get('error', 'failed'))


def _cmd_debug_disable(args: Namespace):
    module = getattr(args, 'module', '') or ''
    r = api_call('GET', '/api/config')
    debug_modules = list(r.get('app', {}).get('debug_modules', []))

    if module:
        debug_modules = [m for m in debug_modules if m != module]
        updated = _dotset(r, 'app.debug_modules', debug_modules)
    else:
        updated = _dotset(r, 'app.console_log_level', 'INFO')
        updated = _dotset(updated, 'app.debug_modules', [])

    r2 = api_call('POST', '/api/config', data=updated)
    if r2.get('status') == 'success' or _ok(r2):
        msg = 'Debug logging disabled'
        if module:
            msg = f"Module '{module}' removed from debug_modules"
        print_status('success', msg)
    else:
        print_status('error', r2.get('message') or r2.get('error', 'failed'))


def _cmd_debug_status(args: Namespace):
    r = api_call('GET', '/api/config')
    level = r.get('app', {}).get('console_log_level', 'INFO')
    mods  = r.get('app', {}).get('debug_modules', [])
    print(f"  {'log level':<20} {colorize(level, 'cyan')}")
    print(f"  {'debug modules':<20} {', '.join(mods) if mods else colorize('(none)', 'dim')}")


# ──────────────────────────────────────────────────────────────────────────────
# perf
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_perf_metrics(data: dict):
    """Pretty-print performance metrics dict."""
    stages = data.get('stages', {})
    print(f"\n{colorize('GPU Pipeline Metrics', 'cyan', bold=True)}")
    print(f"  {'frame_time':<30} {data.get('frame_time_ms', 0):.2f} ms")
    print(f"  {'fps':<30} {data.get('fps', 0):.1f}")
    if stages:
        print(f"\n  {colorize('Stage', 'yellow'):<34} {colorize('ms', 'yellow')}")
        print(f"  {'─'*40}")
        for stage, ms in sorted(stages.items(), key=lambda x: -x[1]):
            bar_len = min(20, int(ms))
            bar = colorize('█' * bar_len, 'green' if ms < 5 else 'yellow' if ms < 15 else 'red')
            print(f"  {stage:<32}  {ms:6.2f}  {bar}")
    print()


def _cmd_perf_metrics(args: Namespace):
    pid = getattr(args, 'player', 'video') or 'video'
    if pid == 'all':
        pid = 'video'

    if getattr(args, 'watch', False):
        try:
            while True:
                # Clear lines (simple approach)
                print('\033[2J\033[H', end='')
                r = api_call('GET', '/api/performance/metrics')
                _require_ok(r, 'perf metrics')
                if getattr(args, 'json', False):
                    print(json.dumps(r, indent=2))
                else:
                    player_metrics = r.get('metrics', {}).get(pid, {})
                    _fmt_perf_metrics(player_metrics)
                time.sleep(getattr(args, 'interval', 1.0))
        except KeyboardInterrupt:
            print()
        return

    r = api_call('GET', '/api/performance/metrics')
    _require_ok(r, 'perf metrics')
    if getattr(args, 'json', False):
        print(json.dumps(r, indent=2))
    else:
        player_metrics = r.get('metrics', {}).get(pid, {})
        _fmt_perf_metrics(player_metrics)


def _cmd_perf_stage(args: Namespace):
    r = api_call('GET', '/api/performance/metrics')
    _require_ok(r, 'perf stage')
    metrics = r.get('metrics', {})
    # Use first available player's stages if not specified
    player_metrics = metrics.get('video', next(iter(metrics.values()), {}))
    stages = player_metrics.get('stages', {})
    ms = stages.get(args.name)
    if ms is None:
        raise CLIError(f"Stage '{args.name}' not found",
                       "Use 'perf metrics' to list available stages")
    print(f"  {colorize(args.name, 'cyan')}: {ms:.3f} ms")


def _cmd_perf_summary(args: Namespace):
    r = api_call('GET', '/api/performance/metrics')
    _require_ok(r, 'perf summary')
    metrics = r.get('metrics', {})
    if not metrics:
        print(colorize('No metrics available.', 'dim'))
        return
    for player_id, player_metrics in metrics.items():
        print(f"{colorize(player_id, 'cyan', bold=True)} player:")
        _fmt_perf_metrics(player_metrics)


def _cmd_perf_enable(args: Namespace):
    r = api_call('POST', '/api/performance/toggle', data={'enabled': True})
    if _ok(r):
        print_status('success', 'Performance collection enabled')
    else:
        print_status('error', r.get('error', 'failed'))


def _cmd_perf_disable(args: Namespace):
    r = api_call('POST', '/api/performance/toggle', data={'enabled': False})
    if _ok(r):
        print_status('success', 'Performance collection disabled')
    else:
        print_status('error', r.get('error', 'failed'))


# ──────────────────────────────────────────────────────────────────────────────
# Dispatch table
# ──────────────────────────────────────────────────────────────────────────────

_DISPATCH: dict[tuple, Callable] = {
    ('player', 'play'):    _cmd_player_play,
    ('player', 'pause'):   _cmd_player_pause,
    ('player', 'stop'):    _cmd_player_stop,
    ('player', 'clear'):   _cmd_player_clear,
    ('player', 'next'):    _cmd_player_next,
    ('player', 'prev'):    _cmd_player_prev,
    ('player', 'status'):  _cmd_player_status,
    ('player', 'set'):     _cmd_player_set,
    ('player', 'sync'):    _cmd_player_sync,

    ('clip', 'load'):      _cmd_clip_load,
    ('clip', 'current'):   _cmd_clip_current,

    ('effect', 'list'):    _cmd_effect_list,
    ('effect', 'add'):     _cmd_effect_add,
    ('effect', 'remove'):  _cmd_effect_remove,
    ('effect', 'set'):     _cmd_effect_set,
    ('effect', 'toggle'):  _cmd_effect_toggle,
    ('effect', 'clear'):   _cmd_effect_clear,

    ('session', 'save'):     _cmd_session_save,
    ('session', 'load'):     _cmd_session_load,
    ('session', 'list'):     _cmd_session_list,
    ('session', 'snapshot'): _cmd_session_snapshot,
    ('session', 'status'):   _cmd_session_status,
    ('session', 'delete'):   _cmd_session_delete,

    ('config', 'get'):     _cmd_config_get,
    ('config', 'set'):     _cmd_config_set,
    ('config', 'list'):    _cmd_config_list,
    ('config', 'reload'):  _cmd_config_reload,

    ('content', 'list'):   _cmd_content_list,

    ('debug', 'enable'):   _cmd_debug_enable,
    ('debug', 'disable'):  _cmd_debug_disable,
    ('debug', 'status'):   _cmd_debug_status,

    ('perf', 'metrics'):   _cmd_perf_metrics,
    ('perf', 'stage'):     _cmd_perf_stage,
    ('perf', 'summary'):   _cmd_perf_summary,
    ('perf', 'enable'):    _cmd_perf_enable,
    ('perf', 'disable'):   _cmd_perf_disable,
}


def execute(args: Namespace) -> None:
    """
    Execute the command described by *args* (as returned by `parse()`).

    Prints output to stdout. Raises CLIError on user errors (caller should
    call .display()). Re-raises unexpected exceptions unchanged.
    """
    key = (getattr(args, 'domain', ''), getattr(args, 'action', ''))
    handler = _DISPATCH.get(key)
    if handler is None:
        raise CLIError(f"Unknown command: {' '.join(k for k in key if k)}",
                       "Run 'flux --help' for a list of commands")
    handler(args)
