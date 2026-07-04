import { useNavigate } from 'react-router-dom'
import TapLink from '../components/TapLink'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'

export default function More() {
  const { user, logout } = useAuth()
  const { mode, setMode } = useTheme()
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
        <TapLink to="/settings" className="more-row">
          <span>Settings</span>
          <span className="more-chevron">›</span>
        </TapLink>
        <div className="more-row more-row-appearance">
          <span>Appearance</span>
          <div className="theme-seg" role="group" aria-label="Appearance">
            {['light', 'system', 'dark'].map((m) => (
              <button
                key={m}
                type="button"
                className={'theme-seg-btn' + (mode === m ? ' active' : '')}
                aria-pressed={mode === m}
                onClick={() => setMode(m)}
              >
                {m === 'light' ? 'Light' : m === 'system' ? 'System' : 'Dark'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Groups */}
      <div className="more-section">
        <TapLink to="/dashboard" className="more-row">
          <span>My Groups</span><span className="more-chevron">›</span>
        </TapLink>
        <TapLink to="/groups/new" className="more-row">
          <span>New Group</span><span className="more-chevron">›</span>
        </TapLink>
        <TapLink to="/groups/join" className="more-row">
          <span>Join Group</span><span className="more-chevron">›</span>
        </TapLink>
      </div>

      {/* App */}
      <div className="more-section">
        <TapLink to="/support" className="more-row">
          <span>Support</span><span className="more-chevron">›</span>
        </TapLink>
        <TapLink to="/legal/privacy" className="more-row">
          <span>Privacy Policy</span><span className="more-chevron">›</span>
        </TapLink>
        <TapLink to="/legal/terms" className="more-row">
          <span>Terms of Service</span><span className="more-chevron">›</span>
        </TapLink>
      </div>

      {/* Admin */}
      {user?.is_admin && (
        <div className="more-section">
          <TapLink to="/admin-tools" className="more-row">
            <span>Admin</span><span className="more-chevron">›</span>
          </TapLink>
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
