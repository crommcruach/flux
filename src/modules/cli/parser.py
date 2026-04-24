"""
Argparse tree for the Flux CLI.

`build_parser()` → fully configured ArgumentParser
`parse(argv)` → (Namespace, parser) tuple, prints help and exits on error.
"""
import argparse
import sys

PLAYERS = ['video', 'artnet']
PLAYER_CHOICES = PLAYERS + ['all']

# ──────────────────────────────────────────────────────────────────────────────
# Custom formatter — wider help text, no positional/optional split noise
# ──────────────────────────────────────────────────────────────────────────────

class _Fmt(argparse.RawDescriptionHelpFormatter):
    def __init__(self, prog, **kw):
        kw.setdefault('max_help_position', 32)
        kw.setdefault('width', 100)
        super().__init__(prog, **kw)


# ──────────────────────────────────────────────────────────────────────────────
# Shared option adders
# ──────────────────────────────────────────────────────────────────────────────

def _add_player(p, *, default='video'):
    p.add_argument(
        '-p', '--player',
        choices=PLAYER_CHOICES,
        default=default,
        metavar='PLAYER',
        help='Target player: video | artnet | all  (default: %(default)s)',
    )

def _add_json(p):
    p.add_argument('--json', action='store_true', help='Machine-readable JSON output')

def _add_confirm(p):
    p.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')


# ──────────────────────────────────────────────────────────────────────────────
# Domain builders
# ──────────────────────────────────────────────────────────────────────────────

def _build_player(sub):
    p = sub.add_parser('player', help='Control playback', formatter_class=_Fmt)
    s = p.add_subparsers(dest='action', metavar='ACTION')
    s.required = True

    for cmd in ('play', 'pause', 'stop', 'clear'):
        sp = s.add_parser(cmd, help=f'{cmd.capitalize()} player', formatter_class=_Fmt)
        _add_player(sp)

    n = s.add_parser('next', help='Next clip in playlist', formatter_class=_Fmt)
    _add_player(n)

    pr = s.add_parser('prev', help='Previous clip in playlist', formatter_class=_Fmt)
    _add_player(pr)

    st = s.add_parser('status', help='Show player state', formatter_class=_Fmt)
    _add_player(st)
    _add_json(st)

    se = s.add_parser('set', help='Set a playback parameter', formatter_class=_Fmt,
                      description='Set a parameter on a player.\n\nparams: brightness, speed, loop, autoplay')
    _add_player(se)
    se.add_argument('param',
                    choices=['brightness', 'speed', 'loop', 'autoplay'],
                    help='Parameter name')
    se.add_argument('value', help='New value')

    sy = s.add_parser('sync', help='Sync all players to same frame', formatter_class=_Fmt)
    _ = sy  # no extra args


def _build_clip(sub):
    p = sub.add_parser('clip', help='Load and inspect clips', formatter_class=_Fmt)
    s = p.add_subparsers(dest='action', metavar='ACTION')
    s.required = True

    ld = s.add_parser('load', help='Load a clip into a player', formatter_class=_Fmt)
    ld.add_argument('path', help='Video file path (relative to video dir, or absolute)')
    _add_player(ld)

    cur = s.add_parser('current', help='Show currently loaded clip', formatter_class=_Fmt)
    _add_player(cur)
    _add_json(cur)


def _build_effect(sub):
    p = sub.add_parser('effect', help='Manage global player effects', formatter_class=_Fmt)
    s = p.add_subparsers(dest='action', metavar='ACTION')
    s.required = True

    ls = s.add_parser('list', help='List active effects', formatter_class=_Fmt)
    _add_player(ls)
    _add_json(ls)

    add = s.add_parser('add', help='Append an effect plugin', formatter_class=_Fmt)
    add.add_argument('plugin_id', help='Plugin ID, e.g. blur, chromakey')
    _add_player(add)

    rm = s.add_parser('remove', help='Remove effect by slot index', formatter_class=_Fmt)
    rm.add_argument('index', type=int, help='Effect slot (0-based)')
    _add_player(rm)

    se = s.add_parser('set', help='Set an effect parameter', formatter_class=_Fmt)
    se.add_argument('index', type=int, help='Effect slot')
    se.add_argument('param', help='Parameter name')
    se.add_argument('value', help='New value')
    _add_player(se)

    tog = s.add_parser('toggle', help='Enable/disable an effect slot', formatter_class=_Fmt)
    tog.add_argument('index', type=int, help='Effect slot')
    _add_player(tog)

    cl = s.add_parser('clear', help='Remove ALL effects', formatter_class=_Fmt)
    _add_player(cl)
    _add_confirm(cl)


def _build_session(sub):
    p = sub.add_parser('session', help='Save / restore session state', formatter_class=_Fmt)
    s = p.add_subparsers(dest='action', metavar='ACTION')
    s.required = True

    sv = s.add_parser('save', help='Save session to a named file', formatter_class=_Fmt)
    sv.add_argument('name', help='Name (no extension, no path)')

    ld = s.add_parser('load', help='Restore a saved session', formatter_class=_Fmt)
    ld.add_argument('filename', help='Filename from data/ directory')

    s.add_parser('list', help='List saved sessions', formatter_class=_Fmt)
    s.add_parser('snapshot', help='Take a quick snapshot to snapshots/', formatter_class=_Fmt)

    st = s.add_parser('status', help='Show live session summary', formatter_class=_Fmt)
    _add_json(st)

    dl = s.add_parser('delete', help='Delete a saved session', formatter_class=_Fmt)
    dl.add_argument('filename', help='Filename from data/ directory')
    _add_confirm(dl)


def _build_config(sub):
    p = sub.add_parser('config', help='Read / write config.json', formatter_class=_Fmt)
    s = p.add_subparsers(dest='action', metavar='ACTION')
    s.required = True

    g = s.add_parser('get', help='Get a value by dot-separated key', formatter_class=_Fmt)
    g.add_argument('key', help='e.g. paths.video_dir')

    se = s.add_parser('set', help='Set a value', formatter_class=_Fmt)
    se.add_argument('key', help='Dot-separated key')
    se.add_argument('value', help='New value (string; cast to int/float/bool automatically)')

    ls = s.add_parser('list', help='List all config keys', formatter_class=_Fmt)
    _add_json(ls)

    s.add_parser('reload', help='Reload config from disk', formatter_class=_Fmt)


def _build_content(sub):
    p = sub.add_parser('content', help='Browse the video library', formatter_class=_Fmt)
    s = p.add_subparsers(dest='action', metavar='ACTION')
    s.required = True

    ls = s.add_parser('list', help='List available video files', formatter_class=_Fmt)
    ls.add_argument('--path', default='', metavar='DIR', help='Subdirectory to list')
    _add_json(ls)


def _build_debug(sub):
    p = sub.add_parser('debug', help='Backend debug logging', formatter_class=_Fmt)
    s = p.add_subparsers(dest='action', metavar='ACTION')
    s.required = True

    en = s.add_parser('enable', help='Enable debug logging', formatter_class=_Fmt)
    en.add_argument('--module', default='', metavar='MODULE',
                    help='Scope to one module (e.g. modules.player.*)')

    dis = s.add_parser('disable', help='Disable debug logging', formatter_class=_Fmt)
    dis.add_argument('--module', default='', metavar='MODULE', help='Remove specific module')

    s.add_parser('status', help='Show current log level and debug modules', formatter_class=_Fmt)


def _build_perf(sub):
    p = sub.add_parser('perf', help='GPU pipeline performance metrics', formatter_class=_Fmt)
    s = p.add_subparsers(dest='action', metavar='ACTION')
    s.required = True

    m = s.add_parser('metrics', help='Show per-stage GPU timing', formatter_class=_Fmt)
    _add_player(m)
    _add_json(m)
    m.add_argument('--watch', action='store_true', help='Live updating (Ctrl-C to stop)')
    m.add_argument('--interval', type=float, default=1.0, metavar='S', help='Refresh seconds (default: 1.0)')

    st = s.add_parser('stage', help='Timing for one pipeline stage', formatter_class=_Fmt)
    st.add_argument('name', help='Stage name')

    s.add_parser('summary', help='Aggregated frame time breakdown', formatter_class=_Fmt)
    s.add_parser('enable',  help='Enable performance collection', formatter_class=_Fmt)
    s.add_parser('disable', help='Disable performance collection', formatter_class=_Fmt)


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level Flux CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog='flux',
        description='Flux — GPU-accelerated video compositor and ArtNet controller',
        formatter_class=_Fmt,
        epilog="Run 'flux <command> --help' for command-specific help.",
    )
    parser.add_argument('--version', action='version', version='flux 0.1.0')

    sub = parser.add_subparsers(dest='domain', metavar='COMMAND')
    sub.required = True

    _build_player(sub)
    _build_clip(sub)
    _build_effect(sub)
    _build_session(sub)
    _build_config(sub)
    _build_content(sub)
    _build_debug(sub)
    _build_perf(sub)

    return parser


def parse(argv: list) -> 'argparse.Namespace':
    """
    Parse *argv* (list of strings, without the program name).
    Exits with a usage message on parse error (argparse default behaviour).
    """
    parser = build_parser()
    # argparse prints help and calls sys.exit(2) on error — that's what we want
    return parser.parse_args(argv)
