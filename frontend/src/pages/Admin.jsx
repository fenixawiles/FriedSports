import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  actionAdminReport,
  approveAdminUser,
  createAdminGame,
  createAdminMetric,
  createAdminPlayer,
  createAdminSeason,
  deleteAdminUser,
  deriveAdminGame,
  emailAdminUser,
  getAdminAuditLog,
  getAdminLab,
  getAdminOverview,
  getAdminReports,
  getAdminSupport,
  getAdminUser,
  getAdminUsers,
  inviteAdminUser,
  promptAdminUser,
  sendAdminBroadcast,
  updateAdminGameStats,
  updateAdminSupportTicket,
  updateAdminUser,
} from '../api/admin'
import BackButton from '../components/BackButton'
import Loading from '../components/Loading'

const TABS = [
  ['users', 'Users'],
  ['support', 'Support'],
  ['reports', 'Reports'],
  ['broadcast', 'Broadcast'],
  ['audit', 'Audit'],
  ['lab', 'Sports Lab'],
]

const STAT_FIELDS = [
  'points', 'fgm', 'fga', 'three_pm', 'three_pa', 'ftm', 'fta',
  'off_rebounds', 'def_rebounds', 'assists', 'steals', 'blocks',
  'turnovers', 'fouls',
]

const emptyStats = STAT_FIELDS.reduce((acc, key) => ({ ...acc, [key]: '' }), {})

function fmtDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function Stat({ label, value }) {
  return (
    <div className="admin-stat">
      <span className="admin-stat-value">{value ?? '—'}</span>
      <span className="admin-stat-label">{label}</span>
    </div>
  )
}

function Notice({ message, tone = 'success' }) {
  if (!message) return null
  return <div className={`flash flash-${tone} admin-flash`}>{message}</div>
}

function TextInput({ label, value, onChange, type = 'text', placeholder = '' }) {
  return (
    <label className="admin-field">
      <span>{label}</span>
      <input type={type} value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)} />
    </label>
  )
}

function SelectInput({ label, value, onChange, children }) {
  return (
    <label className="admin-field">
      <span>{label}</span>
      <select value={value} onChange={e => onChange(e.target.value)}>{children}</select>
    </label>
  )
}

function UsersPanel() {
  const qc = useQueryClient()
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [edit, setEdit] = useState({ email: '', role: 'user', password: '' })
  const [inviteEmail, setInviteEmail] = useState('')
  const [emailForm, setEmailForm] = useState({ subject: '', body: '' })
  const [pendingOnly, setPendingOnly] = useState(false)

  const usersQuery = useQuery({
    queryKey: ['admin-users', query, pendingOnly],
    queryFn: () => getAdminUsers(query, pendingOnly),
  })
  const users = usersQuery.data?.users ?? []
  const pendingCount = usersQuery.data?.pending_count ?? 0
  const firstId = users[0]?.id
  const activeId = selectedId || firstId || null

  const detailQuery = useQuery({
    queryKey: ['admin-user', activeId],
    queryFn: () => getAdminUser(activeId),
    enabled: !!activeId,
  })
  const detail = detailQuery.data
  const user = detail?.user

  useEffect(() => {
    if (!user) return
    setEdit({ email: user.email || '', role: user.role || 'user', password: '' })
  }, [user?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = () => {
    qc.invalidateQueries(['admin-users'])
    qc.invalidateQueries(['admin-user', activeId])
    qc.invalidateQueries(['admin-overview'])
    qc.invalidateQueries(['admin-audit'])
  }

  const updateMut = useMutation({
    mutationFn: () => updateAdminUser(activeId, edit),
    onSuccess: () => { setNotice('User updated'); setError(''); refresh(); setEdit(f => ({ ...f, password: '' })) },
    onError: err => setError(err.message || 'User update failed'),
  })
  const deleteMut = useMutation({
    mutationFn: () => deleteAdminUser(activeId),
    onSuccess: () => { setNotice('User deleted'); setError(''); setSelectedId(null); refresh() },
    onError: err => setError(err.message || 'User delete failed'),
  })
  const inviteMut = useMutation({
    mutationFn: () => inviteAdminUser({ email: inviteEmail }),
    onSuccess: data => {
      setNotice(data.sent ? 'Invite email sent' : `Invite link created: ${data.invite_url}`)
      setError('')
      setInviteEmail('')
      refresh()
    },
    onError: err => setError(err.message || 'Invite failed'),
  })
  const emailMut = useMutation({
    mutationFn: () => emailAdminUser(activeId, emailForm),
    onSuccess: data => {
      setNotice(data.sent ? 'Email sent' : 'Email queued locally but provider is not configured')
      setError('')
      setEmailForm({ subject: '', body: '' })
      refresh()
    },
    onError: err => setError(err.message || 'Email failed'),
  })
  const promptMut = useMutation({
    mutationFn: (kind) => promptAdminUser(activeId, kind),
    onSuccess: data => {
      setNotice(data.sent ? 'Prompt sent' : 'Prompt created, but email provider is not configured')
      setError('')
      refresh()
    },
    onError: err => setError(err.message || 'Prompt failed'),
  })
  const approveMut = useMutation({
    mutationFn: (id) => approveAdminUser(id),
    onSuccess: () => { setNotice('User approved'); setError(''); refresh() },
    onError: err => setError(err.message || 'Approve failed'),
  })

  return (
    <div className="admin-work-grid">
      <section className="admin-panel">
        <div className="admin-panel-head">
          <div>
            <span className="admin-panel-title">Users</span>
            <span className="admin-panel-sub">Search, roles, account actions, and direct emails.</span>
          </div>
        </div>
        <div className="admin-toolbar">
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search users" />
          <button type="button" className="btn-secondary-small" onClick={() => setQuery('')}>Clear</button>
        </div>
        <div className="admin-toolbar">
          <input value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} placeholder="Invite email" />
          <button type="button" className="btn-primary-small" disabled={inviteMut.isPending} onClick={() => inviteMut.mutate()}>
            Invite
          </button>
        </div>
        <div className="admin-filter-row">
          <button type="button" className={pendingOnly ? '' : 'active'} onClick={() => setPendingOnly(false)}>
            All
          </button>
          <button type="button" className={pendingOnly ? 'active' : ''} onClick={() => setPendingOnly(true)}>
            Pending approval {pendingCount > 0 && <span className="notif-count-chip">{pendingCount}</span>}
          </button>
        </div>
        <div className="admin-list">
          {usersQuery.isLoading ? <div className="admin-empty">Loading users…</div> : users.map(row => (
            <button
              type="button"
              key={row.id}
              className={`admin-list-row${activeId === row.id ? ' active' : ''}`}
              onClick={() => setSelectedId(row.id)}>
              <span>
                <strong>{row.name}</strong>
                <small>{row.email}</small>
              </span>
              {row.email_verified
                ? <em>{row.role}</em>
                : <em className="admin-pending-tag">Pending</em>}
            </button>
          ))}
          {!usersQuery.isLoading && users.length === 0 && (
            <div className="admin-empty">{pendingOnly ? 'No one is waiting on approval.' : 'No users found.'}</div>
          )}
        </div>
      </section>

      <section className="admin-panel">
        <Notice message={notice} />
        <Notice message={error} tone="error" />
        {!user ? (
          <div className="admin-empty">Select a user.</div>
        ) : (
          <>
            <div className="admin-detail-head">
              <div>
                <span className="admin-panel-title">{user.name}</span>
                <span className="admin-panel-sub">{user.uid} · joined {fmtDate(user.created_at)}</span>
              </div>
              <div className="admin-detail-badges">
                {!user.email_verified && <span className="admin-pending-tag">Pending</span>}
                <span className={`badge-role ${user.role === 'admin' ? 'owner' : 'member'}`}>{user.role}</span>
              </div>
            </div>
            {!user.email_verified && (
              <div className="admin-approve-banner">
                <span>This account is waiting on approval (verification codes are off).</span>
                <button type="button" className="btn-primary-small" disabled={approveMut.isPending}
                  onClick={() => approveMut.mutate(user.id)}>
                  Approve
                </button>
              </div>
            )}
            <div className="admin-form-grid">
              <TextInput label="Email" value={edit.email} onChange={v => setEdit(f => ({ ...f, email: v }))} />
              <SelectInput label="Role" value={edit.role} onChange={v => setEdit(f => ({ ...f, role: v }))}>
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </SelectInput>
              <TextInput label="New password" type="password" value={edit.password} onChange={v => setEdit(f => ({ ...f, password: v }))} placeholder="Leave blank" />
            </div>
            <div className="admin-actions">
              <button type="button" className="btn-primary-small" disabled={updateMut.isPending} onClick={() => updateMut.mutate()}>
                Save User
              </button>
              <button type="button" className="btn-secondary-small" onClick={() => promptMut.mutate('password')}>Password Reset</button>
              <button type="button" className="btn-secondary-small" onClick={() => promptMut.mutate('username')}>Username Prompt</button>
              <button type="button" className="btn-secondary-small" onClick={() => promptMut.mutate('email')}>Email Prompt</button>
            </div>

            <div className="admin-divider" />
            <div className="admin-form-grid">
              <TextInput label="Subject" value={emailForm.subject} onChange={v => setEmailForm(f => ({ ...f, subject: v }))} />
              <label className="admin-field admin-field-wide">
                <span>Email body</span>
                <textarea value={emailForm.body} onChange={e => setEmailForm(f => ({ ...f, body: e.target.value }))} />
              </label>
            </div>
            <div className="admin-actions">
              <button type="button" className="btn-secondary-small" disabled={emailMut.isPending} onClick={() => emailMut.mutate()}>
                Send Email
              </button>
              <button type="button" className="btn-danger-small"
                disabled={deleteMut.isPending}
                onClick={() => { if (window.confirm(`Delete ${user.email}? This cannot be undone.`)) deleteMut.mutate() }}>
                Delete User
              </button>
            </div>

            <div className="admin-meta-grid">
              <div><span>Terms</span><strong>{fmtDate(user.agreed_to_terms_at)}</strong></div>
              <div><span>Last active</span><strong>{fmtDate(user.last_active_at)}</strong></div>
              <div><span>Status</span><strong>{user.email_verified ? 'Approved' : 'Pending'}</strong></div>
            </div>
            <div className="admin-related">
              <span className="admin-panel-sub">Groups</span>
              {(detail.groups || []).map(g => <span key={`${g.id}-${g.role}`}>{g.name} · {g.role}</span>)}
              {(detail.groups || []).length === 0 && <span>No groups</span>}
            </div>
          </>
        )}
      </section>
    </div>
  )
}

function SupportPanel() {
  const qc = useQueryClient()
  const [status, setStatus] = useState('all')
  const [selectedUid, setSelectedUid] = useState(null)
  const [form, setForm] = useState({ status: '', admin_note: '' })
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const query = useQuery({ queryKey: ['admin-support', status], queryFn: () => getAdminSupport(status) })
  const tickets = query.data?.tickets ?? []
  const active = tickets.find(t => t.uid === selectedUid) || tickets[0]

  useEffect(() => {
    if (!active) return
    setSelectedUid(active.uid)
    setForm({ status: active.next_statuses?.[0] || '', admin_note: active.admin_note || '' })
  }, [active?.uid]) // eslint-disable-line react-hooks/exhaustive-deps

  const updateMut = useMutation({
    mutationFn: () => updateAdminSupportTicket(active.uid, form),
    onSuccess: () => {
      setNotice('Ticket updated')
      setError('')
      qc.invalidateQueries(['admin-support'])
      qc.invalidateQueries(['admin-overview'])
      qc.invalidateQueries(['admin-audit'])
    },
    onError: err => setError(err.message || 'Ticket update failed'),
  })

  return (
    <div className="admin-work-grid">
      <section className="admin-panel">
        <div className="admin-panel-title">Support</div>
        <div className="admin-filter-row">
          {['all', 'received', 'in_progress', 'resolved'].map(s => (
            <button key={s} type="button" className={status === s ? 'active' : ''} onClick={() => setStatus(s)}>
              {s.replace('_', ' ')} {query.data?.counts?.[s] ?? 0}
            </button>
          ))}
        </div>
        <div className="admin-list">
          {query.isLoading ? <div className="admin-empty">Loading tickets…</div> : tickets.map(ticket => (
            <button type="button" key={ticket.uid}
              className={`admin-list-row${active?.uid === ticket.uid ? ' active' : ''}`}
              onClick={() => setSelectedUid(ticket.uid)}>
              <span><strong>{ticket.subject}</strong><small>{ticket.user_name} · {ticket.category}</small></span>
              <em>{ticket.status_label}</em>
            </button>
          ))}
        </div>
      </section>
      <section className="admin-panel">
        <Notice message={notice} />
        <Notice message={error} tone="error" />
        {!active ? <div className="admin-empty">No tickets.</div> : (
          <>
            <div className="admin-detail-head">
              <div>
                <span className="admin-panel-title">{active.uid}</span>
                <span className="admin-panel-sub">{active.user_email} · {fmtDate(active.created_at)}</span>
              </div>
              <span className="badge-role member">{active.status_label}</span>
            </div>
            <p className="admin-copy">{active.description}</p>
            <div className="admin-form-grid">
              <SelectInput label="Move to" value={form.status} onChange={v => setForm(f => ({ ...f, status: v }))}>
                <option value="">No valid transition</option>
                {(active.next_statuses || []).map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
              </SelectInput>
              <label className="admin-field admin-field-wide">
                <span>Admin response</span>
                <textarea value={form.admin_note} onChange={e => setForm(f => ({ ...f, admin_note: e.target.value }))} />
              </label>
            </div>
            <button type="button" className="btn-primary-small" disabled={!form.status || updateMut.isPending} onClick={() => updateMut.mutate()}>
              Update Ticket
            </button>
          </>
        )}
      </section>
    </div>
  )
}

function ReportsPanel() {
  const qc = useQueryClient()
  const [status, setStatus] = useState('open')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const query = useQuery({ queryKey: ['admin-reports', status], queryFn: () => getAdminReports(status) })
  const reports = query.data?.reports ?? []
  const actionMut = useMutation({
    mutationFn: ({ id, action }) => actionAdminReport(id, action),
    onSuccess: () => {
      setNotice('Report action saved')
      setError('')
      qc.invalidateQueries(['admin-reports'])
      qc.invalidateQueries(['admin-overview'])
      qc.invalidateQueries(['admin-audit'])
    },
    onError: err => setError(err.message || 'Report action failed'),
  })

  return (
    <section className="admin-panel admin-panel-full">
      <Notice message={notice} />
      <Notice message={error} tone="error" />
      <div className="admin-panel-title">Moderation Reports</div>
      <div className="admin-filter-row">
        {['open', 'resolved', 'dismissed', 'all'].map(s => (
          <button key={s} type="button" className={status === s ? 'active' : ''} onClick={() => setStatus(s)}>
            {s} {query.data?.counts?.[s] ?? 0}
          </button>
        ))}
      </div>
      <div className="admin-card-list">
        {query.isLoading ? <div className="admin-empty">Loading reports…</div> : reports.map(report => (
          <article key={report.id} className="admin-report-card">
            <div>
              <strong>{report.category_label}</strong>
              <span>{report.reporter} reported {report.author || 'a deleted user'} · {fmtDate(report.created_at)}</span>
            </div>
            <p>{report.body || 'Message unavailable.'}</p>
            {report.reason && <small>{report.reason}</small>}
            <div className="admin-actions">
              {report.thread_id && <Link className="btn-secondary-small" to={`/threads/${report.thread_id}`}>Open Thread</Link>}
              {report.status === 'open' && (
                <>
                  <button type="button" className="btn-danger-small" onClick={() => actionMut.mutate({ id: report.id, action: 'delete_message' })}>
                    Delete Message
                  </button>
                  <button type="button" className="btn-secondary-small" onClick={() => actionMut.mutate({ id: report.id, action: 'dismiss' })}>
                    Dismiss
                  </button>
                </>
              )}
              {report.status !== 'open' && <span className="admin-panel-sub">{report.status} · {report.resolution}</span>}
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

function BroadcastPanel() {
  const [form, setForm] = useState({ target: 'all', target_email: '', subject: '', body_html: '' })
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const mut = useMutation({
    mutationFn: () => sendAdminBroadcast(form),
    onSuccess: data => {
      setNotice(`Sent ${data.sent}; failed ${data.failed}`)
      setError('')
      setForm({ target: 'all', target_email: '', subject: '', body_html: '' })
    },
    onError: err => setError(err.message || 'Broadcast failed'),
  })
  return (
    <section className="admin-panel admin-panel-form">
      <Notice message={notice} />
      <Notice message={error} tone="error" />
      <div className="admin-panel-title">Broadcast</div>
      <div className="admin-form-grid">
        <SelectInput label="Audience" value={form.target} onChange={v => setForm(f => ({ ...f, target: v }))}>
          <option value="all">All users</option>
          <option value="single">Single email</option>
        </SelectInput>
        {form.target === 'single' && (
          <TextInput label="Target email" value={form.target_email} onChange={v => setForm(f => ({ ...f, target_email: v }))} />
        )}
        <TextInput label="Subject" value={form.subject} onChange={v => setForm(f => ({ ...f, subject: v }))} />
        <label className="admin-field admin-field-wide">
          <span>HTML body</span>
          <textarea value={form.body_html} onChange={e => setForm(f => ({ ...f, body_html: e.target.value }))} />
        </label>
      </div>
      <button type="button" className="btn-primary-small" disabled={mut.isPending} onClick={() => mut.mutate()}>Send Broadcast</button>
    </section>
  )
}

function AuditPanel() {
  const query = useQuery({ queryKey: ['admin-audit'], queryFn: getAdminAuditLog })
  const logs = query.data?.logs ?? []
  return (
    <section className="admin-panel admin-panel-full">
      <div className="admin-panel-title">Audit Log</div>
      <div className="admin-list">
        {query.isLoading ? <div className="admin-empty">Loading audit log…</div> : logs.map(log => (
          <div key={log.id} className="admin-list-row static">
            <span>
              <strong>{log.action}</strong>
              <small>{log.admin}{log.target ? ` -> ${log.target}` : ''} · {log.details}</small>
            </span>
            <em>{fmtDate(log.created_at)}</em>
          </div>
        ))}
      </div>
    </section>
  )
}

function SportsLabPanel() {
  const qc = useQueryClient()
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [gameForm, setGameForm] = useState({ league_id: '', season_id: '', date: '', away_team_id: '', home_team_id: '', away_score: '', home_score: '', status: 'final' })
  const [seasonForm, setSeasonForm] = useState({ league_id: '', year: '', season_type: 'regular' })
  const [playerForm, setPlayerForm] = useState({ team_id: '', name: '', position: '' })
  const [metricForm, setMetricForm] = useState({ name: '', slug: '', description: '', formula_type: 'python', output_entity: 'game_team', parameters: '{}' })
  const [selectedGameId, setSelectedGameId] = useState(null)
  const [statsForm, setStatsForm] = useState({ home_stats: emptyStats, away_stats: emptyStats })
  const query = useQuery({ queryKey: ['admin-lab'], queryFn: getAdminLab })
  const data = query.data ?? {}
  const games = data.games ?? []
  const selectedGame = games.find(g => g.id === selectedGameId) || games[0]
  const teams = data.teams ?? []
  const leagues = data.leagues ?? []
  const seasons = data.seasons ?? []

  useEffect(() => {
    if (!selectedGame) return
    setSelectedGameId(selectedGame.id)
    setStatsForm({
      home_stats: { ...emptyStats, ...(selectedGame.home_stats || {}) },
      away_stats: { ...emptyStats, ...(selectedGame.away_stats || {}) },
    })
  }, [selectedGame?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const teamsForLeague = useMemo(() => {
    if (!gameForm.league_id) return teams
    const league = leagues.find(l => String(l.id) === String(gameForm.league_id))?.abbreviation
    return league ? teams.filter(t => t.league === league) : teams
  }, [teams, leagues, gameForm.league_id])

  const refreshLab = () => {
    qc.invalidateQueries(['admin-lab'])
    qc.invalidateQueries(['admin-overview'])
    qc.invalidateQueries(['admin-audit'])
  }
  const createGameMut = useMutation({
    mutationFn: () => createAdminGame(gameForm),
    onSuccess: () => {
      setNotice('Game created')
      setError('')
      setGameForm({ league_id: '', season_id: '', date: '', away_team_id: '', home_team_id: '', away_score: '', home_score: '', status: 'final' })
      refreshLab()
    },
    onError: err => setError(err.message || 'Game create failed'),
  })
  const createSeasonMut = useMutation({
    mutationFn: () => createAdminSeason(seasonForm),
    onSuccess: () => {
      setNotice('Season created')
      setError('')
      setSeasonForm({ league_id: '', year: '', season_type: 'regular' })
      refreshLab()
    },
    onError: err => setError(err.message || 'Season create failed'),
  })
  const createPlayerMut = useMutation({
    mutationFn: () => createAdminPlayer(playerForm),
    onSuccess: () => {
      setNotice('Player created')
      setError('')
      setPlayerForm({ team_id: '', name: '', position: '' })
      refreshLab()
    },
    onError: err => setError(err.message || 'Player create failed'),
  })
  const createMetricMut = useMutation({
    mutationFn: () => createAdminMetric(metricForm),
    onSuccess: () => {
      setNotice('Metric created')
      setError('')
      setMetricForm({ name: '', slug: '', description: '', formula_type: 'python', output_entity: 'game_team', parameters: '{}' })
      refreshLab()
    },
    onError: err => setError(err.message || 'Metric create failed'),
  })
  const updateStatsMut = useMutation({
    mutationFn: () => updateAdminGameStats(selectedGame.id, statsForm),
    onSuccess: () => {
      setNotice('Game stats updated')
      setError('')
      refreshLab()
    },
    onError: err => setError(err.message || 'Stats update failed'),
  })
  const deriveMut = useMutation({
    mutationFn: () => deriveAdminGame(selectedGame.id),
    onSuccess: () => {
      setNotice('Derived metrics computed')
      setError('')
      refreshLab()
    },
    onError: err => setError(err.message || 'Derive failed'),
  })

  function setStats(side, key, value) {
    setStatsForm(f => ({ ...f, [side]: { ...f[side], [key]: value } }))
  }

  return (
    <div className="admin-work-grid">
      <section className="admin-panel">
        <Notice message={notice} />
        <Notice message={error} tone="error" />
        <div className="admin-panel-title">Sports Lab</div>
        <div className="admin-form-grid">
          <SelectInput label="League" value={gameForm.league_id} onChange={v => setGameForm(f => ({ ...f, league_id: v, season_id: '', away_team_id: '', home_team_id: '' }))}>
            <option value="">League</option>
            {leagues.map(l => <option key={l.id} value={l.id}>{l.abbreviation}</option>)}
          </SelectInput>
          <SelectInput label="Season" value={gameForm.season_id} onChange={v => setGameForm(f => ({ ...f, season_id: v }))}>
            <option value="">None</option>
            {seasons.filter(s => !gameForm.league_id || String(s.league_id) === String(gameForm.league_id)).map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
          </SelectInput>
          <TextInput label="Date" type="date" value={gameForm.date} onChange={v => setGameForm(f => ({ ...f, date: v }))} />
          <SelectInput label="Away" value={gameForm.away_team_id} onChange={v => setGameForm(f => ({ ...f, away_team_id: v }))}>
            <option value="">Away team</option>
            {teamsForLeague.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
          </SelectInput>
          <SelectInput label="Home" value={gameForm.home_team_id} onChange={v => setGameForm(f => ({ ...f, home_team_id: v }))}>
            <option value="">Home team</option>
            {teamsForLeague.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
          </SelectInput>
          <TextInput label="Away score" value={gameForm.away_score} onChange={v => setGameForm(f => ({ ...f, away_score: v }))} />
          <TextInput label="Home score" value={gameForm.home_score} onChange={v => setGameForm(f => ({ ...f, home_score: v }))} />
        </div>
        <button type="button" className="btn-primary-small" disabled={createGameMut.isPending} onClick={() => createGameMut.mutate()}>
          Add Game
        </button>

        <div className="admin-divider" />
        <div className="admin-form-grid">
          <SelectInput label="Season league" value={seasonForm.league_id} onChange={v => setSeasonForm(f => ({ ...f, league_id: v }))}>
            <option value="">League</option>
            {leagues.map(l => <option key={l.id} value={l.id}>{l.abbreviation}</option>)}
          </SelectInput>
          <TextInput label="Year" value={seasonForm.year} onChange={v => setSeasonForm(f => ({ ...f, year: v }))} />
          <SelectInput label="Type" value={seasonForm.season_type} onChange={v => setSeasonForm(f => ({ ...f, season_type: v }))}>
            <option value="regular">Regular</option>
            <option value="playoffs">Playoffs</option>
            <option value="preseason">Preseason</option>
          </SelectInput>
        </div>
        <button type="button" className="btn-secondary-small" onClick={() => createSeasonMut.mutate()}>Add Season</button>

        <div className="admin-divider" />
        <div className="admin-form-grid">
          <SelectInput label="Player team" value={playerForm.team_id} onChange={v => setPlayerForm(f => ({ ...f, team_id: v }))}>
            <option value="">Team</option>
            {teams.map(t => <option key={t.id} value={t.id}>{t.league} · {t.label}</option>)}
          </SelectInput>
          <TextInput label="Player" value={playerForm.name} onChange={v => setPlayerForm(f => ({ ...f, name: v }))} />
          <TextInput label="Position" value={playerForm.position} onChange={v => setPlayerForm(f => ({ ...f, position: v }))} />
        </div>
        <button type="button" className="btn-secondary-small" onClick={() => createPlayerMut.mutate()}>Add Player</button>

        <div className="admin-divider" />
        <div className="admin-form-grid">
          <TextInput label="Metric name" value={metricForm.name} onChange={v => setMetricForm(f => ({ ...f, name: v }))} />
          <TextInput label="Slug" value={metricForm.slug} onChange={v => setMetricForm(f => ({ ...f, slug: v }))} />
          <TextInput label="Description" value={metricForm.description} onChange={v => setMetricForm(f => ({ ...f, description: v }))} />
        </div>
        <button type="button" className="btn-secondary-small" onClick={() => createMetricMut.mutate()}>Add Metric</button>
      </section>

      <section className="admin-panel">
        <div className="admin-panel-title">Recent Games</div>
        <div className="admin-list admin-list-compact">
          {query.isLoading ? <div className="admin-empty">Loading lab data…</div> : games.map(game => (
            <button key={game.id} type="button" className={`admin-list-row${selectedGame?.id === game.id ? ' active' : ''}`} onClick={() => setSelectedGameId(game.id)}>
              <span><strong>{game.away_team} at {game.home_team}</strong><small>{game.league} · {game.away_score}-{game.home_score} · {game.date}</small></span>
              <em>{game.has_derived_metrics ? 'derived' : 'raw'}</em>
            </button>
          ))}
        </div>
        {selectedGame && (
          <>
            <div className="admin-divider" />
            <div className="admin-detail-head">
              <div>
                <span className="admin-panel-title">{selectedGame.away_team} at {selectedGame.home_team}</span>
                <span className="admin-panel-sub">{selectedGame.date} · {selectedGame.status}</span>
              </div>
              <button type="button" className="btn-secondary-small" onClick={() => deriveMut.mutate()}>Derive</button>
            </div>
            <div className="admin-stat-editor">
              {['away_stats', 'home_stats'].map(side => (
                <div key={side}>
                  <span className="admin-panel-sub">{side === 'away_stats' ? selectedGame.away_team : selectedGame.home_team}</span>
                  <div className="admin-mini-grid">
                    {STAT_FIELDS.map(field => (
                      <label key={`${side}-${field}`}>
                        <span>{field.replace(/_/g, ' ')}</span>
                        <input value={statsForm[side]?.[field] ?? ''} onChange={e => setStats(side, field, e.target.value)} />
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <button type="button" className="btn-primary-small" disabled={updateStatsMut.isPending} onClick={() => updateStatsMut.mutate()}>
              Save Stats
            </button>
            {selectedGame.derived?.length > 0 && (
              <div className="admin-related">
                <span className="admin-panel-sub">Derived</span>
                {selectedGame.derived.map(row => (
                  <span key={row.team_id}>{row.team}: margin {row.point_margin}, TRB {row.trb_diff}, FG diff {row.fg_pct_diff}</span>
                ))}
              </div>
            )}
          </>
        )}
      </section>
    </div>
  )
}

export default function Admin() {
  const [tab, setTab] = useState('users')
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-overview'],
    queryFn: getAdminOverview,
  })

  if (isLoading) return <Loading full />
  if (error) return <div className="empty-state"><p>Admin access unavailable.</p></div>

  const stats = data?.stats ?? {}

  return (
    <div className="admin-page">
      <BackButton fallback="/more" />
      <div className="admin-page-head">
        <div>
          <span className="section-title">Admin</span>
          <span className="section-sub">React-managed operations, support, moderation, and sports data.</span>
        </div>
      </div>

      <section className="admin-stat-grid" aria-label="Admin summary">
        <Stat label="Users" value={stats.users} />
        <Stat label="Pending" value={stats.pending_verification} />
        <Stat label="Groups" value={stats.groups} />
        <Stat label="Threads" value={stats.active_threads} />
        <Stat label="Open Support" value={stats.support_open} />
        <Stat label="Open Reports" value={stats.reports_open} />
        <Stat label="Lab Games" value={stats.lab_games} />
      </section>

      <div className="admin-tabs" role="tablist" aria-label="Admin sections">
        {TABS.map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            className={tab === value ? 'active' : ''}
            onClick={() => setTab(value)}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'users' && <UsersPanel />}
      {tab === 'support' && <SupportPanel />}
      {tab === 'reports' && <ReportsPanel />}
      {tab === 'broadcast' && <BroadcastPanel />}
      {tab === 'audit' && <AuditPanel />}
      {tab === 'lab' && <SportsLabPanel />}
    </div>
  )
}
