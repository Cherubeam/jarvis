import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // dist/index.html references assets/* (see app.py: /static is mounted on the
  // assets dir). Setting base to / keeps relative refs simple in production.
  base: '/',
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8123',
      // ws: true is REQUIRED for the WebSocket upgrade to forward correctly.
      '/ws': { target: 'ws://127.0.0.1:8123', ws: true },
    },
  },
})
