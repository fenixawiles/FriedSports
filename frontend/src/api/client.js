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

function isPublicRoute(pathname) {
  return (
    pathname === '/' ||
    pathname === '/login' ||
    pathname === '/signup' ||
    pathname === '/send-code' ||
    pathname === '/verify-code' ||
    pathname === '/privacy' ||
    pathname === '/terms' ||
    pathname === '/legal/privacy' ||
    pathname === '/legal/terms' ||
    pathname.startsWith('/reset-password/') ||
    pathname.startsWith('/public/receipts/') ||
    pathname.startsWith('/groups/join/')
  )
}

// Normalise errors so callers always get { message, status, data }
client.interceptors.response.use(
  (res) => res,
  (err) => {
    const status  = err.response?.status
    const data    = err.response?.data
    const message = data?.error || data?.message || err.message || 'Something went wrong'
    const requestUrl = err.config?.url || ''

    // 401 on protected work should send the user to login. Auth bootstrap and
    // public pages handle unauthenticated state themselves so Privacy/Terms and
    // public invite/receipt pages do not get yanked away during /auth/me.
    if (
      status === 401 &&
      !requestUrl.includes('/auth/me') &&
      !isPublicRoute(window.location.pathname)
    ) {
      window.location.replace('/login')
    }

    return Promise.reject({ message, status, data })
  }
)

export default client
