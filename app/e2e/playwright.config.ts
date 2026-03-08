import { defineConfig, devices } from '@playwright/test';

/**
 * E2E tests for BirdLense.
 * Run against a running instance (e.g. docker compose up).
 *
 * BASE_URL: http://localhost:8080 (default) or http://192.168.1.11:8085
 */
const BASE_URL = process.env.BASE_URL || process.env.E2E_BASE_URL || 'http://localhost:80';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    viewport: { width: 1280, height: 720 },
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  timeout: 15000,
  expect: { timeout: 5000 },
});
