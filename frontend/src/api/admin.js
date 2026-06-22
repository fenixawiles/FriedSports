import client from './client'

export const getAdminOverview = () => client.get('/admin/overview').then(r => r.data)
