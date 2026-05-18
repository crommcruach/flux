"""Remove grid MIDI targeting from midi-learn.js and midi-display.css"""

# ── midi-learn.js ──────────────────────────────────────────────────────────
js_path = "frontend/js/midi-learn.js"
js = open(js_path, encoding="utf-8").read()

# 1. _onMIDIMessage: remove grid resolution, revert to plain pattern match
old_routing = """        // Resolve grid target clip ID (if grid coordinates are stored)
        const targetClipId = _resolveGridClipId(mapping);

        document.querySelectorAll('.midi-param-frame').forEach(frame => {
            if (targetClipId !== null) {
                // Grid-targeted: match by clip ID + param suffix
                if (frame.dataset.clipId !== targetClipId) return;
                if (!_sameParamSuffix(frame.dataset.paramPath, mapping.path)) return;
            } else {
                // Wildcard/pattern matching
                if (!matchesMidiPattern(frame.dataset.paramPath, mapping.path)) return;
            }
            _applyValueToFrame(frame, scaled);
        });"""

new_routing = """        document.querySelectorAll('.midi-param-frame').forEach(frame => {
            if (!matchesMidiPattern(frame.dataset.paramPath, mapping.path)) return;
            _applyValueToFrame(frame, scaled);
        });"""

print("routing found:", old_routing in js)
js = js.replace(old_routing, new_routing)

# 2. _openSidebarForFrame: remove grid coord computation block
old_open_grid = """        const frameClipId = frame.dataset.clipId || '';
        const framePlayer = frame.dataset.player || 'clip';

        // \u2500\u2500 Determine grid coordinates from frame \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        const gs = window._midiGridState;
        let defaultPlayer = (gs?.selectedClipPlayerType) || 'video';
        let defaultCol    = -1;  // -1 = currently selected
        let defaultRow    = -1;  // -1 = any layer

        if (frameClipId && gs) {
            // Which player owns this clip?
            for (const [pid, cfg] of Object.entries(gs.playerConfigs ?? {})) {
                const idx = cfg.files?.findIndex(f => f.id === frameClipId);
                if (idx !== undefined && idx >= 0) {
                    defaultPlayer = pid;
                    defaultCol    = idx;
                    defaultRow    = 0;  // base clip
                    break;
                }
            }
            // Is this clip a layer (check clipLayers for all base clips)?
            if (gs.clipLayers) {
                for (const [baseClipId, layers] of Object.entries(gs.clipLayers)) {
                    const layerObj = layers.find(l => l.clip_id === frameClipId);
                    if (layerObj) {
                        defaultRow = layerObj.layer_id;  // layer_id = 1, 2, 3...
                        // Now find base clip col in playlist
                        for (const [pid, cfg] of Object.entries(gs.playerConfigs ?? {})) {
                            const idx = cfg.files?.findIndex(f => f.id === baseClipId);
                            if (idx !== undefined && idx >= 0) {
                                defaultPlayer = pid;
                                defaultCol    = idx;
                                break;
                            }
                        }
                        break;
                    }
                }
            }
        }"""

new_open_grid = ""  # remove entirely

print("open_grid found:", old_open_grid in js)
js = js.replace(old_open_grid, new_open_grid)

# 3. _openSidebarForFrame: remove grid field setVal calls in existing/else blocks
old_set_existing = """        if (existing) {
            _setVal('midiPlayer',   existing.grid_player ?? defaultPlayer);
            _setVal('midiGridCol',  existing.grid_col    ?? defaultCol);
            _setVal('midiGridRow',  existing.grid_row    ?? defaultRow);
            _setVal('midiChannel',  existing.channel    ?? 1);"""
new_set_existing = """        if (existing) {
            _setVal('midiChannel',  existing.channel    ?? 1);"""
print("set_existing found:", old_set_existing in js)
js = js.replace(old_set_existing, new_set_existing)

old_set_else = """        } else {
            _setVal('midiPlayer',   defaultPlayer);
            _setVal('midiGridCol',  defaultCol);
            _setVal('midiGridRow',  defaultRow);
            _setVal('midiChannel',  1);"""
new_set_else = """        } else {
            _setVal('midiChannel',  1);"""
print("set_else found:", old_set_else in js)
js = js.replace(old_set_else, new_set_else)

# 4. Remove _updateGridHint() call at end of sidebar open
js = js.replace("\n        _updateGridHint();\n        sidebar.classList.add('open');",
                "\n        sidebar.classList.add('open');")

# 5. applyMapping: remove grid vars and fields from POST + cache
old_apply = """        const valueMode  = _getRadio('midiMode') || 'absolute';
        const gridPlayer = _getVal('midiPlayer') || 'video';
        const gridCol    = parseInt(_getVal('midiGridCol') ?? -1);
        const gridRow    = parseInt(_getVal('midiGridRow') ?? -1);"""
new_apply = """        const valueMode  = _getRadio('midiMode') || 'absolute';"""
print("apply vars found:", old_apply in js)
js = js.replace(old_apply, new_apply)

old_post_grid = """                    use_14bit:      use14bit,
                    grid_player:    gridPlayer,
                    grid_col:       gridCol,
                    grid_row:       gridRow,
                    name:           name,"""
new_post_grid = """                    use_14bit:      use14bit,
                    name:           name,"""
print("post grid found:", old_post_grid in js)
js = js.replace(old_post_grid, new_post_grid)

old_cache_grid = """                    invert, use_14bit: use14bit,
                    grid_player: gridPlayer, grid_col: gridCol, grid_row: gridRow,
                    name,"""
new_cache_grid = """                    invert, use_14bit: use14bit, name,"""
print("cache grid found:", old_cache_grid in js)
js = js.replace(old_cache_grid, new_cache_grid)

# 6. Badge in applyMapping: revert to simple CH/CC format
old_badge_apply = "                if (badge) badge.textContent = _formatBadge(channel, ccNumber, gridPlayer, gridCol, gridRow);"
new_badge_apply = "                if (badge) badge.textContent = `CH${channel} CC${ccNumber}`;"
print("badge apply found:", old_badge_apply in js)
js = js.replace(old_badge_apply, new_badge_apply)

# 7. _applyBadgesToAllFrames: revert badge to simple format
old_badge_all = "                    if (badge) badge.textContent = _formatBadge(m.channel ?? 1, m.number, m.grid_player || 'video', m.grid_col ?? -1, m.grid_row ?? -1);"
new_badge_all = "                    if (badge) badge.textContent = `CH${m.channel ?? 1} CC${m.number}`;"
print("badge all found:", old_badge_all in js)
js = js.replace(old_badge_all, new_badge_all)

# 8. Remove helper functions: _resolveGridClipId, _sameParamSuffix, _formatBadge, _updateGridHint
import re
# Remove each named function block (from the jsdoc comment to closing brace + blank line)
funcs_to_remove = [
    "_resolveGridClipId",
    "_sameParamSuffix",
    "_formatBadge",
    "_updateGridHint",
]
for fname in funcs_to_remove:
    # Match: optional jsdoc comment + function declaration + body (balanced braces)
    pattern = r'/\*\*[^*]*\*+(?:[^/*][^*]*\*+)*/\s*\nfunction ' + fname + r'\b'
    m = re.search(pattern, js)
    if not m:
        # Try without jsdoc
        pattern = r'function ' + fname + r'\b'
        m = re.search(pattern, js)
    if m:
        start = m.start()
        # Find start of jsdoc if present
        jsdoc_pattern = r'/\*\*[^*]*\*+(?:[^/*][^*]*\*+)*/\s*\nfunction ' + fname + r'\b'
        jdm = re.search(jsdoc_pattern, js)
        if jdm:
            start = jdm.start()
        # Walk forward to find the matching closing brace
        pos = js.index('{', start)
        depth = 0
        end = pos
        while end < len(js):
            if js[end] == '{':
                depth += 1
            elif js[end] == '}':
                depth -= 1
                if depth == 0:
                    end += 1
                    break
            end += 1
        # Consume trailing newlines
        while end < len(js) and js[end] == '\n':
            end += 1
        print(f"removing {fname}: chars {start}-{end}")
        js = js[:start] + js[end:]
    else:
        print(f"WARNING: {fname} not found")

open(js_path, "w", encoding="utf-8").write(js)
print("\nDone. Remaining grid refs:", js.count("gridPlayer") + js.count("gridCol") + js.count("gridRow") + js.count("_midiGridState"))

# ── midi-display.css ───────────────────────────────────────────────────────
css_path = "frontend/css/midi-display.css"
css = open(css_path, encoding="utf-8").read()

old_css = """
/* \u2500\u2500 Grid target inputs (Col / Row) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */

.midi-grid-target-row {
    display: flex;
    gap: 8px;
}
.midi-grid-target-row > div {
    flex: 1;
}
.midi-grid-target-row input[type="number"] {
    width: 100%;
    text-align: center;
}
.midi-grid-hint {
    font-size: 0.65rem;
    color: rgba(0, 255, 255, 0.6);
    text-align: center;
    margin-top: -6px;
    font-style: italic;
}"""
print("\ncss grid block found:", old_css in css)
css = css.replace(old_css, "")
open(css_path, "w", encoding="utf-8").write(css)
print("CSS done.")
