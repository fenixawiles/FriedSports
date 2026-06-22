import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getReportForm, startThread } from '../api/groups'
import { useAuth } from '../context/AuthContext'
import BackButton from '../components/BackButton'
import Loading from '../components/Loading'

const INCIDENT_LABELS = {
  BLOWOUT_ALERT: 'Blowout Alert',
  CHOKED_LEAD: 'Choked Lead',
  FRAUD_WATCH: 'Fraud Watch',
  UPSET_ALERT: 'Upset Alert',
  DISASTER_QUARTER: 'Disaster Quarter',
  PLAYOFF_COLLAPSE: 'Playoff Collapse',
  SHUTOUT_RISK: 'Shutout Risk',
  FINAL_LOSS: 'Final Loss',
  RIVAL_LOSS: 'Rival Loss',
  PREMATURE_SLANDER: 'Premature Slander',
}

export default function Report() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()

  const { data, isLoading } = useQuery({
    queryKey: ['report-form', id],
    queryFn: () => getReportForm(id),
  })

  const [form, setForm] = useState({
    target_user_id: '', target_team_id: '',
    incident_type: '', severity: '3', reported_score_text: '',
  })
  const [error, setError] = useState('')
  const [preview, setPreview] = useState({ color: null, abbr: null })

  const mut = useMutation({
    mutationFn: () => startThread(id, form),
    onSuccess: (data) => navigate(`/threads/${data.thread_id}`),
    onError: (err) => setError(err.message || 'Failed to start thread'),
  })

  // Auto-select target user's favorite team when user changes
  useEffect(() => {
    if (!form.target_user_id || !data?.user_fav_teams) return
    const favTeamId = data.user_fav_teams[form.target_user_id]
    if (favTeamId) setForm(f => ({ ...f, target_team_id: String(favTeamId) }))
  }, [form.target_user_id, data])

  // Update color preview when team changes
  useEffect(() => {
    if (!form.target_team_id || !data?.team_colors) return
    const colors = data.team_colors[form.target_team_id]
    if (colors) setPreview({ color: colors.primary, abbr: colors.abbr })
  }, [form.target_team_id, data])

  if (isLoading) return <Loading full />

  const { members = [], teams_by_league = {} } = data ?? {}
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  return (
    <div className="group-container" style={{ maxWidth: 680 }}>
      <BackButton fallback={`/groups/${id}`} label={data?.group_name || 'Group'} />
      <div className="group-header"><h1>Start A Thread</h1></div>

      {error && <div className="flash flash-error">{error}</div>}

      <form onSubmit={e => { e.preventDefault(); mut.mutate() }}
        style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

        <div className="form-group">
          <label htmlFor="target_user">Who's getting roasted?</label>
          <select id="target_user" required value={form.target_user_id} onChange={set('target_user_id')}>
            <option value="">Select a member…</option>
            {members.map(m => (
              <option key={m.user_id} value={m.user_id}>{m.display_name}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="target_team">
            Their team
            {preview.color && (
              <span style={{ marginLeft: 8, color: preview.color, fontWeight: 700 }}>
                {preview.abbr}
              </span>
            )}
          </label>
          <select id="target_team" required value={form.target_team_id} onChange={set('target_team_id')}>
            <option value="">Select a team…</option>
            {Object.entries(teams_by_league).map(([league, teams]) => (
              <optgroup key={league} label={league}>
                {teams.map(t => (
                  <option key={t.id} value={t.id}
                    data-primary={t.primary_color} data-abbr={t.abbreviation}>
                    {t.city} {t.name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Type of Incident</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.4rem' }}>
            {Object.entries(INCIDENT_LABELS).map(([val, label]) => (
              <label key={val} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.85rem', cursor: 'pointer' }}>
                <input type="radio" name="incident_type" value={val} required
                  checked={form.incident_type === val} onChange={set('incident_type')} />
                {label}
              </label>
            ))}
          </div>
        </div>

        <div className="form-group">
          <label>Severity</label>
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.4rem' }}>
            {[1,2,3,4,5].map(n => (
              <label key={n} style={{ display: 'flex', alignItems: 'center', gap: '0.2rem', fontSize: '0.85rem', cursor: 'pointer' }}>
                <input type="radio" name="severity" value={n}
                  checked={Number(form.severity) === n} onChange={set('severity')} />
                {n}
              </label>
            ))}
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="score_text">Score / Context <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>(optional)</span></label>
          <input id="score_text" type="text" maxLength={120} style={{ fontSize: 16 }}
            placeholder="e.g. Down 20 in the 4th…"
            value={form.reported_score_text} onChange={set('reported_score_text')} />
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button type="submit" className="btn-primary" disabled={mut.isPending}>
            {mut.isPending ? 'Opening…' : 'Open Slander Thread'}
          </button>
          <button type="button" className="btn-secondary" onClick={() => navigate(-1)}>Cancel</button>
        </div>
      </form>
    </div>
  )
}
