import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getThread, sendMessage, reactToMessage, deleteMessage,
         confirmReport, dismissReport, redeemReport } from '../api/threads'
import { useAuth } from '../context/AuthContext'
import Loading from '../components/Loading'

const REACTIONS = [['laugh','😂'],['cook','👨‍🍳'],['fraud','🚨'],['receipt','🧾']]
// Approximate picker width per button so we can keep it on-screen
const BTN_W = 52

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

  // Apply full-height focused layout: sets data-thread on <html> so CSS can
  // override height on html+body without affecting other pages.
  useEffect(() => {
    document.documentElement.setAttribute('data-thread', '')
    return () => document.documentElement.removeAttribute('data-thread')
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

  // ── Long-press reaction picker ────────────────────────────────────────────
  function startPress(e, msg) {
    // Let taps on inner buttons/links pass through normally
    if (e.target.closest('button, a, input, textarea')) return
    pressOrigin.current = { x: e.clientX, y: e.clientY }
    clearTimeout(pressTimer.current)

    const el = e.currentTarget
    pressTimer.current = setTimeout(() => {
      const rect = el.getBoundingClientRect()
      const btnCount = REACTIONS.length + (msg.can_delete ? 1 : 0)
      const pickerW  = btnCount * BTN_W + 16  // buttons + padding
      const pickerH  = 52

      // Show above bubble; fall back to below if near top of screen
      const top = rect.top > pickerH + 12
        ? rect.top - pickerH - 6
        : rect.bottom + 6

      // Horizontally center on bubble, clamp to viewport
      let left = rect.left + rect.width / 2 - pickerW / 2
      left = Math.max(8, Math.min(left, window.innerWidth - pickerW - 8))

      setActiveMenu({ id: msg.id, can_delete: msg.can_delete, top, left })
    }, 500)
  }

  function cancelPress(e) {
    // Cancel if the finger has moved more than 8px (user is scrolling)
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

  const isAdmin  = member?.role === 'owner' || member?.role === 'admin'
  const isTarget = user?.id === thread?.target_user_id

  return (
    <div className="thread-container">

      {/* Header */}
      <div className="thread-header-wrap">
        <div className="thread-header">
          <button type="button" className="back-link"
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
            onClick={() => navigate(-1)}>
            ← {thread?.group_name}
          </button>
          <h1 className="thread-title-large">{thread?.title}</h1>
          {thread && (
            <div className="thread-header-meta">
              <span className="team-chip-lg"
                style={{ color: thread.team_color, borderColor: thread.team_color + '40' }}>
                {thread.team_abbr} · {thread.team_name}
              </span>
              <span className="target-label">{thread.target_user_name}</span>
              <span className={`status-badge ${thread.status}`}>{thread.status}</span>
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
          const mine = msg.is_mine
          if (msg.message_type === 'system') {
            return (
              <div key={msg.id} className="message message-system" data-id={msg.id}>
                <div className="message-system-body">{msg.body}</div>
              </div>
            )
          }

          // Only show reaction chips that have at least one count
          const chips = Object.entries(msg.reactions || {}).filter(([, c]) => c > 0)

          return (
            <div key={msg.id} data-id={msg.id}
              className={`message message-user ${mine ? 'message-mine' : 'message-theirs'}`}>
              {/* Long-press target — entire bubble */}
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
                        const emoji = REACTIONS.find(([r]) => r === rtype)?.[1] ?? rtype
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
            </div>
          )
        })}
      </div>

      {/* ── Floating reaction picker — long-press opens this ── */}
      {activeMenu && (
        <>
          {/* Transparent backdrop catches tap-outside to dismiss */}
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
