import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import App from './App'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
)

// Tell Capacitor to hide the splash screen once React has rendered.
// Using the low-level window.Capacitor bridge so we don't need to add
// @capacitor/splash-screen as an npm dep in the frontend package.
if (window.Capacitor?.isNativePlatform()) {
  window.Capacitor.Plugins?.SplashScreen?.hide()
}
