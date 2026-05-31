import { useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getSupportTickets, createTicket, getTicket } from '../api/user'
import BackButton from '../components/BackButton'
import Loading from '../components/Loading'

const CATEGORIES = [
  ['bug','Bug Report'],['account','Account Issue'],
  ['feature','Feature Request'],['billing','Billing'],['other','Other'],
]

export function SupportList() {
  const { data, isLoading } = useQuery({ queryKey: ['tickets'], queryFn: getSupportTickets })
  if (isLoading) return <Loading full />
  const tickets = data?.tickets ?? []

  return (
    <div className="group-container" style={{ maxWidth: 680 }}>
      <BackButton fallback="/more" />
      <div className="group-header">
        <h1>Support</h1>
        <div className="group-actions">
          <Link to="/support/new" className="btn-primary-small">New Ticket</Link>
        </div>
      </div>
      {tickets.length === 0 ? (
        <div className="empty-state"><p>No tickets yet.</p></div>
      ) : (
        <div className="notif-list">
          {tickets.map(t => (
            <Link key={t.uid} to={`/support/${t.uid}`} className="notif-item">
              <div className="notif-body">
                <div className="notif-message">{t.subject}</div>
                <div className="notif-time">{t.status} · {t.created_at}</div>
              </div>
              <svg className="notif-chevron" xmlns="http://www.w3.org/2000/svg" width="14" height="14"
                viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

export function NewTicket() {
  const navigate = useNavigate()
  const [form, setForm] = useState({ subject: '', category: 'other', description: '' })
  const [error, setError] = useState('')

  const mut = useMutation({
    mutationFn: () => createTicket(form),
    onSuccess: (data) => navigate(`/support/${data.uid}`),
    onError: (err) => setError(err.message || 'Failed to submit'),
  })

  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  return (
    <div className="group-container" style={{ maxWidth: 680 }}>
      <BackButton fallback="/support" />
      <div className="group-header"><h1>Report an Issue</h1></div>
      {error && <div className="flash flash-error">{error}</div>}
      <form onSubmit={e => { e.preventDefault(); mut.mutate() }}
        style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <div className="form-group">
          <label>Subject</label>
          <input type="text" required maxLength={200} style={{ fontSize: 16 }}
            value={form.subject} onChange={set('subject')} />
        </div>
        <div className="form-group">
          <label>Category</label>
          <select value={form.category} onChange={set('category')}>
            {CATEGORIES.map(([v,l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>Description</label>
          <textarea required rows={6} style={{ fontSize: 16 }}
            value={form.description} onChange={set('description')} />
        </div>
        <button type="submit" className="btn-primary" disabled={mut.isPending}>
          {mut.isPending ? 'Submitting…' : 'Submit Report'}
        </button>
      </form>
    </div>
  )
}

export function TicketDetail() {
  const { uid } = useParams()
  const { data, isLoading } = useQuery({
    queryKey: ['ticket', uid],
    queryFn: () => getTicket(uid),
  })
  if (isLoading) return <Loading full />
  const t = data?.ticket
  if (!t) return <div className="empty-state"><p>Ticket not found.</p></div>

  return (
    <div className="group-container" style={{ maxWidth: 680 }}>
      <BackButton fallback="/support" />
      <div className="group-header"><h1>{t.subject}</h1></div>
      <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1rem' }}>
        {t.status} · {t.category} · {t.created_at}
      </div>
      <div style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>{t.description}</div>
      {t.admin_note && (
        <div style={{ marginTop: '1.5rem', padding: '1rem', background: 'var(--bg-elevated)', borderRadius: 8 }}>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>Response</div>
          <div style={{ color: 'var(--text-primary)', lineHeight: 1.6 }}>{t.admin_note}</div>
        </div>
      )}
    </div>
  )
}

export default function Support({ new: isNew }) {
  const { uid } = useParams()
  if (isNew) return <NewTicket />
  if (uid) return <TicketDetail />
  return <SupportList />
}
