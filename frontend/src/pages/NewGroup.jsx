import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createGroup } from '../api/groups'
import BackButton from '../components/BackButton'

const LEAGUES = ['MULTI','NBA','NFL','MLB','NHL','EPL','FIFA','F1','PGA']

export default function NewGroup() {
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', league_scope: 'MULTI', privacy: 'private' })
  const [error, setError] = useState('')
  const [busy, setBusy]   = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    try {
      const data = await createGroup(form)
      navigate(`/groups/${data.group.id}`)
    } catch (err) {
      setError(err.message || 'Failed to create group')
    } finally {
      setBusy(false)
    }
  }

  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  return (
    <div className="group-container" style={{ maxWidth: 680 }}>
      <BackButton fallback="/dashboard" />
      <div className="group-header"><h1>New Group</h1></div>

      {error && <div className="flash flash-error">{error}</div>}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <div className="form-group">
          <label htmlFor="name">Group Name</label>
          <input id="name" type="text" required maxLength={100} style={{ fontSize: 16 }}
            value={form.name} onChange={set('name')} />
        </div>
        <div className="form-group">
          <label htmlFor="league_scope">League Focus</label>
          <select id="league_scope" value={form.league_scope} onChange={set('league_scope')}>
            {LEAGUES.map(l => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="privacy">Privacy</label>
          <select id="privacy" value={form.privacy} onChange={set('privacy')}>
            <option value="private">Private</option>
            <option value="public_readonly">Public (read-only)</option>
          </select>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? 'Creating…' : 'Create Group'}
          </button>
          <button type="button" className="btn-secondary" onClick={() => navigate(-1)}>Cancel</button>
        </div>
      </form>
    </div>
  )
}
