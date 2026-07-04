import { Link, useNavigate } from 'react-router-dom'
import { flashThen } from '../utils/tapFlash'

/**
 * Link with tactile feedback: press-flash + haptic tick, then navigate.
 * Drop-in replacement for react-router's <Link> on nav rows/cards.
 */
export default function TapLink({ to, onClick, children, ...rest }) {
  const navigate = useNavigate()
  return (
    <Link to={to} {...rest}
      onClick={(e) => {
        onClick?.(e)
        if (e.defaultPrevented) return
        e.preventDefault()
        flashThen(e.currentTarget, () => navigate(to))
      }}>
      {children}
    </Link>
  )
}
