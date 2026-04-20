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
    await expect(page.getByLabel(/Frigate topic|Frigate топик/i)).toHaveCount(0);
    await expect(page.getByLabel(/BirdNET topic|BirdNET топик/i)).toHaveCount(0);

    await page.getByRole('button', { name: /Захват и кормушка|Capture & Feeder/i }).click();
    await expect(page.getByLabel(/Resolution|Разрешение/i)).toBeVisible();
    await expect(page.getByText(/OpenCV/i)).toBeVisible();
    await expect(page.getByText(/Frigate/i)).toBeVisible();
    await expect(page.getByText(/Датчик движения|Motion sensor/i)).toBeVisible();
    await expect(page.getByText(/Весы|Scales/i)).toBeVisible();
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

    await page.goto('/settings#processor-weights');
    await page.waitForLoadState('networkidle');
    await unlockSettingsIfNeeded(page);

    const spin = page.getByRole('spinbutton', {
      name: /Max recording seconds|Макс\. секунд записи|最大录音秒数/i,
    });
    if (!(await spin.isVisible())) {
      await page
        .getByRole('button', { name: /Processor & Detection|Процессор и детекция|处理器与检测/i })
        .click();
    }
    await expect(spin).toBeVisible({ timeout: 20000 });

    const beforeRaw = await spin.inputValue();
    const before = Number.parseInt(beforeRaw, 10);
    const base = Number.isFinite(before) ? before : 60;
    const bumped = String(base + 1);

    await spin.fill(bumped);
    await page.getByRole('button', { name: /Сохранить|Save|保存/i }).click();
    await expect(
      page.getByText(/Settings saved|Настройки сохранены|设置已保存/i).first(),
    ).toBeVisible({ timeout: 45000 });

    await spin.fill(String(base));
    await page.getByRole('button', { name: /Сохранить|Save|保存/i }).click();
    await expect(
      page.getByText(/Settings saved|Настройки сохранены|设置已保存/i).first(),
    ).toBeVisible({ timeout: 45000 });
  });
});
