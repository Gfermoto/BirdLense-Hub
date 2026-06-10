import axios from 'axios';
import { describe, expect, it } from 'vitest';
import { ApiHttpError } from './client';
import { fetchReadiness, getApiErrorMessage, resolveImageUrl } from './api';
import { afterEach, vi } from 'vitest';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('resolveImageUrl', () => {
  it('keeps direct non-proxied absolute URLs', () => {
    expect(resolveImageUrl('https://example.com/bird.jpg')).toBe(
      'https://example.com/bird.jpg',
    );
  });

  it('proxies iNaturalist absolute URLs through the hub', () => {
    expect(
      resolveImageUrl('https://static.inaturalist.org/photos/1/original.jpg'),
    ).toBe(
      '/api/ui/species-image?url=https%3A%2F%2Fstatic.inaturalist.org%2Fphotos%2F1%2Foriginal.jpg',
    );
  });

  it('rejects unsafe data URLs', () => {
    expect(
      resolveImageUrl('data:text/html;base64,PHNjcmlwdD4='),
    ).toBeUndefined();
  });
});

describe('getApiErrorMessage', () => {
  it('reads message from ApiHttpError', () => {
    expect(getApiErrorMessage(new ApiHttpError(403, 'denied'), 'fallback')).toBe(
      'denied',
    );
  });

  it('prefers backend JSON error text from axios errors', () => {
    const err = {
      isAxiosError: true,
      response: { data: { error: 'backend said no' } },
      message: 'network fail',
    } as unknown;

    expect(getApiErrorMessage(err, 'fallback')).toBe('backend said no');
  });

  it('falls back to the provided message for unknown errors', () => {
    expect(getApiErrorMessage(new Error(''), 'fallback')).toBe('fallback');
  });

  it('handles real axios error instances too', () => {
    const err = new axios.AxiosError('timeout');
    expect(getApiErrorMessage(err, 'fallback')).toBe('timeout');
  });
});

describe('fetchReadiness', () => {
  it('returns degraded payloads even when backend uses HTTP 503', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue({
      status: 503,
      data: {
        status: 'degraded',
        ready: false,
        checked_at: '2026-04-14T00:00:00Z',
        checks: {
          database: { status: 'error', error: 'database_unavailable' },
          data_dir: {
            path: 'data/',
            exists: true,
            is_dir: true,
            writable: true,
            status: 'ok',
          },
          app_config_dir: {
            path: 'app_config/',
            exists: true,
            is_dir: true,
            writable: true,
            status: 'ok',
          },
        },
        components: {
          web: 'ok',
          processor: 'offline',
          video: 'not_configured',
          mqtt: 'not_configured',
          yolo: 'unknown',
        },
        security_gates: {
          runtime: 'development',
          items: [
            { id: 'strict_api_auth', status: 'warn' },
            { id: 'flask_secret_key', status: 'ok' },
            { id: 'processor_secret', status: 'ok' },
          ],
        },
      },
    });

    const payload = await fetchReadiness();

    expect(payload.ready).toBe(false);
    expect(payload.checks.database?.status).toBe('error');
  });
});
