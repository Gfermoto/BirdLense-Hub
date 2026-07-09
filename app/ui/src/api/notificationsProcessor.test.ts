import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.fn();

vi.mock('./client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./client')>();
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => apiFetchMock(...args),
    BASE_API_URL: '/api/ui',
  };
});

describe('notificationsProcessor API', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('sendTestNotification POST /notify/test', async () => {
    apiFetchMock.mockResolvedValue({ message: 'Sent' });
    const { sendTestNotification } = await import('./notificationsProcessor');
    const result = await sendTestNotification();
    expect(result.success).toBe(true);
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/notify/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
  });

  it('restartProcessor POST /restart-processor', async () => {
    apiFetchMock.mockResolvedValue({ message: 'Restarting' });
    const { restartProcessor } = await import('./notificationsProcessor');
    const result = await restartProcessor();
    expect(result.success).toBe(true);
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/restart-processor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
  });
});
