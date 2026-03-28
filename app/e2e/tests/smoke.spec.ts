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

  test('Overview page loads', async ({ page }) => {
    await page.goto('/', { waitUntil: 'networkidle' });
    await expect(page.getByText(/Overview|Обзор/i).first()).toBeVisible({ timeout: 15000 });
  });

  test('Timeline page loads', async ({ page }) => {
    await page.goto('/timeline', { waitUntil: 'networkidle' });
    await expect(page.getByText(/Timeline|Записи|Select/i).first()).toBeVisible({ timeout: 15000 });
  });

  test('Migration page shows region comparison block', async ({ page }) => {
    await page.goto('/migration-calendar', { waitUntil: 'networkidle' });
    await expect(page.getByText(/Region Comparison|Сравнение с регионом/i).first()).toBeVisible({
      timeout: 15000,
    });
  });

  test('Overview species chart click opens timeline with species filter', async ({ page }) => {
    await page.goto('/', { waitUntil: 'networkidle' });
    const chips = page.getByTestId('overview-species-legend-chip');
    const n = await chips.count();
    if (n === 0) {
      test.skip(true, 'Overview has no species distribution data in this environment');
    }
    await chips.first().click();
    await expect(page).toHaveURL(/\/timeline\?speciesId=\d+&date=/);
  });

  test('Unknowns legacy URL redirects to timeline review mode', async ({ page }) => {
    await page.goto('/unknowns', { waitUntil: 'networkidle' });
    await expect(page).toHaveURL(/\/timeline\?review=1/);
    await expect(page.getByText(/Review|На проверке|Unknown|Неизвестн/i).first()).toBeVisible({
      timeout: 15000,
    });
  });

  test('Species legacy URL redirects to migration page', async ({ page }) => {
    await page.goto('/species', { waitUntil: 'networkidle' });
    await expect(page).toHaveURL(/\/migration-calendar/);
    await expect(page.getByText(/Migration|Мигра/i).first()).toBeVisible({ timeout: 15000 });
  });

  test('System page loads', async ({ page }) => {
    await page.goto('/system', { waitUntil: 'networkidle' });
    await expect(page.getByText(/System|Система/i).first()).toBeVisible({ timeout: 15000 });
  });
});
