import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { signup } from '../api/auth'
import { useAuth } from '../context/AuthContext'

export default function Signup() {
  const { setUser } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    first_name: '', last_name: '', display_name: '',
    display_preference: 'username', email: '', password: '', confirm_password: '',
    agree_terms: false,
  })
  const [error, setError]   = useState('')
  const [busy, setBusy]     = useState(false)

  const set = (key) => (e) => setForm(f => ({ ...f, [key]: e.target.value }))
  const setCheck = (key) => (e) => setForm(f => ({ ...f, [key]: e.target.checked }))

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (form.password !== form.confirm_password) { setError('Passwords do not match'); return }
    if (!form.agree_terms) { setError('You must agree to the Terms and community guidelines to sign up.'); return }
    setBusy(true)
    try {
      const data = await signup(form)
      if (data.next === 'verify-code') {
        navigate(`/verify-code?email=${encodeURIComponent(form.email)}&next=/onboarding`)
      } else if (data.user) {
        setUser(data.user)
        navigate('/onboarding')
      }
    } catch (err) {
      setError(err.message || 'Signup failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">Create Account</h1>
        <p className="auth-sub">Pick your teams, join the trash talk.</p>

        {error && <div className="flash flash-error">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="name-grid">
            <div className="form-group">
              <label htmlFor="first_name">First Name</label>
              <input id="first_name" type="text" required maxLength={64} style={{ fontSize: 16 }}
                value={form.first_name} onChange={set('first_name')} />
            </div>
            <div className="form-group">
              <label htmlFor="last_name">Last Name</label>
              <input id="last_name" type="text" required maxLength={64} style={{ fontSize: 16 }}
                value={form.last_name} onChange={set('last_name')} />
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="display_name">Username</label>
            <input id="display_name" type="text" required maxLength={64} style={{ fontSize: 16 }}
              value={form.display_name} onChange={set('display_name')} />
          </div>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" required style={{ fontSize: 16 }}
              value={form.email} onChange={set('email')} />
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" required minLength={6} style={{ fontSize: 16 }}
              value={form.password} onChange={set('password')} />
          </div>
          <div className="form-group">
            <label htmlFor="confirm_password">Confirm Password</label>
            <input id="confirm_password" type="password" required style={{ fontSize: 16 }}
              value={form.confirm_password} onChange={set('confirm_password')} />
          </div>
          <label className="signup-terms-row">
            <input type="checkbox" checked={form.agree_terms} onChange={setCheck('agree_terms')} required />
            <span>
              I agree to the <Link to="/legal/terms" target="_blank" rel="noopener noreferrer">Terms</Link>,
              {' '}<Link to="/legal/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</Link>,
              and community guidelines.
            </span>
          </label>
          <button type="submit" className="btn-primary btn-full" disabled={busy}>
            {busy ? 'Creating account…' : 'Create Account'}
          </button>
        </form>

        <p className="auth-switch">Already have an account? <Link to="/login">Log in</Link></p>
      </div>
    </div>
  )
}
