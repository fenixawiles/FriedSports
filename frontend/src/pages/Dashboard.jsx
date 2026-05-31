import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDashboard } from '../api/groups'
import { useAuth } from '../context/AuthContext'
import Loading from '../components/Loading'

export default function Dashboard() {
  const { user } = useAuth()
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
  })

  if (isLoading) return <Loading full />
  if (error) return <div className="empty-state"><p>Could not load dashboard.</p></div>

  const { groups = [], active_threads = [], msg_counts = {} } = data

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <h1>{user?.name}</h1>
      </div>

      {groups.length === 0 ? (
        <div className="dashboard-no-groups">
          <p className="no-groups-sub">You're not in any groups yet. Create one or join with an invite code.</p>
          <div className="no-groups-actions">
            <Link to="/groups/new" className="btn-primary btn-large">Create a Group</Link>
            <Link to="/groups/join" className="btn-secondary">Join with Invite Code</Link>
          </div>
        </div>
      ) : (
        <>
          <section className="dashboard-section">
            <div className="section-header">
              <div>
                <span className="section-title">Your Groups</span>
                <span className="section-sub">Tap to see activity and standings</span>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <Link to="/groups/new" className="btn-primary-small">+ New Group</Link>
                <Link to="/groups/join" className="btn-secondary-small">Join</Link>
              </div>
            </div>
            <div className="group-list">
              {groups.map(({ group, member }) => (
                <Link key={group.id} to={`/groups/${group.id}`} className="group-card">
                  <div className="group-card-left">
                    <div className="group-card-name">{group.name}</div>
                    <div className="group-card-meta">
                      <span className="badge-scope">{group.league_scope}</span>
                      <span className={`badge-role ${member.role}`}>{member.role}</span>
                    </div>
                  </div>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>→</span>
                </Link>
              ))}
            </div>
          </section>

          {active_threads.length > 0 && (
            <section className="dashboard-section">
              <div className="section-header">
                <div>
                  <span className="section-title">Active Threads</span>
                  <span className="section-sub">Open discussions you're part of</span>
                </div>
              </div>
              <div className="alert-list">
                {active_threads.map(thread => (
                  <Link key={thread.id} to={`/threads/${thread.id}`} className="alert-banner">
                    <div className="alert-body">
                      <div className="alert-title">{thread.title}</div>
                      <div className="alert-meta">
                        {msg_counts[thread.id] || 0} messages · {thread.group_name}
                      </div>
                    </div>
                    <div className="alert-arrow">→</div>
                  </Link>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
