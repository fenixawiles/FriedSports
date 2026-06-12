// main.js — runs immediately (placed at end of <body>, DOM is ready)

// ── Flash auto-dismiss ───────────────────────────────────────────────────────
function _dismissFlashes() {
  document.querySelectorAll('.flash').forEach(function (el) {
    setTimeout(function () {
      el.style.transition = 'opacity 0.4s';
      el.style.opacity = '0';
      setTimeout(function () { el.remove(); }, 400);
    }, 4000);
  });
}
_dismissFlashes();

// ── Programmatic toasts — same look as server flashes ────────────────────────
window.showToast = function (message, type) {
  type = type || 'info';
  var container = document.querySelector('.flash-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'flash-container';
    document.body.appendChild(container);
  }
  var el = document.createElement('div');
  el.className = 'flash flash-' + type;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(function () {
    el.style.transition = 'opacity 0.4s';
    el.style.opacity = '0';
    setTimeout(function () { el.remove(); }, 400);
  }, 3000);
};

// ── Overflow (three-dot) menus — event delegation, works after Turbo swaps ──
// Guarded: body scripts re-run on every Turbo visit, but document-level
// listeners survive the swap, so wire exactly once.
if (!window._overflowMenusWired) {
  window._overflowMenusWired = true;
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.overflow-menu-btn');
    // Close all open menus on any click
    document.querySelectorAll('.overflow-menu').forEach(function (menu) {
      if (!btn || menu !== document.getElementById(btn.getAttribute('aria-controls'))) {
        menu.hidden = true;
      }
    });
    if (!btn) return;
    e.stopPropagation();
    var menu = document.getElementById(btn.getAttribute('aria-controls'));
    if (menu) menu.hidden = !menu.hidden;
  });
}

// ── Loading state helpers ────────────────────────────────────────────────────
var _bar = document.getElementById('page-loading-bar');

function _startLoad() {
  if (!_bar) _bar = document.getElementById('page-loading-bar');
  if (!_bar) return;
  _bar.className = '';
  _bar.offsetWidth; // force reflow
  _bar.className = 'loading';
}

function _finishLoad() {
  if (!_bar) return;
  _bar.className = 'done';
  setTimeout(function () { _bar.className = ''; }, 500);
}

/**
 * Arm a button: disable it, dim it, and inject a small circular spinner.
 * Idempotent — safe to call twice on the same button.
 */
function _armButton(btn) {
  if (!btn || btn.dataset.loading) return;
  btn.dataset.loading = '1';
  btn.disabled = true;
  btn.style.opacity = '0.55';
  btn.style.cursor = 'default';
  var sp = document.createElement('span');
  sp.className = 'btn-spinner';
  sp.setAttribute('aria-hidden', 'true');
  btn.appendChild(sp);
}

// Finish bar on initial page load
_finishLoad();

// Form submit: start loading bar + arm submit button
document.addEventListener('submit', function (e) {
  if (e.defaultPrevented) return;
  _startLoad();
  var form = e.target;
  var btn = (e.submitter && e.submitter.type === 'submit')
    ? e.submitter
    : form.querySelector('[type="submit"]');
  if (btn) _armButton(btn);
});

// Navigation link clicks: start loading bar + arm the link itself
document.addEventListener('click', function (e) {
  var a = e.target.closest('a[href]');
  if (!a) return;
  var href = a.getAttribute('href');
  if (!href || href.startsWith('#') || href.startsWith('javascript') || a.target === '_blank') return;
  if (href.startsWith('http') && !href.startsWith(window.location.origin)) return;
  _startLoad();
  if (a.className && a.className.match(/btn-/)) _armButton(a);
});

// ── Prefetching ───────────────────────────────────────────────────────────────
// _prefetchUrl(url)  — inject a <link rel="prefetch"> once per unique URL
// _rewirePrefetch()  — wire hover/focus/touchstart listeners on nav elements
// _eagerPrefetch()   — immediately prefetch all visible content-area links
//                      (called after every page render so the next tap is instant)
(function () {
  if (typeof document.createElement('link').relList === 'undefined') return;
  var prefetched = new Set();

  window._prefetchUrl = function (url) {
    if (!url || typeof url !== 'string') return;
    if (url.startsWith('#') || url.startsWith('javascript:') || url.startsWith('mailto:')) return;
    var abs = url.startsWith('http') ? url : window.location.origin + url;
    if (!abs.startsWith(window.location.origin)) return;
    if (prefetched.has(abs)) return;
    prefetched.add(abs);
    var link = document.createElement('link');
    link.rel  = 'prefetch';
    link.as   = 'document';
    link.href = abs;
    document.head.appendChild(link);
  };

  function wireEl(el) {
    var href = el.getAttribute('href');
    if (!href) return;
    el.addEventListener('mouseenter',  function () { window._prefetchUrl(href); });
    el.addEventListener('focus',       function () { window._prefetchUrl(href); });
    el.addEventListener('touchstart',  function () { window._prefetchUrl(href); }, { passive: true });
  }

  // Re-wire event-based prefetch listeners on newly rendered elements
  window._rewirePrefetch = function () {
    document.querySelectorAll('.bottom-nav-item[href]').forEach(wireEl);
    document.querySelectorAll('.nav-link[href]').forEach(wireEl);
    document.querySelectorAll('.thread-row-item[href]').forEach(wireEl);
    document.querySelectorAll('.thread-card[href]').forEach(wireEl);
    document.querySelectorAll('.group-card a[href]').forEach(wireEl);
    document.querySelectorAll('.more-row[href]').forEach(wireEl);
    document.querySelectorAll('.back-link[href]').forEach(wireEl);
  };

  // Eagerly prefetch the most likely next taps without waiting for hover.
  // Bottom nav tabs are always on screen — always warm them.
  // Content-area links (thread rows, group cards) are warmed the moment they render.
  window._eagerPrefetch = function () {
    // Shell: bottom nav is always visible
    document.querySelectorAll('.bottom-nav-item[href]').forEach(function (el) {
      window._prefetchUrl(el.getAttribute('href'));
    });
    // Content: whatever is on the current page
    [
      '.thread-row-item[href]',
      '.group-card[href]',
      '.group-card a[href]',
      '.alert-banner[href]',
    ].forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (el) {
        window._prefetchUrl(el.getAttribute('href'));
      });
    });
  };

  window._rewirePrefetch();
  window._eagerPrefetch();
})();
