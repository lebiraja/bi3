import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:6996',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:6996',
        ws: true,
        rewriteWsOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            console.log('WebSocket proxy error (ignored):', err.message);
          });
        },
      },
    },
  },
})
