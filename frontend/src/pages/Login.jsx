import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { login } from '../api/auth'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const next = new URLSearchParams(location.search).get('next') || '/dashboard'

  const [form, setForm]   = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy]   = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const data = await login(form)
      if (data.next === 'verify-code') {
        navigate(`/verify-code?email=${encodeURIComponent(form.email)}&next=${encodeURIComponent(next)}`)
      } else if (data.user) {
        setUser(data.user)
        navigate(next)
      }
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">Welcome Back</h1>
        <p className="auth-sub">Your group has been talking while you were gone.</p>

        {error && <div className="flash flash-error">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" required placeholder="your@email.com" style={{ fontSize: 16 }}
              value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" required placeholder="Your password" style={{ fontSize: 16 }}
              value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
          </div>
          <button type="submit" className="btn-primary btn-full" disabled={busy}>
            {busy ? 'Signing in…' : 'Log In'}
          </button>
        </form>

        <p className="auth-switch" style={{ marginTop: '0.5rem' }}>
          <Link to="/send-code" style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
            Sign in with a code instead →
          </Link>
        </p>
        <p className="auth-switch">New here? <Link to="/signup">Create an account</Link></p>
      </div>
    </div>
  )
}
