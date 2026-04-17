import { test, expect } from '@playwright/test';
import { unlockSettingsIfNeeded } from '../helpers/settings';

test.describe('Settings page', () => {
  test.beforeEach(async ({ page, request }) => {
    const reqRes = await request.get('/api/ui/settings/requires-password');
    const { requires } = await reqRes.json();
    if (requires && !process.env.E2E_SETTINGS_PASSWORD) {
      test.skip(true, 'Set E2E_SETTINGS_PASSWORD for server with password');
    }
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    await unlockSettingsIfNeeded(page);
  });

  test('Settings form loads with all sections', async ({ page }) => {
    await expect(page.getByText(/Update Settings|Обновить настройки/i)).toBeVisible();
    await expect(page.getByText(/Общее|General/i)).toBeVisible();
    await expect(page.getByText(/Подключения|Connections/i)).toBeVisible();
  });

  test('Settings form has capture and feeder section', async ({ page }) => {
    await expect(page.getByText(/Захват и кормушка|Capture & Feeder/i)).toBeVisible();
  });

  test('Settings form has Save button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Сохранить|Save/i })).toBeVisible();
  });

  test('Settings form exposes moved controls in expanded sections', async ({ page }) => {
    await page.getByRole('button', { name: /Общее|General/i }).click();
    await expect(page.getByText(/MCP/i)).toBeVisible();

    await page.getByRole('button', { name: /Подключения|Connections/i }).click();
    await expect(page.getByLabel(/Home Assistant URL|URL Home Assistant/i)).toBeVisible();

    await page.getByRole('button', { name: /Захват и кормушка|Capture & Feeder/i }).click();
    await expect(page.getByLabel(/Resolution|Разрешение/i)).toBeVisible();

    await page.getByRole('button', { name: /Интеграции|Integrations/i }).click();
    await expect(
      page.getByLabel(/BirdNET installation URL|Ссылка на BirdNET/i),
    ).toBeVisible();
  });
});
