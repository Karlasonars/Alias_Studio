import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

// vitest rides the existing Vite pipeline (same plugins, same transforms),
// which is the whole argument for choosing it over jest: zero parallel
// build config to drift. jsdom stands in for the WebView; the Tauri
// runtime does not exist in tests — src/test/tauri.ts is that boundary.
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      globals: true, // gives testing-library its afterEach cleanup hook
      include: ['src/**/*.test.tsx']
    }
  })
)
