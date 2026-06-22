import { useState, useMemo, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getThreadsList, getThread, createChatThread } from '../api/threads'
import { getFriends } from '../api/friends'
import { Skeleton } from '../components/Skeleton'

function ThreadsSkeleton() {
  return (
    <div className="threads-list-wrap">
      {[1, 2, 3, 4, 5].map(i => (
        <div key={i} className="thread-row-item" style={{ pointerEvents: 'none' }}>
          <Skeleton circle size={42} style={{ marginRight: '0.85rem' }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
              <Skeleton w="45%" h="0.82rem" />
              <Skeleton w="12%" h="0.72rem" />
            </div>
            <Skeleton w="70%" h="0.75rem" />
          </div>
        </div>
      ))}
    </div>
  )
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1)
  const msgDay = new Date(d.getFullYear(), d.getMonth(), d.getDate())

  if (msgDay.getTime() === today.getTime()) {
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }).replace(/^0/, '')
  }
  if (msgDay.getTime() === yesterday.getTime()) return 'Yesterday'
  const diff = (today - msgDay) / 86400000
  if (diff < 7) return d.toLocaleDateString('en-US', { weekday: 'short' })
  return `${d.getMonth() + 1}/${d.getDate()}`
}

export default function Threads() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['threads'],
    queryFn: getThreadsList,
    refetchInterval: 10_000,
  })

  // Eagerly prefetch the first 8 threads so tapping any row is instant.
  useEffect(() => {
    const threads = data?.threads ?? []
    threads.slice(0, 8).forEach(thread => {
      const sid = String(thread.id)
      qc.prefetchQuery({ queryKey: ['thread', sid], queryFn: () => getThread(sid) })
    })
  }, [data]) // eslint-disable-line react-hooks/exhaustive-deps

  const [filterGroup, setFilterGroup]       = useState('all')
  const [filterOpen, setFilterOpen]         = useState(false)
  const [fabOpen, setFabOpen]               = useState(false)
  const [chatError, setChatError]           = useState('')

  const { data: friendsData, isLoading: friendsLoading } = useQuery({
    queryKey: ['friends'],
    queryFn: getFriends,
    enabled: fabOpen,
  })

  const chatMut = useMutation({
    mutationFn: createChatThread,
    onSuccess: (res) => {
      setFabOpen(false)
      setChatError('')
      qc.invalidateQueries(['threads'])
      navigate(`/threads/${res.thread_id}`)
    },
    onError: (err) => setChatError(err.message || 'Could not start chat'),
  })

  const threads   = data?.threads    ?? []
  const groups    = data?.groups     ?? []
  const friends   = friendsData?.friends ?? []
  const lastMsgs  = data?.last_msgs  ?? {}

  const filtered = useMemo(() => {
    if (filterGroup === 'all') return threads
    return threads.filter(t => String(t.group_id) === String(filterGroup))
  }, [threads, filterGroup])

  function startGroupChat(groupId) {
    chatMut.mutate({ type: 'group', group_id: groupId })
  }

  function startDirectChat(userId) {
    chatMut.mutate({ type: 'direct', user_id: userId })
  }

  return (
    <div className="threads-page-container">
      <div className="threads-header-wrap">
        <span className="section-title">Chats</span>
        <div className="threads-filter-wrap">
          <button className="threads-filter-btn" onClick={() => setFilterOpen(o => !o)}
            aria-expanded={filterOpen}>
            ☰
          </button>
          {filterOpen && (
            <div className="threads-filter-menu">
              <button className={`threads-filter-item${filterGroup === 'all' ? ' active' : ''}`}
                onClick={() => { setFilterGroup('all'); setFilterOpen(false) }}>
                All Groups
              </button>
              {groups.map(g => (
                <button key={g.id}
                  className={`threads-filter-item${String(filterGroup) === String(g.id) ? ' active' : ''}`}
                  onClick={() => { setFilterGroup(String(g.id)); setFilterOpen(false) }}>
                  {g.name}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {isLoading ? <ThreadsSkeleton /> : (
        <div className="threads-list-wrap" id="threads-list">
          {filtered.length === 0 ? (
            <div className="empty-state"><p>No chats yet.</p></div>
          ) : filtered.map(thread => {
            const last = lastMsgs[thread.id]
            const isIncident = (thread.thread_type || 'incident') === 'incident'
            const isDirect = thread.thread_type === 'direct_chat'
            const typeLabel = isIncident
              ? (thread.incident_type
                ? thread.incident_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
                : 'Thread')
              : (isDirect ? 'Direct Message' : 'Group Chat')
            const rowTitle = isIncident
              ? `${thread.group_name} · ${typeLabel}`
              : (thread.display_title || thread.title || typeLabel)

            return (
              <Link key={thread.id} to={`/threads/${thread.id}`}
                className="thread-row-item" data-group-id={thread.group_id}>
                <div className="thread-avatar-circle"
                  style={{ background: thread.avatar_color || thread.team_color || 'var(--accent)' }}>
                  <span>{thread.avatar_label || thread.team_abbr || '?'}</span>
                </div>
                <div className="thread-preview-col">
                  <div className="thread-preview-top">
                    <span className="thread-preview-name">
                      {rowTitle}
                    </span>
                    <span className="thread-preview-ts">{fmtTime(last?.created_at)}</span>
                  </div>
                  <div className="thread-preview-msg">
                    {last?.body || (isIncident ? thread.title : 'Start the conversation.')}
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      )}

      {/* FAB */}
      <button className="threads-fab" onClick={() => { setChatError(''); setFabOpen(true) }} aria-label="New chat">+</button>

      {fabOpen && (
        <>
          <div className="threads-fab-backdrop" onClick={() => setFabOpen(false)} />
          <div className="threads-fab-sheet">
            <div className="threads-fab-sheet-handle" />
            <div className="threads-fab-sheet-title">New chat</div>
            {chatError && <div className="threads-fab-error">{chatError}</div>}

            <div className="threads-fab-section-label">Groups</div>
            {groups.length === 0 ? (
              <div className="threads-fab-empty">Join or create a group first.</div>
            ) : groups.map(g => (
              <button key={`group-${g.id}`} type="button" className="threads-fab-group-row"
                disabled={chatMut.isPending}
                onClick={() => startGroupChat(g.id)}>
                <span className="threads-fab-row-main">{g.name}</span>
                <span className="threads-fab-row-sub">Group chat</span>
              </button>
            ))}

            <div className="threads-fab-section-label">Friends</div>
            {friendsLoading ? (
              <div className="threads-fab-empty">Loading friends…</div>
            ) : friends.length === 0 ? (
              <div className="threads-fab-empty">Add a friend to start a direct chat.</div>
            ) : friends.map(f => (
              <button key={`friend-${f.id}`} type="button" className="threads-fab-group-row"
                disabled={chatMut.isPending}
                onClick={() => startDirectChat(f.id)}>
                <span className="threads-fab-row-main">{f.name}</span>
                <span className="threads-fab-row-sub">Direct message</span>
              </button>
            ))}
            <button className="threads-fab-cancel" onClick={() => setFabOpen(false)}>Cancel</button>
          </div>
        </>
      )}
    </div>
  )
}
