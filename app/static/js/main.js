// Auto-dismiss flash messages after 4 seconds
document.addEventListener('DOMContentLoaded', function () {
  var flashes = document.querySelectorAll('.flash');
  flashes.forEach(function (el) {
    setTimeout(function () {
      el.style.transition = 'opacity 0.4s';
      el.style.opacity = '0';
      setTimeout(function () { el.remove(); }, 400);
    }, 4000);
  });
});

// ── Loading state helpers ────────────────────────────────────────────────────

var _bar = null;
document.addEventListener('DOMContentLoaded', function () {
  _bar = document.getElementById('page-loading-bar');
});

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
  // Inject spinner span inside the button
  var sp = document.createElement('span');
  sp.className = 'btn-spinner';
  sp.setAttribute('aria-hidden', 'true');
  btn.appendChild(sp);
}

// Finish bar when page is ready
document.addEventListener('DOMContentLoaded', _finishLoad);

// Form submit: start loading bar + arm submit button
document.addEventListener('submit', function (e) {
  if (e.defaultPrevented) return; // confirm() was cancelled or JS validation failed
  _startLoad();
  var form = e.target;
  // Try the exact [type=submit] that was clicked first, then fall back to any submit btn
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
  // Visually arm anchor links that look like buttons
  if (a.className && a.className.match(/btn-/)) _armButton(a);
});
