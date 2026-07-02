import client from './client'

export const getAdminOverview = () => client.get('/admin/overview').then(r => r.data)
export const getAdminUsers = (q = '', pending = false) =>
  client.get('/admin/users', { params: { q, pending: pending ? 1 : undefined } }).then(r => r.data)
export const getAdminUser = (id) => client.get(`/admin/users/${id}`).then(r => r.data)
export const approveAdminUser = (id) => client.post(`/admin/users/${id}/approve`).then(r => r.data)
export const updateAdminUser = (id, data) => client.patch(`/admin/users/${id}`, data).then(r => r.data)
export const deleteAdminUser = (id) => client.delete(`/admin/users/${id}`).then(r => r.data)
export const inviteAdminUser = (data) => client.post('/admin/users/invite', data).then(r => r.data)
export const emailAdminUser = (id, data) => client.post(`/admin/users/${id}/email`, data).then(r => r.data)
export const promptAdminUser = (id, kind) => client.post(`/admin/users/${id}/prompt/${kind}`).then(r => r.data)
export const getAdminSupport = (status = 'all') =>
  client.get('/admin/support', { params: { status } }).then(r => r.data)
export const updateAdminSupportTicket = (uid, data) =>
  client.patch(`/admin/support/${uid}`, data).then(r => r.data)
export const getAdminReports = (status = 'open') =>
  client.get('/admin/reports', { params: { status } }).then(r => r.data)
export const actionAdminReport = (id, action) =>
  client.post(`/admin/reports/${id}/action`, { action }).then(r => r.data)
export const sendAdminBroadcast = (data) => client.post('/admin/broadcast', data).then(r => r.data)
export const getAdminAuditLog = () => client.get('/admin/audit-log').then(r => r.data)
export const getAdminLab = () => client.get('/admin/lab').then(r => r.data)
export const createAdminSeason = (data) => client.post('/admin/lab/seasons', data).then(r => r.data)
export const createAdminGame = (data) => client.post('/admin/lab/games', data).then(r => r.data)
export const updateAdminGameStats = (id, data) =>
  client.patch(`/admin/lab/games/${id}/stats`, data).then(r => r.data)
export const deriveAdminGame = (id) => client.post(`/admin/lab/games/${id}/derive`).then(r => r.data)
export const createAdminPlayer = (data) => client.post('/admin/lab/players', data).then(r => r.data)
export const createAdminMetric = (data) => client.post('/admin/lab/metrics', data).then(r => r.data)
