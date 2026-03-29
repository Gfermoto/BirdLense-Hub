import { test, expect } from '@playwright/test';

/**
 * Critical operator paths for Migration (issue #118).
 * Filters render only when the calendar has species rows (non-empty DB).
 */
test.describe('Migration calendar', () => {
  test.describe.configure({ timeout: 45_000 });

  test('From year filter refetches table without error', async ({ page }) => {
    await page.goto('/migration-calendar', { waitUntil: 'networkidle' });
    const fromYear = page.getByLabel(/From year|С года/i);
    if (!(await fromYear.isVisible().catch(() => false))) {
      test.skip(true, 'No migration table (empty species) — filters not rendered');
    }
    const targetYear = new Date().getFullYear() - 1;
    await fromYear.click();
    await page.getByRole('option', { name: String(targetYear) }).click();
    await expect(page.getByText(/Error loading migration calendar|Ошибка загрузки/i)).toHaveCount(0);
    await expect(page.getByRole('table')).toBeVisible({ timeout: 25_000 });
    await expect(page.getByRole('columnheader', { name: 'Σ' })).toBeVisible();
  });

  test('From year can be reset to All years', async ({ page }) => {
    await page.goto('/migration-calendar', { waitUntil: 'networkidle' });
    const fromYear = page.getByLabel(/From year|С года/i);
    if (!(await fromYear.isVisible().catch(() => false))) {
      test.skip(true, 'No migration table (empty species) — filters not rendered');
    }
    const targetYear = new Date().getFullYear() - 2;
    await fromYear.click();
    await page.getByRole('option', { name: String(targetYear) }).click();
    await expect(page.getByRole('table')).toBeVisible({ timeout: 25_000 });

    await fromYear.click();
    await page.getByRole('option', { name: /All years|Все годы/i }).click();
    await expect(page.getByRole('table')).toBeVisible({ timeout: 25_000 });
    await expect(page.getByText(/Error loading migration calendar|Ошибка загрузки/i)).toHaveCount(0);
  });
});
