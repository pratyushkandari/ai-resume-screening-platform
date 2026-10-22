// Vite configuration for the React single-page app.
//   npm run dev      -> dev server on http://localhost:5173 with hot reload
//   npm run build    -> optimised static files in dist/ (served by Nginx in Docker)
//   npm run preview  -> serve dist/ locally on http://localhost:4173
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

export default defineConfig({
  root: __dirname,
  plugins: [react()],
  server: {
    // The app calls same-origin /api/...; in development forward those requests to
    // the FastAPI server so no CORS setup is needed (Nginx does the same in Docker).
    // `vite preview` reuses this proxy.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
