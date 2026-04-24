"""
Unit tests for the new Flux CLI (parser + executor).

These tests are completely offline — no running backend required.
They mock api_client.api_call to verify:
  1. Parser correctly maps argv → Namespace fields
  2. Executor calls the right API endpoint with the right method/body
  3. Output is printed correctly for success and error responses
  4. CLIError is raised / displayed on API failures
"""
import json
import sys
import os
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock, call
from argparse import Namespace

# ── add project src to path ───────────────────────────────────────────────────
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, 'src'))

from modules.cli.parser import build_parser, parse
from modules.cli.executor import execute, _cast_value, _dotget, _dotset, _players_for
from modules.cli.errors import CLIError
from modules.cli.colors import colorize  # smoke-test import


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse(*argv):
    """Parse argv list and return Namespace (raises SystemExit on bad input)."""
    return build_parser().parse_args(list(argv))


def _exec_mock(argv_list, api_responses):
    """
    Execute CLI command with mocked api_call.

    api_responses: list of dicts returned by successive api_call() calls.
    Returns (stdout_text, calls_made).
    """
    call_log = []
    resp_iter = iter(api_responses)

    def fake_api(method, path, data=None, params=None, timeout=5.0):
        call_log.append({'method': method, 'path': path, 'data': data, 'params': params})
        try:
            return next(resp_iter)
        except StopIteration:
            return {'success': True}

    buf = StringIO()
    args = _parse(*argv_list)
    with patch('modules.cli.executor.api_call', side_effect=fake_api), \
         patch('sys.stdout', buf):
        execute(args)

    return buf.getvalue(), call_log


# ─────────────────────────────────────────────────────────────────────────────
# 1. Parser tests
# ─────────────────────────────────────────────────────────────────────────────

class TestParser(unittest.TestCase):

    def test_player_play_defaults(self):
        ns = _parse('player', 'play')
        self.assertEqual(ns.domain, 'player')
        self.assertEqual(ns.action, 'play')
        self.assertEqual(ns.player, 'video')

    def test_player_play_artnet(self):
        ns = _parse('player', 'play', '-p', 'artnet')
        self.assertEqual(ns.player, 'artnet')

    def test_player_play_all(self):
        ns = _parse('player', 'play', '-p', 'all')
        self.assertEqual(ns.player, 'all')

    def test_player_set(self):
        ns = _parse('player', 'set', 'brightness', '0.8')
        self.assertEqual(ns.domain, 'player')
        self.assertEqual(ns.action, 'set')
        self.assertEqual(ns.param, 'brightness')
        self.assertEqual(ns.value, '0.8')

    def test_player_status_json(self):
        ns = _parse('player', 'status', '--json')
        self.assertTrue(ns.json)

    def test_clip_load(self):
        ns = _parse('clip', 'load', 'intro.npy')
        self.assertEqual(ns.domain, 'clip')
        self.assertEqual(ns.action, 'load')
        self.assertEqual(ns.path, 'intro.npy')
        self.assertEqual(ns.player, 'video')

    def test_clip_load_artnet(self):
        ns = _parse('clip', 'load', 'loop.mp4', '-p', 'artnet')
        self.assertEqual(ns.player, 'artnet')

    def test_effect_add(self):
        ns = _parse('effect', 'add', 'blur')
        self.assertEqual(ns.domain, 'effect')
        self.assertEqual(ns.action, 'add')
        self.assertEqual(ns.plugin_id, 'blur')

    def test_effect_set(self):
        ns = _parse('effect', 'set', '0', 'radius', '10')
        self.assertEqual(ns.index, 0)
        self.assertEqual(ns.param, 'radius')
        self.assertEqual(ns.value, '10')

    def test_effect_remove(self):
        ns = _parse('effect', 'remove', '2')
        self.assertEqual(ns.index, 2)

    def test_effect_toggle(self):
        ns = _parse('effect', 'toggle', '1')
        self.assertEqual(ns.index, 1)

    def test_effect_clear_confirm(self):
        ns = _parse('effect', 'clear', '--confirm')
        self.assertTrue(ns.confirm)

    def test_session_save(self):
        ns = _parse('session', 'save', 'show_night1')
        self.assertEqual(ns.name, 'show_night1')

    def test_session_load(self):
        ns = _parse('session', 'load', 'backup.json')
        self.assertEqual(ns.filename, 'backup.json')

    def test_session_status_json(self):
        ns = _parse('session', 'status', '--json')
        self.assertTrue(ns.json)

    def test_config_get(self):
        ns = _parse('config', 'get', 'paths.video_dir')
        self.assertEqual(ns.key, 'paths.video_dir')

    def test_config_set(self):
        ns = _parse('config', 'set', 'artnet.fps', '44')
        self.assertEqual(ns.key, 'artnet.fps')
        self.assertEqual(ns.value, '44')

    def test_perf_metrics_watch(self):
        ns = _parse('perf', 'metrics', '--watch', '--interval', '0.5')
        self.assertTrue(ns.watch)
        self.assertAlmostEqual(ns.interval, 0.5)

    def test_perf_stage(self):
        ns = _parse('perf', 'stage', 'clip_effects')
        self.assertEqual(ns.name, 'clip_effects')

    def test_debug_enable_module(self):
        ns = _parse('debug', 'enable', '--module', 'modules.player.*')
        self.assertEqual(ns.module, 'modules.player.*')

    def test_content_list_path(self):
        ns = _parse('content', 'list', '--path', 'subdir')
        self.assertEqual(ns.path, 'subdir')

    def test_invalid_domain_exits(self):
        with self.assertRaises(SystemExit):
            _parse('nonexistent', 'action')

    def test_player_invalid_player_choice_exits(self):
        with self.assertRaises(SystemExit):
            _parse('player', 'play', '-p', 'invalid')

    def test_help_exits_cleanly(self):
        with self.assertRaises(SystemExit) as cm:
            _parse('--help')
        self.assertEqual(cm.exception.code, 0)

    def test_player_help_exits_cleanly(self):
        with self.assertRaises(SystemExit) as cm:
            _parse('player', '--help')
        self.assertEqual(cm.exception.code, 0)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Executor — player commands
# ─────────────────────────────────────────────────────────────────────────────

class TestExecutorPlayer(unittest.TestCase):

    def test_play_calls_correct_endpoint(self):
        _, calls = _exec_mock(
            ['player', 'play', '-p', 'video'],
            [{'success': True, 'player_id': 'video', 'status': 'playing'}],
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['method'], 'POST')
        self.assertEqual(calls[0]['path'], '/api/player/video/play')

    def test_pause_artnet(self):
        _, calls = _exec_mock(
            ['player', 'pause', '-p', 'artnet'],
            [{'success': True}],
        )
        self.assertEqual(calls[0]['path'], '/api/player/artnet/pause')

    def test_stop_default_player(self):
        _, calls = _exec_mock(
            ['player', 'stop'],
            [{'success': True}],
        )
        self.assertEqual(calls[0]['path'], '/api/player/video/stop')

    def test_play_all_calls_both_players(self):
        _, calls = _exec_mock(
            ['player', 'play', '-p', 'all'],
            [{'success': True}, {'success': True}],
        )
        paths = [c['path'] for c in calls]
        self.assertIn('/api/player/video/play', paths)
        self.assertIn('/api/player/artnet/play', paths)

    def test_next_calls_next_endpoint(self):
        _, calls = _exec_mock(
            ['player', 'next'],
            [{'success': True}],
        )
        self.assertEqual(calls[0]['path'], '/api/player/video/next')

    def test_prev_calls_previous_endpoint(self):
        _, calls = _exec_mock(
            ['player', 'prev'],
            [{'success': True}],
        )
        self.assertEqual(calls[0]['path'], '/api/player/video/previous')

    def test_status_prints_human_output(self):
        out, _ = _exec_mock(
            ['player', 'status'],
            [{
                'success': True,
                'player_id': 'video',
                'is_playing': True,
                'is_paused': False,
                'current_frame': 42,
                'total_frames': 100,
                'current_video': 'test.npy',
                'playlist': [],
                'playlist_index': 0,
                'loop': True,
                'autoplay': True,
            }],
        )
        self.assertIn('video', out)
        self.assertIn('test.npy', out)
        self.assertIn('42/100', out)

    def test_status_json_output(self):
        fake = {'success': True, 'player_id': 'video', 'is_playing': False,
                'is_paused': False, 'current_frame': 0, 'total_frames': 0,
                'current_video': None, 'playlist': [], 'playlist_index': -1,
                'loop': False, 'autoplay': False}
        out, _ = _exec_mock(['player', 'status', '--json'], [fake])
        parsed = json.loads(out)
        self.assertEqual(parsed['player_id'], 'video')

    def test_play_api_error_shows_error(self):
        out, _ = _exec_mock(
            ['player', 'play'],
            [{'success': False, 'error': 'Kein Video geladen'}],
        )
        self.assertIn('Kein Video geladen', out)

    def test_set_loop(self):
        _, calls = _exec_mock(
            ['player', 'set', 'loop', 'true'],
            [{'success': True}],
        )
        self.assertEqual(calls[0]['method'], 'POST')
        self.assertIn('/api/player/video/settings', calls[0]['path'])
        self.assertEqual(calls[0]['data'], {'loop': True})

    def test_set_autoplay(self):
        _, calls = _exec_mock(
            ['player', 'set', 'autoplay', 'false'],
            [{'success': True}],
        )
        self.assertFalse(calls[0]['data']['autoplay'])


# ─────────────────────────────────────────────────────────────────────────────
# 3. Executor — clip commands
# ─────────────────────────────────────────────────────────────────────────────

class TestExecutorClip(unittest.TestCase):

    def test_clip_load(self):
        _, calls = _exec_mock(
            ['clip', 'load', 'intro.npy'],
            [{'success': True, 'clip_id': 'abc123'}],
        )
        self.assertEqual(calls[0]['method'], 'POST')
        self.assertEqual(calls[0]['path'], '/api/player/video/clip/load')
        self.assertEqual(calls[0]['data']['path'], 'intro.npy')
        self.assertEqual(calls[0]['data']['type'], 'video')

    def test_clip_load_artnet(self):
        _, calls = _exec_mock(
            ['clip', 'load', 'loop.mp4', '-p', 'artnet'],
            [{'success': True}],
        )
        self.assertEqual(calls[0]['path'], '/api/player/artnet/clip/load')

    def test_clip_load_error(self):
        out, _ = _exec_mock(
            ['clip', 'load', 'notexist.npy'],
            [{'success': False, 'error': 'Video not found: notexist.npy'}],
        )
        self.assertIn('Video not found', out)

    def test_clip_current_shows_clip(self):
        out, calls = _exec_mock(
            ['clip', 'current'],
            [{'success': True, 'current_video': 'intro.npy', 'clip_id': 'abc123'}],
        )
        self.assertIn('intro.npy', out)
        self.assertEqual(calls[0]['path'], '/api/player/video/status')

    def test_clip_current_json(self):
        out, _ = _exec_mock(
            ['clip', 'current', '--json'],
            [{'success': True, 'current_video': 'test.npy', 'clip_id': 'xyz'}],
        )
        parsed = json.loads(out)
        self.assertEqual(parsed['clip'], 'test.npy')


# ─────────────────────────────────────────────────────────────────────────────
# 4. Executor — effect commands
# ─────────────────────────────────────────────────────────────────────────────

class TestExecutorEffect(unittest.TestCase):

    def test_effect_list(self):
        _, calls = _exec_mock(
            ['effect', 'list'],
            [{'success': True, 'effects': [{'plugin_id': 'blur', 'enabled': True, 'params': {'radius': 5}}]}],
        )
        self.assertEqual(calls[0]['path'], '/api/player/video/effects')

    def test_effect_list_json(self):
        out, _ = _exec_mock(
            ['effect', 'list', '--json'],
            [{'success': True, 'effects': [{'plugin_id': 'blur', 'params': {}}]}],
        )
        parsed = json.loads(out)
        self.assertEqual(parsed['effects'][0]['plugin_id'], 'blur')

    def test_effect_add(self):
        _, calls = _exec_mock(
            ['effect', 'add', 'chromakey'],
            [{'success': True, 'index': 0}],
        )
        self.assertEqual(calls[0]['method'], 'POST')
        self.assertEqual(calls[0]['path'], '/api/player/video/effects/add')
        self.assertEqual(calls[0]['data']['plugin_id'], 'chromakey')

    def test_effect_remove(self):
        _, calls = _exec_mock(
            ['effect', 'remove', '1'],
            [{'success': True}],
        )
        self.assertEqual(calls[0]['method'], 'DELETE')
        self.assertIn('/effects/1', calls[0]['path'])

    def test_effect_set(self):
        _, calls = _exec_mock(
            ['effect', 'set', '0', 'radius', '12'],
            [{'success': True}],
        )
        self.assertEqual(calls[0]['method'], 'PUT')
        self.assertIn('/effects/0/parameter', calls[0]['path'])
        self.assertEqual(calls[0]['data']['name'], 'radius')
        self.assertEqual(calls[0]['data']['value'], 12)  # cast to int

    def test_effect_toggle(self):
        _, calls = _exec_mock(
            ['effect', 'toggle', '0'],
            [{'success': True, 'enabled': False}],
        )
        self.assertIn('/effects/0/toggle', calls[0]['path'])

    def test_effect_clear_with_confirm(self):
        _, calls = _exec_mock(
            ['effect', 'clear', '--confirm'],
            [{'success': True}],
        )
        self.assertIn('/effects/clear', calls[0]['path'])

    def test_effect_clear_without_confirm_prompts(self):
        """Without --confirm, should ask user; 'n' cancels."""
        calls_made = []

        def fake_api(method, path, data=None, params=None, timeout=5.0):
            calls_made.append(path)
            return {'success': True}

        args = _parse('effect', 'clear')
        buf = StringIO()
        with patch('modules.cli.executor.api_call', side_effect=fake_api), \
             patch('builtins.input', return_value='n'), \
             patch('sys.stdout', buf):
            execute(args)

        self.assertEqual(len(calls_made), 0)  # no API call made
        self.assertIn('Cancelled', buf.getvalue())


# ─────────────────────────────────────────────────────────────────────────────
# 5. Executor — session commands
# ─────────────────────────────────────────────────────────────────────────────

class TestExecutorSession(unittest.TestCase):

    def test_session_save(self):
        _, calls = _exec_mock(
            ['session', 'save', 'show_night1'],
            [{'success': True, 'filename': 'show_night1_20260424.json'}],
        )
        self.assertEqual(calls[0]['method'], 'POST')
        self.assertEqual(calls[0]['path'], '/api/session/save')
        self.assertEqual(calls[0]['data']['name'], 'show_night1')

    def test_session_load(self):
        _, calls = _exec_mock(
            ['session', 'load', 'backup.json'],
            [{'success': True}],
        )
        self.assertEqual(calls[0]['path'], '/api/session/restore')
        self.assertEqual(calls[0]['data']['filename'], 'backup.json')

    def test_session_list(self):
        _, calls = _exec_mock(
            ['session', 'list'],
            [{'success': True, 'sessions': [{'filename': 'a.json', 'created': '2026-04-24', 'size': '12 KB'}]}],
        )
        self.assertEqual(calls[0]['method'], 'GET')
        self.assertEqual(calls[0]['path'], '/api/session/list')

    def test_session_status_json(self):
        fake = {'success': True, 'state': {'video_player': {'is_playing': True}, 'artnet_player': {}}}
        out, _ = _exec_mock(['session', 'status', '--json'], [fake])
        parsed = json.loads(out)
        self.assertIn('state', parsed)

    def test_session_snapshot(self):
        _, calls = _exec_mock(
            ['session', 'snapshot'],
            [{'success': True, 'filename': 'snap_20260424.json'}],
        )
        self.assertEqual(calls[0]['path'], '/api/session/snapshot')

    def test_session_delete_confirm(self):
        _, calls = _exec_mock(
            ['session', 'delete', 'old.json', '--confirm'],
            [{'success': True}],
        )
        self.assertEqual(calls[0]['method'], 'POST')
        self.assertEqual(calls[0]['data']['filename'], 'old.json')

    def test_session_delete_cancelled(self):
        calls_made = []

        def fake_api(method, path, data=None, params=None, timeout=5.0):
            calls_made.append(path)
            return {'success': True}

        args = _parse('session', 'delete', 'old.json')
        with patch('modules.cli.executor.api_call', side_effect=fake_api), \
             patch('builtins.input', return_value='n'), \
             patch('sys.stdout', StringIO()):
            execute(args)

        self.assertEqual(len(calls_made), 0)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Executor — config commands
# ─────────────────────────────────────────────────────────────────────────────

class TestExecutorConfig(unittest.TestCase):

    def test_config_get_existing_key(self):
        out, _ = _exec_mock(
            ['config', 'get', 'artnet.fps'],
            [{'artnet': {'fps': 30, 'target_ip': '127.0.0.1'}}],
        )
        self.assertIn('artnet.fps', out)
        self.assertIn('30', out)

    def test_config_get_missing_key_shows_error(self):
        out, _ = _exec_mock(
            ['config', 'get', 'does.not.exist'],
            [{'some': 'data'}],
        )
        self.assertIn('not found', out.lower())

    def test_config_set(self):
        fake_current = {'artnet': {'fps': 30}}
        _, calls = _exec_mock(
            ['config', 'set', 'artnet.fps', '44'],
            [fake_current, {'status': 'success'}],
        )
        # Second call is the POST with updated config
        self.assertEqual(calls[1]['method'], 'POST')
        self.assertEqual(calls[1]['data']['artnet']['fps'], 44)

    def test_config_list(self):
        _, calls = _exec_mock(
            ['config', 'list'],
            [{'paths': {'video_dir': 'video'}, 'artnet': {'fps': 30}}],
        )
        self.assertEqual(calls[0]['method'], 'GET')
        self.assertEqual(calls[0]['path'], '/api/config')


# ─────────────────────────────────────────────────────────────────────────────
# 7. Executor — content commands
# ─────────────────────────────────────────────────────────────────────────────

class TestExecutorContent(unittest.TestCase):

    def test_content_list(self):
        _, calls = _exec_mock(
            ['content', 'list'],
            [{'success': True, 'tree': [{'type': 'folder', 'name': 'video', 'children': []}]}],
        )
        self.assertEqual(calls[0]['method'], 'GET')
        self.assertIn('/api/files/tree', calls[0]['path'])

    def test_content_list_with_path(self):
        _, calls = _exec_mock(
            ['content', 'list', '--path', 'subdir'],
            [{'success': True, 'tree': []}],
        )
        self.assertEqual(calls[0]['params'], {'path': 'subdir'})

    def test_content_list_json(self):
        fake = {'success': True, 'files': ['x.npy'], 'dirs': []}
        out, _ = _exec_mock(['content', 'list', '--json'], [fake])
        parsed = json.loads(out)
        self.assertIn('files', parsed)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Executor — debug commands
# ─────────────────────────────────────────────────────────────────────────────

class TestExecutorDebug(unittest.TestCase):

    def test_debug_enable(self):
        fake_cfg = {'app': {'console_log_level': 'INFO', 'debug_modules': []}}
        _, calls = _exec_mock(
            ['debug', 'enable'],
            [fake_cfg, {'status': 'success'}],
        )
        posted = calls[1]['data']
        self.assertEqual(posted['app']['console_log_level'], 'DEBUG')

    def test_debug_enable_module(self):
        fake_cfg = {'app': {'console_log_level': 'INFO', 'debug_modules': []}}
        _, calls = _exec_mock(
            ['debug', 'enable', '--module', 'modules.player.*'],
            [fake_cfg, {'status': 'success'}],
        )
        posted = calls[1]['data']
        self.assertIn('modules.player.*', posted['app']['debug_modules'])

    def test_debug_disable(self):
        fake_cfg = {'app': {'console_log_level': 'DEBUG', 'debug_modules': ['mod']}}
        _, calls = _exec_mock(
            ['debug', 'disable'],
            [fake_cfg, {'status': 'success'}],
        )
        posted = calls[1]['data']
        self.assertEqual(posted['app']['console_log_level'], 'INFO')
        self.assertEqual(posted['app']['debug_modules'], [])

    def test_debug_status(self):
        out, _ = _exec_mock(
            ['debug', 'status'],
            [{'app': {'console_log_level': 'DEBUG', 'debug_modules': ['mod_a']}}],
        )
        self.assertIn('DEBUG', out)
        self.assertIn('mod_a', out)


# ─────────────────────────────────────────────────────────────────────────────
# 9. Helper functions
# ─────────────────────────────────────────────────────────────────────────────

class TestHelpers(unittest.TestCase):

    def test_cast_int(self):
        self.assertEqual(_cast_value('42'), 42)

    def test_cast_float(self):
        self.assertAlmostEqual(_cast_value('3.14'), 3.14)

    def test_cast_bool_true(self):
        self.assertIs(_cast_value('true'), True)
        self.assertIs(_cast_value('True'), True)

    def test_cast_bool_false(self):
        self.assertIs(_cast_value('false'), False)

    def test_cast_str(self):
        self.assertEqual(_cast_value('hello'), 'hello')

    def test_dotget_nested(self):
        d = {'a': {'b': {'c': 42}}}
        self.assertEqual(_dotget(d, 'a.b.c'), 42)

    def test_dotget_missing(self):
        self.assertIsNone(_dotget({}, 'a.b'))

    def test_dotset_deep(self):
        d = {'a': {'b': 1}}
        result = _dotset(d, 'a.b', 99)
        self.assertEqual(result['a']['b'], 99)
        # Original unchanged
        self.assertEqual(d['a']['b'], 1)

    def test_dotset_creates_missing(self):
        result = _dotset({}, 'x.y.z', 'val')
        self.assertEqual(result['x']['y']['z'], 'val')

    def test_players_for_single(self):
        ns = _parse('player', 'play', '-p', 'video')
        self.assertEqual(_players_for(ns), ['video'])

    def test_players_for_all(self):
        ns = _parse('player', 'play', '-p', 'all')
        self.assertEqual(_players_for(ns), ['video', 'artnet'])


# ─────────────────────────────────────────────────────────────────────────────
# 10. CLIError display
# ─────────────────────────────────────────────────────────────────────────────

class TestCLIError(unittest.TestCase):

    def test_display_message(self):
        err = CLIError('Something went wrong', 'Try again')
        buf = StringIO()
        with patch('sys.stdout', buf):
            err.display()
        self.assertIn('Something went wrong', buf.getvalue())
        self.assertIn('Try again', buf.getvalue())

    def test_display_with_examples(self):
        err = CLIError('Oops', examples=['player play', 'player status'])
        buf = StringIO()
        with patch('sys.stdout', buf):
            err.display()
        out = buf.getvalue()
        self.assertIn('player play', out)
        self.assertIn('player status', out)

    def test_api_error_raises_cli_error(self):
        """CLIError is raised (not printed) when api_call raises it."""
        def bad_api(method, path, data=None, params=None, timeout=5.0):
            raise CLIError('Cannot connect to Flux backend')

        args = _parse('player', 'play')
        with patch('modules.cli.executor.api_call', side_effect=bad_api):
            with self.assertRaises(CLIError):
                execute(args)


# ─────────────────────────────────────────────────────────────────────────────
# 11. Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases(unittest.TestCase):

    def test_effect_list_empty(self):
        out, _ = _exec_mock(
            ['effect', 'list'],
            [{'success': True, 'effects': []}],
        )
        self.assertIn('none', out.lower())

    def test_content_list_empty(self):
        out, _ = _exec_mock(
            ['content', 'list'],
            [{'success': True, 'files': [], 'dirs': []}],
        )
        self.assertIn('empty', out.lower())

    def test_perf_stage_missing_raises(self):
        def fake_api(method, path, data=None, params=None, timeout=5.0):
            return {'success': True, 'metrics': {'video': {'stages': {'clip_effects': 2.1}}}}

        args = _parse('perf', 'stage', 'nonexistent_stage')
        with patch('modules.cli.executor.api_call', side_effect=fake_api):
            with self.assertRaises(CLIError):
                execute(args)

    def test_effect_set_value_cast_float(self):
        _, calls = _exec_mock(
            ['effect', 'set', '0', 'opacity', '0.75'],
            [{'success': True}],
        )
        self.assertAlmostEqual(calls[0]['data']['value'], 0.75)

    def test_config_set_value_cast_int(self):
        fake_cfg = {'artnet': {'fps': 30}}
        _, calls = _exec_mock(
            ['config', 'set', 'artnet.fps', '60'],
            [fake_cfg, {'status': 'success'}],
        )
        self.assertEqual(calls[1]['data']['artnet']['fps'], 60)

    def test_session_list_empty(self):
        out, _ = _exec_mock(
            ['session', 'list'],
            [{'success': True, 'sessions': []}],
        )
        self.assertIn('No saved sessions', out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
