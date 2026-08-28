import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Tauri expects a fixed dev port and no auto-open.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1430,
    strictPort: true,
    fs: {
      // PrivacyNotice imports PRIVACY.md?raw from the repository root —
      // one file, versioned with the code, no copy to drift. The dev
      // server's default allow-list stops at app/, so widen it one level
      // or the import 403s in `tauri dev` while building fine.
      allow: [resolve(__dirname, '..')]
    },
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
