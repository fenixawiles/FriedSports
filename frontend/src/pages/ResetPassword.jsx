import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { resetPassword } from '../api/auth'
import { useAuth } from '../context/AuthContext'

export default function ResetPassword() {
  const { token } = useParams()
  const { setUser } = useAuth()
  const navigate = useNavigate()

  const [form, setForm]   = useState({ password: '', confirm_password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy]   = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (form.password !== form.confirm_password) { setError('Passwords do not match'); return }
    setBusy(true)
    try {
      const data = await resetPassword(token, { password: form.password })
      setUser(data.user)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || 'Reset failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">New Password</h1>

        {error && <div className="flash flash-error">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="password">New Password</label>
            <input id="password" type="password" required minLength={6} style={{ fontSize: 16 }}
              value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
          </div>
          <div className="form-group">
            <label htmlFor="confirm">Confirm Password</label>
            <input id="confirm" type="password" required style={{ fontSize: 16 }}
              value={form.confirm_password} onChange={e => setForm(f => ({ ...f, confirm_password: e.target.value }))} />
          </div>
          <button type="submit" className="btn-primary btn-full" disabled={busy}>
            {busy ? 'Saving…' : 'Set Password'}
          </button>
        </form>
      </div>
    </div>
  )
}
