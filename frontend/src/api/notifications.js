import client from './client'

export const getNotifications = () => client.get('/notifications').then(r => r.data)
export const markAllRead      = () => client.post('/notifications/mark-read').then(r => r.data)
