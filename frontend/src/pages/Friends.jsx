import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getFriends, searchUsers, sendRequest, removeFriend, blockUser, reportUser } from '../api/friends'
import { Skeleton } from '../components/Skeleton'
import IdentityAvatar from '../components/IdentityAvatar'

export default function Friends() {
  const qc = useQueryClient()
  const [query, setQuery]     = useState('')
  const [results, setResults] = useState(null)
  const [menuFriend, setMenuFriend] = useState(null) // friend whose options sheet is open
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
  const blockMut = useMutation({
    mutationFn: (uid) => blockUser(uid),
    onSuccess: () => qc.invalidateQueries(['friends']),
  })
  const reportMut = useMutation({
    mutationFn: ({ uid, reason }) => reportUser(uid, reason),
    onSuccess: () => window.alert('Report submitted. Our moderators will take a look.'),
  })

  function doRemove(f) {
    setMenuFriend(null)
    if (window.confirm(`Remove ${f.name}?`)) removeMut.mutate(f.id)
  }
  function doBlock(f) {
    setMenuFriend(null)
    if (window.confirm(`Block ${f.name}? You'll be unfriended and you won't see each other's content.`)) blockMut.mutate(f.id)
  }
  function doReport(f) {
    setMenuFriend(null)
    const reason = window.prompt(`Report ${f.name} to the moderators? Add a reason (optional):`, '')
    if (reason !== null) reportMut.mutate({ uid: f.id, reason: reason || '' })
  }

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
            <p>Trash talk hits different with witnesses. Search above and add your first rival.</p>
          </div>
        ) : (
          <div className="friend-list">
            {friends.map(f => (
              <div key={f.id} className="friend-list-row">
                <IdentityAvatar identity={f.identity} fallbackLabel={f.name} className="friend-list-avatar" />
                <div className="friend-list-info">
                  <span className="member-name">{f.name}</span>
                  <span className="friend-list-uid">{f.uid}</span>
                </div>
                <button className="friend-menu-btn" aria-label="Friend options"
                  onClick={() => setMenuFriend(f)}>
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"
                    fill="currentColor" aria-hidden="true">
                    <circle cx="12" cy="5" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="12" cy="19" r="1.6"/>
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Friend options sheet (reuses the pw-sheet styles) */}
      {menuFriend && (
        <div className="pw-sheet" onClick={(e) => { if (e.target === e.currentTarget) setMenuFriend(null) }}>
          <div className="pw-sheet-backdrop" onClick={() => setMenuFriend(null)} />
          <div className="pw-sheet-card" role="dialog" aria-modal="true">
            <div className="pw-sheet-head">
              <div className="pw-sheet-title">{menuFriend.name}</div>
            </div>
            <button type="button" className="pw-sheet-opt" onClick={() => doReport(menuFriend)}>
              <span className="pw-opt-main">Report</span>
              <span className="pw-opt-sub">Flag this user for the moderators</span>
            </button>
            <button type="button" className="pw-sheet-opt" onClick={() => doBlock(menuFriend)}>
              <span className="pw-opt-main">Block</span>
              <span className="pw-opt-sub">Unfriend and hide each other's content</span>
            </button>
            <button type="button" className="pw-sheet-opt pw-opt-danger" onClick={() => doRemove(menuFriend)}>
              <span className="pw-opt-main">Remove friend</span>
            </button>
            <button type="button" className="pw-sheet-cancel" onClick={() => setMenuFriend(null)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  )
}
