import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getNotifications, markAllRead } from '../api/notifications'
import { acceptRequest, declineRequest } from '../api/friends'
import { joinGroup } from '../api/groups'
import Loading from '../components/Loading'

export default function Notifications() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [tab, setTab] = useState('messages')
  const [inviteErr, setInviteErr] = useState('')

  const { data, isLoading } = useQuery({ queryKey: ['notifications'], queryFn: getNotifications })

  const markRead = useMutation({
    mutationFn: markAllRead,
    onSuccess: () => qc.invalidateQueries(['notifications']),
  })
  // Accept a group invite in one tap — join straight from the Invites tab.
  const acceptInvite = useMutation({
    mutationFn: (n) => {
      const code = (n.link_url || '').split('/groups/join/')[1]
      if (!code) return Promise.reject(new Error('This invite link is no longer valid.'))
      return joinGroup(code)
    },
    onSuccess: (res) => {
      qc.invalidateQueries(['notifications'])
      qc.invalidateQueries(['dashboard'])
      navigate(`/groups/${res.group_id}`)
    },
    onError: (err) => setInviteErr(err.message || 'Could not join. Try opening the invite link.'),
  })
  const accept = useMutation({
    mutationFn: (id) => acceptRequest(id),
    onSuccess: () => qc.invalidateQueries(['notifications']),
  })
  const decline = useMutation({
    mutationFn: (id) => declineRequest(id),
    onSuccess: () => qc.invalidateQueries(['notifications']),
  })

  const messages   = data?.messages   ?? []
  const invites    = data?.invites    ?? []
  const pending_fr = data?.pending_fr ?? []

  if (isLoading) return <Loading full />

  return (
    <div className="group-container" style={{ maxWidth: 680 }}>
      <div className="group-header">
        <div><h1>Notifications</h1></div>
        <div className="group-actions">
          <button className="btn-secondary-small" onClick={() => markRead.mutate()}>
            Mark All Read
          </button>
        </div>
      </div>

      {/* Friend requests */}
      {pending_fr.length > 0 && (
        <section className="group-section" style={{ borderTop: 'none', paddingTop: 0, marginBottom: '0.5rem' }}>
          <div className="section-header" style={{ marginBottom: '0.75rem' }}>
            <span className="section-title">Friend Requests</span>
            <span className="notif-count-chip">{pending_fr.length}</span>
          </div>
          {pending_fr.map(fr => (
            <div key={fr.id} className="notif-fr-row">
              <div className="notif-fr-info">
                <span className="notif-fr-name">{fr.from_user.name}</span>
                <span className="notif-fr-uid">{fr.from_user.uid}</span>
              </div>
              <div className="notif-fr-actions">
                <button className="btn-primary-small" onClick={() => accept.mutate(fr.id)}>Accept</button>
                <button className="btn-secondary-small" onClick={() => decline.mutate(fr.id)}>Decline</button>
              </div>
            </div>
          ))}
        </section>
      )}

      {/* Tabs */}
      <div className="notif-tabs">
        {[['messages', 'Messages', messages], ['invites', 'Invites', invites]].map(([key, label, items]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`notif-tab${tab === key ? ' active' : ''}`}
            style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
            {label}
            {items.length > 0 && <span className="notif-count-chip">{items.length}</span>}
          </button>
        ))}
      </div>

      {/* Messages panel — tappable links */}
      {tab === 'messages' && (
        <section className="notif-panel group-section" style={{ borderTop: 'none', paddingTop: 0 }}>
          {messages.length === 0 ? (
            <div className="empty-state"><p>No messages yet.</p></div>
          ) : (
            <div className="notif-list">
              {messages.map(n => (
                <Link key={n.id} to={n.link_url || '/dashboard'}
                  className={`notif-item${!n.is_read ? ' notif-unread' : ''}`}>
                  <div className="notif-dot" />
                  <div className="notif-body">
                    <div className="notif-message">{n.message}</div>
                    <div className="notif-time">{n.created_at}</div>
                  </div>
                  <svg className="notif-chevron" xmlns="http://www.w3.org/2000/svg" width="14" height="14"
                    viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                    strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="9 18 15 12 9 6"/>
                  </svg>
                </Link>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Invites panel — accept a group invite in one tap */}
      {tab === 'invites' && (
        <section className="notif-panel group-section" style={{ borderTop: 'none', paddingTop: 0 }}>
          {inviteErr && <div className="flash flash-error" style={{ marginBottom: '0.6rem' }}>{inviteErr}</div>}
          {invites.length === 0 ? (
            <div className="empty-state"><p>No invites right now.</p></div>
          ) : (
            <div className="notif-list">
              {invites.map(n => (
                <div key={n.id} className={`notif-item notif-invite${!n.is_read ? ' notif-unread' : ''}`}>
                  <div className="notif-dot" />
                  <div className="notif-body">
                    <div className="notif-message">{n.message}</div>
                    <div className="notif-time">{n.created_at}</div>
                  </div>
                  <button className="btn-primary-small"
                    disabled={acceptInvite.isPending}
                    onClick={() => { setInviteErr(''); acceptInvite.mutate(n) }}>
                    {acceptInvite.isPending ? 'Joining…' : 'Accept'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}
