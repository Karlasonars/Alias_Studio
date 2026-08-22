import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Tauri expects a fixed dev port and no auto-open.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1430,
    strictPort: true,
    watch: {
      // cargo writes into src-tauri/target mid-build; Vite's watcher racing
      // those file locks crashes the dev server on Windows (EBUSY).
      ignored: ['**/src-tauri/**']
    }
  },
  build: {
    target: 'es2022'
  }
})
