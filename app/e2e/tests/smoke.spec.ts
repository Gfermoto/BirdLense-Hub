import { test, expect } from '@playwright/test';

async function gotoReady(page: import('@playwright/test').Page, path = '/') {
  await page.goto(path, { waitUntil: 'domcontentloaded' });
  // UI не дергает /api/ui/health на каждой странице (readiness — отдельно). Ждём любой успешный GET к API хаба.
  await page
    .waitForResponse(
      (response) => {
        const url = response.url();
        return (
          url.includes('/api/ui/') &&
          response.request().method() === 'GET' &&
          response.ok()
        );
      },
      { timeout: 20000 },
    )
    .catch(() => undefined);
}

/** Страницы с React Query часто показывают MUI progressbar в main после первого API-ответа. */
async function waitMainSpinnerGone(page: import('@playwright/test').Page) {
  const bar = page.locator('main [role="progressbar"]');
  await expect(bar).toHaveCount(0, { timeout: 60000 });
}

async function isSettingsProtected(page: import('@playwright/test').Page) {
  return page
    .getByRole('dialog', { name: /Password for settings access/i })
    .isVisible()
    .catch(() => false);
}

async function detectViewMode(
  page: import('@playwright/test').Page,
  unlockedHeading: RegExp,
) {
  const deadline = Date.now() + 15000;
  const protectedHeading = page
    .getByRole('heading')
    .filter({ hasText: /Station settings|Service|Настройки станции|Сервис/i })
    .first();
  const unlocked = page.getByRole('heading', { name: unlockedHeading }).first();
  while (Date.now() < deadline) {
    if (await isSettingsProtected(page)) return 'protected' as const;
    if (await unlocked.isVisible().catch(() => false)) return 'unlocked' as const;
    if (await protectedHeading.isVisible().catch(() => false)) return 'protected' as const;
    await page.waitForTimeout(300);
  }
  return 'unknown' as const;
}

test.describe('Smoke tests', () => {
  test('homepage loads and shows main navigation', async ({ page }) => {
    await gotoReady(page, '/');
    await expect(page).toHaveTitle(/Bird/i, { timeout: 15000 });
    await expect(page.getByTestId('nav-pill-timeline')).toBeVisible({ timeout: 15000 });
  });

  test('navigation links work', async ({ page }) => {
    await gotoReady(page, '/');
    await page.getByTestId('nav-pill-timeline').click();
    await expect(page).toHaveURL(/\/timeline/);

    await page.goto('/settings');
    await expect(page).toHaveURL(/\/settings/);

    await page.goto('/live');
    await expect(page).toHaveURL(/\/live/);
  });

  test('Settings page loads', async ({ page }) => {
    await gotoReady(page, '/settings');
    const mode = await detectViewMode(
      page,
      /Station settings|Настройки станции|站点设置/i,
    );
    if (mode === 'protected') {
      await expect(
        page.getByText(/This area is for station setup or service maintenance/i),
      ).toBeVisible({ timeout: 15000 });
      await expect(
        page.getByRole('dialog', { name: /Password for settings access/i }),
      ).toBeVisible({ timeout: 15000 });
      await expect(
        page
          .getByRole('dialog', { name: /Password for settings access/i })
          .locator('input[type="password"]')
          .first(),
      ).toBeVisible({ timeout: 15000 });
      return;
    }
    expect(mode).toBe('unlocked');
    await expect(
      page.getByRole('heading', {
        name: /Station settings|Настройки станции|站点设置/i,
      }),
    ).toBeVisible({ timeout: 15000 });
  });

  test('Live page loads', async ({ page }) => {
    await gotoReady(page, '/live');
    await expect(page.getByRole('heading', { name: /Live|直播/i })).toBeVisible({ timeout: 15000 });
  });

  test('Overview page loads', async ({ page }) => {
    await gotoReady(page, '/');
    await waitMainSpinnerGone(page);
    // nav.dashboard: EN «Dashboard», RU «Панель», ZH «仪表板» (не «Overview»).
    await expect(page.getByText(/Dashboard|Панель|仪表板|Overview|Обзор/i).first()).toBeVisible({
      timeout: 15000,
    });
  });

  test('Timeline page loads', async ({ page }) => {
    await gotoReady(page, '/timeline');
    await expect(page.getByText(/Timeline|Записи|时间线|时间轴|选择|Select/i).first()).toBeVisible({
      timeout: 15000,
    });
  });

  test('Migration page shows region comparison block', async ({ page }) => {
    await gotoReady(page, '/migration-calendar');
    await waitMainSpinnerGone(page);
    await expect(
      page.getByText(/Region Comparison|Сравнение с регионом|区域比较|地区比较/i).first(),
    ).toBeVisible({
      timeout: 15000,
    });
  });

  test('Overview species chart: legend opens timeline or shows empty state', async ({ page }) => {
    await gotoReady(page, '/');
    await waitMainSpinnerGone(page);
    const topHeading = page.getByRole('heading', {
      name: /Top Species Distribution|Топ видов|主要物种分布/i,
    });
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
      panel.getByText(/No data for selected day|Нет данных за выбранный день|所选日期没有数据/i),
    ).toBeVisible({ timeout: 15000 });
  });

  test('Unknowns legacy URL lands on timeline', async ({ page }) => {
    await gotoReady(page, '/unknowns');
    // /unknowns → /timeline?review=1. На хабе без пароля canEdit=true — review=1 остаётся (это ок).
    // С паролем гость получает replace без review=1 (см. TimelinePage useEffect).
    await expect(page).toHaveURL(/\/timeline/);
    await expect(page.getByText(/Timeline|Записи|时间线|时间轴|选择|Select/i).first()).toBeVisible({
      timeout: 15000,
    });
  });

  test('Species catalog URL shows migration calendar', async ({ page }) => {
    await gotoReady(page, '/species');
    await waitMainSpinnerGone(page);
    await expect(page).toHaveURL(/\/species/);
    await expect(
      page
        .getByText(
          /Monthly grid|Таблица по месяцам|按月统计|By years|По годам|按年份|Species scope|Каталог видов|品种范围/i,
        )
        .first(),
    ).toBeVisible({ timeout: 15000 });
  });

  test('System page loads', async ({ page }) => {
    await gotoReady(page, '/system');
    const mode = await detectViewMode(page, /System|Система|系统/i);
    if (mode === 'protected') {
      await expect(
        page.getByText(/This area is for station setup or service maintenance/i),
      ).toBeVisible({ timeout: 15000 });
      await expect(
        page.getByRole('dialog', { name: /Password for settings access/i }),
      ).toBeVisible({ timeout: 15000 });
      await expect(
        page
          .getByRole('dialog', { name: /Password for settings access/i })
          .locator('input[type="password"]')
          .first(),
      ).toBeVisible({ timeout: 15000 });
      return;
    }
    expect(mode).toBe('unlocked');
    await expect(page.getByText(/System|Система|系统/i).first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Ready|Готово|已就绪|Needs attention|Требует внимания/i).first()).toBeVisible({
      timeout: 15000,
    });
  });
});
