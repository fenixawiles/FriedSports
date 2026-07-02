import { useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getGroup, getMembers, muteGroup, leaveGroup, deleteGroup,
         removeMember, transferOwner, inviteEmail, regenerateInvite } from '../api/groups'
import { useAuth } from '../context/AuthContext'
import BackButton from '../components/BackButton'
import { Skeleton } from '../components/Skeleton'

const TAGLINES = [
  'Trash talk is one click away.',
  'Rumors lie behind this button.',
  'The group deserves to know.',
  "Somebody's team needs answering for this.",
  'Start the allegations.',
  'Permanent receipts begin here.',
  'Open a case against a friend.',
  'This is where narratives are manufactured.',
  'Formal accusations encouraged.',
  'Justice is subjective.',
]

export default function Group() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const qc = useQueryClient()

  const [inviteOpen, setInviteOpen]   = useState(false)
  const [inviteEmail_, setInviteEmail_] = useState('')
  const [inviteMsg, setInviteMsg]     = useState('')
  const [copied, setCopied]           = useState(false)
  const [actionError, setActionError] = useState('')

  const { data, isLoading } = useQuery({ queryKey: ['group', id], queryFn: () => getGroup(id) })
  const { data: membersData, isLoading: membersLoading } = useQuery({ queryKey: ['group-members', id], queryFn: () => getMembers(id) })

  const mutOpts = { onSuccess: () => qc.invalidateQueries(['group', id]) }
  const muteMut    = useMutation({ mutationFn: () => muteGroup(id),    ...mutOpts })
  const regenMut   = useMutation({ mutationFn: () => regenerateInvite(id), ...mutOpts })
  const leaveMut   = useMutation({
    mutationFn: () => leaveGroup(id),
    onSuccess: () => {
      qc.invalidateQueries(['dashboard'])
      navigate('/dashboard')
    },
    onError: (err) => setActionError(err.message || 'Could not leave group'),
  })
  const deleteMut  = useMutation({
    mutationFn: () => deleteGroup(id),
    onSuccess: () => {
      qc.invalidateQueries(['dashboard'])
      qc.invalidateQueries(['threads'])
      navigate('/dashboard')
    },
    onError: (err) => setActionError(err.message || 'Could not delete group'),
  })
  const inviteMut  = useMutation({
    mutationFn: () => inviteEmail(id, inviteEmail_),
    onSuccess: (data) => {
      setInviteMsg(data?.sent
        ? `Invite emailed to ${inviteEmail_}.`
        : `We couldn't email that invite (they'll still get an in-app invite if they have an account). Share the link below instead.`)
      setInviteEmail_('')
    },
    onError: (err) => setInviteMsg(err.message || 'Could not send invite.'),
  })
  const removeMut  = useMutation({ mutationFn: (uid) => removeMember(id, uid), ...mutOpts })
  const transferMut = useMutation({ mutationFn: (uid) => transferOwner(id, uid), ...mutOpts })

  if (isLoading) return (
    <div className="group-container">
      <Skeleton w="48px" h="0.8rem" mb="1.25rem" />
      <div className="group-header">
        <div style={{ flex: 1 }}>
          <Skeleton w="55%" h="1.6rem" mb="0.6rem" />
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Skeleton w="60px" h="1.2rem" radius="20px" />
            <Skeleton w="80px" h="1.2rem" radius="20px" />
          </div>
        </div>
      </div>
      <section className="group-section" style={{ marginTop: '1.5rem' }}>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.6rem 0', borderBottom: '1px solid var(--border)' }}>
            <Skeleton w="40%" h="0.85rem" />
            <Skeleton w="15%" h="0.75rem" />
          </div>
        ))}
      </section>
    </div>
  )

  const { group, member, receipts = [] } = data ?? {}
  if (!group) return <div className="empty-state"><p>Group not found.</p></div>

  const isOwner  = member?.role === 'owner'
  const isAdmin  = member?.role === 'owner' || member?.role === 'admin'
  const members  = membersData ?? []
  const tagline  = TAGLINES[Math.floor(Math.random() * TAGLINES.length)]
  const inviteUrl = `${window.location.origin}/groups/join/${group.invite_code}`

  function copyLink() {
    navigator.clipboard.writeText(inviteUrl).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="group-container">
      <BackButton fallback="/dashboard" />
      {actionError && <div className="flash flash-error">{actionError}</div>}

      <div className="group-header">
        <div>
          <h1>{group.name}</h1>
          <div className="group-header-meta">
            <span className="badge-scope">{group.league_scope}</span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{group.member_count} members</span>
            {isAdmin && <span className={`badge-role ${member.role}`}>{member.role}</span>}
          </div>
        </div>
        {member && (
          <div className="group-actions">
            <button className="btn-primary-small" onClick={() => setInviteOpen(o => !o)}>+ Invite</button>
            <div className="invite-box">
              <span className="invite-label">Code</span>
              <code className="invite-code">{group.invite_code}</code>
            </div>
            <button className="btn-secondary-small" onClick={() => muteMut.mutate()}>
              {member.mute_notifications ? 'Unmute' : 'Mute'}
            </button>
            {isOwner && (
              <button className="btn-danger-small"
                disabled={deleteMut.isPending}
                onClick={() => { if(window.confirm(`Delete ${group.name}?`)) deleteMut.mutate() }}>
                {deleteMut.isPending ? 'Deleting…' : 'Delete Group'}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Invite panel */}
      {member && inviteOpen && (
        <div className="invite-panel invite-panel-open">
          <div className="invite-panel-inner">
            <div className="invite-panel-label">Invite by email — or copy the link below</div>
            <div className="invite-panel-row">
              <input type="email" className="invite-url-input" placeholder="friend@example.com"
                value={inviteEmail_} onChange={e => setInviteEmail_(e.target.value)} />
              <button className="btn-primary-small" disabled={inviteMut.isPending || !inviteEmail_}
                onClick={() => inviteMut.mutate()}>Send Invite</button>
            </div>
            {inviteMsg && <div className="invite-panel-note">{inviteMsg}</div>}
            <div className="invite-panel-label" style={{ marginTop: '0.75rem' }}>Or share the link directly</div>
            <div className="invite-panel-row">
              <input type="text" className="invite-url-input" readOnly value={inviteUrl} />
              <button className="btn-secondary-small invite-copy-btn" onClick={copyLink}>
                {copied ? 'Copied!' : 'Copy Link'}
              </button>
              {isAdmin && (
                <button className="btn-danger-small"
                  onClick={() => { if(window.confirm('Regenerate? Current link stops working.')) regenMut.mutate() }}>
                  Regenerate
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Start thread CTA */}
      <section className="group-section">
        <div className="section-header" style={{ marginBottom: '0.85rem' }}>
          <div>
            <span className="section-title">Threads</span>
            <span className="section-sub">Start a thread to call someone out</span>
            {member && <div className="thread-tagline">{tagline}</div>}
          </div>
          {member && (
            <Link to={`/groups/${id}/report`} className="btn-primary">Start A Thread</Link>
          )}
        </div>
      </section>

      {/* Members */}
      <section className="group-section">
        <div className="section-header" style={{ marginBottom: '0.85rem' }}>
          <span className="section-title">Members</span>
          <span className="section-sub">Who's in this group</span>
        </div>
        {membersLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', paddingTop: '0.5rem' }}>
            {[1, 2, 3].map(i => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.55rem 0', borderBottom: '1px solid var(--border)' }}>
                <Skeleton w="40%" h="0.85rem" />
                <Skeleton w="15%" h="0.75rem" />
              </div>
            ))}
          </div>
        ) : members.length === 0 ? (
          <div className="empty-state"><p>No members found.</p></div>
        ) : (
          <div className="member-table">
            <div className="member-row member-header">
              <span>Member</span><span>Role</span>
              {isAdmin && <span />}
            </div>
            {members.map(m => (
              <div key={m.user_id} className="member-row">
                <span className="member-name">{m.display_name}</span>
                <span><span className={`badge-role ${m.role}`}>{m.role}</span></span>
                {isAdmin && (
                  <span style={{ display: 'flex', gap: '0.4rem' }}>
                    {m.can_remove && (
                      <button className="btn-danger-tiny"
                        onClick={() => { if(window.confirm(`Remove ${m.display_name}?`)) removeMut.mutate(m.user_id) }}>
                        Remove
                      </button>
                    )}
                    {m.can_transfer && (
                      <button className="btn-secondary-tiny"
                        onClick={() => { if(window.confirm(`Transfer to ${m.display_name}?`)) transferMut.mutate(m.user_id) }}>
                        Owner
                      </button>
                    )}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Leave */}
      {member && !isOwner && (
        <section className="group-section group-danger-zone">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
            <div>
              <span className="section-title" style={{ color: 'var(--accent)' }}>Leave Group</span>
              <span className="section-sub">You'll lose access to this group's threads and members.</span>
            </div>
            <button className="btn-danger-small"
              disabled={leaveMut.isPending}
              onClick={() => { if(window.confirm(`Leave ${group.name}?`)) leaveMut.mutate() }}>
              {leaveMut.isPending ? 'Leaving…' : 'Leave Group'}
            </button>
          </div>
        </section>
      )}
      {isOwner && (
        <section className="group-section group-danger-zone">
          <p className="group-danger-hint">You own this group. Transfer ownership to a member before you can leave.</p>
        </section>
      )}

      {/* Receipts */}
      {receipts.length > 0 && (
        <section className="group-section">
          <div className="section-header" style={{ marginBottom: '0.85rem' }}>
            <span className="section-title">Receipts</span>
          </div>
          <div className="receipt-list">
            {receipts.map(r => (
              <a key={r.public_slug} href={`/public/receipts/${r.public_slug}`}
                className="receipt-item" target="_blank" rel="noopener noreferrer">
                <span className="receipt-title">{r.title}</span>
                <span className="receipt-shame">{r.shame_points} shame</span>
                <span className="receipt-arrow">↗</span>
              </a>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
