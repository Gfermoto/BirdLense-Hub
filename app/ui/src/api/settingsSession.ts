import axios from 'axios';
import type { Settings } from '../types';
import { BASE_API_URL } from './client';

export type RequiresPasswordResult = {
  requires: boolean;
  has_contributor_tier?: boolean;
};

export const fetchSettingsRequiresPassword =
  async (): Promise<RequiresPasswordResult> => {
    const response = await axios.get(
      `${BASE_API_URL}/settings/requires-password`,
      {
        withCredentials: true,
      },
    );
    return {
      requires: response.data?.requires === true,
      has_contributor_tier: response.data?.has_contributor_tier === true,
    };
  };

export type CheckAccessResult =
  | { unlocked: true; role?: 'admin' | 'contributor' }
  | { unlocked: false; error?: 'network' };

export const checkSettingsAccess = async (): Promise<CheckAccessResult> => {
  try {
    const response = await axios.get(`${BASE_API_URL}/settings/check-access`, {
      withCredentials: true,
    });
    if (response.data?.unlocked === true) {
      return { unlocked: true, role: response.data?.role || 'admin' };
    }
    return { unlocked: false };
  } catch (e: unknown) {
    if (axios.isAxiosError(e) && e.response?.status === 403) {
      return { unlocked: false };
    }
    return { unlocked: false, error: 'network' };
  }
};

export type VerifyPasswordResult =
  | { ok: true; role?: 'admin' | 'contributor' }
  | {
      ok: false;
      error: 'wrong_password' | 'csrf_or_auth' | 'server_error';
    };

export const verifySettingsPassword = async (
  password: string,
): Promise<VerifyPasswordResult> => {
  try {
    const response = await axios.post(
      `${BASE_API_URL}/settings/verify-password`,
      { password },
      { withCredentials: true },
    );
    if (response.data?.ok === true) {
      return { ok: true, role: response.data?.role || 'admin' };
    }
    return { ok: false, error: 'wrong_password' };
  } catch (e: unknown) {
    if (!axios.isAxiosError(e) || e.response == null) {
      return { ok: false, error: 'server_error' };
    }
    const status = e.response.status;
    const msg = (e.response.data as { error?: string })?.error;
    if (status === 401) {
      return { ok: false, error: 'wrong_password' };
    }
    if (
      status === 403 &&
      (msg === 'CSRF token required' || msg === 'Authentication required')
    ) {
      return { ok: false, error: 'csrf_or_auth' };
    }
    return { ok: false, error: 'server_error' };
  }
};

export const logoutSettingsSession = async (): Promise<void> => {
  await axios.post(
    `${BASE_API_URL}/settings/logout`,
    {},
    { withCredentials: true },
  );
};

export const fetchSettings = async () => {
  const response = await axios.get(`${BASE_API_URL}/settings`, {
    withCredentials: true,
  });
  return response.data;
};

export type EbirdMappingSuggestion = {
  ebird_name: string;
  birdlense_name: string | null;
  kind: 'case_variant' | 'fuzzy' | 'unmatched';
  score: number | null;
};

export type EbirdMappingSuggestionsResponse = {
  region_code: string;
  ebird_api_configured: boolean;
  top_count: number;
  suggestions: EbirdMappingSuggestion[];
};

export const fetchEbirdMappingSuggestions =
  async (): Promise<EbirdMappingSuggestionsResponse> => {
    const response = await axios.get(
      `${BASE_API_URL}/settings/ebird-species-mapping-suggestions`,
      { withCredentials: true },
    );
    return response.data;
  };

export const updateSettings = async (settings: Settings) => {
  const payload = JSON.parse(JSON.stringify(settings)) as Record<
    string,
    unknown
  >;
  const perf = payload.performance as Record<string, unknown> | undefined;
  if (perf && typeof perf === 'object') {
    delete perf.redis_url_effective_masked;
  }
  const response = await axios.patch(`${BASE_API_URL}/settings`, payload, {
    withCredentials: true,
  });
  return response.data;
};

/** Deep-merge PATCH (same as full save); use for small updates e.g. Library file replay mode. */
export const patchSettings = async (partial: Record<string, unknown>) => {
  const response = await axios.patch(`${BASE_API_URL}/settings`, partial, {
    withCredentials: true,
  });
  return response.data;
};
