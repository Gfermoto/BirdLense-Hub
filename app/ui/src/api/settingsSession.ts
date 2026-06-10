import type { Settings } from '../types';
import {
  BASE_API_URL,
  ApiHttpError,
  apiFetch,
  resetCsrfToken,
} from './client';

export type RequiresPasswordResult = {
  requires: boolean;
  has_contributor_tier?: boolean;
};

export const fetchSettingsRequiresPassword =
  async (): Promise<RequiresPasswordResult> => {
    const data = await apiFetch<{
      requires?: boolean;
      has_contributor_tier?: boolean;
    }>(`${BASE_API_URL}/settings/requires-password`);
    return {
      requires: data?.requires === true,
      has_contributor_tier: data?.has_contributor_tier === true,
    };
  };

export type CheckAccessResult =
  | { unlocked: true; role?: 'admin' | 'contributor' }
  | { unlocked: false; error?: 'network' };

export const checkSettingsAccess = async (): Promise<CheckAccessResult> => {
  try {
    const data = await apiFetch<{
      unlocked?: boolean;
      role?: 'admin' | 'contributor';
    }>(`${BASE_API_URL}/settings/check-access`);
    if (data?.unlocked === true) {
      return { unlocked: true, role: data?.role || 'admin' };
    }
    return { unlocked: false };
  } catch (e: unknown) {
    if (e instanceof ApiHttpError && e.status === 403) {
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

type VerifyPasswordResponse = {
  ok?: boolean;
  role?: 'admin' | 'contributor';
  error?: string;
};

export const verifySettingsPassword = async (
  password: string,
): Promise<VerifyPasswordResult> => {
  const postPassword = () =>
    apiFetch<VerifyPasswordResponse>(
      `${BASE_API_URL}/settings/verify-password`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      },
    );

  try {
    const data = await postPassword();
    if (data?.ok === true) {
      return { ok: true, role: data?.role || 'admin' };
    }
    return { ok: false, error: 'wrong_password' };
  } catch (e: unknown) {
    if (!(e instanceof ApiHttpError)) {
      return { ok: false, error: 'server_error' };
    }
    const status = e.status;
    const msg = (e.data as { error?: string })?.error;
    if (status === 401) {
      return { ok: false, error: 'wrong_password' };
    }
    if (
      status === 403 &&
      (msg === 'CSRF token required' || msg === 'Authentication required')
    ) {
      resetCsrfToken();
      try {
        const data = await postPassword();
        if (data?.ok === true) {
          return { ok: true, role: data?.role || 'admin' };
        }
      } catch {
        // Fall through to the user-facing CSRF/session hint below.
      }
      return { ok: false, error: 'csrf_or_auth' };
    }
    return { ok: false, error: 'server_error' };
  }
};

export const logoutSettingsSession = async (): Promise<void> => {
  await apiFetch(`${BASE_API_URL}/settings/logout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
};

export const fetchSettings = async () =>
  apiFetch(`${BASE_API_URL}/settings`);

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
  async (): Promise<EbirdMappingSuggestionsResponse> =>
    apiFetch(`${BASE_API_URL}/settings/ebird-species-mapping-suggestions`);

export const updateSettings = async (
  settings: Settings,
): Promise<Record<string, unknown> | undefined> => {
  const payload = JSON.parse(JSON.stringify(settings)) as Record<
    string,
    unknown
  >;
  const perf = payload.performance as Record<string, unknown> | undefined;
  if (perf && typeof perf === 'object') {
    delete perf.redis_url_effective_masked;
  }
  return apiFetch<Record<string, unknown>>(`${BASE_API_URL}/settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
};

/** Deep-merge PATCH (same as full save); use for small updates e.g. Library file replay mode. */
export const patchSettings = async (
  partial: Record<string, unknown>,
): Promise<Record<string, unknown> | undefined> =>
  apiFetch<Record<string, unknown>>(`${BASE_API_URL}/settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(partial),
  });
