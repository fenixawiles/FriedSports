import { useRef } from 'react'
import { haptic } from '../native/haptics'

/**
 * Press-and-hold detector that composes with existing pointer/swipe handlers.
 *
 * Call begin/move/end from the row's own onPointerDown/Move/Up, and clickGuard
 * from onClick. Fires `onLongPress` after `ms` of a steady press; any drag
 * beyond `slop` px (i.e. a swipe) cancels it. After it fires, the next click
 * is swallowed so the row doesn't also navigate.
 */
export default function useLongPress(onLongPress, { ms = 450, slop = 10 } = {}) {
  const timer = useRef(null)
  const fired = useRef(false)
  const origin = useRef({ x: 0, y: 0 })

  function begin(e) {
    fired.current = false
    origin.current = { x: e.clientX, y: e.clientY }
    clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      fired.current = true
      haptic('medium') // the "menu is opening" thunk
      onLongPress()
    }, ms)
  }
  function move(e) {
    if (Math.abs(e.clientX - origin.current.x) > slop ||
        Math.abs(e.clientY - origin.current.y) > slop) {
      clearTimeout(timer.current)
    }
  }
  function end() {
    clearTimeout(timer.current)
  }
  function clickGuard(e) {
    if (fired.current) {
      e.preventDefault()
      e.stopPropagation()
      fired.current = false
      return true // caller should bail out of its own click handling
    }
    return false
  }
  return { begin, move, end, clickGuard }
}
