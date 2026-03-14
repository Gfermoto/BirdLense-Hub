import { test, expect } from '@playwright/test';

/** Verify settings password if required. Call before settings tests. */
async function ensureSettingsUnlocked(request: any) {
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

test.describe('API endpoints @api', () => {
  test('GET /api/ui/health returns ok', async ({ request }) => {
    const res = await request.get('/api/ui/health');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty('status', 'ok');
  });

  test('GET /api/ui/status returns component status', async ({ request }) => {
    const res = await request.get('/api/ui/status');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty('web', 'ok');
    expect(body).toHaveProperty('processor');
    expect(['ok', 'offline']).toContain(body.processor);
    expect(body).toHaveProperty('video');
    expect(body).toHaveProperty('mqtt');
    expect(body).toHaveProperty('esphome');
    expect(body).toHaveProperty('yolo');
    // mqtt/esphome: ok | error | not_configured | not_used
    const validMqtt = ['ok', 'error', 'not_configured', 'not_used'];
    const validEsp = ['ok', 'error', 'not_configured', 'not_used'];
    expect(validMqtt).toContain(body.mqtt);
    expect(validEsp).toContain(body.esphome);
  });

  test('GET /api/ui/settings returns settings', async ({ request }) => {
    const reqRes = await request.get('/api/ui/settings/requires-password');
    const { requires } = await reqRes.json();
    if (requires && !process.env.E2E_SETTINGS_PASSWORD) {
      test.skip(true, 'Settings require password — set E2E_SETTINGS_PASSWORD for full test');
    }
    await ensureSettingsUnlocked(request);
    const res = await request.get('/api/ui/settings');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toBeDefined();
    expect(typeof body).toBe('object');
  });

  test('GET /api/ui/cameras returns cameras list', async ({ request }) => {
    const res = await request.get('/api/ui/cameras');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty('cameras');
    expect(Array.isArray(body.cameras)).toBeTruthy();
  });

  test('GET /api/ui/weather returns weather or empty', async ({ request }) => {
    const res = await request.get('/api/ui/weather');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toBeDefined();
  });

  test('POST /api/ui/feed/dispense returns 200 or 500 (not 404)', async ({ request }) => {
    const res = await request.post('/api/ui/feed/dispense');
    expect(res.status()).toBeLessThan(600);
    expect(res.status()).not.toBe(404);
    const body = await res.json().catch(() => ({}));
    if (res.ok()) {
      expect(body).toHaveProperty('message');
    } else {
      expect(body).toHaveProperty('error');
    }
  });
});
