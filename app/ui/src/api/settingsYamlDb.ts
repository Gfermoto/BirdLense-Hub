import {
  BASE_API_URL,
  ApiHttpError,
  apiBlob,
  apiFetch,
  triggerBlobDownload,
} from './client';

export const downloadSettingsYamlSafe = async (): Promise<void> => {
  const { blob, filename } = await apiBlob(
    `${BASE_API_URL}/settings/yaml-export?mode=safe`,
  );
  triggerBlobDownload(blob, filename || 'user_config_safe.yaml');
};

export const downloadSettingsYamlFull = async (): Promise<void> => {
  const { blob, filename } = await apiBlob(
    `${BASE_API_URL}/settings/yaml-export?mode=full&ack=full`,
  );
  triggerBlobDownload(blob, filename || 'user_config_full.yaml');
};

export const importSettingsYaml = async (
  file: File,
): Promise<{ ok: boolean; message?: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  try {
    const data = await apiFetch<{ message?: string }>(
      `${BASE_API_URL}/settings/yaml-import`,
      {
        method: 'POST',
        body: formData,
      },
    );
    return { ok: true, message: data.message };
  } catch (e) {
    if (e instanceof ApiHttpError) {
      return { ok: false, message: e.message };
    }
    throw e;
  }
};

export const downloadDbBackup = async (): Promise<void> => {
  const { blob, filename } = await apiBlob(`${BASE_API_URL}/system/db/backup`);
  triggerBlobDownload(
    blob,
    filename ||
      `birdlense_db_backup_${new Date().toISOString().replace(/[:.]/g, '-')}.db`,
  );
};

/** Restore SQLite DB from uploaded file (.db). */
export const restoreDbBackup = async (
  file: File,
): Promise<{ message: string; backup_path?: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  return apiFetch(`${BASE_API_URL}/system/db/restore`, {
    method: 'POST',
    body: formData,
  });
};

export type PurgeStorageBody =
  | { date: string }
  | { start_date: string; end_date: string };

/** Delete recordings by cutoff date or inclusive calendar range (admin). */
export const purgeStorageRecordings = async (
  body: PurgeStorageBody,
): Promise<{ message: string; deletedCount: number; deletedSize: number }> =>
  apiFetch(`${BASE_API_URL}/storage/purge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

/** External Nominatim geocoding — not Hub API (#617 documented exception). */
export const fetchCoordinatesByZip = async (
  zip: string,
): Promise<{ lat: string; lon: string }> => {
  const params = new URLSearchParams({
    format: 'json',
    postalcode: zip,
    countrycodes: 'ru,us,de,gb',
  });
  const response = await fetch(
    `https://nominatim.openstreetmap.org/search?${params}`,
  );
  if (!response.ok) {
    throw new Error(`Nominatim request failed: ${response.status}`);
  }
  const data = (await response.json()) as Array<{ lat: string; lon: string }>;

  if (data.length > 0) {
    return {
      lat: data[0].lat,
      lon: data[0].lon,
    };
  }
  throw new Error('Invalid ZIP code or no data found.');
};
