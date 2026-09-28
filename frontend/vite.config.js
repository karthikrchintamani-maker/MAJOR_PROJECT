import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      // REST API
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
      // MJPEG stream
      '/stream': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
      // WebSocket telemetry
      '/ws': {
        target: 'ws://localhost:5001',
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
