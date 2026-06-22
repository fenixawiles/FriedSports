import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getBlockedUsers, unblockUser } from '../api/friends'
import BackButton from '../components/BackButton'
import Loading from '../components/Loading'

export default function BlockedUsers() {
  const qc = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ['blocked-users'],
    queryFn: getBlockedUsers,
  })
  const unblockMut = useMutation({
    mutationFn: unblockUser,
    onSuccess: () => {
      qc.invalidateQueries(['blocked-users'])
      qc.invalidateQueries(['friends'])
    },
  })

  if (isLoading) return <Loading full />
  if (error) return <div className="empty-state"><p>Could not load blocked users.</p></div>

  const blocked = data?.blocked_users ?? []

  return (
    <div className="settings-page">
      <BackButton fallback="/settings" />
      <div className="settings-title-row">
        <span className="section-title">Blocked Users</span>
        <span className="section-sub">People here cannot message you or appear in search.</span>
      </div>

      {blocked.length === 0 ? (
        <div className="empty-state"><p>You have not blocked anyone.</p></div>
      ) : (
        <div className="settings-group">
          {blocked.map(user => (
            <div key={user.id} className="settings-row blocked-user-row">
              <span>
                <span className="blocked-user-name">{user.name}</span>
                <span className="blocked-user-uid">{user.uid}</span>
              </span>
              <button
                type="button"
                className="btn-secondary-small"
                disabled={unblockMut.isPending}
                onClick={() => unblockMut.mutate(user.id)}>
                Unblock
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
