import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getFriends, searchUsers, sendRequest, removeFriend } from '../api/friends'
import { Skeleton } from '../components/Skeleton'

export default function Friends() {
  const qc = useQueryClient()
  const [query, setQuery]     = useState('')
  const [results, setResults] = useState(null)
  const debounceRef = useRef(null)

  const { data, isLoading } = useQuery({ queryKey: ['friends'], queryFn: getFriends })

  const sendMut = useMutation({
    mutationFn: (uid) => sendRequest(uid),
    onSuccess: () => { qc.invalidateQueries(['friends']); setResults(null) },
  })
  const removeMut = useMutation({
    mutationFn: (uid) => removeFriend(uid),
    onSuccess: () => qc.invalidateQueries(['friends']),
  })

  useEffect(() => {
    clearTimeout(debounceRef.current)
    if (query.length < 2) { setResults(null); return }
    debounceRef.current = setTimeout(async () => {
      try { setResults(await searchUsers(query)) } catch {}
    }, 280)
    return () => clearTimeout(debounceRef.current)
  }, [query])

  const friends = data?.friends ?? []

  return (
    <div className="group-container" style={{ maxWidth: 680 }}>
      <div className="group-header">
        <div>
          <h1>Friends</h1>
          <div className="group-header-meta">
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              {friends.length} friend{friends.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>
      </div>

      {/* Search */}
      <section className="group-section" style={{ borderTop: 'none', paddingTop: 0 }}>
        <div className="friend-search-block">
          <div className="friend-search-form">
            <input type="text" value={query} onChange={e => setQuery(e.target.value)}
              placeholder="Search for a friend"
              autoComplete="off" />
            {query && (
              <button className="btn-secondary-small" onClick={() => { setQuery(''); setResults(null) }}>
                Clear
              </button>
            )}
          </div>
          <p className="friend-search-hint">Search by username, FS ID, or email. FS IDs look like FS-123456.</p>
        </div>

        {results && (
          <div className="member-table" style={{ marginTop: '1rem' }}>
            <div className="member-row member-header" style={{ gridTemplateColumns: '1fr auto auto' }}>
              <span>User</span><span>UID</span><span />
            </div>
            {results.length === 0 && (
              <div className="empty-state"><p>No users found.</p></div>
            )}
            {results.map(item => (
              <div key={item.id} className="member-row" style={{ gridTemplateColumns: '1fr auto auto' }}>
                <span className="member-name">{item.name}</span>
                <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--text-muted)' }}>{item.uid}</span>
                <span>
                  {item.status === 'friends' && <span className="badge-role member">Friends</span>}
                  {item.status === 'pending_sent' && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Request sent</span>}
                  {item.status === 'pending_received' && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Wants to add you</span>}
                  {item.status === 'none' && (
                    <button className="btn-secondary-small" onClick={() => sendMut.mutate(item.id)}>
                      Add Friend
                    </button>
                  )}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Friends list */}
      <section className="group-section">
        <div className="section-header" style={{ marginBottom: '0.85rem' }}>
          <span className="section-title">Your Friends</span>
        </div>
        {isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {[1,2,3].map(i => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.5rem 0' }}>
                <Skeleton circle size={36} />
                <div style={{ flex: 1 }}><Skeleton w="45%" h="0.85rem" /></div>
                <Skeleton w="20%" h="0.75rem" />
              </div>
            ))}
          </div>
        ) : friends.length === 0 ? (
          <div className="empty-state">
            <p>No friends yet. Search above to add someone.</p>
          </div>
        ) : (
          <div className="member-table">
            <div className="member-row member-header" style={{ gridTemplateColumns: '1fr auto auto' }}>
              <span>Name</span><span>UID</span><span />
            </div>
            {friends.map(f => (
              <div key={f.id} className="member-row" style={{ gridTemplateColumns: '1fr auto auto' }}>
                <span className="member-name">{f.name}</span>
                <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--text-muted)' }}>{f.uid}</span>
                <span>
                  <button className="btn-danger-tiny"
                    onClick={() => { if (window.confirm(`Remove ${f.name}?`)) removeMut.mutate(f.id) }}>
                    Remove
                  </button>
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
