import { BASE_API_URL, apiFetch } from './client';

export type FileTestFileRow = {
  name: string;
  size: number;
  duration_sec: number | null;
};

export type FileTestFilesResponse = {
  file_dir: string;
  files: FileTestFileRow[];
};

export type FileTestStatusPayload = {
  file_dir: string;
  desired: Record<string, unknown>;
  processor: Record<string, unknown> | null;
  config_loop_default: boolean;
  video_source: string;
  /** Effective upload cap (MiB) from video.file_test_max_upload_mb */
  file_test_max_upload_mb?: number;
};

export const fetchFileTestFiles = async (): Promise<FileTestFilesResponse> =>
  apiFetch(`${BASE_API_URL}/system/file-test/files`);

export const fetchFileTestStatus = async (): Promise<FileTestStatusPayload> =>
  apiFetch(`${BASE_API_URL}/system/file-test/status`);

export const fileTestRun = async (body: { armed?: boolean; loop?: boolean }) =>
  apiFetch(`${BASE_API_URL}/system/file-test/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

export const fileTestStop = async () =>
  apiFetch(`${BASE_API_URL}/system/file-test/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });

export const fileTestDeleteFile = async (name: string) => {
  await apiFetch(`${BASE_API_URL}/system/file-test/files/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });
};

export const fileTestUpload = async (file: File) => {
  const fd = new FormData();
  fd.append('file', file);
  return apiFetch<{ ok: boolean; name?: string }>(
    `${BASE_API_URL}/system/file-test/upload`,
    {
      method: 'POST',
      body: fd,
    },
  );
};
