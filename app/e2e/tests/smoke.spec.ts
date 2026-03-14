import { test, expect } from '@playwright/test';

test.describe('Smoke tests', () => {
  test('homepage loads and shows main navigation', async ({ page }) => {
    await page.goto('/', { waitUntil: 'networkidle' });
    await expect(page).toHaveTitle(/Bird/i, { timeout: 15000 });
    await expect(page.getByRole('link', { name: 'Timeline' }).first()).toBeVisible({ timeout: 15000 });
  });

  test('navigation links work', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.getByRole('link', { name: /Timeline|Записи/i }).first().click();
    await expect(page).toHaveURL(/\/timeline/);

    await page.goto('/settings');
    await expect(page).toHaveURL(/\/settings/);

    await page.goto('/live');
    await expect(page).toHaveURL(/\/live/);
  });

  test('Settings page loads', async ({ page }) => {
    await page.goto('/settings', { waitUntil: 'networkidle' });
    await expect(page.getByText(/Update Settings|Обновить настройки/i)).toBeVisible({ timeout: 15000 });
  });

  test('Live page loads', async ({ page }) => {
    await page.goto('/live', { waitUntil: 'networkidle' });
    await expect(page.getByRole('heading', { name: /Live/i })).toBeVisible({ timeout: 15000 });
  });
});
