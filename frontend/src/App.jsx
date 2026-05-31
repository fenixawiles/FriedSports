import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import Shell from './components/Shell'
import Loading from './components/Loading'

// Pages — auth
import Landing      from './pages/Landing'
import Login        from './pages/Login'
import Signup       from './pages/Signup'
import SendCode     from './pages/SendCode'
import VerifyCode   from './pages/VerifyCode'
import ResetPassword from './pages/ResetPassword'

// Pages — main tabs
import Dashboard    from './pages/Dashboard'
import Threads      from './pages/Threads'
import Friends      from './pages/Friends'
import Notifications from './pages/Notifications'
import More         from './pages/More'

// Pages — groups
import Group        from './pages/Group'
import NewGroup     from './pages/NewGroup'
import JoinGroup    from './pages/JoinGroup'
import Report       from './pages/Report'

// Pages — thread chat
import ThreadChat   from './pages/ThreadChat'

// Pages — account
import Onboarding   from './pages/Onboarding'
import Settings     from './pages/Settings'

// Pages — support + public
import Support      from './pages/Support'
import SupportTicket from './pages/SupportTicket'
import Receipt      from './pages/Receipt'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5 * 60_000,       // 5 min — show cached data, refresh silently in bg
      gcTime:    10 * 60_000,       // Keep unused data in memory 10 min
      refetchOnWindowFocus: false,  // Don't blast the API every time the user alt-tabs back
    },
  },
})

// Route guard — redirects to /login if not authenticated
function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading full />
  if (!user) return <Navigate to="/login" replace />
  return children
}

// Redirect logged-in users away from auth screens
function RedirectIfAuthed({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading full />
  if (user) return <Navigate to="/dashboard" replace />
  return children
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider>
          <BrowserRouter>
            <Routes>
              {/* ── Public shell ── */}
              <Route element={<Shell />}>

                {/* Landing */}
                <Route path="/" element={<Landing />} />

                {/* Auth — only accessible when logged out */}
                <Route path="/login"       element={<RedirectIfAuthed><Login /></RedirectIfAuthed>} />
                <Route path="/signup"      element={<RedirectIfAuthed><Signup /></RedirectIfAuthed>} />
                <Route path="/send-code"   element={<RedirectIfAuthed><SendCode /></RedirectIfAuthed>} />
                <Route path="/verify-code" element={<RedirectIfAuthed><VerifyCode /></RedirectIfAuthed>} />
                <Route path="/reset-password/:token" element={<ResetPassword />} />

                {/* Public receipt — no auth required */}
                <Route path="/public/receipts/:slug" element={<Receipt />} />

                {/* ── Authenticated routes ── */}
                <Route path="/onboarding"  element={<RequireAuth><Onboarding /></RequireAuth>} />
                <Route path="/dashboard"   element={<RequireAuth><Dashboard /></RequireAuth>} />
                <Route path="/threads"     element={<RequireAuth><Threads /></RequireAuth>} />
                <Route path="/friends"     element={<RequireAuth><Friends /></RequireAuth>} />
                <Route path="/notifications" element={<RequireAuth><Notifications /></RequireAuth>} />
                <Route path="/more"        element={<RequireAuth><More /></RequireAuth>} />
                <Route path="/settings"    element={<RequireAuth><Settings /></RequireAuth>} />

                {/* Groups */}
                <Route path="/groups/new"          element={<RequireAuth><NewGroup /></RequireAuth>} />
                <Route path="/groups/join"          element={<RequireAuth><JoinGroup /></RequireAuth>} />
                <Route path="/groups/join/:code"    element={<JoinGroup />} />
                <Route path="/groups/:id"           element={<RequireAuth><Group /></RequireAuth>} />
                <Route path="/groups/:id/report"    element={<RequireAuth><Report /></RequireAuth>} />

                {/* Thread chat */}
                <Route path="/threads/:id" element={<RequireAuth><ThreadChat /></RequireAuth>} />

                {/* Support */}
                <Route path="/support"        element={<RequireAuth><Support /></RequireAuth>} />
                <Route path="/support/new"    element={<RequireAuth><SupportTicket new /></RequireAuth>} />
                <Route path="/support/:uid"   element={<RequireAuth><SupportTicket /></RequireAuth>} />

              </Route>
            </Routes>
          </BrowserRouter>
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}
