import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteGroup, getDashboard, getGroup, leaveGroup } from '../api/groups'
import { getThread } from '../api/threads'
import { useAuth } from '../context/AuthContext'
import { Skeleton } from '../components/Skeleton'

function DashboardSkeleton() {
  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <Skeleton w="160px" h="1.8rem" mb="1.5rem" />
      </div>
      <section className="dashboard-section">
        <div className="section-header" style={{ marginBottom: '0.85rem' }}>
          <Skeleton w="90px" h="1rem" />
        </div>
        <div className="group-list">
          {[1, 2, 3].map(i => (
            <div key={i} className="group-card" style={{ pointerEvents: 'none', gap: '0.5rem' }}>
              <div style={{ flex: 1 }}>
                <Skeleton w="55%" h="0.95rem" mb="0.45rem" />
                <Skeleton w="30%" h="0.72rem" />
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

function GroupSwipeRow({ group, member, pending, onDelete, onLeave }) {
  const [offset, setOffset] = useState(0)
  const [dragging, setDragging] = useState(false)
  const startRef = useMemo(() => ({ x: 0, y: 0, base: 0, current: 0, active: false, swiped: false }), [])
  const isOwner = member.role === 'owner'
  const actionLabel = isOwner ? 'Delete' : 'Leave'
  const maxOffset = 88

  function close() {
    setDragging(false)
    startRef.current = 0
    setOffset(0)
  }
  function onPointerDown(e) {
    if (e.pointerType === 'mouse' && e.button !== 0) return
    startRef.x = e.clientX
    startRef.y = e.clientY
    startRef.base = offset
    startRef.active = false
    startRef.swiped = false
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }
  function onPointerMove(e) {
    const dx = e.clientX - startRef.x
    const dy = e.clientY - startRef.y
    if (!startRef.active) {
      if (Math.abs(dx) < 8 || Math.abs(dx) <= Math.abs(dy) * 1.2) return
      startRef.active = true
      setDragging(true)
    }
    const next = Math.max(-maxOffset, Math.min(0, startRef.base + dx))
    startRef.current = next
    setOffset(next)
  }
  function onPointerUp() {
    if (!startRef.active) return
    const next = startRef.current < -(maxOffset / 2) ? -maxOffset : 0
    setDragging(false)
    startRef.current = next
    setOffset(next)
    startRef.swiped = true
    setTimeout(() => { startRef.swiped = false }, 80)
  }
  function onClick(e) {
    if (offset !== 0 || startRef.swiped) {
      e.preventDefault()
      close()
    }
  }
  function runAction() {
    close()
    if (isOwner) onDelete(group)
    else onLeave(group)
  }

  return (
    <div className="group-swipe">
      <div className="group-swipe-actions">
        <button type="button" className="group-swipe-delete" disabled={pending} onClick={runAction}>
          {pending ? '...' : actionLabel}
        </button>
      </div>
      <Link
        to={`/groups/${group.id}`}
        className={`group-card${dragging ? ' dragging' : ''}`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onClick={onClick}
        style={{ transform: `translateX(${offset}px)` }}>
        <div className="group-card-left">
          <div className="group-card-name">{group.name}</div>
          <div className="group-card-meta">
            <span className="badge-scope">{group.league_scope}</span>
            <span className={`badge-role ${member.role}`}>{member.role}</span>
          </div>
        </div>
        <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>→</span>
      </Link>
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const [groupActionError, setGroupActionError] = useState('')
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
  })
  const groupActionMut = useMutation({
    mutationFn: ({ group, action }) => {
      if (action === 'delete') return deleteGroup(group.id)
      return leaveGroup(group.id)
    },
    onSuccess: () => {
      setGroupActionError('')
      qc.invalidateQueries(['dashboard'])
      qc.invalidateQueries(['threads'])
    },
    onError: (err) => setGroupActionError(err.message || 'Could not update group'),
  })

  // Eagerly prefetch every group and active thread visible on this page.
  // By the time the user taps a card the data is already in cache — no spinner.
  useEffect(() => {
    const groups = data?.groups ?? []
    const threads = data?.active_threads ?? []
    groups.forEach(({ group }) => {
      const sid = String(group.id)
      qc.prefetchQuery({ queryKey: ['group', sid], queryFn: () => getGroup(sid) })
    })
    threads.forEach(thread => {
      const sid = String(thread.id)
      qc.prefetchQuery({ queryKey: ['thread', sid], queryFn: () => getThread(sid) })
    })
  }, [data]) // eslint-disable-line react-hooks/exhaustive-deps

  if (isLoading) return <DashboardSkeleton />
  if (error) return <div className="empty-state"><p>Could not load dashboard.</p></div>

  const { groups = [], active_threads = [], msg_counts = {} } = data

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <h1>{user?.name}</h1>
      </div>
      {groupActionError && <div className="flash flash-error">{groupActionError}</div>}

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
                <GroupSwipeRow
                  key={group.id}
                  group={group}
                  member={member}
                  pending={groupActionMut.isPending && groupActionMut.variables?.group?.id === group.id}
                  onDelete={(g) => {
                    if (window.confirm(`Delete ${g.name}? This permanently removes the group and its threads.`)) {
                      groupActionMut.mutate({ group: g, action: 'delete' })
                    }
                  }}
                  onLeave={(g) => {
                    if (window.confirm(`Leave ${g.name}?`)) {
                      groupActionMut.mutate({ group: g, action: 'leave' })
                    }
                  }}
                />
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
