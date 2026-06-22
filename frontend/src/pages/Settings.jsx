import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getSettings, updateSettings, deleteAccount } from '../api/user'
import { useAuth } from '../context/AuthContext'
import BackButton from '../components/BackButton'
import Loading from '../components/Loading'

export default function Settings() {
  const navigate = useNavigate()
  const { logout } = useAuth()
  const { data, isLoading } = useQuery({ queryKey: ['settings'], queryFn: getSettings })

  const [form, setForm] = useState({
    first_name: '', last_name: '', display_name: '',
    display_preference: 'username', avatar_url: '',
    current_password: '', new_password: '', confirm_password: '',
  })
  const [teamSelections, setTeamSelections] = useState({})
  const [error, setError]   = useState('')
  const [success, setSuccess] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [showPwSheet, setShowPwSheet] = useState(false)

  useEffect(() => {
    if (!data?.user) return
    const u = data.user
    setForm(f => ({
      ...f,
      first_name: u.first_name || '',
      last_name: u.last_name || '',
      display_name: u.display_name || '',
      display_preference: u.display_preference || 'username',
      avatar_url: u.avatar_url || '',
    }))
    if (data.fav_teams) {
      const sel = {}
      Object.entries(data.fav_teams).forEach(([league, t]) => {
        sel[`${league.toLowerCase()}_team_id`] = t?.id || ''
      })
      setTeamSelections(sel)
    }
  }, [data])

  const saveMut = useMutation({
    mutationFn: (scope) => updateSettings({ ...form, ...teamSelections, session_scope: scope || '' }),
    onSuccess: async (data) => {
      if (data?.signed_out) { await logout(); navigate('/login'); return }
      setSuccess('Settings saved!'); setTimeout(() => setSuccess(''), 3000)
      setForm(f => ({ ...f, current_password: '', new_password: '', confirm_password: '' }))
    },
    onError: (err) => setError(err.message || 'Failed to save'),
  })

  function handleSave() {
    setError('')
    // Changing the password requires choosing which devices stay signed in.
    if (form.new_password) { setShowPwSheet(true); return }
    saveMut.mutate('')
  }
  function chooseScope(scope) {
    setShowPwSheet(false)
    saveMut.mutate(scope)
  }

  const deleteMut = useMutation({
    mutationFn: () => deleteAccount({ password: confirmPw }),
    onSuccess: async () => { await logout(); navigate('/') },
    onError: (err) => setError(err.message || 'Delete failed'),
  })

  if (isLoading) return <Loading full />

  const { teams_by_league = {}, league_labels = {} } = data ?? {}
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  return (
    <div className="group-container" style={{ maxWidth: 680 }}>
      <BackButton fallback="/more" />
      <div className="group-header"><h1>Settings</h1></div>

      {error   && <div className="flash flash-error">{error}</div>}
      {success && <div className="flash flash-success">{success}</div>}

      {/* Identity */}
      <section className="group-section">
        <div className="section-header"><span className="section-title">Profile</span></div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="form-group">
            <label>First Name</label>
            <input type="text" maxLength={64} style={{ fontSize: 16 }}
              value={form.first_name} onChange={set('first_name')} />
          </div>
          <div className="form-group">
            <label>Last Name</label>
            <input type="text" maxLength={64} style={{ fontSize: 16 }}
              value={form.last_name} onChange={set('last_name')} />
          </div>
          <div className="form-group">
            <label>Username</label>
            <input type="text" maxLength={64} style={{ fontSize: 16 }}
              value={form.display_name} onChange={set('display_name')} />
          </div>
          <div className="form-group">
            <label>Display As</label>
            <div style={{ display: 'flex', gap: '1rem', marginTop: '0.3rem' }}>
              {['username','real_name'].map(v => (
                <label key={v} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.85rem', cursor: 'pointer' }}>
                  <input type="radio" name="display_preference" value={v}
                    checked={form.display_preference === v} onChange={set('display_preference')} />
                  {v === 'username' ? 'Username' : 'Real name'}
                </label>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Teams */}
      <section className="group-section">
        <div className="section-header"><span className="section-title">Favorite Teams</span></div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {Object.entries(teams_by_league).map(([league, teams]) => (
            <div key={league} className="form-group">
              <label>{league_labels[league] || league}</label>
              <select value={teamSelections[`${league.toLowerCase()}_team_id`] || ''}
                onChange={e => setTeamSelections(s => ({ ...s, [`${league.toLowerCase()}_team_id`]: e.target.value }))}>
                <option value="">No team</option>
                {teams.map(t => <option key={t.id} value={t.id}>{t.city} {t.name}</option>)}
              </select>
            </div>
          ))}
        </div>
      </section>

      {/* Password */}
      <section className="group-section">
        <div className="section-header"><span className="section-title">Change Password</span></div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {['current_password','new_password','confirm_password'].map(k => (
            <div key={k} className="form-group">
              <label>{k.replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase())}</label>
              <input type="password" style={{ fontSize: 16 }}
                value={form[k]} onChange={set(k)} />
            </div>
          ))}
        </div>
      </section>

      <button className="btn-primary" style={{ marginBottom: '2rem' }}
        onClick={handleSave} disabled={saveMut.isPending}>
        {saveMut.isPending ? 'Saving…' : 'Save Changes'}
      </button>

      {/* Danger zone */}
      <section className="group-section group-danger-zone">
        <span className="section-title" style={{ color: 'var(--accent)' }}>Delete Account</span>
        <p className="group-danger-hint">This is permanent and cannot be undone.</p>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input type="password" placeholder="Confirm password" style={{ fontSize: 16, flex: 1, minWidth: 200 }}
            value={confirmPw} onChange={e => setConfirmPw(e.target.value)} />
          <button className="btn-danger-small"
            onClick={() => { if(window.confirm('Permanently delete your account?')) deleteMut.mutate() }}
            disabled={!confirmPw || deleteMut.isPending}>
            Delete Account
          </button>
        </div>
      </section>

      {/* Password-change device sign-out sheet */}
      {showPwSheet && (
        <div className="pw-sheet" onClick={(e) => { if (e.target === e.currentTarget) setShowPwSheet(false) }}>
          <div className="pw-sheet-backdrop" onClick={() => setShowPwSheet(false)} />
          <div className="pw-sheet-card" role="dialog" aria-modal="true">
            <div className="pw-sheet-head">
              <div className="pw-sheet-title">Update your password</div>
              <div className="pw-sheet-sub">Choose which devices stay signed in.</div>
            </div>
            <button type="button" className="pw-sheet-opt" onClick={() => chooseScope('this_device')}>
              <span className="pw-opt-main">Sign out other devices</span>
              <span className="pw-opt-sub">Stay signed in on this device only</span>
            </button>
            <button type="button" className="pw-sheet-opt" onClick={() => chooseScope('all_devices')}>
              <span className="pw-opt-main">Keep all devices signed in</span>
              <span className="pw-opt-sub">Nothing else gets logged out</span>
            </button>
            <button type="button" className="pw-sheet-opt pw-opt-danger" onClick={() => chooseScope('sign_out_all')}>
              <span className="pw-opt-main">Sign out everywhere</span>
              <span className="pw-opt-sub">This device too — you'll log in again</span>
            </button>
            <button type="button" className="pw-sheet-cancel" onClick={() => setShowPwSheet(false)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  )
}
