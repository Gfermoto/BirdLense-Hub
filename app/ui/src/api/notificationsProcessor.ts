import axios from 'axios';
import { BASE_API_URL, csrfFetch } from './client';

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

export const sendTestNotification = async (): Promise<{
  success: boolean;
  message?: string;
}> => {
  try {
    const response = await axios.post(
      `${BASE_API_URL}/notify/test`,
      {},
      {
        withCredentials: true,
      },
    );
    return {
      success: true,
      message: response.data?.message || 'Sent',
    };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      success: false,
      message: err.response?.data?.error || 'Failed',
    };
  }
};

export const refreshTelegramProxy = async (): Promise<{
  success: boolean;
  message?: string;
}> => {
  try {
    const response = await axios.post(
      `${BASE_API_URL}/system/telegram-proxy/refresh`,
      {},
      {
        withCredentials: true,
      },
    );
    return {
      success: true,
      message: response.data?.message || 'Started',
    };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      success: false,
      message: err.response?.data?.error || 'Failed',
    };
  }
};

export const restartProcessor = async (): Promise<{
  success: boolean;
  message?: string;
}> => {
  try {
    const response = await axios.post(
      `${BASE_API_URL}/restart-processor`,
      {},
      {
        withCredentials: true,
      },
    );
    return { success: true, message: response.data?.message };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      success: false,
      message: err.response?.data?.error || 'Failed to restart',
    };
  }
};

