import { createContext, useContext, useState, useEffect, useCallback } from 'react'

const ThemeContext = createContext(null)

// Modes: 'light' | 'dark' | 'system'. Default (no stored choice) = dark.
const prefersDark = () => window.matchMedia('(prefers-color-scheme: dark)')

function resolvesDark(mode) {
  return mode === 'dark' || (mode === 'system' && prefersDark().matches)
}

// Tell the native iOS layer (AppDelegate's fsTheme handler) the current bg color
// so the rubber-band/overscroll area is painted to match instead of flashing the
// light default. No-op on web (the handler doesn't exist there).
function syncNativeTheme() {
  try {
    const h = window.webkit?.messageHandlers?.fsTheme
    if (!h) return
    const hex = getComputedStyle(document.documentElement)
      .getPropertyValue('--bg-primary').trim()
    if (hex) h.postMessage(hex)
  } catch { /* never let theme sync throw */ }
}

function applyTheme(mode) {
  if (resolvesDark(mode)) document.documentElement.setAttribute('data-theme', 'dark')
  else document.documentElement.removeAttribute('data-theme')
  syncNativeTheme()
}

export function ThemeProvider({ children }) {
  const [mode, setModeState] = useState(() => localStorage.getItem('theme') || 'dark')

  const setMode = useCallback((m) => {
    localStorage.setItem('theme', m)
    setModeState(m)
    applyTheme(m)
  }, [])

  useEffect(() => { applyTheme(mode) }, [mode])

  // Live-flip when the OS theme changes while we're in System mode.
  useEffect(() => {
    const m = prefersDark()
    const onChange = () => {
      if ((localStorage.getItem('theme') || 'dark') === 'system') applyTheme('system')
    }
    m.addEventListener('change', onChange)
    return () => m.removeEventListener('change', onChange)
  }, [])

  return (
    <ThemeContext.Provider value={{ mode, setMode }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
