import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getAdminOverview } from '../api/admin'
import BackButton from '../components/BackButton'
import Loading from '../components/Loading'

const isNative = window.Capacitor?.isNativePlatform?.() === true
const ADMIN_ORIGIN = import.meta.env.VITE_API_ORIGIN?.replace(/\/$/, '') || (isNative ? 'https://www.friedsports.com' : '')

function adminHref(path) {
  return `${ADMIN_ORIGIN}${path}`
}

function Stat({ label, value }) {
  return (
    <div className="admin-stat">
      <span className="admin-stat-value">{value ?? '—'}</span>
      <span className="admin-stat-label">{label}</span>
    </div>
  )
}

function AdminLink({ href, title, detail, tone }) {
  return (
    <a href={adminHref(href)} className={`admin-tool-link${tone ? ` ${tone}` : ''}`}>
      <span>
        <span className="admin-tool-title">{title}</span>
        <span className="admin-tool-detail">{detail}</span>
      </span>
      <span className="more-chevron">›</span>
    </a>
  )
}

export default function Admin() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-overview'],
    queryFn: getAdminOverview,
  })

  if (isLoading) return <Loading full />
  if (error) return <div className="empty-state"><p>Admin access unavailable.</p></div>

  const stats = data?.stats ?? {}
  const recentGames = data?.recent_games ?? []

  return (
    <div className="admin-page">
      <BackButton fallback="/more" />
      <div className="admin-page-head">
        <div>
          <span className="section-title">Admin</span>
          <span className="section-sub">Operations, support, moderation, and sports lab tools.</span>
        </div>
        <a href={adminHref('/admin/')} className="btn-secondary-small">Classic</a>
      </div>

      <section className="admin-stat-grid" aria-label="Admin summary">
        <Stat label="Users" value={stats.users} />
        <Stat label="Groups" value={stats.groups} />
        <Stat label="Threads" value={stats.active_threads} />
        <Stat label="Open Support" value={stats.support_open} />
        <Stat label="Open Reports" value={stats.reports_open} />
        <Stat label="Lab Games" value={stats.lab_games} />
      </section>

      <section className="admin-section">
        <div className="settings-label">Operations</div>
        <div className="admin-tool-list">
          <AdminLink href="/admin/users" title="Users" detail="Search users, roles, account actions, and emails" />
          <AdminLink href="/admin/support" title="Support" detail="Review tickets and reply to users" />
          <AdminLink href="/admin/reports" title="Moderation Reports" detail="Message reports and moderation outcomes" />
          <AdminLink href="/admin/broadcast" title="Broadcast" detail="Send a platform-wide announcement" />
          <AdminLink href="/admin/audit-log" title="Audit Log" detail="Track privileged admin actions" />
        </div>
      </section>

      <section className="admin-section">
        <div className="settings-label">Sports Lab</div>
        <div className="admin-tool-list">
          <AdminLink href="/admin/games" title="Games" detail="Manage games, scores, stats, and derived metrics" />
          <AdminLink href="/admin/games/new" title="Add Game" detail="Create a new lab game with team stats" />
          <AdminLink href="/admin/players" title="Players" detail="Manage player records and team assignments" />
          <AdminLink href="/admin/metrics" title="Metrics" detail="Metric definitions used by derived analysis" />
          <AdminLink href="/admin/lab/rebound" title="Rebound Lab" detail="Explore rebound leverage queries" />
        </div>
      </section>

      {recentGames.length > 0 && (
        <section className="admin-section">
          <div className="settings-label">Recent Lab Games</div>
          <div className="admin-recent-list">
            {recentGames.map(game => (
              <a key={game.id} href={adminHref(`/admin/games/${game.id}`)} className="admin-recent-row">
                <span>
                  <span className="admin-recent-title">{game.away_team} at {game.home_team}</span>
                  <span className="admin-recent-detail">{game.league} · {game.status} · {game.date}</span>
                </span>
                <span className="more-chevron">›</span>
              </a>
            ))}
          </div>
        </section>
      )}

      <section className="admin-section">
        <div className="settings-label">React Port Status</div>
        <div className="admin-note">
          This page is the cleaned React entry point. The deep admin forms still use the existing Flask tools so none of the privileged workflows get lost during the app migration.
        </div>
      </section>

      <Link to="/more" className="btn-secondary-small">Back to More</Link>
    </div>
  )
}
