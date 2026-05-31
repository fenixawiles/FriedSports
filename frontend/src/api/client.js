import axios from 'axios'

// Base axios instance — all API calls go through here.
// `withCredentials: true` ensures Flask-Login session cookies are sent on
// every request, even during Vite dev (cross-origin to localhost:5001).
const client = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

// Normalise errors so callers always get { message, status, data }
client.interceptors.response.use(
  (res) => res,
  (err) => {
    const status  = err.response?.status
    const data    = err.response?.data
    const message = data?.error || data?.message || err.message || 'Something went wrong'

    // 401 → redirect to /login (unless we're already there)
    if (status === 401 && !window.location.pathname.startsWith('/login')) {
      window.location.replace('/login')
    }

    return Promise.reject({ message, status, data })
  }
)

export default client
