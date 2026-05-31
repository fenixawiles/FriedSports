import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getJoinInfo, joinGroup } from '../api/groups'
import { useAuth } from '../context/AuthContext'
import Loading from '../components/Loading'
import BackButton from '../components/BackButton'

export default function JoinGroup() {
  const { code } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [manualCode, setManualCode] = useState('')
  const [error, setError] = useState('')

  // When code is in URL, fetch group info
  const { data, isLoading } = useQuery({
    queryKey: ['join-info', code],
    queryFn: () => getJoinInfo(code),
    enabled: !!code,
  })

  const joinMut = useMutation({
    mutationFn: (c) => joinGroup(c),
    onSuccess: (data) => navigate(`/groups/${data.group_id}`),
    onError: (err) => setError(err.message || 'Failed to join'),
  })

  // Code entry form (no code in URL)
  if (!code) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <BackButton fallback="/dashboard" />
          <h1 className="auth-title">Join a Group</h1>
          {error && <div className="flash flash-error">{error}</div>}
          <form className="auth-form" onSubmit={e => { e.preventDefault(); navigate(`/groups/join/${manualCode}`) }}>
            <div className="form-group">
              <label htmlFor="invite_code">Invite Code</label>
              <input id="invite_code" type="text" required autoFocus style={{ fontSize: 16 }}
                value={manualCode} onChange={e => setManualCode(e.target.value.trim())} />
            </div>
            <button type="submit" className="btn-primary btn-full">Join Group</button>
          </form>
          <p className="auth-switch"><Link to="/groups/new">Create a new group instead</Link></p>
        </div>
      </div>
    )
  }

  if (isLoading) return <Loading full />

  const { group, member_count, already_member } = data ?? {}

  if (!group) return <div className="empty-state"><p>Invalid invite link.</p></div>

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">{group.name}</h1>
        <p className="auth-sub">
          {group.league_scope} · {member_count} member{member_count !== 1 ? 's' : ''}
        </p>

        {error && <div className="flash flash-error">{error}</div>}

        {already_member ? (
          <Link to={`/groups/${group.id}`} className="btn-primary btn-full">Go to Group →</Link>
        ) : !user ? (
          <>
            <Link to={`/signup?next=/groups/join/${code}`} className="btn-primary btn-full">Create Account to Join</Link>
            <p className="auth-switch"><Link to={`/login?next=/groups/join/${code}`}>Already have an account?</Link></p>
          </>
        ) : (
          <button className="btn-primary btn-full" onClick={() => joinMut.mutate(code)}>
            {joinMut.isPending ? 'Joining…' : `Join ${group.name}`}
          </button>
        )}
      </div>
    </div>
  )
}
