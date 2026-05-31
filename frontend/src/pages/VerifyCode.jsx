import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { verifyCode, sendCode } from '../api/auth'
import { useAuth } from '../context/AuthContext'

export default function VerifyCode() {
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  const email  = params.get('email') || ''
  const next   = params.get('next')  || '/dashboard'

  const [code, setCode]   = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy]   = useState(false)
  const [resent, setResent] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const data = await verifyCode({ email, code })
      setUser(data.user)
      navigate(data.next || next)
    } catch (err) {
      setError(err.message || 'Invalid code')
    } finally {
      setBusy(false)
    }
  }

  async function handleResend() {
    try {
      await sendCode({ email })
      setResent(true)
    } catch {}
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">Enter Code</h1>
        <p className="auth-sub">We sent an 8-digit code to <strong>{email}</strong></p>

        {error && <div className="flash flash-error">{error}</div>}
        {resent && <div className="flash flash-success">Code resent!</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          <input type="hidden" name="email" value={email} />
          <div className="form-group">
            <label htmlFor="code">Verification Code</label>
            <input id="code" type="text" required maxLength={8} inputMode="numeric"
              pattern="[0-9]*" autoFocus autoComplete="one-time-code" style={{ fontSize: 16 }}
              value={code} onChange={e => setCode(e.target.value)} />
          </div>
          <button type="submit" className="btn-primary btn-full" disabled={busy}>
            {busy ? 'Verifying…' : 'Sign In'}
          </button>
        </form>

        <p className="auth-switch">
          <button type="button" onClick={handleResend}
            style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: '0.85rem' }}>
            ← Send a new code
          </button>
        </p>
      </div>
    </div>
  )
}
