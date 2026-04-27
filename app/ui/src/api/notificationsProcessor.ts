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

export type ProcessorWeightsSlotStatus = {
  path: string | null;
  uses_custom_dir: boolean;
  default_path: string;
  bytes: number | null;
  mtime_unix: number | null;
  /** First 16 hex chars of SHA256 over file bytes (matches CLI validate report). */
  fingerprint_sha256_16?: string | null;
};

export type ProcessorWeightsAllowlistStatus = {
  path: string | null;
  uses_custom_dir: boolean;
  bytes: number | null;
  mtime_unix: number | null;
  fingerprint_sha256_16?: string | null;
};

export type ProcessorWeightsStatusResponse = {
  custom_weights_dir: string;
  binary: ProcessorWeightsSlotStatus;
  classifier: ProcessorWeightsSlotStatus;
  allowlist: ProcessorWeightsAllowlistStatus;
};

export const fetchProcessorWeightsStatus =
  async (): Promise<ProcessorWeightsStatusResponse> => {
    const response = await axios.get(
      `${BASE_API_URL}/system/processor-weights/status`,
      {
        withCredentials: true,
      },
    );
    return response.data as ProcessorWeightsStatusResponse;
  };

const _PROCESSOR_WEIGHTS_UPLOAD_TIMEOUT_MS = 3_600_000; // 1 h

export const uploadProcessorWeight = async (
  role: 'binary' | 'classifier' | 'class_names',
  file: File,
  options?: { acknowledgeClassifierOnly?: boolean },
): Promise<{
  ok: boolean;
  error?: string;
  status?: ProcessorWeightsStatusResponse;
}> => {
  const form = new FormData();
  form.append('file', file);
  const params: Record<string, string> = { role };
  if (options?.acknowledgeClassifierOnly) {
    params.acknowledge_classifier_only = '1';
  }
  try {
    const response = await axios.post(
      `${BASE_API_URL}/system/processor-weights/upload`,
      form,
      {
        withCredentials: true,
        params,
        timeout: _PROCESSOR_WEIGHTS_UPLOAD_TIMEOUT_MS,
        headers: { 'Content-Type': 'multipart/form-data' },
      },
    );
    return { ok: true, status: response.data?.status };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      ok: false,
      error: err.response?.data?.error || 'upload_failed',
    };
  }
};

export const resetProcessorWeights = async (
  roles: Array<'binary' | 'classifier' | 'class_names' | 'all'>,
): Promise<{
  ok: boolean;
  error?: string;
  status?: ProcessorWeightsStatusResponse;
}> => {
  try {
    const response = await axios.post(
      `${BASE_API_URL}/system/processor-weights/reset`,
      { roles },
      { withCredentials: true },
    );
    return { ok: true, status: response.data?.status };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      ok: false,
      error: err.response?.data?.error || 'reset_failed',
    };
  }
};
