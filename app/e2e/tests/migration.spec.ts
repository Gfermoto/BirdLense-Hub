import { test, expect } from '@playwright/test';

/**
 * Critical operator paths for Migration (issue #118).
 * Filters render only when the calendar has species rows (non-empty DB).
 */
test.describe('Migration calendar', () => {
  test.describe.configure({ timeout: 45_000 });

  async function expectMigrationTableOrEmptyState(page: import('@playwright/test').Page) {
    // При смене фильтра React Query снова ставит isLoading — целая страница в PageLoadingState
    // без таблицы и без пустого текста; нельзя один раз проверять table.isVisible().
    const migrationTable = page.getByRole('table', {
      name: /Species by month|Виды по месяцам|按月/i,
    });
    const emptyState = page.getByText(
      /No observed species for the selected period|Нет наблюдаемых видов|所选期间没有观察到的物种/i,
    );
    const loadError = page.getByText(
      /Could not load the seasonality|Не удалось загрузить таблицу сезонности|无法加载季节性/i,
    );

    await expect(loadError).toHaveCount(0);
    const settled = migrationTable.or(emptyState);
    await expect(settled).toBeVisible({ timeout: 35_000 });
    if (await migrationTable.isVisible().catch(() => false)) {
      await expect(page.getByRole('columnheader', { name: 'Σ' })).toBeVisible();
    }
  }

  test('From year filter refetches table without error', async ({ page }) => {
    await page.goto('/migration-calendar', { waitUntil: 'networkidle' });
    const fromYear = page.getByLabel(/From year|С года/i);
    if (!(await fromYear.isVisible().catch(() => false))) {
      test.skip(true, 'No migration table (empty species) — filters not rendered');
    }
    const targetYear = new Date().getFullYear() - 1;
    await fromYear.click();
    await page.getByRole('option', { name: String(targetYear) }).click();
    await expectMigrationTableOrEmptyState(page);
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
    await expectMigrationTableOrEmptyState(page);

    await fromYear.click();
    await page.getByRole('option', { name: /All years|Все годы/i }).click();
    await expectMigrationTableOrEmptyState(page);
  });
});
