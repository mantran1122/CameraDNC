'use strict';

// ── State ──────────────────────────────────────────────────────────────
var DEMOS_DATA = [];
var CATEGORIES = [];
var currentCategory = 'Tất cả';
var currentSearch   = '';
var runningSet      = new Set();

// ── Theme ──────────────────────────────────────────────────────────────
(function applyStoredTheme() {
    var saved = localStorage.getItem('theme') || 'dark';
    if (saved === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
    }
    _syncThemeIcon();
})();

function _syncThemeIcon() {
    var isLight = document.documentElement.getAttribute('data-theme') === 'light';
    var icon = document.getElementById('theme-icon');
    if (!icon) { return; }
    icon.className = isLight ? 'fas fa-sun' : 'fas fa-moon';
    var btn = document.getElementById('theme-btn');
    if (btn) { btn.title = isLight ? 'Chuyển sang giao diện tối' : 'Chuyển sang giao diện sáng'; }
}

function toggleTheme() {
    var isLight = document.documentElement.getAttribute('data-theme') === 'light';
    var next = isLight ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    _syncThemeIcon();
    if (window.backend) { backend.set_theme(next); }
}

// ── Race-condition-safe init ────────────────────────────────────────────
var _appData = null, _platformInfo = null;

window.initApp = function(appData, platformInfo) {
    _appData      = appData;
    _platformInfo = platformInfo;
    if (window.backend) { _doInit(); }
};

new QWebChannel(qt.webChannelTransport, function(channel) {
    window.backend = channel.objects.backend;
    backend.demo_started.connect(onDemoStarted);
    backend.demo_stopped.connect(onDemoStopped);
    backend.demo_error.connect(onDemoError);
    backend.app_status.connect(onStatusUpdate);
    backend.set_theme(document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark');
    if (_appData) { _doInit(); }
});

// ── Init ───────────────────────────────────────────────────────────────
function _doInit() {
    DEMOS_DATA = _appData.demos;
    CATEGORIES = _appData.categories;

    // Env info sidebar
    document.getElementById('env-python').textContent   = _platformInfo.python;
    document.getElementById('env-platform').textContent = _platformInfo.platform;
    document.getElementById('env-qt').textContent       = _platformInfo.qt;

    // Category bar
    var bar = document.getElementById('category-bar');
    bar.innerHTML = '';
    CATEGORIES.forEach(function(cat) {
        var btn = document.createElement('button');
        btn.className = 'cat-btn' + (cat === currentCategory ? ' active' : '');
        btn.textContent = cat;
        btn.onclick = function() { selectCategory(cat); };
        bar.appendChild(btn);
    });

    renderCards();
    setStatus('Sẵn sàng', 'var(--green)');
}

// ── Filtering ──────────────────────────────────────────────────────────
function getFilteredDemos() {
    var q = currentSearch.toLowerCase().trim();
    return DEMOS_DATA.filter(function(d) {
        var catOk = (currentCategory === 'Tất cả') || (d.category === currentCategory);
        if (!catOk) { return false; }
        if (!q) { return true; }
        var haystack = [d.label, d.module_name, d.description].concat(d.keywords).join(' ').toLowerCase();
        return haystack.indexOf(q) !== -1;
    });
}

// ── Render ─────────────────────────────────────────────────────────────
function renderCards() {
    var grid  = document.getElementById('demo-grid');
    var empty = document.getElementById('empty-state');
    grid.innerHTML = '';

    var filtered = getFilteredDemos();
    if (filtered.length === 0) {
        grid.style.display  = 'none';
        empty.style.display = 'flex';
        return;
    }
    grid.style.display  = 'grid';
    empty.style.display = 'none';

    filtered.forEach(function(demo, idx) {
        grid.appendChild(createCard(demo, idx));
    });
}

function createCard(demo, idx) {
    var isRunning = runningSet.has(demo.module_path);

    var card = document.createElement('div');
    card.className = 'demo-card' + (isRunning ? ' running' : '');
    card.setAttribute('data-module', demo.module_path);
    card.style.setProperty('--card-accent', demo.accent);
    card.style.animationDelay = (Math.min(idx, 7) * 0.03 + 0.03) + 's';

    card.innerHTML =
        '<div class="card-top">' +
            '<div class="icon-box" style="background:' + demo.accent + '22;color:' + demo.accent + '">' +
                '<i class="fas ' + demo.icon_key + '"></i>' +
            '</div>' +
            '<div class="card-badges">' +
                '<span class="running-badge" style="display:' + (isRunning ? 'inline' : 'none') + '">RUNNING</span>' +
                '<span class="cat-chip" style="color:' + demo.accent + ';background:' + demo.accent + '18;border:1px solid ' + demo.accent + '40">' + _esc(demo.category) + '</span>' +
            '</div>' +
        '</div>' +
        '<div class="card-title">' + _esc(demo.label) + '</div>' +
        '<div class="card-bot">' +
            '<button class="pill-btn"' + (isRunning ? ' disabled' : '') + '>' +
                '<span class="pill-btn__ico" aria-hidden="true"><i class="fas fa-play"></i></span>' +
                'Mở demo' +
            '</button>' +
        '</div>';

    var btn = card.querySelector('.pill-btn');
    btn.addEventListener('click', function(e) {
        e.stopPropagation();
        openDemo(demo.module_path);
    });

    card.addEventListener('click', function() {
        openDemo(demo.module_path);
    });

    return card;
}

function _esc(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ── Targeted DOM update (no full re-render for state changes) ──────────
function _updateCardDOM(modulePath, isRunning, isError) {
    var card = document.querySelector('.demo-card[data-module="' + modulePath + '"]');
    if (!card) { return; }
    card.classList.toggle('running', isRunning);
    card.classList.toggle('error',   isError);
    var badge = card.querySelector('.running-badge');
    var btn   = card.querySelector('.pill-btn');
    if (badge) { badge.style.display = isRunning ? 'inline' : 'none'; }
    if (btn)   { btn.disabled = isRunning; }
}

function updateStatChip() {
    var el = document.getElementById('stat-running');
    if (el) { el.textContent = runningSet.size; }
}

// ── Bridge signal handlers ─────────────────────────────────────────────
function onDemoStarted(mp) {
    runningSet.add(mp);
    updateStatChip();
    _updateCardDOM(mp, true, false);
}

function onDemoStopped(mp) {
    runningSet.delete(mp);
    updateStatChip();
    _updateCardDOM(mp, false, false);
}

function onDemoError(mp, err) {
    _updateCardDOM(mp, false, true);
    setTimeout(function() { _updateCardDOM(mp, false, false); }, 4000);
}

function onStatusUpdate(msg, color) {
    setStatus(msg, color);
}

function setStatus(msg, color) {
    document.getElementById('status-dot').style.color = color;
    document.getElementById('status-msg').textContent = msg;
}

// ── UI actions ─────────────────────────────────────────────────────────
function selectCategory(cat) {
    currentCategory = cat;
    document.querySelectorAll('.cat-btn').forEach(function(btn) {
        btn.classList.toggle('active', btn.textContent === cat);
    });
    renderCards();
}

function onSearch(val) {
    currentSearch = val;
    renderCards();
}

function onRefresh() {
    var inp = document.getElementById('search-input');
    inp.value = '';
    currentSearch = '';
    selectCategory('Tất cả');
    setStatus('Danh sách đã làm mới.', 'var(--green)');
    setTimeout(function() { setStatus('Sẵn sàng', 'var(--green)'); }, 2500);
}

function openDemo(modulePath) {
    if (window.backend) { backend.launch(modulePath); }
}

function openFolder() {
    if (window.backend) { backend.open_folder(); }
}

function quitApp() {
    if (window.backend) { backend.quit_app(); }
}

// ── Global functions called from Python via runJavaScript ──────────────
window.focusSearch = function() {
    var inp = document.getElementById('search-input');
    inp.focus();
    inp.select();
};

window.handleEsc = function() {
    var inp = document.getElementById('search-input');
    if (inp.value) {
        inp.value = '';
        onSearch('');
    }
};

// ── Keyboard (when focus is inside WebView) ────────────────────────────
document.addEventListener('keydown', function(e) {
    if (e.ctrlKey && e.key === 'f') { e.preventDefault(); window.focusSearch(); }
    if (e.ctrlKey && e.key === 'q') { e.preventDefault(); quitApp(); }
    if (e.key === 'Escape')         { window.handleEsc(); }
});
