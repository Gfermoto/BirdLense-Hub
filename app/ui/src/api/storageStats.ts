import { BASE_API_URL, apiFetch } from './client';

export type StorageStatsDay = {
  date: string;
  fileCount: number;
  totalSize: number;
};

export const fetchStorageStats = async (): Promise<StorageStatsDay[]> => {
  const data = await apiFetch<StorageStatsDay[]>(`${BASE_API_URL}/storage/stats`);
  return Array.isArray(data) ? data : [];
};

export function sumStorageStats(days: StorageStatsDay[]): {
  totalBytes: number;
  totalFiles: number;
} {
  return days.reduce(
    (acc, row) => {
      if (
        typeof row.totalSize === 'number' &&
        Number.isFinite(row.totalSize) &&
        typeof row.fileCount === 'number' &&
        Number.isFinite(row.fileCount)
      ) {
        acc.totalBytes += row.totalSize;
        acc.totalFiles += row.fileCount;
      }
      return acc;
    },
    { totalBytes: 0, totalFiles: 0 },
  );
}
