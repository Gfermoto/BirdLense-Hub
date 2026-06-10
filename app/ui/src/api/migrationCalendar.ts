/** Migration calendar grid API (#343). */
import { BASE_API_URL, apiFetch } from './client';

export interface MigrationCalendarData {
  species: Array<{
    id: number | null;
    name: string;
    image_url: string | null;
    monthly_counts: number[];
    total: number;
  }>;
  month_labels: string[];
  catalog?: 'observed' | 'all';
}

export type MigrationCalendarParams = {
  start_year?: number;
  end_year?: number;
  start_date?: string;
  end_date?: string;
  catalog?: 'observed' | 'all' | 'dataset' | 'full_eu' | 'active' | 'full';
};

function migrationCalendarQuery(params?: MigrationCalendarParams): string {
  if (!params) return '';
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      q.set(key, String(value));
    }
  }
  const qs = q.toString();
  return qs ? `?${qs}` : '';
}

export const fetchMigrationCalendar = async (
  params?: MigrationCalendarParams,
): Promise<MigrationCalendarData> =>
  apiFetch(`${BASE_API_URL}/migration-calendar${migrationCalendarQuery(params)}`);
