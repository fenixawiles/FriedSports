import client from './client'

export const getThreadsList = ()          => client.get('/threads').then(r => r.data)
export const createChatThread = (data)    => client.post('/threads', data).then(r => r.data)
export const getThread      = (id)        => client.get(`/threads/${id}`).then(r => r.data)
export const archiveThread  = (id)        => client.post(`/threads/${id}/archive`).then(r => r.data)
export const unarchiveThread = (id)       => client.post(`/threads/${id}/unarchive`).then(r => r.data)
export const deleteThreadLocal = (id)     => client.post(`/threads/${id}/delete-local`).then(r => r.data)
export const restoreThread  = (id)        => client.post(`/threads/${id}/restore`).then(r => r.data)
export const sendMessage    = (id, body)  =>
  client.post(`/threads/${id}/messages`, { body }).then(r => r.data)
export const reactToMessage = (id, type)  =>
  client.post(`/messages/${id}/react`, { reaction_type: type }).then(r => r.data)
export const deleteMessage  = (id)        =>
  client.post(`/messages/${id}/delete`).then(r => r.data)
export const confirmReport  = (id)        => client.post(`/reports/${id}/confirm`).then(r => r.data)
export const dismissReport  = (id)        => client.post(`/reports/${id}/dismiss`).then(r => r.data)
export const redeemReport   = (id)        => client.post(`/reports/${id}/redeem`).then(r => r.data)
