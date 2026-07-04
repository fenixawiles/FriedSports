import client from './client'

export const getNotifications = () => client.get('/notifications').then(r => r.data)
export const markAllRead      = () => client.post('/notifications/mark-read').then(r => r.data)
export const markOneRead      = (id) => client.post(`/notifications/${id}/read`).then(r => r.data)
