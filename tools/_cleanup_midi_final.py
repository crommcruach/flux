"""Remove lines 171-211 (0-based 170-210) from midi-learn.js — grid coord block"""
path = "frontend/js/midi-learn.js"
lines = open(path, encoding="utf-8").readlines()

# Lines 171-211 are 0-based indices 170-210 (inclusive)
# That's: frameClipId, framePlayer, blank, grid comment, gs, defaultPlayer/Col/Row, if block, blank
# Keep everything before line 171 (index 170) and from line 212 (index 211) onward
del lines[170:211]

open(path, "w", encoding="utf-8").writelines(lines)

# Verify
js = open(path, encoding="utf-8").read()
remaining = [kw for kw in ['frameClipId', 'framePlayer', '_midiGridState', 'defaultPlayer', 'defaultCol', 'defaultRow',
                            'gridPlayer', 'gridCol', 'gridRow', '_updateGridHint', '_resolveGrid', '_sameParam', '_formatBadge']
             if kw in js]
print("Remaining grid refs:", remaining if remaining else "NONE")
print("Total lines:", len(lines))
