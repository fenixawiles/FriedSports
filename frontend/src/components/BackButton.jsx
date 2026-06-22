import { useNavigate } from 'react-router-dom'

export default function BackButton({ fallback = '/dashboard', label = 'Back' }) {
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
      <button type="button" className="page-back-btn" onClick={handleBack} aria-label="Back">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        {label}
      </button>
    </div>
  )
}
