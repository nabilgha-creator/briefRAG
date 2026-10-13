import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// en développement, /api/... est redirigé vers l'API FastAPI (uvicorn backend.api.app:app, port 8000) :
// le navigateur ne voit qu'une seule origine, pas de problème de CORS
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.API_CIBLE ?? 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (chemin) => chemin.replace(/^\/api/, ''),
      },
    },
  },
})
