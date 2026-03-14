import { expect } from '@playwright/test';

/** Verify settings password via API. Call before settings API tests. */
export async function ensureSettingsUnlocked(request: any) {
  const reqRes = await request.get('/api/ui/settings/requires-password');
  const { requires } = await reqRes.json();
  if (!requires) return;
  const pw = process.env.E2E_SETTINGS_PASSWORD || '';
  if (!pw) return;
  const verifyRes = await request.post('/api/ui/settings/verify-password', {
    data: { password: pw },
  });
  expect(verifyRes.ok(), 'verify-password should succeed').toBeTruthy();
}

/** Unlock settings dialog if shown (UI). Call in beforeEach for settings page tests. */
export async function unlockSettingsIfNeeded(page: any) {
  const dialog = page.getByRole('dialog');
  const pw = process.env.E2E_SETTINGS_PASSWORD || '';
  const visible = await dialog.isVisible().catch(() => false);
  if (visible && pw) {
    await dialog.locator('input[type="password"]').fill(pw);
    await dialog.getByRole('button', { name: /Enter|Войти|Submit|Отправить/i }).click();
    await expect(dialog).not.toBeVisible({ timeout: 10000 });
  }
}
