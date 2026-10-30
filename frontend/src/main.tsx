import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/atkinson-hyperlegible-next/wght.css'
import '@fontsource-variable/newsreader/opsz.css'
import '@fontsource-variable/newsreader/opsz-italic.css'
// Optional faces from Settings (files download only when chosen)
import '@fontsource-variable/outfit/wght.css'
import '@fontsource-variable/plus-jakarta-sans/wght.css'
import './index.css'
import './themes.css'
import './lumina.css'
import App from './App.jsx'
import { warmUp } from './api'
import Analytics from "@vercel/analytics"
import { injectSpeedInsights } from "@vercel/speed-insights"

// After a redeploy, a tab opened earlier can't load the new code chunks
// ("Failed to fetch dynamically imported module"): reload once to get the new
// version instead of hanging (at most once a minute, so it can't loop).
window.addEventListener('vite:preloadError', (event) => {
  try {
    const last = Number(sessionStorage.getItem('lumina_reloaded_at') || 0)
    if (Date.now() - last < 60_000) return
    sessionStorage.setItem('lumina_reloaded_at', String(Date.now()))
  } catch { /* storage unavailable: still reload */ }
  event.preventDefault()
  window.location.reload()
})

// Initialize Vercel analytics and speed insights
Analytics.inject()
injectSpeedInsights()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Start waking the backend now, while the app itself loads
warmUp()
