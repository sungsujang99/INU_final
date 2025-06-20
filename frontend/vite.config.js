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
      // Use environment variable for backend URL, with fallback to default
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://192.168.0.37:5001',
        changeOrigin: true,
      }
    }
  },
  publicDir: 'static'
})
