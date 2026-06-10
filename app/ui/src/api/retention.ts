import { BASE_API_URL, apiFetch } from './client';

export type OrphanRecordingFiles = {
  orphan_session_count: number;
  orphan_bytes: number;
  sample_paths?: string[];
};

export type RetentionConfigSnapshot = {
  mode: string;
  days?: number | null;
  max_gb?: number | null;
  orphan_recording_files?: OrphanRecordingFiles;
  last_run?: string | null;
  last_deleted_count?: number;
  last_freed_bytes?: number;
};

export const fetchRetentionConfig =
  async (): Promise<RetentionConfigSnapshot> =>
    apiFetch(`${BASE_API_URL}/system/retention`);
