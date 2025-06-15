// import react from "@vitejs/plugin-react";
// import { defineConfig } from "vite";

// // https://vite.dev/config/
// export default defineConfig({
//   plugins: [react()],
//   publicDir: "./static",
//   base: "./",
// });
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // 프런트에서 /api/** 로 부르면 → 백엔드 http://192.168.0.37:5001 로 전달
      '/api': {
        target: 'http://192.168.0.37:5001',
        changeOrigin: true,
      }
    }
  },
  publicDir: 'static'
})
