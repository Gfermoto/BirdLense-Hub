import { test, expect } from '@playwright/test';

test.describe('Settings page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
  });

  test('Settings form loads with all sections', async ({ page }) => {
    await expect(page.getByText('Update Settings')).toBeVisible();
    await expect(page.getByText('General')).toBeVisible();
  });

  test('Settings form has Video & MQTT section', async ({ page }) => {
    await expect(page.getByText('Video & MQTT')).toBeVisible();
  });

  test('Settings form has Save button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Save|Update/i })).toBeVisible();
  });

  test('Settings form shows feed source options', async ({ page }) => {
    await expect(page.getByText('Weather & Feed')).toBeVisible();
  });
});
