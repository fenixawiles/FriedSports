// Native bridge for the Capacitor iOS wrapper.
//
// Gives the app genuine native capabilities (share sheet + haptics) so it isn't
// a bare WebView — the concrete answer to App Store Guideline 4.2. Everything
// here is fully guarded: on the mobile web (where window.Capacitor is absent)
// it degrades to the Web Share API or clipboard, and haptics become no-ops.
(function () {
  var Cap = window.Capacitor;
  var isNative = !!(Cap && typeof Cap.isNativePlatform === 'function' && Cap.isNativePlatform());

  function plugin(name) {
    return (Cap && Cap.Plugins && Cap.Plugins[name]) || null;
  }

  // ── Share: native sheet in-app → Web Share API → clipboard → manual ─────────
  function share(opts) {
    opts = opts || {};
    var url   = opts.url   || window.location.href;
    var title = opts.title || document.title;
    var text  = opts.text  || '';

    if (isNative) {
      var Share = plugin('Share');
      if (Share && Share.share) {
        return Share.share({ title: title, text: text, url: url, dialogTitle: 'Share' })
          .then(function () { return 'native'; })
          .catch(function () { return 'cancelled'; });
      }
    }
    if (navigator.share) {
      return navigator.share({ title: title, text: text, url: url })
        .then(function () { return 'web'; })
        .catch(function () { return 'cancelled'; });
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(url).then(function () { return 'copied'; });
    }
    return Promise.reject('unsupported');
  }

  // ── Haptics (native only; silent no-op on web) ──────────────────────────────
  function haptic(style) {
    if (!isNative) return;
    var H = plugin('Haptics');
    if (!H) return;
    try {
      if (style === 'selection' && H.selectionChanged) { H.selectionChanged(); }
      else if (H.impact) { H.impact({ style: style || 'LIGHT' }); }
    } catch (e) { /* never let feedback throw */ }
  }

  window.FSNative = { isNative: isNative, share: share, haptic: haptic };

  // Lets CSS/JS adapt to the native shell if needed.
  if (isNative) document.documentElement.classList.add('is-native-app');

  // ── Haptic feedback on core interactions (delegated once; survives Turbo) ───
  if (isNative && !window._fsHapticsWired) {
    window._fsHapticsWired = true;
    document.addEventListener('click', function (e) {
      var t = e.target;
      if (t.closest && (t.closest('.chat-submit'))) haptic('LIGHT');
      else if (t.closest && (t.closest('.vote-btn') || t.closest('.reaction-btn'))) haptic('MEDIUM');
    }, true);
  }
})();
