import { test, expect } from '@playwright/test';

test.describe('Settings page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
  });

  test('Settings form loads with all sections', async ({ page }) => {
    await expect(page.getByText('Update Settings')).toBeVisible();
    await expect(page.getByText('1. Подключение')).toBeVisible();
  });

  test('Settings form has cameras section', async ({ page }) => {
    await expect(page.getByText('2. Камеры')).toBeVisible();
  });

  test('Settings form has Save button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Сохранить|Save/i })).toBeVisible();
  });

  test('Settings form shows feed relay section', async ({ page }) => {
    await expect(page.getByText('4. Реле подкормки')).toBeVisible();
  });
});
