import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

const THRESHOLD = 68
const MAX_PULL = 96

function isEditableTarget(el) {
  if (!el) return false
  return !!el.closest?.('input, textarea, select, [contenteditable="true"], .pw-sheet, .bottom-nav, .navbar')
}

export default function PullToRefresh({ disabled = false }) {
  const qc = useQueryClient()
  const [pull, setPull] = useState(0)
  const [refreshing, setRefreshing] = useState(false)
  const state = useRef({ tracking: false, startX: 0, startY: 0, pull: 0, refreshing: false })

  useEffect(() => {
    state.current.refreshing = refreshing
  }, [refreshing])

  useEffect(() => {
    if (disabled) return

    function reset() {
      state.current.tracking = false
      state.current.pull = 0
      setPull(0)
    }

    async function refresh() {
      setRefreshing(true)
      state.current.refreshing = true
      try {
        await Promise.all([
          qc.invalidateQueries({ refetchType: 'active' }),
          new Promise(resolve => setTimeout(resolve, 450)),
        ])
      } finally {
        setRefreshing(false)
        state.current.refreshing = false
        reset()
      }
    }

    function onTouchStart(e) {
      if (state.current.refreshing || e.touches.length !== 1) return
      if (window.scrollY > 0 || document.documentElement.scrollTop > 0) return
      if (document.body.classList.contains('input-focus-mode')) return
      if (isEditableTarget(e.target)) return
      const touch = e.touches[0]
      state.current.tracking = true
      state.current.startX = touch.clientX
      state.current.startY = touch.clientY
      state.current.pull = 0
    }

    function onTouchMove(e) {
      if (!state.current.tracking || e.touches.length !== 1) return
      const touch = e.touches[0]
      const dx = touch.clientX - state.current.startX
      const dy = touch.clientY - state.current.startY

      if (dy < 0 || window.scrollY > 0 || document.documentElement.scrollTop > 0) {
        reset()
        return
      }
      if (Math.abs(dx) > Math.abs(dy) || dy < 8) return

      e.preventDefault()
      const next = Math.min(MAX_PULL, (dy - 8) * 0.55)
      state.current.pull = next
      setPull(next)
    }

    function onTouchEnd() {
      if (!state.current.tracking) return
      if (state.current.pull >= THRESHOLD) {
        void refresh()
      } else {
        reset()
      }
    }

    document.addEventListener('touchstart', onTouchStart, { passive: true })
    document.addEventListener('touchmove', onTouchMove, { passive: false })
    document.addEventListener('touchend', onTouchEnd, { passive: true })
    document.addEventListener('touchcancel', reset, { passive: true })
    return () => {
      document.removeEventListener('touchstart', onTouchStart)
      document.removeEventListener('touchmove', onTouchMove)
      document.removeEventListener('touchend', onTouchEnd)
      document.removeEventListener('touchcancel', reset)
    }
  }, [disabled, qc])

  const active = pull > 0 || refreshing
  const armed = pull >= THRESHOLD || refreshing

  return (
    <div
      className={`pull-refresh-indicator${active ? ' visible' : ''}${armed ? ' armed' : ''}${refreshing ? ' refreshing' : ''}`}
      aria-hidden={!active}
      style={{ '--pull-y': `${Math.min(36, pull * 0.38)}px` }}>
      <span className="pull-refresh-glyph" />
    </div>
  )
}
