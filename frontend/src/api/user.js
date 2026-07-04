import client from './client'

export const getSettings      = ()     => client.get('/settings').then(r => r.data)
export const updateSettings   = (data) => client.post('/settings', data).then(r => r.data)
export const uploadAvatar     = (data_url) => client.post('/settings/avatar', { data_url }).then(r => r.data)
export const removeAvatar     = ()     => client.delete('/settings/avatar').then(r => r.data)
export const completeProfile  = (data) => client.post('/profile/complete', data).then(r => r.data)
export const deleteAccount    = (data) => client.post('/settings/delete-account', data).then(r => r.data)
export const getOnboarding    = ()     => client.get('/onboarding').then(r => r.data)
export const submitOnboarding = (data) => client.post('/onboarding', data).then(r => r.data)
export const getSupportTickets = ()    => client.get('/support/tickets').then(r => r.data)
export const createTicket     = (data) => client.post('/support/tickets', data).then(r => r.data)
export const getTicket        = (uid)  => client.get(`/support/tickets/${uid}`).then(r => r.data)
export const getReceipt       = (slug) => client.get(`/public/receipts/${slug}`).then(r => r.data)
