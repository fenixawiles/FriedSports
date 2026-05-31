import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { sendCode } from '../api/auth'

export default function SendCode() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy]   = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await sendCode({ email })
      navigate(`/verify-code?email=${encodeURIComponent(email)}`)
    } catch (err) {
      setError(err.message || 'Failed to send code')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">Sign In</h1>
        <p className="auth-sub">We'll email you a one-time code.</p>

        {error && <div className="flash flash-error">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" required autoComplete="email" style={{ fontSize: 16 }}
              value={email} onChange={e => setEmail(e.target.value)} />
          </div>
          <button type="submit" className="btn-primary btn-full" disabled={busy}>
            {busy ? 'Sending…' : 'Send Code'}
          </button>
        </form>

        <p className="auth-switch">
          <Link to="/login" style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
            ← Back to password login
          </Link>
        </p>
      </div>
    </div>
  )
}
