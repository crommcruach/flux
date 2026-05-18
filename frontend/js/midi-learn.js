/**
 * MIDI Learn Manager â€” Resolume-style visual MIDI binding.
 *
 * Interaction:
 *   Ctrl+M or toggle button   â†’ enter/exit MIDI learn mode
 *   Click any magenta frame   â†’ select it (dashed white), open left sidebar
 *   Sidebar "Learn CC" button â†’ arm for next CC input from MIDI device
 *   Sidebar "Map" button      â†’ save mapping to backend
 *   Sidebar "Unmap" button    â†’ delete mapping from backend
 *
 * Requires (globals): socket (SocketIO), showToast (toast-loader.js)
 * Web MIDI API: Chrome / Edge / Opera only.
 */
'use strict';

class VisualMIDILearnManager {
    constructor() {
        this.learnModeActive  = false;
        this.selectedFrame    = null;  // currently selected .midi-param-frame
        this.listeningForCC   = false; // "Learn CC" mode
        this.midiAccess       = null;
        this.mappings         = {};    // key "cc:N" â†’ mapping object (local cache)
        this._scanDebounce    = null;
        this._mutationObserver = null;

        this._initKeyboard();
        this._initMIDI();
        this._initMutationObserver();
        // Restore side preference
        const savedSide = localStorage.getItem('midiSidebarSide');
        if (savedSide === 'right') {
            document.getElementById('midiSidebar')?.classList.add('right');
        }
        // Initial scan after a short delay (player.js renders after DOMContentLoaded)
        setTimeout(() => this._refreshAllFrames(), 600);
    }

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Keyboard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    _initKeyboard() {
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'm') {
                e.preventDefault();
                this.toggleLearnMode();
            }
            if (e.key === 'Escape' && this.learnModeActive) {
                if (this.listeningForCC) {
                    this._stopListeningCC();
                } else {
                    this.deselectFrame();
                }
            }
        });
    }

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Web MIDI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async _initMIDI() {
        if (!navigator.requestMIDIAccess) {
            console.warn('[MIDI] Web MIDI API not supported. Use Chrome or Edge.');
            return;
        }
        try {
            this.midiAccess = await navigator.requestMIDIAccess();
            this._attachMIDIInputs();
            this.midiAccess.onstatechange = () => this._attachMIDIInputs();
        } catch (err) {
            console.error('[MIDI] Access denied:', err);
        }
    }

    _attachMIDIInputs() {
        for (const input of this.midiAccess.inputs.values()) {
            input.onmidimessage = (e) => this._onMIDIMessage(e);
        }
    }

    _onMIDIMessage(ev) {
        const [status, number, value] = ev.data;
        const statusType = status & 0xF0;
        const channel    = (status & 0x0F) + 1;

        // Only CC messages
        if (statusType !== 0xB0) return;

        // â”€â”€ "Learn CC" armed: capture channel + CC â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if (this.listeningForCC) {
            this._stopListeningCC();
            const channelInput = document.getElementById('midiChannel');
            const ccInput      = document.getElementById('midiCC');
            if (channelInput) channelInput.value = channel;
            if (ccInput)      ccInput.value      = number;
            if (typeof showToast === 'function') showToast(`Captured CH${channel} CC${number}`, 'success');
            return;
        }

        // â”€â”€ Route incoming CC to mapped parameters â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        const key     = `cc:${number}`;
        const mapping = this.mappings[key];
        if (!mapping) return;

        let normalised = value / 127; // 0..1
        if (mapping.invert) normalised = 1 - normalised;
        const scaled = mapping.min + normalised * (mapping.max - mapping.min);

        document.querySelectorAll('.midi-param-frame').forEach(frame => {
            if (!matchesMidiPattern(frame.dataset.paramPath, mapping.path)) return;
            _applyValueToFrame(frame, scaled);
        });
    }

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ MutationObserver â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    _initMutationObserver() {
        this._mutationObserver = new MutationObserver(() => {
            clearTimeout(this._scanDebounce);
            this._scanDebounce = setTimeout(() => {
                this._applyBadgesToAllFrames();
            }, 350);
        });

        const root = document.getElementById('effectsPanel') ||
                     document.querySelector('.app-layout')   ||
                     document.body;
        this._mutationObserver.observe(root, { childList: true, subtree: true });
    }

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Learn mode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    toggleLearnMode() {
        this.learnModeActive = !this.learnModeActive;
        document.body.classList.toggle('midi-learn-mode', this.learnModeActive);
        document.getElementById('midiLearnToggle')?.classList.toggle('active', this.learnModeActive);

        if (this.learnModeActive) {
            this._refreshAllFrames();
            if (typeof showToast === 'function') showToast('MIDI Learn â€” click a parameter to bind', 'info');
        } else {
            this._stopListeningCC();
            this.deselectFrame();
            this.closeSidebar();
            if (typeof showToast === 'function') showToast('MIDI Learn off', 'info');
        }
        this._updateMappingBadge();
    }

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Frame selection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    selectFrame(frame) {
        if (!this.learnModeActive) return;

        // Deselect previous
        this.selectedFrame?.classList.remove('midi-selected');
        this._stopListeningCC();

        this.selectedFrame = frame;
        frame.classList.add('midi-selected');
        this._openSidebarForFrame(frame);
    }

    deselectFrame() {
        this.selectedFrame?.classList.remove('midi-selected');
        this.selectedFrame = null;
    }

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Sidebar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    _openSidebarForFrame(frame) {
        const sidebar = document.getElementById('midiSidebar');
        if (!sidebar) return;

        const path      = frame.dataset.paramPath || '';
        const name      = frame.dataset.paramName || path.split('.').pop() || 'Parameter';
        const pMin      = parseFloat(frame.dataset.paramMin ?? 0);
        const pMax      = parseFloat(frame.dataset.paramMax ?? 100);
        // ── Show selection info ──────────────────────────────────────────────
        const infoEl = document.getElementById('midiSidebarInfo');
        if (infoEl) {
            infoEl.classList.add('has-param');
            infoEl.innerHTML =
                `<div><strong>${name}</strong></div>` +
                `<div class="midi-sel-path" title="${path}">${path}</div>`;
        }

        // ── Look up existing mapping for this path ───────────────────────────
        const existing = Object.values(this.mappings).find(m => m.path === path);

        if (existing) {
            _setVal('midiChannel',  existing.channel    ?? 1);
            _setVal('midiCC',       existing.number     ?? 0);
            _setVal('midi14Bit',    existing.use_14bit  ?? false, 'check');
            _setVal('midiInvert',   existing.invert     ?? false, 'check');
            _setVal('midiRangeMin', existing.min        ?? pMin);
            _setVal('midiRangeMax', existing.max        ?? pMax);
            _setRadio('midiMode',   existing.value_mode ?? 'absolute');
        } else {
            _setVal('midiChannel',  1);
            _setVal('midiCC',       0);
            _setVal('midi14Bit',    false, 'check');
            _setVal('midiInvert',   false, 'check');
            _setVal('midiRangeMin', pMin);
            _setVal('midiRangeMax', pMax);
            _setRadio('midiMode',   'absolute');
        }

        sidebar.classList.add('open');
    }

    closeSidebar() {
        document.getElementById('midiSidebar')?.classList.remove('open');
        this.deselectFrame();
        this._stopListeningCC();
    }

    flipSide() {
        const sidebar = document.getElementById('midiSidebar');
        if (!sidebar) return;
        const isRight = sidebar.classList.toggle('right');
        localStorage.setItem('midiSidebarSide', isRight ? 'right' : 'left');
    }

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Learn CC button â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    startListeningCC() {
        if (!this.selectedFrame) {
            if (typeof showToast === 'function') showToast('Select a parameter first', 'warning');
            return;
        }
        this.listeningForCC = true;
        const btn = document.getElementById('midiLearnCCBtn');
        if (btn) {
            btn.textContent = 'Listeningâ€¦';
            btn.classList.add('listening');
        }
        if (typeof showToast === 'function') showToast('Move a MIDI controllerâ€¦', 'info');
    }

    _stopListeningCC() {
        this.listeningForCC = false;
        const btn = document.getElementById('midiLearnCCBtn');
        if (btn) {
            btn.textContent = 'Learn CC';
            btn.classList.remove('listening');
        }
    }

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Map / Unmap â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async applyMapping() {
        if (!this.selectedFrame) {
            if (typeof showToast === 'function') showToast('No parameter selected', 'warning');
            return;
        }

        const frame     = this.selectedFrame;
        const path      = frame.dataset.paramPath;
        const name      = frame.dataset.paramName || path;
        const channel   = parseInt(_getVal('midiChannel')) || 1;
        const ccNumber  = parseInt(_getVal('midiCC'))      ?? 0;
        const use14bit  = _getVal('midi14Bit',  'check');
        const invert    = _getVal('midiInvert', 'check');
        const rangeMin  = parseFloat(_getVal('midiRangeMin')) || 0;
        const rangeMax  = parseFloat(_getVal('midiRangeMax')) || 100;
        const valueMode = _getRadio('midiMode') || 'absolute';

        try {
            const res = await fetch('/api/midi/mappings', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    midi_type:      'cc',
                    midi_number:    ccNumber,
                    midi_channel:   channel,
                    parameter_path: path,
                    min_value:      rangeMin,
                    max_value:      rangeMax,
                    mapping_mode:   'local',
                    value_mode:     valueMode,
                    invert:         invert,
                    use_14bit:      use14bit,
                    name:           name,
                }),
            });
            const data = await res.json();
            if (data.success) {
                const key = `cc:${ccNumber}`;
                this.mappings[key] = {
                    type: 'cc', number: ccNumber, channel, path,
                    min: rangeMin, max: rangeMax, value_mode: valueMode,
                    invert, use_14bit: use14bit, name,
                };
                frame.classList.add('has-mapping');
                const badge = frame.querySelector('.midi-addr-badge');
                if (badge) badge.textContent = `CH${channel} CC${ccNumber}`;
                if (typeof showToast === 'function') showToast(`Mapped CH${channel} CC${ccNumber} â†’ ${name}`, 'success');
                this._updateMappingBadge();
            } else {
                if (typeof showToast === 'function') showToast('Mapping failed: ' + (data.error || '?'), 'error');
            }
        } catch (err) {
            console.error('[MIDI] Map error:', err);
        }
    }

    async removeSelectedMapping() {
        if (!this.selectedFrame) return;
        const path    = this.selectedFrame.dataset.paramPath;
        const mapping = Object.values(this.mappings).find(m => m.path === path);
        if (!mapping) {
            if (typeof showToast === 'function') showToast('No mapping for this parameter', 'info');
            return;
        }
        try {
            const res  = await fetch(`/api/midi/mappings/${mapping.type}/${mapping.number}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                delete this.mappings[`${mapping.type}:${mapping.number}`];
                this.selectedFrame.classList.remove('has-mapping');
                const badge = this.selectedFrame.querySelector('.midi-addr-badge');
                if (badge) badge.textContent = '';
                if (typeof showToast === 'function') showToast('Mapping removed', 'success');
                this._updateMappingBadge();
            }
        } catch (err) {
            console.error('[MIDI] Unmap error:', err);
        }
    }

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Frame state sync â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async _refreshAllFrames() {
        await this._loadMappings();
        this._applyBadgesToAllFrames();
    }

    async _loadMappings() {
        try {
            const res  = await fetch('/api/midi/mappings');
            const data = await res.json();
            if (!data.success) return;
            this.mappings = {};
            data.mappings.forEach(m => {
                const key = `${m.type}:${m.number}`;
                this.mappings[key] = m;
            });
        } catch (err) {
            console.error('[MIDI] Load mappings error:', err);
        }
    }

    _applyBadgesToAllFrames() {
        // Reset all frames
        document.querySelectorAll('.midi-param-frame').forEach(frame => {
            frame.classList.remove('has-mapping');
            const badge = frame.querySelector('.midi-addr-badge');
            if (badge) badge.textContent = '';
        });

        // Apply from cache
        Object.values(this.mappings).forEach(m => {
            document.querySelectorAll('.midi-param-frame').forEach(frame => {
                if (matchesMidiPattern(frame.dataset.paramPath, m.path)) {
                    frame.classList.add('has-mapping');
                    const badge = frame.querySelector('.midi-addr-badge');
                    if (badge) badge.textContent = `CH${m.channel ?? 1} CC${m.number}`;
                }
            });
        });
        this._updateMappingBadge();
    }

    _updateMappingBadge() {
        const badge = document.getElementById('midiMappingCount');
        if (!badge) return;
        const count = Object.keys(this.mappings).length;
        badge.textContent   = count;
        badge.style.display = count > 0 ? 'inline-block' : 'none';
    }
}

// â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function _setVal(id, value, type = 'value') {
    const el = document.getElementById(id);
    if (!el) return;
    if (type === 'check') el.checked = !!value;
    else                  el.value   = value;
}

function _getVal(id, type = 'value') {
    const el = document.getElementById(id);
    if (!el) return type === 'check' ? false : '';
    return type === 'check' ? el.checked : el.value;
}

function _setRadio(name, value) {
    const el = document.querySelector(`input[name="${name}"][value="${value}"]`);
    if (el) el.checked = true;
}

function _getRadio(name) {
    const el = document.querySelector(`input[name="${name}"]:checked`);
    return el ? el.value : null;
}

function _applyValueToFrame(frame, scaled) {
    // Playlist select: scroll through playlist tabs (view by index)
    if (frame.dataset.paramType === 'playlist-select') {
        const mgr = window.playlistTabsManager;
        if (!mgr || !mgr.playlists.length) return;
        const idx = Math.min(Math.floor((scaled / 128) * mgr.playlists.length), mgr.playlists.length - 1);
        mgr.viewPlaylist(mgr.playlists[idx].id);
        return;
    }

    // Playlist activate: launch the currently viewed playlist when CC >= 64
    if (frame.dataset.paramType === 'playlist-activate') {
        if (scaled < 0.5) return;
        const mgr = window.playlistTabsManager;
        if (!mgr || !mgr.viewedPlaylistId) return;
        mgr.activatePlaylist(mgr.viewedPlaylistId);
        return;
    }

    // Tab selector: scaled 0-2 → effects / sources / files
    if (frame.dataset.paramType === 'tab-select') {
        const tabs = ['effects', 'sources', 'files'];
        const idx = Math.max(0, Math.min(Math.floor(scaled), tabs.length - 1));
        window.switchTab?.(tabs[idx]);
        return;
    }

    // File cursor: scaled 0-127 → focus file at proportional index
    if (frame.dataset.paramType === 'file-navigate') {
        const ft = window.filesTab;
        if (!ft) return;
        const container = document.getElementById(ft.containerId);
        const total = container?.querySelectorAll('.file-item, .tree-node.file').length ?? 0;
        if (total === 0) return;
        const idx = Math.min(Math.floor((scaled / 128) * total), total - 1);
        ft.setFocusedIndex(idx);
        return;
    }

    // Clip cursor: scaled 0-127 → focus clip at proportional index in a playlist
    if (frame.dataset.paramType === 'clip-navigate') {
        const playerType = frame.dataset.paramPath.split('.')[0]; // 'video' or 'artnet'
        const files = window.playerConfigs?.[playerType]?.files;
        if (!files || files.length === 0) return;
        const idx = Math.min(Math.floor((scaled / 128) * files.length), files.length - 1);
        if (!window._clipMidiFocus) window._clipMidiFocus = {};
        window._clipMidiFocus[playerType] = idx;
        // Visual highlight
        const containerId = playerType === 'video' ? 'videoPlaylist' : 'artnetPlaylist';
        const container = document.getElementById(containerId);
        if (!container) return;
        container.querySelectorAll('.playlist-item-wrapper').forEach((el, i) => {
            el.classList.toggle('midi-clip-focused', i === idx);
        });
        const wrappers = container.querySelectorAll('.playlist-item-wrapper');
        wrappers[idx]?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        return;
    }

    // BPM set: scaled to 20-300 range, send to bpm widget
    if (frame.dataset.paramType === 'bpm-set') {
        const bpmInput = frame.querySelector('input');
        if (bpmInput) {
            bpmInput.value = Math.round(scaled * 10) / 10;
            bpmInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
        return;
    }

    // Trigger: scaled >= 0.5 → fire the button / action for this frame
    if (frame.dataset.paramType === 'trigger') {
        if (scaled < 0.5) return;
        const path = frame.dataset.paramPath;
        // BPM tap
        if (path === 'bpm.tap') { window.bpmWidget?.tap(); return; }
        // BPM resync
        if (path === 'bpm.resync') { window.bpmWidget?.resync(); return; }
        // Clip load: load the MIDI-focused clip into the player
        if (path === 'video.clip.load' || path === 'artnet.clip.load') {
            const playerType = path.split('.')[0];
            const idx = window._clipMidiFocus?.[playerType] ?? -1;
            const containerId = playerType === 'video' ? 'videoPlaylist' : 'artnetPlaylist';
            const container = document.getElementById(containerId);
            if (idx < 0 || !container) return;
            const attr = playerType === 'video' ? 'data-video-index' : 'data-artnet-index';
            const item = container.querySelector(`.playlist-item[${attr}="${idx}"]`);
            item?.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            return;
        }
        // Clip FX select: click the fx-tab (blue button) of the focused clip
        if (path === 'video.clip.fx' || path === 'artnet.clip.fx') {
            const playerType = path.split('.')[0];
            const idx = window._clipMidiFocus?.[playerType] ?? -1;
            const containerId = playerType === 'video' ? 'videoPlaylist' : 'artnetPlaylist';
            const container = document.getElementById(containerId);
            if (idx < 0 || !container) return;
            const fxTab = container.querySelector(`.playlist-item-fx-tab[data-clip-index="${idx}"][data-playlist="${playerType}"]`);
            fxTab?.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            return;
        }
        // File load → add focused file to playlist
        const ft = window.filesTab;
        if (!ft) return;
        const file = ft.getFocusedFile();
        if (!file) return;
        const playerId = path?.endsWith('.video') ? 'video' : 'artnet';
        ft.addToPlaylist(playerId, file.path);
        return;
    }

    // Boolean toggle (effect enable/disable)
    if (frame.dataset.paramType === 'boolean') {
        const checkbox = frame.querySelector('input[type="checkbox"]');
        if (checkbox) {
            const shouldBeChecked = scaled >= 0.5;
            if (checkbox.checked !== shouldBeChecked) {
                // Trigger the effect toggle via the enable-switch click handler
                const switchEl = frame.querySelector('.effect-enable-switch');
                if (switchEl) {
                    switchEl.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                } else {
                    checkbox.checked = shouldBeChecked;
                    checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        }
        return;
    }
    // Try triple-slider integration first
    const sliderContainer = frame.querySelector('.triple-slider-container');
    if (sliderContainer && typeof getTripleSlider === 'function') {
        const slider = getTripleSlider(sliderContainer.id);
        if (slider) {
            const range = slider.getRange();
            slider.updateValues(scaled, range.min, range.max);
            slider.updateUI();
            const valueEl = document.getElementById(`${sliderContainer.id}_value`);
            if (valueEl) {
                if (valueEl.tagName === 'INPUT') valueEl.value = scaled;
                else valueEl.textContent = scaled;
            }
            return;
        }
    }
    // Fallback: plain input/select
    const input = frame.querySelector('input[type="range"], input[type="number"], select');
    if (input) {
        input.value = scaled;
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }
}

/**
 * Returns true when `path` matches `pattern`.
 * '*' matches any single dot-separated segment.
 */
function matchesMidiPattern(path, pattern) {
    if (!path || !pattern) return false;
    if (path === pattern)  return true;
    const pp = pattern.split('.');
    const lp = path.split('.');
    if (pp.length !== lp.length) return false;
    return pp.every((seg, i) => seg === '*' || seg === lp[i]);
}

// â”€â”€ SocketIO: apply server-routed MIDI values â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

if (typeof socket !== 'undefined') {
    socket.on('midi_apply', ({ type, number, value, path, min, max, invert }) => {
        let normalised = value / 127;
        if (invert) normalised = 1 - normalised;
        const scaled = (min ?? 0) + normalised * ((max ?? 100) - (min ?? 0));
        document.querySelectorAll('.midi-param-frame').forEach(frame => {
            if (matchesMidiPattern(frame.dataset.paramPath, path)) {
                _applyValueToFrame(frame, scaled);
            }
        });
    });
}

// â”€â”€ Initialise singleton â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

window.midiLearnManager = new VisualMIDILearnManager();
