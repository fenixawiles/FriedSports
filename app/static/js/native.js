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

  // ── Native keyboard ─────────────────────────────────────────────────────────
  // resize:"native" (capacitor.config) shrinks the web view frame above the
  // keyboard, so the flex chat layout fits on its own — the header stays pinned
  // and the composer rides just above the keyboard instead of the whole page
  // scrolling up. We still toggle .keyboard-open so the composer can drop its
  // home-indicator inset while the keyboard is up. The Keyboard plugin's events
  // are the reliable signal here (visualViewport can't see it once the frame
  // itself resizes). Wired once — these native listeners survive Turbo swaps.
  // With resize:"none" the web view stays full-height (no late frame snap), so
  // we shrink the thread layout ourselves: publish the keyboard height as --kb
  // and let CSS transition `height: calc(100dvh - var(--kb))` in sync with the
  // keyboard. keyboardWillShow fires at the START of the keyboard animation, so
  // the CSS transition rides up with it. .keyboard-open also drops the composer's
  // home-indicator inset (the web view still touches the bottom under resize:none).
  if (isNative && !window._fsKeyboardWired) {
    var Keyboard = plugin('Keyboard');
    if (Keyboard && Keyboard.addListener) {
      window._fsKeyboardWired = true;
      Keyboard.addListener('keyboardWillShow', function (info) {
        var h = (info && info.keyboardHeight) ? info.keyboardHeight : 0;
        document.body.style.setProperty('--kb', h + 'px');
        document.body.classList.add('keyboard-open');
      });
      Keyboard.addListener('keyboardWillHide', function () {
        document.body.style.setProperty('--kb', '0px');
        document.body.classList.remove('keyboard-open');
      });
    }
  }

  // ── Per-page document bounce ────────────────────────────────────────────────
  // The elastic document rubber-band is great on scrolling pages, but on a chat
  // (fixed-height body) it drags the whole UI — including the composer — when you
  // overscroll the message list. Tell native to disable the MAIN scroll view's
  // bounce on thread pages (the inner .chat-window keeps its own bounce); re-enable
  // it everywhere else. Posted on every Turbo visit.
  if (isNative) {
    var syncBounce = function () {
      try {
        var h = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.fsBounce;
        if (!h) return;
        h.postMessage(document.body.classList.contains('thread-view') ? '0' : '1');
      } catch (e) { /* no-op on web */ }
    };
    syncBounce();
    if (!window._fsBounceWired) {
      window._fsBounceWired = true;
      document.addEventListener('turbo:load', syncBounce);
    }
  }

  // ── Theme-aware native overscroll color ─────────────────────────────────────
  // The WKWebView's rubber-band/overscroll area is painted by the native layer,
  // which can't read the web-only (localStorage) dark-mode toggle. Post the
  // current resolved --bg-primary to MainViewController so the bounce matches
  // the active theme instead of flashing a fixed color. Fully guarded: on the
  // mobile web (no fsTheme handler) every call is a silent no-op.
  if (isNative) {
    var syncThemeColor = function () {
      try {
        var h = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.fsTheme;
        if (!h) return;
        var hex = getComputedStyle(document.documentElement)
                    .getPropertyValue('--bg-primary').trim();
        if (hex) h.postMessage(hex);
      } catch (e) { /* never let theme sync throw */ }
    };
    // Sync now (CSS is applied by the time this body script runs) and on every
    // Turbo navigation (this script re-runs per visit).
    syncThemeColor();
    // Wire long-lived listeners exactly once — they survive Turbo body swaps.
    if (!window._fsThemeWired) {
      window._fsThemeWired = true;
      document.addEventListener('turbo:load', syncThemeColor);
      // Fires the instant the in-app toggle flips data-theme on <html>.
      new MutationObserver(syncThemeColor).observe(document.documentElement, {
        attributes: true, attributeFilter: ['data-theme']
      });
    }
  }
})();
