"""Verify all grid MIDI changes"""
js  = open("frontend/js/midi-learn.js", encoding="utf-8").read()
py  = open("src/modules/api/midi.py", encoding="utf-8").read()
css = open("frontend/css/midi-display.css", encoding="utf-8").read()
html = open("frontend/player.html", encoding="utf-8").read()

checks = [
    ("js: midiTarget gone",            "midiTarget" not in js),
    ("js: gridPlayer present",          "gridPlayer" in js),
    ("js: _formatBadge calls x2",       js.count("_formatBadge") >= 2),
    ("js: _resolveGridClipId defined",  "function _resolveGridClipId" in js),
    ("js: _sameParamSuffix defined",    "function _sameParamSuffix" in js),
    ("js: _formatBadge defined",        "function _formatBadge" in js),
    ("js: _updateGridHint defined",     "function _updateGridHint" in js),
    ("py: grid_player stored",          "grid_player" in py),
    ("py: grid_col stored",             "grid_col" in py),
    ("py: grid_row stored",             "grid_row" in py),
    ("py: old target field gone",       "'target':" not in py),
    ("css: .midi-grid-target-row",      ".midi-grid-target-row" in css),
    ("css: .midi-grid-hint",            ".midi-grid-hint" in css),
    ("html: oninput on Col/Row inputs", "_updateGridHint" in html),
]
for label, ok in checks:
    print(("OK  " if ok else "FAIL") + label)
