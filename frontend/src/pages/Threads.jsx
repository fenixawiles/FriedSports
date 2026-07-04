import { useState, useMemo, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { archiveThread, deleteThreadLocal, getThreadsList, getThread,
         restoreThread, unarchiveThread } from '../api/threads'
import { Skeleton } from '../components/Skeleton'
import IdentityAvatar from '../components/IdentityAvatar'
import useLongPress from '../hooks/useLongPress'
import { haptic } from '../native/haptics'

const STATUS_FILTERS = [
  ['active', 'Threads'],
  ['archived', 'Archived'],
  ['deleted', 'Recently Deleted'],
]

const TYPE_FILTERS = [
  ['all', 'All'],
  ['direct', 'Direct'],
  ['groups', 'Groups'],
]

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

function threadMeta(thread) {
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
  return { isIncident, isDirect, typeLabel, rowTitle }
}

function ThreadRow({ thread, last, pending, onAction, onMenu }) {
  const [offset, setOffset] = useState(0)
  const [dragging, setDragging] = useState(false)
  const startRef = useMemo(() => ({ x: 0, y: 0, base: 0, current: 0, active: false, swiped: false }), [])
  const category = thread.category || 'active'
  const isDeleted = category === 'deleted'
  const maxOffset = isDeleted ? 88 : 176
  const { isIncident, rowTitle } = threadMeta(thread)
  const press = useLongPress(() => onMenu(thread))

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
    const shouldOpen = startRef.current < -(maxOffset / 2)
    const next = shouldOpen ? -maxOffset : 0
    setDragging(false)
    startRef.current = next
    setOffset(next)
    startRef.swiped = true
    setTimeout(() => { startRef.swiped = false }, 80)
  }

  function onRowClick(e) {
    if (press.clickGuard(e)) return
    if (offset !== 0 || startRef.swiped) {
      e.preventDefault()
      close()
    }
  }

  const actions = isDeleted
    ? [['restore', 'Restore', 'restore']]
    : [
        [category === 'archived' ? 'unarchive' : 'archive', category === 'archived' ? 'Unarchive' : 'Archive', 'archive'],
        ['delete', 'Delete', 'delete'],
      ]

  return (
    <div className={`thread-swipe${offset !== 0 || dragging ? ' open' : ''}`}>
      <div className="thread-swipe-actions" aria-hidden={offset === 0}>
        {actions.map(([action, label, tone]) => (
          <button
            key={action}
            type="button"
            className={`swipe-act swipe-${tone}`}
            disabled={pending}
            onClick={() => { close(); onAction(thread.id, action) }}>
            {pending ? '...' : label}
          </button>
        ))}
      </div>
      <Link
        to={`/threads/${thread.id}`}
        className={`thread-row-item longpressable${dragging ? ' dragging' : ''}`}
        data-group-id={thread.group_id || ''}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onContextMenu={(e) => e.preventDefault()}
        onClick={onRowClick}
        style={{ transform: `translateX(${offset}px)` }}>
        <IdentityAvatar identity={thread.identity} fallbackLabel={thread.avatar_label || thread.team_abbr || '?'} />
        <div className="thread-preview-col">
          <div className="thread-preview-top">
            <span className="thread-preview-name">
              {thread.unread_count > 0 && category === 'active' && <span className="unread-dot" />}
              {rowTitle}
            </span>
            <span className="thread-preview-ts">{fmtTime(last?.created_at)}</span>
          </div>
          <div className="thread-preview-msg">
            {last?.body || (isIncident ? thread.title : 'Start the conversation.')}
          </div>
          <div className="thread-preview-activity">
            <span>{thread.reply_count || 0} {(thread.reply_count || 0) === 1 ? 'reply' : 'replies'}</span>
            {thread.unread_count > 0 && category === 'active' && <span className="unread-chip">{thread.unread_count} new</span>}
            {last?.author && <span>last by {last.author}</span>}
          </div>
        </div>
      </Link>
    </div>
  )
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

  const [filterOpen, setFilterOpen]         = useState(false)
  const [statusFilter, setStatusFilter]     = useState('active')
  const [typeFilter, setTypeFilter]         = useState('all')
  const [actionError, setActionError]       = useState('')
  const [menuThread, setMenuThread]         = useState(null)  // long-press sheet
  const [sheetArmed, setSheetArmed]         = useState(false)

  // The sheet opens mid-press; swallow input until the finger has lifted so
  // the release-click can't land on the backdrop and dismiss it instantly.
  useEffect(() => {
    if (!menuThread) return
    setSheetArmed(false)
    const t = setTimeout(() => setSheetArmed(true), 350)
    return () => clearTimeout(t)
  }, [menuThread])

  const threads   = data?.threads    ?? []
  const lastMsgs  = data?.last_msgs  ?? {}
  const catCounts = data?.cat_counts ?? {}

  const actionMut = useMutation({
    mutationFn: ({ id, action }) => {
      if (action === 'archive') return archiveThread(id)
      if (action === 'unarchive') return unarchiveThread(id)
      if (action === 'delete') return deleteThreadLocal(id)
      if (action === 'restore') return restoreThread(id)
      throw new Error('Unknown action')
    },
    onSuccess: () => {
      haptic('medium')
      setActionError('')
      qc.invalidateQueries(['threads'])
    },
    onError: (err) => setActionError(err.message || 'Could not update thread'),
  })

  const filtered = useMemo(() => {
    return threads.filter(t => {
      const category = t.category || 'active'
      if (category !== statusFilter) return false
      if (typeFilter === 'direct') return t.thread_type === 'direct_chat'
      if (typeFilter === 'groups') return t.thread_type !== 'direct_chat'
      return true
    })
  }, [threads, statusFilter, typeFilter])

  const emptyCopy = {
    active: 'Dead silence. Someone\'s team deserves a conversation — start one.',
    archived: 'Nothing tucked away. The drama is all still live.',
    deleted: 'Recently Deleted is empty. No evidence destroyed... yet.',
  }[statusFilter]

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
              {STATUS_FILTERS.map(([value, label]) => (
                <button key={value}
                  className={`threads-filter-item${statusFilter === value ? ' active' : ''}`}
                  onClick={() => { setStatusFilter(value); setFilterOpen(false) }}>
                  <span className="threads-filter-checkmark">{statusFilter === value ? '✓' : ''}</span>
                  <span>{label}</span>
                  {catCounts[value] > 0 && <span className="threads-filter-count">{catCounts[value]}</span>}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="thread-type-tabs" role="tablist" aria-label="Thread type">
        {TYPE_FILTERS.map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={typeFilter === value}
            className={`thread-type-tab${typeFilter === value ? ' active' : ''}`}
            onClick={() => setTypeFilter(value)}>
            {label}
          </button>
        ))}
      </div>

      {actionError && <div className="threads-action-error">{actionError}</div>}

      {isLoading ? <ThreadsSkeleton /> : (
        <div className="threads-list-wrap" id="threads-list">
          {filtered.length === 0 ? (
            <div className="empty-state"><p>{emptyCopy}</p></div>
          ) : filtered.map(thread => (
            <ThreadRow
              key={thread.id}
              thread={thread}
              last={lastMsgs[thread.id]}
              pending={actionMut.isPending && actionMut.variables?.id === thread.id}
              onAction={(id, action) => actionMut.mutate({ id, action })}
              onMenu={(t) => setMenuThread(t)}
            />
          ))}
        </div>
      )}

      {/* Long-press thread action sheet — same actions as swipe */}
      {menuThread && (() => {
        const category = menuThread.category || 'active'
        const isDeleted = category === 'deleted'
        const run = (action) => { setMenuThread(null); actionMut.mutate({ id: menuThread.id, action }) }
        return (
          <div className="pw-sheet" style={{ pointerEvents: sheetArmed ? 'auto' : 'none' }}
            onClick={(e) => { if (e.target === e.currentTarget) setMenuThread(null) }}>
            <div className="pw-sheet-backdrop" onClick={() => setMenuThread(null)} />
            <div className="pw-sheet-card" role="dialog" aria-modal="true">
              <div className="pw-sheet-head">
                <div className="pw-sheet-title">{threadMeta(menuThread).rowTitle}</div>
              </div>
              {isDeleted ? (
                <button type="button" className="pw-sheet-opt" onClick={() => run('restore')}>
                  <span className="pw-opt-main">Restore</span>
                  <span className="pw-opt-sub">Move back to your chats</span>
                </button>
              ) : (
                <>
                  <button type="button" className="pw-sheet-opt"
                    onClick={() => run(category === 'archived' ? 'unarchive' : 'archive')}>
                    <span className="pw-opt-main">{category === 'archived' ? 'Unarchive' : 'Archive'}</span>
                    <span className="pw-opt-sub">
                      {category === 'archived' ? 'Move back to your chats' : 'Tuck away without deleting'}
                    </span>
                  </button>
                  <button type="button" className="pw-sheet-opt pw-opt-danger" onClick={() => run('delete')}>
                    <span className="pw-opt-main">Delete</span>
                    <span className="pw-opt-sub">Clears your copy — others keep theirs</span>
                  </button>
                </>
              )}
              <button type="button" className="pw-sheet-cancel" onClick={() => setMenuThread(null)}>Cancel</button>
            </div>
          </div>
        )
      })()}

      {/* FAB */}
      <button className="threads-fab" onClick={() => navigate('/threads/new')} aria-label="New chat">+</button>
    </div>
  )
}
