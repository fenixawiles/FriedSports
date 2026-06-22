import axios from 'axios'

const isNative = window.Capacitor?.isNativePlatform?.() === true
const envApiOrigin = import.meta.env.VITE_API_ORIGIN?.replace(/\/$/, '')
const apiOrigin = envApiOrigin || (isNative ? 'https://www.friedsports.com' : '')

// Base axios instance — all API calls go through here.
// `withCredentials: true` ensures Flask-Login session cookies are sent on
// every request, including native iOS where the bundled app talks to Railway.
const client = axios.create({
  baseURL: `${apiOrigin}/api`,
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
