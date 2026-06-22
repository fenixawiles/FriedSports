import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import App from './App'

function isNativePlatform() {
  return window.Capacitor?.isNativePlatform?.() === true
}

function capacitorPlugin(name) {
  return window.Capacitor?.Plugins?.[name] ?? null
}

function setupNativeShellBridge() {
  if (!isNativePlatform()) return

  document.documentElement.classList.add('is-native-app')

  if (!window.__fsKeyboardWired) {
    const Keyboard = capacitorPlugin('Keyboard')
    if (Keyboard?.addListener) {
      window.__fsKeyboardWired = true
      Keyboard.addListener('keyboardWillShow', () => {
        document.body.classList.add('keyboard-open')
      })
      Keyboard.addListener('keyboardWillHide', () => {
        document.body.classList.remove('keyboard-open')
      })
    }
  }

  const syncBounce = () => {
    try {
      const handler = window.webkit?.messageHandlers?.fsBounce
      if (!handler) return
      handler.postMessage(document.documentElement.hasAttribute('data-thread') ? '0' : '1')
    } catch {
      // Web fallback only; the bridge is optional outside the native shell.
    }
  }

  syncBounce()
  if (!window.__fsBounceWired) {
    window.__fsBounceWired = true
    new MutationObserver(syncBounce).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-thread'],
    })
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
)

// Tell Capacitor to hide the splash screen once React has rendered.
// Using the low-level window.Capacitor bridge so we don't need to add
// @capacitor/splash-screen as an npm dep in the frontend package.
if (isNativePlatform()) {
  setupNativeShellBridge()
  capacitorPlugin('SplashScreen')?.hide?.()
}
