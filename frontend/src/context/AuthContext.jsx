import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { getMe, logout as apiLogout } from '../api/auth'
import { initPush } from '../native/push'

const AuthContext = createContext(null)
const AUTH_USER_KEY = 'FRIEDSPORTS_AUTH_USER'

function readCachedUser() {
  try {
    const raw = localStorage.getItem(AUTH_USER_KEY)
    return raw ? JSON.parse(raw) : undefined
  } catch {
    return undefined
  }
}

function persistUser(user) {
  try {
    if (user) localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user))
    else localStorage.removeItem(AUTH_USER_KEY)
  } catch {
    // localStorage can be unavailable in private/locked-down contexts.
  }
}

export function AuthProvider({ children }) {
  const [userState, setUserState] = useState(readCachedUser) // undefined = unknown, null = not authed
  const [loading, setLoading] = useState(true)

  const setUser = useCallback((next) => {
    setUserState((prev) => {
      const resolved = typeof next === 'function' ? next(prev) : next
      persistUser(resolved)
      return resolved
    })
  }, [])

  // Fetch current user from Flask session on mount
  const refresh = useCallback(async () => {
    try {
      const data = await getMe()
      setUser(data.user)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [setUser])

  useEffect(() => { refresh() }, [refresh])

  // Register for APNs push once we know who the user is (native shell only;
  // initPush self-guards against web, denial, and double-wiring).
  useEffect(() => {
    if (userState?.id) initPush()
  }, [userState?.id])

  const logout = useCallback(async () => {
    try { await apiLogout() } catch {}
    setUser(null)
  }, [setUser])

  return (
    <AuthContext.Provider value={{ user: userState, loading, setUser, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
