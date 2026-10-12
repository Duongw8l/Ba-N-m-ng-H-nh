import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Back-end mà Vite chuyển tiếp các yêu cầu /api tới (nên trình duyệt không cần CORS).
// Chạy ngoài Docker: localhost:8000. Trong Docker Compose: http://backend:8000 (đặt qua biến môi trường).
const apiTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
    },
    watch: {
      // Bind mount của Docker trên Windows không phát sự kiện thay đổi file, nên cần polling.
      usePolling: process.env.VITE_USE_POLLING === 'true',
    },
  },
})
