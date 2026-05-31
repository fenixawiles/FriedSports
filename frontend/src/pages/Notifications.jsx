import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getNotifications, markAllRead } from '../api/notifications'
import { acceptRequest, declineRequest } from '../api/friends'
import Loading from '../components/Loading'

export default function Notifications() {
  const qc = useQueryClient()
  const [tab, setTab] = useState('messages')

  const { data, isLoading } = useQuery({ queryKey: ['notifications'], queryFn: getNotifications })

  const markRead = useMutation({
    mutationFn: markAllRead,
    onSuccess: () => qc.invalidateQueries(['notifications']),
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

      {/* Panels */}
      {[['messages', messages], ['invites', invites]].map(([key, items]) => (
        tab === key && (
          <section key={key} className="notif-panel group-section" style={{ borderTop: 'none', paddingTop: 0 }}>
            {items.length === 0 ? (
              <div className="empty-state">
                <p>{key === 'messages' ? 'No messages yet.' : 'No invites.'}</p>
              </div>
            ) : (
              <div className="notif-list">
                {items.map(n => (
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
        )
      ))}
    </div>
  )
}
