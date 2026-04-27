import axios from 'axios';
import { BASE_API_URL, csrfFetch } from './client';

const _downloadYamlResponse = async (url: string, fallbackName: string) => {
  const res = await fetch(url, { credentials: 'include' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  const blob = await res.blob();
  const cd = res.headers.get('Content-Disposition');
  const filename = cd?.match(/filename="?([^";\n]+)"?/)?.[1] || fallbackName;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
};

export const downloadSettingsYamlSafe = async (): Promise<void> => {
  await _downloadYamlResponse(
    `${BASE_API_URL}/settings/yaml-export?mode=safe`,
    'user_config_safe.yaml',
  );
};

export const downloadSettingsYamlFull = async (): Promise<void> => {
  await _downloadYamlResponse(
    `${BASE_API_URL}/settings/yaml-export?mode=full&ack=full`,
    'user_config_full.yaml',
  );
};

export const importSettingsYaml = async (
  file: File,
): Promise<{ ok: boolean; message?: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await csrfFetch(`${BASE_API_URL}/settings/yaml-import`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return {
      ok: false,
      message: (data as { error?: string }).error || res.statusText,
    };
  }
  return { ok: true, message: (data as { message?: string }).message };
};

export const downloadDbBackup = async (): Promise<void> => {
  const res = await fetch(`${BASE_API_URL}/system/db/backup`, {
    credentials: 'include',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  const blob = await res.blob();
  const cd = res.headers.get('Content-Disposition');
  const filename =
    cd?.match(/filename="?([^";\n]+)"?/)?.[1] ||
    `birdlense_db_backup_${new Date().toISOString().replace(/[:.]/g, '-')}.db`;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
};

/** Restore SQLite DB from uploaded file (.db). */
export const restoreDbBackup = async (
  file: File,
): Promise<{ message: string; backup_path?: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await csrfFetch(`${BASE_API_URL}/system/db/restore`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
};

export type PurgeStorageBody =
  | { date: string }
  | { start_date: string; end_date: string };

/** Delete recordings by cutoff date or inclusive calendar range (admin). */
export const purgeStorageRecordings = async (
  body: PurgeStorageBody,
): Promise<{ message: string; deletedCount: number; deletedSize: number }> => {
  const { data } = await axios.post(`${BASE_API_URL}/storage/purge`, body, {
    withCredentials: true,
  });
  return data;
};

export const fetchCoordinatesByZip = async (
  zip: string,
): Promise<{ lat: string; lon: string }> => {
  const response = await axios.get(
    'https://nominatim.openstreetmap.org/search',
    {
      params: {
        format: 'json',
        postalcode: zip,
        countrycodes: 'ru,us,de,gb',
      },
    },
  );
  const data = response.data;

  if (data && data.length > 0) {
    return {
      lat: data[0].lat,
      lon: data[0].lon,
    };
  } else {
    throw new Error('Invalid ZIP code or no data found.');
  }
};
