import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Landing() {
  const { user } = useAuth()

  return (
    <>
      <div className="hero">
        <div className="hero-eyebrow">Sports trash talk, organized</div>
        <h1 className="hero-title">Your team just choked.<br /><em>Your group is already waiting.</em></h1>
        <p className="hero-sub">
          FriedSports is a private platform for holding your friends accountable when their teams blow it.
          Start threads, roast with the group, and track who's been the most delusional fan all season.
        </p>
        <div className="hero-actions">
          {user ? (
            <>
              <Link to="/groups/new" className="btn-primary">Create New Group</Link>
              <Link to="/groups/join" className="btn-secondary">Join with Invite Code</Link>
            </>
          ) : (
            <>
              <Link to="/signup" className="btn-primary">Get Started — It's Free</Link>
              <Link to="/login" className="btn-secondary">Log In</Link>
            </>
          )}
        </div>
      </div>

      <div className="features">
        <div className="features-label">How it works</div>
        <div className="feature-grid">
          {[
            ['01', 'Pick Your Teams', 'NBA, NFL, MLB, NHL, Premier League, FIFA, F1, PGA — pick the teams you ride or die with.'],
            ['02', 'Start Threads', "Blowout, choked lead, playoff collapse — open a thread when someone's team embarrasses them."],
            ['03', 'Group Roast Threads', 'Every report opens a group thread. Pile in, talk trash, award reactions. The target gets notified.'],
            ['04', 'Permanent Receipts', "After every major disaster, a shareable receipt gets generated. The evidence doesn't disappear."],
          ].map(([n, t, d]) => (
            <div key={n} className="feature-card">
              <div className="feature-number">{n}</div>
              <h3>{t}</h3>
              <p>{d}</p>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
