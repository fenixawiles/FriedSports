import client from './client'

export const getFeed = () => client.get('/feed').then(r => r.data)
