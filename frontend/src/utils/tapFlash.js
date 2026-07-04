import { haptic } from '../native/haptics'

/**
 * Tactile navigation: play a ~140ms press-flash + haptic tick on the tapped
 * element, THEN run the action (usually navigate). Fixes "the chat just
 * instantly opens" — the user gets a visual + physical cue that the tap
 * landed before the screen changes.
 *
 * Usage in an onClick handler:
 *   e.preventDefault()
 *   flashThen(e.currentTarget, () => navigate(to))
 */
export function flashThen(el, action, ms = 140) {
  try {
    haptic('light')
    if (el) {
      el.classList.remove('tap-flash') // restart if re-tapped quickly
      // force reflow so the animation replays
      void el.offsetWidth
      el.classList.add('tap-flash')
    }
  } catch { /* feedback must never block navigation */ }
  setTimeout(action, ms)
}
