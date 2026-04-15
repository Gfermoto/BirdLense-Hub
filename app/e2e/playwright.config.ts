import { defineConfig, devices } from '@playwright/test';

/**
 * E2E tests for BirdLense Hub.
 * Run against a running instance (docker compose up) or the public hub.
 *
 * BASE_URL / E2E_BASE_URL переопределяют значение по умолчанию (локально: http://localhost:8085).
 */
const BASE_URL =
  process.env.BASE_URL ||
  process.env.E2E_BASE_URL ||
  'https://birdlense.eyera.info';

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
  // gotoReady ждёт до 20s ответ API; пер-тестовый лимит должен быть с запасом.
  timeout: process.env.CI ? 45000 : 15000,
  expect: { timeout: 5000 },
});
