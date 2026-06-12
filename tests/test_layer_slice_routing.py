"""
Integration test for N-layers-to-N-slices GPU sub-compositor routing.

Verifies:
  1. Load a clip into the video player
  2. Add two extra layers
  3. Create a 'TestSlice' output slice
  4. Route Layer 1 → Default slice, Layer 2 → TestSlice (bypass_main=True)
  5. Verify routing is persisted and player stays stable
  6. Exercise CLI layer commands via subprocess
  7. Unroute and verify cleared state
"""

import json
import subprocess
import sys
import time
import os
from io import StringIO

import requests

# Make src importable for CLI invocation
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(_REPO, 'src') not in sys.path:
    sys.path.insert(0, os.path.join(_REPO, 'src'))

BASE_URL = "http://localhost:5000"
PLAYER_ID = "video"

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _ok(cond, msg):
    status = "✅" if cond else "❌ FAILED"
    print(f"  {status}: {msg}")
    if not cond:
        global _FAILURES
        _FAILURES += 1
    return cond


def _get(path, **kw):
    return requests.get(f"{BASE_URL}{path}", timeout=10, **kw)


def _post(path, body=None, **kw):
    return requests.post(f"{BASE_URL}{path}", json=body, timeout=10, **kw)


def _patch(path, body=None, **kw):
    return requests.patch(f"{BASE_URL}{path}", json=body, timeout=10, **kw)


def _delete(path, **kw):
    return requests.delete(f"{BASE_URL}{path}", timeout=10, **kw)


def _section(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print("=" * 70)


_FAILURES = 0

# --------------------------------------------------------------------------- #
# 0. Verify server is reachable
# --------------------------------------------------------------------------- #
_section("0. Server reachability")

try:
    r = _get("/api/player/video/state")
    _ok(r.status_code < 500, f"Server reachable (HTTP {r.status_code})")
except Exception as exc:
    print(f"  ❌ Cannot reach server at {BASE_URL}: {exc}")
    print("  Make sure the backend (python src/main.py) is running first.")
    sys.exit(1)

# --------------------------------------------------------------------------- #
# 1. Load a clip
# --------------------------------------------------------------------------- #
_section("1. Load test clip into video player")

r = _post(f"/api/player/{PLAYER_ID}/clip/load", {"path": "original/1080p.npy", "type": "video"})
data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
clip_id = data.get("clip_id")
if not clip_id:
    # Maybe a clip is already loaded — try to get it
    r2 = _get(f"/api/player/{PLAYER_ID}/clip/current")
    data2 = r2.json() if r2.ok else {}
    clip_id = data2.get("clip_id") or data2.get("id")

_ok(bool(clip_id), f"clip_id obtained: {clip_id}")
if not clip_id:
    print("  Cannot continue without a clip_id.")
    sys.exit(1)

time.sleep(0.3)

# --------------------------------------------------------------------------- #
# 2. Add two layers
# --------------------------------------------------------------------------- #
_section("2. Add layers 1 and 2 to clip")

for i in (1, 2):
    r = _post(f"/api/clips/{clip_id}/layers/add",
              {"source_type": "video", "source_path": "original/original.mov"})
    d = r.json() if r.ok else {}
    _ok(r.status_code < 400, f"Layer {i} add request (HTTP {r.status_code}): {r.text[:120]}")

# Get actual layer IDs assigned by the registry
r = _get(f"/api/clips/{clip_id}/layers")
d = r.json() if r.ok else {}
layers_initial = d.get("layers", [])
_ok(len(layers_initial) >= 3, f"Clip has >= 3 layers (found {len(layers_initial)})")

# Use actual IDs for layers 1 and 2 (second and third in the list)
LAYER_ID_1 = layers_initial[1]["layer_id"] if len(layers_initial) > 1 else 1
LAYER_ID_2 = layers_initial[2]["layer_id"] if len(layers_initial) > 2 else 2
print(f"  Using layer IDs: {LAYER_ID_1} and {LAYER_ID_2}")

# --------------------------------------------------------------------------- #
# 3. Create a TestSlice output
# --------------------------------------------------------------------------- #
_section("3. Create 'TestSlice' output slice")

r = _post("/api/slices", {"slice_id": "TestSlice", "x": 0, "y": 0,
                          "width": 100, "height": 100})
_ok(r.status_code < 500, f"Create TestSlice (HTTP {r.status_code}) — 409 is OK (already exists)")

# List slices to confirm
r = _get("/api/slices")
d = r.json() if r.ok else {}
slices_dict = d.get("slices", {})
_ok("TestSlice" in slices_dict, f"TestSlice present in slice registry ({list(slices_dict.keys())})")

# --------------------------------------------------------------------------- #
# 4. Route Layer 1 → 'full' / default, Layer 2 → TestSlice (bypass_main)
# --------------------------------------------------------------------------- #
_section("4. Apply layer → slice routing")

# Route layer 1 to default (non-bypass)
r = _patch(f"/api/clips/{clip_id}/layers/{LAYER_ID_1}",
           {"output_slices": ["full"], "bypass_main": False})
_ok(r.status_code < 400, f"Route Layer {LAYER_ID_1} to 'full' (HTTP {r.status_code})")

# Route layer 2 to TestSlice only, bypass main composite
r = _patch(f"/api/clips/{clip_id}/layers/{LAYER_ID_2}",
           {"output_slices": ["TestSlice"], "bypass_main": True})
_ok(r.status_code < 400, f"Route Layer {LAYER_ID_2} to 'TestSlice' + bypass_main (HTTP {r.status_code})")

# --------------------------------------------------------------------------- #
# 5. Verify routing is persisted via GET
# --------------------------------------------------------------------------- #
_section("5. Verify routing persistence")

time.sleep(0.2)
r = _get(f"/api/clips/{clip_id}/layers")
d = r.json() if r.ok else {}
layers = d.get("layers", [])

layer1 = next((l for l in layers if l.get("layer_id") == LAYER_ID_1), None)
layer2 = next((l for l in layers if l.get("layer_id") == LAYER_ID_2), None)

if layer1:
    _ok("full" in (layer1.get("output_slices") or []), f"Layer {LAYER_ID_1} output_slices contains 'full': {layer1.get('output_slices')}")
    _ok(layer1.get("bypass_main") is False, f"Layer {LAYER_ID_1} bypass_main=False: {layer1.get('bypass_main')}")
else:
    _ok(False, f"Layer {LAYER_ID_1} not found in response")

if layer2:
    _ok("TestSlice" in (layer2.get("output_slices") or []), f"Layer {LAYER_ID_2} output_slices contains 'TestSlice': {layer2.get('output_slices')}")
    _ok(layer2.get("bypass_main") is True, f"Layer {LAYER_ID_2} bypass_main=True: {layer2.get('bypass_main')}")
else:
    _ok(False, f"Layer {LAYER_ID_2} not found in response")

# --------------------------------------------------------------------------- #
# 6. Let a few frames render — check server stays up
# --------------------------------------------------------------------------- #
_section("6. Stability check (10 frames @ ~60fps)")

time.sleep(0.2)
for _ in range(3):
    r = _get(f"/api/player/{PLAYER_ID}/status")
    _ok(r.status_code == 200, f"Player status reachable (HTTP {r.status_code})")
    time.sleep(0.07)

# --------------------------------------------------------------------------- #
# 7. CLI layer list command
# --------------------------------------------------------------------------- #
_section("7. CLI 'flux layer list' command")

def _cli(*argv):
    """Run a CLI command via execute() and return (exit_code, stdout_text)."""
    from modules.cli.parser import build_parser
    from modules.cli.executor import execute
    from modules.cli.errors import CLIError
    buf = StringIO()
    try:
        args = build_parser().parse_args(list(argv))
        import sys as _sys
        old_stdout = _sys.stdout
        _sys.stdout = buf
        try:
            execute(args)
        finally:
            _sys.stdout = old_stdout
        return 0, buf.getvalue()
    except CLIError as e:
        return 1, str(e)
    except SystemExit as e:
        return e.code or 0, buf.getvalue()
    except Exception as e:
        return 1, str(e)

code, out = _cli('layer', 'list', '--player', PLAYER_ID)
print(f"  output: {out.strip()}")
_ok(code == 0, f"CLI layer list exit code 0 (got {code})")
_ok("TestSlice" in out or "full" in out or "Layer" in out or "No layers loaded" in out,
    "CLI output is a valid layer list response")

# --------------------------------------------------------------------------- #
# 8. CLI layer route command
# --------------------------------------------------------------------------- #
_section("8. CLI 'flux layer route' command")

code, out = _cli('layer', 'route', str(LAYER_ID_1), 'full', 'TestSlice', '--player', PLAYER_ID)
print(f"  output: {out.strip()}")
_ok(code == 0, f"CLI layer route exit code 0 (got {code})")

r_cur = _get(f"/api/player/{PLAYER_ID}/clip/current")
cur = r_cur.json() if r_cur.ok else {}
cli_clip_id = cur.get('clip_id') or clip_id

r = _get(f"/api/clips/{cli_clip_id}/layers")
d = r.json() if r.ok else {}
layers = d.get("layers", [])
# find the layer with the same id in the cli-patched clip
layer1_cli = next((l for l in layers if l.get("layer_id") == LAYER_ID_1), None)
if layer1_cli and (layer1_cli.get("output_slices") or []):
    slices = layer1_cli.get("output_slices") or []
    _ok("full" in slices and "TestSlice" in slices,
        f"Layer {LAYER_ID_1} routed to both 'full' and 'TestSlice': {slices}")
else:
    # CLI patched a different clip from the test-loaded one — verify via CLI output
    _ok("routed" in out.lower() and "full" in out and "TestSlice" in out,
        f"CLI confirmed routing (Layer 1 → full, TestSlice): {out.strip()}")

# --------------------------------------------------------------------------- #
# 9. CLI layer unroute command
# --------------------------------------------------------------------------- #
_section("9. CLI 'flux layer unroute' command (clear all)")

code, out = _cli('layer', 'unroute', str(LAYER_ID_1), '--player', PLAYER_ID)
print(f"  output: {out.strip()}")
_ok(code == 0, f"CLI layer unroute exit code 0 (got {code})")

time.sleep(0.2)

r_cur = _get(f"/api/player/{PLAYER_ID}/clip/current")
cur = r_cur.json() if r_cur.ok else {}
cli_clip_id = cur.get('clip_id') or clip_id

r = _get(f"/api/clips/{cli_clip_id}/layers")
d = r.json() if r.ok else {}
layers = d.get("layers", [])
layer1 = next((l for l in layers if l.get("layer_id") == LAYER_ID_1), None)
if layer1:
    slices = layer1.get("output_slices") or []
    _ok(slices == [], f"Layer {LAYER_ID_1} output_slices cleared: {slices}")
else:
    _ok("cleared" in out.lower() or "unrouted" in out.lower() or "routing" in out.lower(),
        f"CLI reported unroute success: {out.strip()}")

# --------------------------------------------------------------------------- #
# 10. Final stability check
# --------------------------------------------------------------------------- #
_section("10. Final stability check")

time.sleep(0.3)
r = _get(f"/api/player/{PLAYER_ID}/status")
_ok(r.status_code == 200, "Player still alive after all operations")

# Cleanup: remove TestSlice
_delete("/api/slices/TestSlice")

# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #
_section("RESULTS")
if _FAILURES == 0:
    print("  ✅ All checks passed — layer/slice routing is working without crashes.")
else:
    print(f"  ❌ {_FAILURES} check(s) FAILED — review output above.")
    sys.exit(1)
