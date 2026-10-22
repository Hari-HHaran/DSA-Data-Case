import { defineConfig } from '@playwright/test'

// Requires the API (port 8000, freshly seeded) and the Vite dev server (port 5173) to be running.
export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5173',
    viewport: { width: 1440, height: 900 },
    launchOptions: process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {},
    screenshot: 'only-on-failure',
  },
  reporter: [['list']],
})
