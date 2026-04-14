import { test, expect } from '@playwright/test';

async function gotoReady(page: import('@playwright/test').Page, path = '/') {
  await page.goto(path, { waitUntil: 'domcontentloaded' });
  await page.waitForResponse((response) => {
    return (
      response.url().includes('/api/ui/health') &&
      response.request().method() === 'GET' &&
      response.ok()
    );
  }, { timeout: 15000 }).catch(() => undefined);
}

test.describe('Smoke tests', () => {
  test('homepage loads and shows main navigation', async ({ page }) => {
    await gotoReady(page, '/');
    await expect(page).toHaveTitle(/Bird/i, { timeout: 15000 });
    await expect(page.locator('a[href="/timeline"]').first()).toBeVisible({ timeout: 15000 });
  });

  test('navigation links work', async ({ page }) => {
    await gotoReady(page, '/');
    await page.locator('a[href="/timeline"]').first().click();
    await expect(page).toHaveURL(/\/timeline/);

    await page.goto('/settings');
    await expect(page).toHaveURL(/\/settings/);

    await page.goto('/live');
    await expect(page).toHaveURL(/\/live/);
  });

  test('Settings page loads', async ({ page }) => {
    await gotoReady(page, '/settings');
    await expect(page.getByText(/Update Settings|Обновить настройки/i)).toBeVisible({ timeout: 15000 });
  });

  test('Live page loads', async ({ page }) => {
    await gotoReady(page, '/live');
    await expect(page.getByRole('heading', { name: /Live/i })).toBeVisible({ timeout: 15000 });
  });

  test('Overview page loads', async ({ page }) => {
    await gotoReady(page, '/');
    await expect(page.getByText(/Overview|Обзор/i).first()).toBeVisible({ timeout: 15000 });
  });

  test('Timeline page loads', async ({ page }) => {
    await gotoReady(page, '/timeline');
    await expect(page.getByText(/Timeline|Записи|时间线|Select/i).first()).toBeVisible({ timeout: 15000 });
  });

  test('Migration page shows region comparison block', async ({ page }) => {
    await gotoReady(page, '/migration-calendar');
    await expect(page.getByText(/Region Comparison|Сравнение с регионом|区域比较/i).first()).toBeVisible({
      timeout: 15000,
    });
  });

  test('Overview species chart: legend opens timeline or shows empty state', async ({ page }) => {
    await gotoReady(page, '/');
    const topHeading = page.getByRole('heading', { name: /Top Species Distribution|Топ видов/i });
    await expect(topHeading).toBeVisible({ timeout: 20000 });

    const chips = page.getByTestId('overview-species-legend-chip');
    if ((await chips.count()) > 0) {
      await chips.first().click();
      await expect(page).toHaveURL(/\/timeline\?speciesId=\d+&date=/);
      return;
    }

    const chartEmpty = page.getByTestId('overview-species-chart-empty');
    if (await chartEmpty.isVisible()) {
      await expect(chartEmpty).toBeVisible();
      return;
    }

    // Несколько блоков Overview делят один и тот же текст «no data» — привязываем к секции «Топ видов».
    const panel = topHeading.locator('..');
    await expect(
      panel.getByText(/No data for selected day|Нет данных за выбранный день/i),
    ).toBeVisible({ timeout: 15000 });
  });

  test('Unknowns legacy URL redirects to timeline review mode', async ({ page }) => {
    await gotoReady(page, '/unknowns');
    await expect(page).toHaveURL(/\/timeline\?review=1/);
    await expect(page.getByText(/Review|На проверке|Unknown|Неизвестн/i).first()).toBeVisible({
      timeout: 15000,
    });
  });

  test('Species legacy URL redirects to migration page', async ({ page }) => {
    await gotoReady(page, '/species');
    await expect(page).toHaveURL(/\/migration-calendar/);
    await expect(page.getByText(/Migration|Мигра/i).first()).toBeVisible({ timeout: 15000 });
  });

  test('System page loads', async ({ page }) => {
    await gotoReady(page, '/system');
    await expect(page.getByText(/System|Система|系统/i).first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Ready|Готово|已就绪|Needs attention|Требует внимания/i).first()).toBeVisible({
      timeout: 15000,
    });
  });
});
