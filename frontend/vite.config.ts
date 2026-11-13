import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Forward /api calls to the FastAPI backend. The browser then sees a single
    // origin, which avoids CORS problems and lets one HTTPS tunnel cover the whole app.
    proxy: {
      '/api': 'http://localhost:8000',
    },
    // Allow opening the dev server through an HTTPS tunnel (phones need HTTPS for the mic).
    allowedHosts: ['.trycloudflare.com', '.ngrok-free.app'],
  },
})
