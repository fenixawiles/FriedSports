import client from './client'

export const getFriends     = ()    => client.get('/friends').then(r => r.data)
export const searchUsers    = (q)   => client.get('/users/search', { params: { q } }).then(r => r.data)
export const sendRequest    = (uid) => client.post(`/friends/request/${uid}`).then(r => r.data)
export const acceptRequest  = (id)  => client.post(`/friends/accept/${id}`).then(r => r.data)
export const declineRequest = (id)  => client.post(`/friends/decline/${id}`).then(r => r.data)
export const removeFriend   = (uid) => client.delete(`/friends/${uid}`).then(r => r.data)
export const blockUser      = (uid) => client.post(`/friends/${uid}/block`).then(r => r.data)
export const reportUser     = (uid, reason) => client.post(`/users/${uid}/report`, { reason }).then(r => r.data)
export const getBlockedUsers = ()   => client.get('/blocked-users').then(r => r.data)
export const unblockUser    = (uid) => client.delete(`/blocked-users/${uid}`).then(r => r.data)
