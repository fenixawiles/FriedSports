import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { archiveGroup, deleteGroup, getDashboard, getGroup, leaveGroup, unarchiveGroup } from '../api/groups'
import { getThread } from '../api/threads'
import { useAuth } from '../context/AuthContext'
import { Skeleton } from '../components/Skeleton'
import useLongPress from '../hooks/useLongPress'

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

function GroupSwipeRow({ group, member, pending, onDelete, onLeave, onMenu }) {
  const [offset, setOffset] = useState(0)
  const [dragging, setDragging] = useState(false)
  const startRef = useMemo(() => ({ x: 0, y: 0, base: 0, current: 0, active: false, swiped: false }), [])
  const isOwner = member.role === 'owner'
  const actionLabel = isOwner ? 'Delete' : 'Leave'
  const maxOffset = 88
  const press = useLongPress(() => onMenu(group, member))

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
    press.begin(e)
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }
  function onPointerMove(e) {
    press.move(e)
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
    press.end()
    if (!startRef.active) return
    const next = startRef.current < -(maxOffset / 2) ? -maxOffset : 0
    setDragging(false)
    startRef.current = next
    setOffset(next)
    startRef.swiped = true
    setTimeout(() => { startRef.swiped = false }, 80)
  }
  function onClick(e) {
    if (press.clickGuard(e)) return
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
    <div className={`group-swipe${offset !== 0 ? ' open' : ''}`}>
      <div className="group-swipe-actions">
        <button type="button" className="group-swipe-delete" disabled={pending} onClick={runAction}>
          {pending ? '...' : actionLabel}
        </button>
      </div>
      <Link
        to={`/groups/${group.id}`}
        className={`group-card longpressable${dragging ? ' dragging' : ''}`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onContextMenu={(e) => e.preventDefault()}
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
  const [menuFor, setMenuFor] = useState(null)          // { group, member } — long-press sheet
  const [sheetArmed, setSheetArmed] = useState(false)
  const [showArchived, setShowArchived] = useState(false)

  // The sheet opens while the finger is still down (long-press fires at
  // 450ms). Without this, releasing the finger lands a click on the freshly
  // rendered backdrop and instantly dismisses it. Ignore all input until the
  // press has certainly ended.
  useEffect(() => {
    if (!menuFor) return
    setSheetArmed(false)
    const t = setTimeout(() => setSheetArmed(true), 350)
    return () => clearTimeout(t)
  }, [menuFor])
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
  })
  const groupActionMut = useMutation({
    mutationFn: ({ group, action }) => {
      if (action === 'delete') return deleteGroup(group.id)
      if (action === 'archive') return archiveGroup(group.id)
      if (action === 'unarchive') return unarchiveGroup(group.id)
      return leaveGroup(group.id)
    },
    onSuccess: () => {
      setGroupActionError('')
      qc.invalidateQueries(['dashboard'])
      qc.invalidateQueries(['threads'])
    },
    onError: (err) => setGroupActionError(err.message || 'Could not update group'),
  })

  function sheetAction(action) {
    const { group, member } = menuFor
    setMenuFor(null)
    if (action === 'delete') {
      if (window.confirm(`Delete ${group.name}? This permanently removes the group and its threads.`)) {
        groupActionMut.mutate({ group, action: 'delete' })
      }
    } else if (action === 'leave') {
      if (window.confirm(`Leave ${group.name}?`)) {
        groupActionMut.mutate({ group, action: 'leave' })
      }
    } else {
      groupActionMut.mutate({ group, action })
    }
  }

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
  const activeGroups   = groups.filter(g => !g.member?.archived)
  const archivedGroups = groups.filter(g => g.member?.archived)

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
              {activeGroups.map(({ group, member }) => (
                <GroupSwipeRow
                  key={group.id}
                  group={group}
                  member={member}
                  pending={groupActionMut.isPending && groupActionMut.variables?.group?.id === group.id}
                  onMenu={(g, m) => setMenuFor({ group: g, member: m })}
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
              {activeGroups.length === 0 && archivedGroups.length > 0 && (
                <div className="empty-state"><p>All your groups are archived.</p></div>
              )}
            </div>
          </section>

          {archivedGroups.length > 0 && (
            <section className="dashboard-section">
              <button type="button" className="archived-toggle"
                onClick={() => setShowArchived(s => !s)} aria-expanded={showArchived}>
                Archived ({archivedGroups.length}) {showArchived ? '▾' : '▸'}
              </button>
              {showArchived && (
                <div className="group-list">
                  {archivedGroups.map(({ group, member }) => (
                    <GroupSwipeRow
                      key={group.id}
                      group={group}
                      member={member}
                      pending={groupActionMut.isPending && groupActionMut.variables?.group?.id === group.id}
                      onMenu={(g, m) => setMenuFor({ group: g, member: m })}
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
              )}
            </section>
          )}

          {/* Long-press group action sheet */}
          {menuFor && (
            <div className="pw-sheet" style={{ pointerEvents: sheetArmed ? 'auto' : 'none' }}
              onClick={(e) => { if (e.target === e.currentTarget) setMenuFor(null) }}>
              <div className="pw-sheet-backdrop" onClick={() => setMenuFor(null)} />
              <div className="pw-sheet-card" role="dialog" aria-modal="true">
                <div className="pw-sheet-head">
                  <div className="pw-sheet-title">{menuFor.group.name}</div>
                  <div className="pw-sheet-sub">{menuFor.member.role}</div>
                </div>
                <button type="button" className="pw-sheet-opt"
                  onClick={() => sheetAction(menuFor.member.archived ? 'unarchive' : 'archive')}>
                  <span className="pw-opt-main">{menuFor.member.archived ? 'Unarchive' : 'Archive'}</span>
                  <span className="pw-opt-sub">
                    {menuFor.member.archived
                      ? 'Move back to your groups'
                      : 'Hide from your dashboard — you stay a member'}
                  </span>
                </button>
                {menuFor.member.role === 'owner' ? (
                  <button type="button" className="pw-sheet-opt pw-opt-danger" onClick={() => sheetAction('delete')}>
                    <span className="pw-opt-main">Delete group</span>
                    <span className="pw-opt-sub">Permanently removes the group and its threads for everyone</span>
                  </button>
                ) : (
                  <button type="button" className="pw-sheet-opt pw-opt-danger" onClick={() => sheetAction('leave')}>
                    <span className="pw-opt-main">Leave group</span>
                  </button>
                )}
                <button type="button" className="pw-sheet-cancel" onClick={() => setMenuFor(null)}>Cancel</button>
              </div>
            </div>
          )}

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
