import { BASE_API_URL, ApiHttpError, apiFetch, csrfFetch } from './client';

/** Web Push: get VAPID public key for subscription. */
export const fetchVapidPublicKey = async (): Promise<string> => {
  const res = await fetch(`${BASE_API_URL}/push/vapid-public`, {
    credentials: 'include',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || 'Web Push not available');
  }
  const data = await res.json();
  return data.vapid_public_key;
};

/** Web Push: register subscription with server. */
export const subscribePush = async (
  subscription: globalThis.PushSubscription,
): Promise<void> => {
  const sub = subscription.toJSON();
  const keys = sub.keys;
  if (!keys) throw new Error('Invalid subscription');
  const res = await csrfFetch(`${BASE_API_URL}/push/subscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      subscription: {
        endpoint: sub.endpoint,
        keys: { p256dh: keys.p256dh, auth: keys.auth },
      },
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || 'Subscribe failed');
  }
};

function processorActionErrorMessage(e: unknown, fallback: string): string {
  if (e instanceof ApiHttpError) {
    const err = (e.data as { error?: string } | null)?.error;
    if (typeof err === 'string' && err.trim()) {
      return err;
    }
    if (e.message.trim()) {
      return e.message;
    }
  }
  return fallback;
}

export const sendTestNotification = async (): Promise<{
  success: boolean;
  message?: string;
}> => {
  try {
    const data = await apiFetch<{ message?: string }>(
      `${BASE_API_URL}/notify/test`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      },
    );
    return {
      success: true,
      message: data?.message || 'Sent',
    };
  } catch (e: unknown) {
    return {
      success: false,
      message: processorActionErrorMessage(e, 'Failed'),
    };
  }
};

export const refreshTelegramProxy = async (): Promise<{
  success: boolean;
  message?: string;
}> => {
  try {
    const data = await apiFetch<{ message?: string }>(
      `${BASE_API_URL}/system/telegram-proxy/refresh`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      },
    );
    return {
      success: true,
      message: data?.message || 'Started',
    };
  } catch (e: unknown) {
    return {
      success: false,
      message: processorActionErrorMessage(e, 'Failed'),
    };
  }
};

export const restartProcessor = async (): Promise<{
  success: boolean;
  message?: string;
}> => {
  try {
    const data = await apiFetch<{ message?: string }>(
      `${BASE_API_URL}/restart-processor`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      },
    );
    return { success: true, message: data?.message };
  } catch (e: unknown) {
    return {
      success: false,
      message: processorActionErrorMessage(e, 'Failed to restart'),
    };
  }
};
