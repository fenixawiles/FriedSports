import client from '../api/client'

const APNS_ENV = import.meta.env.VITE_APNS_ENV === 'sandbox' ? 'sandbox' : 'production'

/**
 * APNs push registration — native shell only.
 *
 * Called once per app session after the user is authenticated. Uses the
 * low-level window.Capacitor bridge (same pattern as SplashScreen/Keyboard)
 * so the frontend package needs no @capacitor npm deps. No-ops on web and
 * when permission is denied.
 */
export async function initPush() {
  if (window.Capacitor?.isNativePlatform?.() !== true) return
  const Push = window.Capacitor?.Plugins?.PushNotifications
  if (!Push) return
  if (window.__fsPushWired) return
  window.__fsPushWired = true

  try {
    let { receive } = await Push.checkPermissions()
    if (receive === 'prompt' || receive === 'prompt-with-rationale') {
      receive = (await Push.requestPermissions()).receive
    }
    if (receive !== 'granted') return

    // APNs token → backend. Fires on every register() call, including token
    // rotations, so the server row stays fresh.
    await Push.addListener('registration', ({ value }) => {
      client.post('/device-token', { token: value, environment: APNS_ENV }).catch(() => {})
    })
    await Push.addListener('registrationError', (err) => {
      console.warn('Push registration error', err)
    })
    // Tapping a notification deep-links to the payload's link_url.
    await Push.addListener('pushNotificationActionPerformed', (action) => {
      const link = action?.notification?.data?.link_url
      if (link && typeof link === 'string' && link.startsWith('/')) {
        window.location.assign(link)
      }
    })

    await Push.register()
  } catch (e) {
    console.warn('Push setup failed', e)
  }
}
