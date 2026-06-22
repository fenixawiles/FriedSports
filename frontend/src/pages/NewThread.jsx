import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getThreadsList, createChatThread } from '../api/threads'
import { getFriends } from '../api/friends'
import Loading from '../components/Loading'

function initials(name, fallback = '?') {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
  return (parts[0]?.slice(0, 2) || fallback).toUpperCase()
}

export default function NewThread() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [mode, setMode] = useState('friends')
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [pendingKey, setPendingKey] = useState('')

  const { data: threadsData, isLoading: groupsLoading } = useQuery({
    queryKey: ['threads'],
    queryFn: getThreadsList,
  })
  const { data: friendsData, isLoading: friendsLoading } = useQuery({
    queryKey: ['friends'],
    queryFn: getFriends,
  })

  const groups = threadsData?.groups ?? []
  const friends = friendsData?.friends ?? []
  const activeItems = mode === 'groups' ? groups : friends
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return activeItems
    return activeItems.filter(item => {
      const name = (item.name || '').toLowerCase()
      const uid = (item.uid || '').toLowerCase()
      return name.includes(q) || uid.includes(q)
    })
  }, [activeItems, search])

  const createMut = useMutation({
    mutationFn: createChatThread,
    onSuccess: (res) => {
      qc.invalidateQueries(['threads'])
      navigate(`/threads/${res.thread_id}`)
    },
    onError: (err) => {
      setPendingKey('')
      setError(err.message || 'Could not start chat')
    },
  })

  function startGroup(groupId) {
    setError('')
    setPendingKey(`group-${groupId}`)
    createMut.mutate({ type: 'group', group_id: groupId })
  }

  function startFriend(userId) {
    setError('')
    setPendingKey(`friend-${userId}`)
    createMut.mutate({ type: 'direct', user_id: userId })
  }

  const loading = mode === 'groups' ? groupsLoading : friendsLoading
  const emptyCopy = mode === 'groups'
    ? 'No groups yet.'
    : 'No friends yet.'

  return (
    <div className="new-thread-page">
      <div className="new-thread-top">
        <button type="button" className="back-link new-thread-back" onClick={() => navigate('/threads')}>
          ← Chats
        </button>
        <h1 className="new-thread-title">New Chat</h1>
      </div>

      <div className="new-thread-segment" role="tablist" aria-label="Chat type">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'friends'}
          className={`new-thread-seg-btn${mode === 'friends' ? ' active' : ''}`}
          onClick={() => { setMode('friends'); setSearch(''); setError('') }}>
          Friend
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'groups'}
          className={`new-thread-seg-btn${mode === 'groups' ? ' active' : ''}`}
          onClick={() => { setMode('groups'); setSearch(''); setError('') }}>
          Group
        </button>
      </div>

      <div className="new-thread-search">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={mode === 'groups' ? 'Search groups' : 'Search friends'}
          autoCapitalize="none"
        />
      </div>

      {error && <div className="new-thread-error">{error}</div>}

      {loading ? (
        <Loading />
      ) : filtered.length === 0 ? (
        <div className="new-thread-empty">
          <p>{emptyCopy}</p>
          {mode === 'friends' ? (
            <Link to="/friends" className="new-thread-empty-action">Find friends</Link>
          ) : (
            <Link to="/dashboard" className="new-thread-empty-action">View groups</Link>
          )}
        </div>
      ) : (
        <div className="new-thread-list">
          {filtered.map(item => {
            const key = mode === 'groups' ? `group-${item.id}` : `friend-${item.id}`
            const isPending = createMut.isPending && pendingKey === key
            return (
              <button
                key={key}
                type="button"
                className="new-thread-row"
                disabled={createMut.isPending}
                onClick={() => mode === 'groups' ? startGroup(item.id) : startFriend(item.id)}>
                <span className="new-thread-avatar">{initials(item.name, mode === 'groups' ? 'G' : 'F')}</span>
                <span className="new-thread-copy">
                  <span className="new-thread-name">{item.name}</span>
                  <span className="new-thread-meta">
                    {mode === 'groups'
                      ? 'Group thread'
                      : (item.uid || `${item.shared_group_count || 0} shared groups`)}
                  </span>
                </span>
                <span className="new-thread-chevron">{isPending ? 'Starting' : '›'}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
