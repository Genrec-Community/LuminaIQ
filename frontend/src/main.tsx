import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import Analytics from "@vercel/analytics"
import { injectSpeedInsights } from "@vercel/speed-insights"

// Initialize Vercel analytics and speed insights
Analytics.inject()
injectSpeedInsights()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
