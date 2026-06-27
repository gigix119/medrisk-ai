import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    env: {
      // No .env file exists in CI (it's gitignored, dev-only). Tests never make real
      // network requests (see src/test/server.ts's MSW handlers), so this placeholder
      // just satisfies the required-env-var check in src/config/environment.ts.
      VITE_API_BASE_URL: 'http://localhost:8000',
    },
  },
})
