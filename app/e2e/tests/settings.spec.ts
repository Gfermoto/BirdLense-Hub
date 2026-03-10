import { test, expect } from '@playwright/test';

/** Unlock settings if password dialog is shown. */
async function unlockSettingsIfNeeded(page: any) {
  const dialog = page.getByRole('dialog');
  const pw = process.env.E2E_SETTINGS_PASSWORD || '';
  if (await dialog.isVisible().catch(() => false) && pw) {
    await dialog.locator('input[type="password"]').fill(pw);
    await dialog.getByRole('button', { name: /Enter|Войти/i }).click();
    await expect(dialog).not.toBeVisible({ timeout: 5000 });
  }
}

test.describe('Settings page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    await unlockSettingsIfNeeded(page);
  });

  test('Settings form loads with all sections', async ({ page }) => {
    await expect(page.getByText(/Update Settings|Обновить настройки/i)).toBeVisible();
    await expect(page.getByText(/1\. (Подключение|Connection)/)).toBeVisible();
  });

  test('Settings form has cameras section', async ({ page }) => {
    await expect(page.getByText(/2\. (Камеры|Cameras)/)).toBeVisible();
  });

  test('Settings form has Save button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Сохранить|Save/i })).toBeVisible();
  });

  test('Settings form shows feed relay section', async ({ page }) => {
    await expect(page.getByText(/4\. (Реле подкормки|Feed Relay)/)).toBeVisible();
  });
});
