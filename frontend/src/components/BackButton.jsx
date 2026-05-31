import { useNavigate } from 'react-router-dom'

export default function BackButton({ fallback = '/dashboard', label = '← Back' }) {
  const navigate = useNavigate()

  function handleBack() {
    if (window.history.length > 1) {
      navigate(-1)
    } else {
      navigate(fallback)
    }
  }

  return (
    <div className="page-back-wrap">
      <button type="button" className="page-back-btn" onClick={handleBack}>
        {label}
      </button>
    </div>
  )
}
