import { execSync } from 'node:child_process'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Build identity for the About screen (E16-F03). AGPL-3.0 obliges the
// running app to point at the source of the exact version it was built
// from — the commit, not whatever main holds today. Baked here so dev,
// build and vitest all get it from the same evaluation, and read only
// through src/buildInfo.ts. Empty strings mean "no git at build time"
// (a source-archive build) — a state the About screen handles honestly
// rather than a state that breaks the build.
function git(args: string): string {
  try {
    return execSync(`git ${args}`, { stdio: ['ignore', 'pipe', 'ignore'] })
      .toString()
      .trim()
  } catch {
    return ''
  }
}

// Tauri expects a fixed dev port and no auto-open.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  define: {
    __BUILD_COMMIT__: JSON.stringify(git('rev-parse HEAD')),
    __BUILD_TAG__: JSON.stringify(git('describe --tags --exact-match')),
    __BUILD_DIRTY__: JSON.stringify(git('status --porcelain') !== '')
  },
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
