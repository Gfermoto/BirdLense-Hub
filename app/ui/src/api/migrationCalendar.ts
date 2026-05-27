/** Migration calendar grid API (#343). */
import axios from 'axios';
import { BASE_API_URL } from './client';

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

export const fetchMigrationCalendar = async (
  params?: MigrationCalendarParams,
): Promise<MigrationCalendarData> => {
  const response = await axios.get(`${BASE_API_URL}/migration-calendar`, {
    params: params || {},
  });
  return response.data;
};
