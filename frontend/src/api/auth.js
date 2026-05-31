import client from './client'

export const getMe        = ()       => client.get('/auth/me').then(r => r.data)
export const login        = (data)   => client.post('/auth/login', data).then(r => r.data)
export const signup       = (data)   => client.post('/auth/signup', data).then(r => r.data)
export const sendCode     = (data)   => client.post('/auth/send-code', data).then(r => r.data)
export const verifyCode   = (data)   => client.post('/auth/verify-code', data).then(r => r.data)
export const logout       = ()       => client.post('/auth/logout').then(r => r.data)
export const resetPassword = (token, data) =>
  client.post(`/auth/reset-password/${token}`, data).then(r => r.data)
