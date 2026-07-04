import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../context/AuthContext'
import { getDashboard } from '../api/groups'
import { getThreadsList } from '../api/threads'
import { getNotifications } from '../api/notifications'
import { getFriends } from '../api/friends'
import { Skeleton } from '../components/Skeleton'
import IdentityAvatar from '../components/IdentityAvatar'

function HomeActivity() {
  const { user } = useAuth()
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: getDashboard })
  const threadsQ = useQuery({ queryKey: ['threads'], queryFn: getThreadsList })
  const notificationsQ = useQuery({ queryKey: ['notifications'], queryFn: getNotifications })
  const friendsQ = useQuery({ queryKey: ['friends'], queryFn: getFriends })

  const groups = dashboard.data?.groups ?? []
  const activeGroups = groups.filter(g => !g.member?.archived)
  const dashboardThreads = dashboard.data?.active_threads ?? []
  const threads = threadsQ.data?.threads ?? []
  const activeThreads = threads.filter(t => (t.category || 'active') === 'active')
  const unreadThreads = activeThreads.filter(t => (t.unread_count || 0) > 0)
  const directThreads = activeThreads.filter(t => t.thread_type === 'direct_chat')
  const invites = notificationsQ.data?.invites ?? []
  const pendingFriends = notificationsQ.data?.pending_fr ?? []
  const unreadNotifications = notificationsQ.data?.unread_count ?? 0
  const friends = friendsQ.data?.friends ?? []
  const loading = dashboard.isLoading || threadsQ.isLoading || notificationsQ.isLoading || friendsQ.isLoading

  const recentThreads = activeThreads.slice(0, 4)
  const attention = [
    ...unreadThreads.slice(0, 3).map(t => ({
      key: `thread-${t.id}`,
      title: t.display_title || t.title || 'Thread',
      detail: `${t.unread_count} new ${t.unread_count === 1 ? 'message' : 'messages'}`,
      to: `/threads/${t.id}`,
    })),
    ...pendingFriends.slice(0, 2).map(fr => ({
      key: `friend-${fr.id}`,
      title: fr.from_user?.name || 'Friend request',
      detail: 'Friend request waiting',
      to: '/notifications',
    })),
    ...invites.slice(0, 2).map(invite => ({
      key: `invite-${invite.id}`,
      title: invite.message,
      detail: 'Group invite',
      to: '/notifications',
    })),
  ].slice(0, 5)

  return (
    <div className="home-dashboard">
      <div className="home-dashboard-head">
        <div>
          <span className="home-kicker">Your FriedSports</span>
          <h1>{user?.name || 'Home'}</h1>
          <p>What needs a reply, what changed, and where the heat is.</p>
        </div>
        <Link to="/threads/new" className="btn-primary-small">Start Chat</Link>
      </div>

      <section className="home-stat-row" aria-label="Activity summary">
        {loading ? (
          [1,2,3,4].map(i => <Skeleton key={i} h="72px" />)
        ) : (
          <>
            <Link to="/threads" className={`home-stat${unreadThreads.length === 0 ? ' calm' : ' hot'}`}>
              <strong>{unreadThreads.length || 'OK'}</strong>
              <span>{unreadThreads.length ? 'Unread threads' : "You're caught up"}</span>
            </Link>
            <Link to="/notifications" className={`home-stat${unreadNotifications === 0 ? ' calm' : ' hot'}`}>
              <strong>{unreadNotifications || 'Clear'}</strong>
              <span>{unreadNotifications ? 'Notifications' : 'No alerts'}</span>
            </Link>
            <Link to="/dashboard" className="home-stat">
              <strong>{activeGroups.length}</strong>
              <span>Active groups</span>
            </Link>
            <Link to="/friends" className="home-stat">
              <strong>{friends.length}</strong>
              <span>Friends</span>
            </Link>
          </>
        )}
      </section>

      <div className="home-grid">
        <section className="home-panel">
          <div className="home-panel-head">
            <div>
              <span className="section-title">Needs Attention</span>
              <span className="section-sub">Unread messages, invites, and requests</span>
            </div>
            <Link to="/notifications" className="btn-secondary-small">View All</Link>
          </div>
          {loading ? (
            <div className="home-list">
              {[1,2,3].map(i => <Skeleton key={i} h="52px" />)}
            </div>
          ) : attention.length === 0 ? (
            <div className="home-empty">
              <strong>All quiet right now.</strong>
              <span>No unread threads, invites, or friend requests.</span>
            </div>
          ) : (
            <div className="home-list">
              {attention.map(item => (
                <Link key={item.key} to={item.to} className="home-list-row">
                  <span>
                    <strong>{item.title}</strong>
                    <small>{item.detail}</small>
                  </span>
                  <em>Open</em>
                </Link>
              ))}
            </div>
          )}
        </section>

        <section className="home-panel">
          <div className="home-panel-head">
            <div>
              <span className="section-title">Recent Activity</span>
              <span className="section-sub">What moved across friends and groups</span>
            </div>
            <Link to="/threads" className="btn-secondary-small">Threads</Link>
          </div>
          {recentThreads.length === 0 && !loading ? (
            <div className="home-empty">
              <strong>No active threads yet.</strong>
              <span>Start a direct chat or open something with a group.</span>
              <div className="home-empty-actions">
                <Link to="/threads/new" className="btn-primary-small">Start Chat</Link>
                <Link to="/groups/new" className="btn-secondary-small">New Group</Link>
              </div>
            </div>
          ) : (
            <div className="home-list">
              {(loading ? [null, null, null] : recentThreads).map((thread, i) => thread ? (
                <Link key={thread.id} to={`/threads/${thread.id}`} className="home-thread-row">
                  <IdentityAvatar
                    identity={thread.identity}
                    fallbackLabel={thread.avatar_label || thread.team_abbr || '?'}
                    className="home-thread-avatar" />
                  <span>
                    <strong>{thread.display_title || thread.title}</strong>
                    <small>{thread.last_msg?.body || `${thread.reply_count || 0} replies`}</small>
                  </span>
                  {(thread.unread_count || 0) > 0 && <em>{thread.unread_count}</em>}
                </Link>
              ) : <Skeleton key={i} h="58px" />)}
            </div>
          )}
        </section>
      </div>

      <section className="home-panel home-wide-panel">
        <div className="home-panel-head">
          <div>
            <span className="section-title">Your World</span>
            <span className="section-sub">Groups, direct chats, and quick actions</span>
          </div>
          <Link to="/dashboard" className="btn-secondary-small">Groups</Link>
        </div>
        <div className="home-world-grid">
          <Link to="/dashboard" className="home-world-item">
            <strong>{activeGroups[0]?.group?.name || 'Create your first group'}</strong>
            <span>{dashboardThreads.length} active group threads</span>
          </Link>
          <Link to="/threads" className="home-world-item">
            <strong>{directThreads.length} direct chats</strong>
            <span>One-on-one sports accountability</span>
          </Link>
          <Link to="/friends" className="home-world-item">
            <strong>{friends.length ? 'Find someone' : 'Add friends'}</strong>
            <span>Search by username, FS ID, or email</span>
          </Link>
        </div>
      </section>
    </div>
  )
}

export default function Landing() {
  const { user } = useAuth()

  if (user) return <HomeActivity />

  return (
    <>
      <div className="hero">
        <div className="hero-eyebrow">Sports trash talk, organized</div>
        <h1 className="hero-title">Your team just choked.<br /><em>Your group is already waiting.</em></h1>
        <p className="hero-sub">
          FriedSports is a private platform for holding your friends accountable when their teams blow it.
          Start threads, roast with the group, and track who's been the most delusional fan all season.
        </p>
        <div className="hero-actions">
          {user ? (
            <>
              <Link to="/groups/new" className="btn-primary">Create New Group</Link>
              <Link to="/groups/join" className="btn-secondary">Join with Invite Code</Link>
            </>
          ) : (
            <>
              <Link to="/signup" className="btn-primary">Get Started — It's Free</Link>
              <Link to="/login" className="btn-secondary">Log In</Link>
            </>
          )}
        </div>
      </div>

      <div className="features">
        <div className="features-label">How it works</div>
        <div className="feature-grid">
          {[
            ['01', 'Pick Your Teams', 'NBA, NFL, MLB, NHL, Premier League, FIFA, F1, PGA — pick the teams you ride or die with.'],
            ['02', 'Start Threads', "Blowout, choked lead, playoff collapse — open a thread when someone's team embarrasses them."],
            ['03', 'Group Roast Threads', 'Every report opens a group thread. Pile in, talk trash, award reactions. The target gets notified.'],
            ['04', 'Permanent Receipts', "After every major disaster, a shareable receipt gets generated. The evidence doesn't disappear."],
          ].map(([n, t, d]) => (
            <div key={n} className="feature-card">
              <div className="feature-number">{n}</div>
              <h3>{t}</h3>
              <p>{d}</p>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
