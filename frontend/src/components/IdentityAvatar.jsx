import { useEffect, useState } from 'react'

function fallbackLabel(identity, fallback) {
  return (identity?.label || fallback || '?').slice(0, 3).toUpperCase()
}

export default function IdentityAvatar({ identity, fallbackLabel: fallback = '?', className = '' }) {
  const [failedSrc, setFailedSrc] = useState('')
  const team = identity?.team || null
  const avatarUrl = identity?.avatar_url || ''
  const teamLogoUrl = team?.logo_url || ''
  const image = avatarUrl && failedSrc !== avatarUrl ? avatarUrl : ''
  const teamLogo = !image && teamLogoUrl && failedSrc !== teamLogoUrl ? teamLogoUrl : ''
  const badge = identity?.badge_label || team?.abbreviation || ''
  const color = identity?.color || team?.primary_color || 'var(--accent)'
  const label = fallbackLabel(identity, fallback)

  useEffect(() => {
    setFailedSrc('')
  }, [identity?.avatar_url, team?.logo_url])

  function handleImageError(e) {
    setFailedSrc(e.currentTarget.getAttribute('src') || '')
  }

  return (
    <div className={`identity-avatar ${identity?.kind || 'fallback'} ${className}`}
      style={{ '--avatar-color': color }}>
      {image ? (
        <img src={image} alt="" loading="lazy" onError={handleImageError} />
      ) : teamLogo ? (
        <img src={teamLogo} alt="" loading="lazy" onError={handleImageError} />
      ) : (
        <span className="identity-avatar-label">{label}</span>
      )}
      {badge && <span className="identity-avatar-badge">{badge.slice(0, 4).toUpperCase()}</span>}
    </div>
  )
}
