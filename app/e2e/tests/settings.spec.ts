import { test, expect } from '@playwright/test';
import { ensureSettingsUnlocked, unlockSettingsIfNeeded } from '../helpers/settings';

test.describe('Settings page', () => {
  const settingsHeading = /Station settings|Настройки станции|站点设置/i;

  test.beforeEach(async ({ page, request }) => {
    const reqRes = await request.get('/api/ui/settings/requires-password');
    const { requires } = await reqRes.json();
    if (requires && !process.env.E2E_SETTINGS_PASSWORD) {
      test.skip(true, 'Set E2E_SETTINGS_PASSWORD for server with password');
    }
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    // `request` fixture is isolated from `page`; unlock via page-bound API + UI.
    await ensureSettingsUnlocked(page.request);
    await page.goto('/settings');
    await page.waitForLoadState('domcontentloaded');
    await unlockSettingsIfNeeded(page);
  });

  test('Settings form loads with all sections', async ({ page }) => {
    await expect(page.getByRole('heading', { name: settingsHeading })).toBeVisible();
    await expect(page.getByRole('button', { name: /Общее|General/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Подключения|Connections/i })).toBeVisible();
  });

  test('Settings form has capture and feeder section', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Захват и кормушка|Capture & Feeder/i })).toBeVisible();
  });

  test('Settings form has Save button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Сохранить|Save/i })).toBeVisible();
  });

  test('Settings form exposes moved controls in expanded sections', async ({ page }) => {
    await page.getByRole('button', { name: /Общее|General/i }).click();
    await expect(page.getByRole('heading', { name: /^MCP$/i })).toBeVisible();

    await page.getByRole('button', { name: /Подключения|Connections/i }).click();
    await expect(page.getByLabel(/Home Assistant URL|URL Home Assistant/i)).toBeVisible();
    // Saved config may already expose Frigate/BirdNET topic fields — do not assert count 0 here.

    await page.getByRole('button', { name: /Захват и кормушка|Capture & Feeder/i }).click();
    await expect(page.getByLabel(/Resolution|Разрешение/i)).toBeVisible();
    await expect(page.getByRole('heading', { name: /^OpenCV$/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /^Frigate$/i })).toBeVisible();
    await expect(page.getByText(/Датчик движения|Motion sensor/i).first()).toBeVisible();
    await expect(page.getByText(/Весы|Scales/i).first()).toBeVisible();
    await page.getByRole('checkbox', { name: /Frigate \(MQTT|Frigate/i }).check();
    await expect(page.getByLabel(/Frigate topic|Frigate топик/i)).toBeVisible();

    await page.getByRole('button', { name: /Интеграции|Integrations/i }).click();
    await expect(
      page.getByLabel(/BirdNET installation URL|Ссылка на BirdNET/i),
    ).toBeVisible();
    await expect(page.getByLabel(/BirdNET topic|BirdNET топик/i)).toBeVisible();
  });
});

test.describe('Settings processor save', () => {
  test('round-trip max recording seconds (Processor)', async ({ page, request }) => {
    const reqRes = await request.get('/api/ui/settings/requires-password');
    const { requires } = await reqRes.json();
    if (requires && !process.env.E2E_SETTINGS_PASSWORD) {
      test.skip(true, 'Set E2E_SETTINGS_PASSWORD for server with password');
    }

    await page.goto('/settings');
    await page.waitForLoadState('domcontentloaded');
    await ensureSettingsUnlocked(page.request);
    await page.goto('/settings');
    await page.waitForLoadState('domcontentloaded');
    await unlockSettingsIfNeeded(page);
    await expect(page.getByRole('heading', { name: settingsHeading })).toBeVisible({ timeout: 30000 });

    const spin = page.getByRole('spinbutton', {
      name: /Max recording seconds|Макс\. секунд записи|最大录音秒数/i,
    });
    await page.getByRole('button', { name: /Processor & Detection|Процессор|处理器/i }).first().click();
    await expect(spin).toBeVisible({ timeout: 30000 });

    const beforeRaw = await spin.inputValue();
    const before = Number.parseInt(beforeRaw, 10);
    const base = Number.isFinite(before) ? before : 60;
    const bumped = String(base + 1);

    await spin.fill(bumped);
    await page.getByRole('button', { name: /Сохранить|Save|保存/i }).click();
    await expect(
      page.getByText(/Settings saved|Настройки сохранены|设置已保存/i).first(),
    ).toBeVisible({ timeout: 45000 });

    // Form may remount after save; ensure Processor accordion shows the field again.
    const procBtn = page.getByRole('button', { name: /Processor & Detection|Процессор|处理器/i }).first();
    let spinAfter = page.getByRole('spinbutton', {
      name: /Max recording seconds|Макс\. секунд записи|最大录音秒数/i,
    });
    for (let i = 0; i < 4; i++) {
      if (await spinAfter.isVisible().catch(() => false)) break;
      await procBtn.click();
      await spinAfter.waitFor({ state: 'visible', timeout: 5000 }).catch(() => undefined);
      spinAfter = page.getByRole('spinbutton', {
        name: /Max recording seconds|Макс\. секунд записи|最大录音秒数/i,
      });
    }
    await expect(spinAfter).toBeVisible({ timeout: 20000 });
    await spinAfter.fill(String(base));
    await page.getByRole('button', { name: /Сохранить|Save|保存/i }).click();
    await expect(
      page.getByText(/Settings saved|Настройки сохранены|设置已保存/i).first(),
    ).toBeVisible({ timeout: 45000 });
  });
});
