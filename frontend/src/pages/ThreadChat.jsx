import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getThread, sendMessage, reactToMessage, deleteMessage,
         confirmReport, dismissReport, redeemReport } from '../api/threads'
import { useAuth } from '../context/AuthContext'
import Loading from '../components/Loading'

const REACTIONS = [['laugh','😂'],['cook','👨‍🍳'],['fraud','🚨'],['receipt','🧾']]
const BTN_W = 52   // approximate picker button width for on-screen clamping

export default function ThreadChat() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const chatWindowRef = useRef(null)
  const inputRef      = useRef(null)
  const pressTimer    = useRef(null)
  const pressOrigin   = useRef(null)

  const [body, setBody]       = useState('')
  const [sending, setSending] = useState(false)
  // activeMenu: { id, can_delete, top, left } | null
  const [activeMenu, setActiveMenu] = useState(null)

  // Apply full-height focused layout
  useEffect(() => {
    document.documentElement.setAttribute('data-thread', '')
    document.body.classList.add('thread-view')
    return () => {
      document.documentElement.removeAttribute('data-thread')
      document.body.classList.remove('thread-view', 'keyboard-open')
    }
  }, [])

  const { data, isLoading } = useQuery({
    queryKey: ['thread', id],
    queryFn: () => getThread(id),
    refetchInterval: 3_000,
    refetchIntervalInBackground: false,
  })

  const thread   = data?.thread
  const messages = data?.messages ?? []
  const member   = data?.member
  const ir       = data?.incident_report

  // Scroll to bottom on new messages
  const scrollToBottom = useCallback(() => {
    const el = chatWindowRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [])
  useEffect(() => { scrollToBottom() }, [messages.length, scrollToBottom])

  // Textarea auto-grow
  function handleInput(e) {
    setBody(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
  }

  // Submit
  async function handleSend(e) {
    e?.preventDefault()
    const trimmed = body.trim()
    if (!trimmed || sending) return
    setBody('')
    if (inputRef.current) { inputRef.current.style.height = '' }
    setSending(true)
    try {
      await sendMessage(id, trimmed)
      qc.invalidateQueries(['thread', id])
    } catch {
      setBody(trimmed) // restore on failure
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // ── Shared picker open logic ───────────────────────────────────────────────
  // Computes position from an element's bounding rect and opens the menu.
  function openPickerAt(anchorRect, msg) {
    const btnCount = REACTIONS.length + (msg.can_delete ? 1 : 0)
    const pickerW  = btnCount * BTN_W + 16
    const pickerH  = 52

    // Prefer above the anchor; fall back to below if near top of screen
    const top = anchorRect.top > pickerH + 12
      ? anchorRect.top - pickerH - 6
      : anchorRect.bottom + 6

    // Center horizontally on the anchor, clamped to viewport
    let left = anchorRect.left + anchorRect.width / 2 - pickerW / 2
    left = Math.max(8, Math.min(left, window.innerWidth - pickerW - 8))

    setActiveMenu({ id: msg.id, can_delete: msg.can_delete, top, left })
  }

  // ── Desktop: click the hover-revealed react button ────────────────────────
  function onReactBtnClick(e, msg) {
    e.stopPropagation()
    openPickerAt(e.currentTarget.getBoundingClientRect(), msg)
  }

  // ── Mobile: long-press the bubble (500 ms) ────────────────────────────────
  function startPress(e, msg) {
    // Let clicks on inner buttons/links pass through
    if (e.target.closest('button, a, input, textarea')) return
    pressOrigin.current = { x: e.clientX, y: e.clientY }
    clearTimeout(pressTimer.current)
    const el = e.currentTarget
    pressTimer.current = setTimeout(() => {
      openPickerAt(el.getBoundingClientRect(), msg)
    }, 500)
  }

  function cancelPress(e) {
    if (e && pressOrigin.current) {
      const dx = Math.abs(e.clientX - pressOrigin.current.x)
      const dy = Math.abs(e.clientY - pressOrigin.current.y)
      if (dx > 8 || dy > 8) {
        clearTimeout(pressTimer.current)
        pressOrigin.current = null
        return
      }
    }
    clearTimeout(pressTimer.current)
    pressOrigin.current = null
  }

  function closeMenu() { setActiveMenu(null) }
  // ─────────────────────────────────────────────────────────────────────────

  const reactMut = useMutation({
    mutationFn: ({ msgId, type }) => reactToMessage(msgId, type),
    onSuccess: () => qc.invalidateQueries(['thread', id]),
  })
  const deleteMut = useMutation({
    mutationFn: (msgId) => deleteMessage(msgId),
    onSuccess: () => { qc.invalidateQueries(['thread', id]); closeMenu() },
  })
  const confirmMut = useMutation({
    mutationFn: () => confirmReport(ir.id),
    onSuccess: () => qc.invalidateQueries(['thread', id]),
  })
  const dismissMut = useMutation({
    mutationFn: () => dismissReport(ir.id),
    onSuccess: () => qc.invalidateQueries(['thread', id]),
  })
  const redeemMut = useMutation({
    mutationFn: () => redeemReport(ir.id),
    onSuccess: () => qc.invalidateQueries(['thread', id]),
  })

  if (isLoading) return <Loading full />

  const threadType = thread?.thread_type || 'incident'
  const isIncidentThread = threadType === 'incident'
  const isAdmin  = member?.role === 'owner' || member?.role === 'admin'
  const isTarget = isIncidentThread && user?.id === thread?.target_user_id
  const backLabel = thread?.group_name || 'Chats'

  return (
    <div className="thread-container">

      {/* Header */}
      <div className="thread-header-wrap">
        <div className="thread-header">
          <button type="button" className="back-link"
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
            onClick={() => navigate(-1)}>
            ← {backLabel}
          </button>
          <h1 className="thread-title-large">{thread?.title}</h1>
          {thread && (
            <div className="thread-header-meta">
              {isIncidentThread && thread.team_abbr && (
                <span className="team-chip-lg"
                  style={{ color: thread.team_color, borderColor: thread.team_color + '40' }}>
                  {thread.team_abbr} · {thread.team_name}
                </span>
              )}
              {isIncidentThread && thread.target_user_name && (
                <span className="target-label">{thread.target_user_name}</span>
              )}
              <span className={`status-badge ${thread.status}`}>
                {isIncidentThread ? thread.status : (threadType === 'direct_chat' ? 'Direct' : 'Group Chat')}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Chat window */}
      <div className="chat-window" id="chat-window" ref={chatWindowRef}>

        {/* Incident strip */}
        {ir && (
          <div className="incident-strip">
            <div className="incident-strip-text">
              <span className="istrip-type">
                {ir.incident_type.replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase())}
              </span>
              <span className="istrip-sep">·</span>
              <span>Severity {ir.severity}/5</span>
              <span className="istrip-sep">·</span>
              <span>by {ir.reporter_name}</span>
              {ir.reported_score_text && (
                <><span className="istrip-sep">·</span>
                <span className="istrip-context">"{ir.reported_score_text}"</span></>
              )}
            </div>
            {(isAdmin || isTarget) && ir.status !== 'redeemed' && (
              <div className="incident-strip-actions">
                {isAdmin && ir.status === 'active' && (
                  <button className="istrip-action-btn"
                    onClick={() => confirmMut.mutate()}>Confirm</button>
                )}
                {isAdmin && !['dismissed','redeemed'].includes(ir.status) && (
                  <button className="istrip-action-btn istrip-action-danger"
                    onClick={() => { if(window.confirm('Dismiss? Reporter loses 5 pts.')) dismissMut.mutate() }}>
                    Dismiss
                  </button>
                )}
                {(isTarget || isAdmin) && ir.status !== 'redeemed' && (
                  <button className="istrip-action-btn"
                    onClick={() => redeemMut.mutate()}>Mark Redeemed</button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Messages */}
        {messages.map(msg => {
          const mine  = msg.is_mine
          if (msg.message_type === 'system') {
            return (
              <div key={msg.id} className="message message-system" data-id={msg.id}>
                <div className="message-system-body">{msg.body}</div>
              </div>
            )
          }

          // Passive reaction chips — only shown when count > 0
          const chips = Object.entries(msg.reactions || {}).filter(([, c]) => c > 0)

          // Desktop react button — placed as a flex sibling of the bubble.
          // For "mine" (right-aligned) it goes BEFORE the bubble → sits on the left.
          // For "theirs" (left-aligned) it goes AFTER the bubble → sits on the right.
          const reactBtn = (
            <button
              className="react-trigger"
              aria-label="Add reaction"
              onClick={e => onReactBtnClick(e, msg)}>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14"
                viewBox="0 0 24 24" fill="none" stroke="currentColor"
                strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <path d="M8 13s1.5 2 4 2 4-2 4-2"/>
                <line x1="9" y1="9" x2="9.01" y2="9"/>
                <line x1="15" y1="9" x2="15.01" y2="9"/>
              </svg>
            </button>
          )

          return (
            <div key={msg.id} data-id={msg.id}
              className={`message message-user ${mine ? 'message-mine' : 'message-theirs'}`}>

              {/* Desktop react trigger — left of bubble for "mine" */}
              {mine && reactBtn}

              {/* Long-press target for mobile */}
              <div className="message-bubble"
                onPointerDown={e => startPress(e, msg)}
                onPointerUp={cancelPress}
                onPointerMove={cancelPress}
                onPointerCancel={cancelPress}
                style={{ userSelect: 'none', WebkitUserSelect: 'none' }}>
                {!mine && <div className="message-author">{msg.author}</div>}
                <div className="message-text">{msg.body}</div>

                {/* Footer: passive reaction chips + timestamp */}
                <div className="message-footer">
                  {chips.length > 0 && (
                    <div className="reaction-chips">
                      {chips.map(([rtype, count]) => {
                        const emoji  = REACTIONS.find(([r]) => r === rtype)?.[1] ?? rtype
                        const reacted = msg.user_reactions?.includes(rtype)
                        return (
                          <span key={rtype}
                            className={`reaction-chip${reacted ? ' reacted' : ''}`}>
                            {emoji} {count}
                          </span>
                        )
                      })}
                    </div>
                  )}
                  <span className="message-time">
                    {msg.created_at
                      ? new Date(msg.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
                      : ''}
                  </span>
                </div>
              </div>

              {/* Desktop react trigger — right of bubble for "theirs" */}
              {!mine && reactBtn}
            </div>
          )
        })}
      </div>

      {/* ── Floating reaction picker ── */}
      {activeMenu && (
        <>
          {/* Transparent backdrop — tap outside to dismiss */}
          <div className="reaction-picker-backdrop" onPointerDown={closeMenu} />
          <div className="reaction-picker"
            style={{ top: activeMenu.top, left: activeMenu.left }}>
            {REACTIONS.map(([rtype, emoji]) => (
              <button key={rtype} className="reaction-picker-btn"
                onPointerDown={e => {
                  e.stopPropagation()
                  reactMut.mutate({ msgId: activeMenu.id, type: rtype })
                  closeMenu()
                }}>
                {emoji}
              </button>
            ))}
            {activeMenu.can_delete && (
              <>
                <div className="reaction-picker-divider" />
                <button className="reaction-picker-btn reaction-picker-delete"
                  onPointerDown={e => {
                    e.stopPropagation()
                    closeMenu()
                    if (window.confirm('Delete this message?')) deleteMut.mutate(activeMenu.id)
                  }}>
                  🗑️
                </button>
              </>
            )}
          </div>
        </>
      )}

      {/* Input */}
      {thread?.status === 'active' ? (
        <div className="chat-input-area">
          <form className="chat-form" id="chat-form" onSubmit={handleSend}>
            <div className="chat-input-pill">
              <textarea ref={inputRef} id="chat-input" name="body"
                placeholder="Say something…" maxLength={1000} rows={1} required
                style={{ fontSize: 16 }} enterKeyHint="send"
                value={body} onChange={handleInput}
                onKeyDown={handleKeyDown} />
              <button type="submit" className="chat-submit" id="chat-send"
                disabled={!body.trim() || sending} aria-label="Send">
                <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24"
                  fill="none" stroke="currentColor" strokeWidth="2.5"
                  strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="19" x2="12" y2="5"/>
                  <polyline points="5 12 12 5 19 12"/>
                </svg>
              </button>
            </div>
          </form>
        </div>
      ) : (
        <div className="thread-closed-notice">This thread is closed.</div>
      )}
    </div>
  )
}
