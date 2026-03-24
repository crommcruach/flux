/**
 * ScrubInput — reusable drag-to-scrub number input component
 *
 * Two usage patterns:
 *
 * 1) Enhance an existing <input type="number"> in place:
 *      ScrubInput.init(inputEl, { buttons: true, onChange: (v) => console.log(v) });
 *
 * 2) Build a complete HTML string to drop into a template:
 *      const html = ScrubInput.render({
 *          name:    'myInput',          // used for input id/name
 *          value:   1.0,
 *          min:     0.1, max: 5.0, step: 0.1,
 *          buttons: true,               // default true — show − / + buttons
 *          extraInputClasses: 'my-cls', // extra CSS classes on the <input>
 *          title:   'Drag or type',
 *          onInput: "myHandler(this)",  // inline oninput attribute string
 *          onContextmenu: "myReset(this); return false;",
 *      });
 *      // After inserting html into the DOM:
 *      ScrubInput.initByName('myInput');
 *      // -- or init all uninitialised ones at once:
 *      ScrubInput.initAll();
 *
 * CSS dependency: css/scrub-input.css  (or import inside your main stylesheet)
 */
const ScrubInput = (() => {
    const PIXELS_PER_STEP = 10;

    // ── Internal drag logic ────────────────────────────────────────────────

    function _startDrag(event, inputEl, plusBtn, minusBtn) {
        if (event.button !== 0) return;

        const startX = event.clientX;
        const startY = event.clientY;
        let lastX = startX;
        let lastY = startY;
        let hasDragged = false;
        let accumulator = 0;

        function applyChange(delta) {
            const min = parseFloat(inputEl.min) || -Infinity;
            const max = parseFloat(inputEl.max) || Infinity;
            const step = parseFloat(inputEl.step) || 1;
            const decimals = (step.toString().split('.')[1] || '').length;
            let val = Math.max(min, Math.min(max, parseFloat(inputEl.value) + delta));
            val = parseFloat(val.toFixed(decimals));
            inputEl.value = val;
            inputEl.dispatchEvent(new Event('input', { bubbles: true }));
        }

        function highlight(increasing) {
            if (!plusBtn || !minusBtn) return;
            if (increasing) {
                plusBtn.classList.add('active');
                minusBtn.classList.remove('active');
            } else {
                minusBtn.classList.add('active');
                plusBtn.classList.remove('active');
            }
        }

        function onMove(e) {
            const dx = e.clientX - lastX;
            const dy = lastY - e.clientY; // up = positive
            lastX = e.clientX;
            lastY = e.clientY;

            if (!hasDragged && (Math.abs(e.clientX - startX) > 3 || Math.abs(e.clientY - startY) > 3)) {
                hasDragged = true;
                inputEl.blur();
            }

            if (!hasDragged) return;

            const step = parseFloat(inputEl.step) || 1;
            const moveDelta = Math.abs(dx) > Math.abs(dy) ? dx : dy;
            accumulator += moveDelta;

            if (accumulator >= PIXELS_PER_STEP) highlight(true);
            else if (accumulator <= -PIXELS_PER_STEP) highlight(false);

            while (accumulator >= PIXELS_PER_STEP) {
                applyChange(step);
                accumulator -= PIXELS_PER_STEP;
            }
            while (accumulator <= -PIXELS_PER_STEP) {
                applyChange(-step);
                accumulator += PIXELS_PER_STEP;
            }
        }

        function onUp() {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);

            if (plusBtn) plusBtn.classList.remove('active');
            if (minusBtn) minusBtn.classList.remove('active');

            if (!hasDragged) {
                inputEl.focus();
                inputEl.select();
            }
        }

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    }

    function _startBtnDrag(event, inputEl, step, plusBtn, minusBtn, clickedBtn) {
        if (event.button !== 0) return;
        event.preventDefault();

        // Immediate highlight
        clickedBtn.classList.add('active');
        const otherBtn = clickedBtn === plusBtn ? minusBtn : plusBtn;

        const startX = event.clientX;
        const startY = event.clientY;
        let lastX = startX;
        let lastY = startY;
        let hasDragged = false;
        let accumulator = 0;

        function applyChange(delta) {
            const min = parseFloat(inputEl.min) || -Infinity;
            const max = parseFloat(inputEl.max) || Infinity;
            const decimals = (Math.abs(delta).toString().split('.')[1] || '').length;
            let val = Math.max(min, Math.min(max, parseFloat(inputEl.value) + delta));
            val = parseFloat(val.toFixed(decimals));
            inputEl.value = val;
            inputEl.dispatchEvent(new Event('input', { bubbles: true }));
        }

        function highlight(increasing) {
            if (increasing) {
                plusBtn.classList.add('active');
                minusBtn.classList.remove('active');
            } else {
                minusBtn.classList.add('active');
                plusBtn.classList.remove('active');
            }
        }

        function onMove(e) {
            const dx = e.clientX - lastX;
            const dy = lastY - e.clientY;
            lastX = e.clientX;
            lastY = e.clientY;

            if (!hasDragged && (Math.abs(e.clientX - startX) > 3 || Math.abs(e.clientY - startY) > 3)) {
                hasDragged = true;
            }

            if (!hasDragged) return;

            const moveDelta = Math.abs(dx) > Math.abs(dy) ? dx : dy;
            accumulator += moveDelta;

            if (accumulator >= PIXELS_PER_STEP) highlight(true);
            else if (accumulator <= -PIXELS_PER_STEP) highlight(false);

            while (accumulator >= PIXELS_PER_STEP) {
                applyChange(Math.abs(step));
                accumulator -= PIXELS_PER_STEP;
            }
            while (accumulator <= -PIXELS_PER_STEP) {
                applyChange(-Math.abs(step));
                accumulator += PIXELS_PER_STEP;
            }
        }

        function onUp() {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);

            if (!hasDragged) {
                // Single click — one step, brief flash
                applyChange(step);
                const btn = step > 0 ? plusBtn : minusBtn;
                btn.classList.add('active');
                setTimeout(() => btn.classList.remove('active'), 150);
            } else {
                plusBtn.classList.remove('active');
                minusBtn.classList.remove('active');
            }
        }

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    }

    // ── Public API ─────────────────────────────────────────────────────────

    /**
     * Progressively enhance an existing <input type="number">.
     * The input is wrapped in a .scrub-input-wrapper div.
     * @param {HTMLInputElement} inputEl
     * @param {object} [opts]
     * @param {boolean} [opts.buttons=true]       - add − / + step buttons
     * @param {function} [opts.onChange]          - called with numeric value on every change
     */
    function init(inputEl, opts = {}) {
        if (!inputEl || inputEl._scrubInputInit) return;
        inputEl._scrubInputInit = true;

        const showButtons = opts.buttons !== false;
        const step = parseFloat(inputEl.step) || 1;

        // Wrap
        const wrapper = document.createElement('div');
        wrapper.className = 'scrub-input-wrapper';
        inputEl.parentNode.insertBefore(wrapper, inputEl);
        wrapper.appendChild(inputEl);

        let plusBtn = null;
        let minusBtn = null;

        if (showButtons) {
            minusBtn = document.createElement('button');
            minusBtn.type = 'button';
            minusBtn.className = 'scrub-input-btn scrub-input-btn-minus';
            minusBtn.textContent = '−';
            minusBtn.title = 'Decrease (hold & drag to scrub)';

            plusBtn = document.createElement('button');
            plusBtn.type = 'button';
            plusBtn.className = 'scrub-input-btn scrub-input-btn-plus';
            plusBtn.textContent = '+';
            plusBtn.title = 'Increase (hold & drag to scrub)';

            wrapper.insertBefore(minusBtn, inputEl);
            wrapper.appendChild(plusBtn);

            minusBtn.addEventListener('mousedown', (e) =>
                _startBtnDrag(e, inputEl, -step, plusBtn, minusBtn, minusBtn));
            plusBtn.addEventListener('mousedown', (e) =>
                _startBtnDrag(e, inputEl, step, plusBtn, minusBtn, plusBtn));
        }

        // Drag on the input itself
        inputEl.addEventListener('mousedown', (e) =>
            _startDrag(e, inputEl, plusBtn, minusBtn));

        // External onChange callback
        if (typeof opts.onChange === 'function') {
            inputEl.addEventListener('input', () => opts.onChange(parseFloat(inputEl.value)));
        }
    }

    /**
     * Init all <input type="number" data-scrub-input> elements inside a root.
     * Use data-scrub-buttons="false" to suppress buttons on individual inputs.
     * @param {Element} [root=document]
     */
    function initAll(root = document) {
        root.querySelectorAll('input[type="number"][data-scrub-input]').forEach(el => {
            const showButtons = el.dataset.scrubButtons !== 'false';
            init(el, { buttons: showButtons });
        });
    }

    /**
     * Init a specific element by its id.
     * @param {string} id
     * @param {object} [opts]
     */
    function initById(id, opts = {}) {
        const el = document.getElementById(id);
        if (el) init(el, opts);
    }

    /**
     * Build an HTML string for a complete scrub-input widget.
     * Insert it into the DOM, then call ScrubInput.initById(name) or ScrubInput.initAll().
     *
     * @param {object} opts
     * @param {string}  opts.name               - used as id and name on the <input>
     * @param {number}  [opts.value=0]
     * @param {number}  [opts.min]
     * @param {number}  [opts.max]
     * @param {number}  [opts.step=1]
     * @param {boolean} [opts.buttons=true]
     * @param {string}  [opts.extraInputClasses]
     * @param {string}  [opts.title]
     * @param {string}  [opts.onInput]           - oninput attribute value
     * @param {string}  [opts.onContextmenu]     - oncontextmenu attribute value
     * @returns {string} HTML string
     */
    function render(opts = {}) {
        const {
            name = '',
            value = 0,
            min,
            max,
            step = 1,
            buttons = true,
            extraInputClasses = '',
            title = '',
            onInput = '',
            onContextmenu = '',
        } = opts;

        const minAttr = min !== undefined ? `min="${min}"` : '';
        const maxAttr = max !== undefined ? `max="${max}"` : '';
        const titleAttr = title ? `title="${title}"` : '';
        const onInputAttr = onInput ? `oninput="${onInput}"` : '';
        const onCtxAttr = onContextmenu ? `oncontextmenu="${onContextmenu}"` : '';
        const idAttr = name ? `id="${name}" name="${name}"` : '';

        const inputHtml = `<input type="number"
            class="scrub-input-field ${extraInputClasses}"
            data-scrub-input
            data-scrub-buttons="${buttons}"
            value="${value}"
            step="${step}"
            ${minAttr} ${maxAttr}
            ${idAttr}
            ${titleAttr}
            ${onInputAttr}
            ${onCtxAttr}>`;

        return inputHtml;
    }

    return { init, initAll, initById, render };
})();

window.ScrubInput = ScrubInput;
