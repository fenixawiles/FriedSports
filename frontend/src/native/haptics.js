/**
 * Tiny haptic moments — native shell only, no-op on web.
 *
 * Uses the window.Capacitor bridge (same pattern as push/splash) so the
 * frontend package needs no npm dep. navigator.vibrate does NOT work in
 * iOS WKWebView; @capacitor/haptics is the only path that actually taps.
 *
 *   haptic('light')   — taps: send, react, toggle
 *   haptic('medium')  — commitments: archive, delete, sheet open
 *   haptic('success') — wins: invite accepted, friend added
 */
export function haptic(kind = 'light') {
  try {
    const H = window.Capacitor?.Plugins?.Haptics
    if (!H) return
    if (kind === 'success' || kind === 'warning' || kind === 'error') {
      H.notification({ type: kind.toUpperCase() })
    } else {
      const style = kind.charAt(0).toUpperCase() + kind.slice(1) // Light|Medium|Heavy
      H.impact({ style })
    }
  } catch { /* haptics must never break a tap */ }
}
