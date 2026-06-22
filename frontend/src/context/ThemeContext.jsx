import { createContext, useContext, useState, useEffect, useCallback } from 'react'

const ThemeContext = createContext(null)

// Modes: 'light' | 'dark' | 'system'. Default (no stored choice) = dark.
const prefersDark = () => window.matchMedia('(prefers-color-scheme: dark)')

function resolvesDark(mode) {
  return mode === 'dark' || (mode === 'system' && prefersDark().matches)
}

function applyTheme(mode) {
  if (resolvesDark(mode)) document.documentElement.setAttribute('data-theme', 'dark')
  else document.documentElement.removeAttribute('data-theme')
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
