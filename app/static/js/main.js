// Auto-dismiss flash messages after 4 seconds
document.addEventListener('DOMContentLoaded', function () {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(function (el) {
    setTimeout(function () {
      el.style.transition = 'opacity 0.4s';
      el.style.opacity = '0';
      setTimeout(function () { el.remove(); }, 400);
    }, 4000);
  });
});

// Global loading bar
(function () {
  var bar = document.getElementById('page-loading-bar');

  function startLoad() {
    if (!bar) return;
    bar.className = '';
    bar.offsetWidth; // force reflow to restart transition
    bar.className = 'loading';
  }

  function finishLoad() {
    if (!bar) return;
    bar.className = 'done';
    setTimeout(function () { bar.className = ''; }, 500);
  }

  // Finish bar when page is fully ready
  document.addEventListener('DOMContentLoaded', finishLoad);

  // Start bar + disable submit button on form submit
  document.addEventListener('submit', function (e) {
    if (e.defaultPrevented) return; // confirm() was cancelled
    var form = e.target;
    startLoad();
    var btn = form.querySelector('[type="submit"]');
    if (btn) {
      btn.disabled = true;
      btn.style.opacity = '0.6';
    }
  });

  // Start bar on internal link clicks
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a[href]');
    if (!a) return;
    var href = a.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('javascript') || a.target === '_blank') return;
    if (href.startsWith('http') && !href.startsWith(window.location.origin)) return;
    startLoad();
  });
})();
