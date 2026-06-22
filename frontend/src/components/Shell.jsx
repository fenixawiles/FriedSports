import { Outlet, NavLink, Link, useNavigate, useMatch, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { getNotifications } from '../api/notifications'
import { getDashboard } from '../api/groups'
import { getThreadsList } from '../api/threads'
import { getFriends } from '../api/friends'
import logo from '../logo.png'

export default function Shell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const qc = useQueryClient()

  // Thread chat is a focused full-screen view — hide all navigation chrome.
  // useMatch returns a truthy object when the current path matches the pattern.
  const threadChatMatch = useMatch('/threads/:id')
  const isThreadChat = !!threadChatMatch && threadChatMatch.params.id !== 'new'
  const location     = useLocation()
  const navRef       = useRef(null)

  // Auto-hide the top navbar on scroll-down, reveal it back at the top.
  // Direct classList toggle via ref so it never re-renders the page content.
  useEffect(() => {
    let ticking = false
    function onScroll() {
      if (ticking) return
      ticking = true
      requestAnimationFrame(() => {
        ticking = false
        const nav = navRef.current
        if (!nav) return
        const y = window.scrollY || document.documentElement.scrollTop || 0
        if (y > 64) nav.classList.add('nav-hidden')
        else if (y < 12) nav.classList.remove('nav-hidden')
      })
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Each new page starts at the top — make sure the navbar is shown.
  useEffect(() => {
    navRef.current?.classList.remove('nav-hidden')
  }, [location.pathname])

  // Prefetch all main tab data the moment the user is authenticated.
  // Fires 4 parallel requests in the background so every first tab tap is instant.
  useEffect(() => {
    if (!user) return
    qc.prefetchQuery({ queryKey: ['dashboard'],     queryFn: getDashboard })
    qc.prefetchQuery({ queryKey: ['threads'],        queryFn: getThreadsList })
    qc.prefetchQuery({ queryKey: ['friends'],        queryFn: getFriends })
    qc.prefetchQuery({ queryKey: ['notifications'],  queryFn: getNotifications })
  }, [user?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const { data: notifData } = useQuery({
    queryKey: ['notifications'],
    queryFn: getNotifications,
    refetchInterval: 30_000,
    enabled: !!user,
  })

  const unread = notifData?.unread_count ?? 0

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <>
      {/* ── Top navbar — hidden on thread chat (focused conversation view) ── */}
      {!isThreadChat && (
        <nav className="navbar" id="main-nav" ref={navRef}>
          <div className="nav-inner">
            <Link to="/" className="nav-logo">
              <img src={logo} className="nav-logo-img" alt="FS" width="24" height="24" />
              FriedSports
            </Link>

            {user && (
              <Link to="/notifications" className="nav-bell" aria-label="Notifications">
                <svg xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24"
                  fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                  <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
                {unread > 0 && (
                  <span className="notif-badge">{unread >= 10 ? '9+' : unread}</span>
                )}
              </Link>
            )}
          </div>
        </nav>
      )}

      {/* ── Page content ── */}
      <main className={`main-content${isThreadChat ? ' thread-main' : ''}`}>
        {/* key=location.key forces remount on every navigation → CSS enter animation fires */}
        <div key={location.key} className="page-enter">
          <Outlet />
        </div>
      </main>

      {/* ── Bottom nav — hidden on thread chat ── */}
      {user && !isThreadChat && (
        <nav className="bottom-nav" id="bottom-nav" aria-label="Mobile navigation">
          <NavLink to="/" end className={({ isActive }) => 'bottom-nav-item' + (isActive ? ' active' : '')}>
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
            <span className="bottom-nav-label">Home</span>
          </NavLink>

          <NavLink to="/dashboard" className={({ isActive }) => 'bottom-nav-item' + (isActive ? ' active' : '')}>
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
              <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
            </svg>
            <span className="bottom-nav-label">Groups</span>
          </NavLink>

          <NavLink to="/threads" className={({ isActive }) => 'bottom-nav-item' + (isActive ? ' active' : '')}>
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            <span className="bottom-nav-label">Threads</span>
          </NavLink>

          <NavLink to="/friends" className={({ isActive }) => 'bottom-nav-item' + (isActive ? ' active' : '')}>
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
            <span className="bottom-nav-label">Friends</span>
          </NavLink>

          <NavLink to="/more" className={({ isActive }) => 'bottom-nav-item' + (isActive ? ' active' : '')}>
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>
            </svg>
            <span className="bottom-nav-label">More</span>
          </NavLink>
        </nav>
      )}
    </>
  )
}
