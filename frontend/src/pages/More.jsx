import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'

export default function More() {
  const { user, logout } = useAuth()
  const { dark, toggle } = useTheme()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <div className="more-container">
      {user && (
        <div className="more-user-card">
          <div className="more-user-name">{user.name}</div>
          <div className="more-user-uid">{user.uid}</div>
        </div>
      )}

      {/* Account */}
      <div className="more-section">
        <Link to="/settings" className="more-row">
          <span>Settings</span>
          <span className="more-chevron">›</span>
        </Link>
        <label className="more-row more-row-toggle" style={{ cursor: 'pointer' }}>
          <span>Dark Mode</span>
          <span className="theme-switch">
            <input type="checkbox" checked={dark} onChange={toggle} style={{ display: 'none' }} />
            <span className="theme-switch-track" style={{
              display: 'inline-block', width: 44, height: 24, borderRadius: 12,
              background: dark ? 'var(--accent)' : 'var(--bg-elevated)',
              border: '2px solid var(--border)',
              position: 'relative', transition: 'background 0.2s',
            }}>
              <span style={{
                position: 'absolute', top: 2, left: dark ? 20 : 2,
                width: 16, height: 16, borderRadius: '50%',
                background: dark ? '#fff' : 'var(--text-muted)',
                transition: 'left 0.2s',
              }} />
            </span>
          </span>
        </label>
      </div>

      {/* Groups */}
      <div className="more-section">
        <Link to="/dashboard" className="more-row">
          <span>My Groups</span><span className="more-chevron">›</span>
        </Link>
        <Link to="/groups/new" className="more-row">
          <span>New Group</span><span className="more-chevron">›</span>
        </Link>
        <Link to="/groups/join" className="more-row">
          <span>Join Group</span><span className="more-chevron">›</span>
        </Link>
      </div>

      {/* App */}
      <div className="more-section">
        <Link to="/support" className="more-row">
          <span>Support</span><span className="more-chevron">›</span>
        </Link>
        <Link to="/legal/privacy" className="more-row">
          <span>Privacy Policy</span><span className="more-chevron">›</span>
        </Link>
        <Link to="/legal/terms" className="more-row">
          <span>Terms of Service</span><span className="more-chevron">›</span>
        </Link>
      </div>

      {/* Admin */}
      {user?.is_admin && (
        <div className="more-section">
          <a href="/admin/dashboard" className="more-row">
            <span>Admin</span><span className="more-chevron">›</span>
          </a>
        </div>
      )}

      {/* Logout */}
      <div className="more-section">
        <button onClick={handleLogout}
          className="more-row more-row-danger"
          style={{ width: '100%', textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer' }}>
          Log Out
        </button>
      </div>
    </div>
  )
}
