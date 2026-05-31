import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { getMe, logout as apiLogout } from '../api/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(undefined) // undefined = loading, null = not authed
  const [loading, setLoading] = useState(true)

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
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const logout = useCallback(async () => {
    try { await apiLogout() } catch {}
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, setUser, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
