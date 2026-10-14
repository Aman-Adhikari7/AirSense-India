import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/map': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/places': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/about': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/agent': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/auth': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/compare': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/forecast': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/scrape': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
