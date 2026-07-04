import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSettings, updateSettings, deleteAccount, uploadAvatar, removeAvatar } from '../api/user'
import { useAuth } from '../context/AuthContext'
import BackButton from '../components/BackButton'
import IdentityAvatar from '../components/IdentityAvatar'
import Loading from '../components/Loading'
import { fileToSquareDataUrl } from '../utils/imageCrop'
import { haptic } from '../native/haptics'

export default function Settings() {
  const navigate = useNavigate()
  const { logout } = useAuth()
  const { data, isLoading } = useQuery({ queryKey: ['settings'], queryFn: getSettings })

  const qc = useQueryClient()
  const [form, setForm] = useState({
    first_name: '', last_name: '', display_name: '',
    display_preference: 'username',
    current_password: '', new_password: '', confirm_password: '',
  })
  // Photo lives OUTSIDE the form: upload/remove hit dedicated endpoints so a
  // later "Save Changes" can never clobber a fresh upload with a stale URL.
  const [avatarUrl, setAvatarUrl] = useState('')
  const [avatarBusy, setAvatarBusy] = useState(false)
  const fileRef = useRef(null)
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
    }))
    setAvatarUrl(u.avatar_url || '')
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

  async function handlePhotoPick(e) {
    const file = e.target.files?.[0]
    e.target.value = '' // allow re-picking the same file
    if (!file) return
    setError('')
    setAvatarBusy(true)
    try {
      const dataUrl = await fileToSquareDataUrl(file)
      const res = await uploadAvatar(dataUrl)
      setAvatarUrl(res.avatar_url || dataUrl)
      haptic('success')
      // Every list that shows the user's face refreshes on next fetch.
      qc.invalidateQueries(['settings'])
      qc.invalidateQueries(['friends'])
      qc.invalidateQueries(['feed'])
    } catch (err) {
      setError(err.message || 'Could not upload that photo')
    } finally {
      setAvatarBusy(false)
    }
  }

  async function handlePhotoRemove() {
    setError('')
    setAvatarBusy(true)
    try {
      await removeAvatar()
      setAvatarUrl('')
      qc.invalidateQueries(['settings'])
    } catch (err) {
      setError(err.message || 'Could not remove photo')
    } finally {
      setAvatarBusy(false)
    }
  }

  if (isLoading) return <Loading full />

  const { teams_by_league = {}, league_labels = {} } = data ?? {}
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  return (
    <div className="settings-page">
      <BackButton fallback="/more" />
      <div className="settings-title-row">
        <span className="section-title">Settings</span>
      </div>

      {error   && <div className="flash flash-error">{error}</div>}
      {success && <div className="flash flash-success">{success}</div>}

      <form className="settings-form" onSubmit={(e) => { e.preventDefault(); handleSave() }}>
        <div className="settings-label">Profile</div>
        <div className="settings-group">
          <div className="settings-row">
            <label htmlFor="display_name">Username</label>
            <input id="display_name" type="text" maxLength={64}
              value={form.display_name} onChange={set('display_name')} placeholder="username" />
          </div>
          <div className="settings-row">
            <label htmlFor="first_name">First name</label>
            <input id="first_name" type="text" maxLength={64}
              value={form.first_name} onChange={set('first_name')} placeholder="First" />
          </div>
          <div className="settings-row">
            <label htmlFor="last_name">Last name</label>
            <input id="last_name" type="text" maxLength={64}
              value={form.last_name} onChange={set('last_name')} placeholder="Last" />
          </div>
          <div className="settings-row settings-row-stack">
            <label>Show others my</label>
            <div className="settings-segment">
              {['username','real_name'].map(v => (
                <label key={v}>
                  <input type="radio" name="display_preference" value={v}
                    checked={form.display_preference === v} onChange={set('display_preference')} />
                  <span>{v === 'username' ? 'Username' : 'Real name'}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="settings-row settings-photo-row">
            <label>Photo</label>
            <div className="settings-photo-controls">
              <IdentityAvatar
                identity={{ kind: 'user', label: form.display_name || '?', avatar_url: avatarUrl }}
                className="settings-photo-preview" />
              <input ref={fileRef} type="file" accept="image/*" hidden onChange={handlePhotoPick} />
              <button type="button" className="btn-secondary-small" disabled={avatarBusy}
                onClick={() => fileRef.current?.click()}>
                {avatarBusy ? 'Working…' : (avatarUrl ? 'Change' : 'Upload')}
              </button>
              {avatarUrl && (
                <button type="button" className="btn-danger-small" disabled={avatarBusy}
                  onClick={handlePhotoRemove}>
                  Remove
                </button>
              )}
            </div>
          </div>
        </div>
        {data?.user?.uid && (
          <div className="settings-hint">Your FS ID is <code>{data.user.uid}</code> — share it to get added.</div>
        )}

        <div className="settings-label">Teams <span className="settings-label-sub">one per league</span></div>
        <div className="settings-group">
          {Object.entries(teams_by_league).map(([league, teams]) => (
            <div key={league} className="settings-row">
              <label htmlFor={`${league.toLowerCase()}_team_id`}>{league_labels[league] || league}</label>
              <select value={teamSelections[`${league.toLowerCase()}_team_id`] || ''}
                id={`${league.toLowerCase()}_team_id`}
                className="settings-select"
                onChange={e => setTeamSelections(s => ({ ...s, [`${league.toLowerCase()}_team_id`]: e.target.value }))}>
                <option value="">None</option>
                {teams.map(t => <option key={t.id} value={t.id}>{t.city} {t.name}</option>)}
              </select>
            </div>
          ))}
        </div>

        <div className="settings-label">Password <span className="settings-label-sub">optional</span></div>
        <div className="settings-group">
          <div className="settings-row">
            <label htmlFor="current_password">Current</label>
            <input id="current_password" type="password" value={form.current_password}
              onChange={set('current_password')} placeholder="Leave blank to keep" />
          </div>
          <div className="settings-row">
            <label htmlFor="new_password">New</label>
            <input id="new_password" type="password" value={form.new_password}
              onChange={set('new_password')} placeholder="6+ characters" />
          </div>
          <div className="settings-row">
            <label htmlFor="confirm_password">Confirm</label>
            <input id="confirm_password" type="password" value={form.confirm_password}
              onChange={set('confirm_password')} placeholder="Repeat new" />
          </div>
        </div>

        <button type="submit" className="btn-primary btn-full settings-save-btn" disabled={saveMut.isPending}>
          {saveMut.isPending ? 'Saving…' : 'Save changes'}
        </button>
      </form>

      <div className="settings-label">Safety</div>
      <div className="settings-group">
        <Link to="/friends/blocked" className="settings-row settings-link">
          <span>Blocked users</span>
          <span className="more-chevron">›</span>
        </Link>
      </div>

      <div className="settings-label settings-label-danger">Danger zone</div>
      <div className="settings-group">
        <div className="settings-delete">
          <div className="settings-row settings-row-stack settings-delete-row">
            <label htmlFor="confirm_password_delete">Delete account — confirm with your password</label>
            <input id="confirm_password_delete" type="password" placeholder="Your password"
              value={confirmPw} onChange={e => setConfirmPw(e.target.value)} />
          </div>
          <button type="button" className="settings-delete-btn"
            onClick={() => { if(window.confirm('This permanently deletes your account and all data. There is no undo.')) deleteMut.mutate() }}
            disabled={!confirmPw || deleteMut.isPending}>
            {deleteMut.isPending ? 'Deleting…' : 'Delete my account'}
          </button>
        </div>
      </div>

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
