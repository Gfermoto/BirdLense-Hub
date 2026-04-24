import axios from 'axios';
import { BASE_API_URL } from './client';

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

export const fetchFileTestFiles = async (): Promise<FileTestFilesResponse> => {
  const response = await axios.get(`${BASE_API_URL}/system/file-test/files`, {
    withCredentials: true,
  });
  return response.data;
};

export const fetchFileTestStatus = async (): Promise<FileTestStatusPayload> => {
  const response = await axios.get(`${BASE_API_URL}/system/file-test/status`, {
    withCredentials: true,
  });
  return response.data;
};

export const fileTestRun = async (body: {
  armed?: boolean;
  loop?: boolean;
}) => {
  const response = await axios.post(
    `${BASE_API_URL}/system/file-test/run`,
    body,
    {
      withCredentials: true,
    },
  );
  return response.data;
};

export const fileTestStop = async () => {
  const response = await axios.post(
    `${BASE_API_URL}/system/file-test/stop`,
    {},
    { withCredentials: true },
  );
  return response.data;
};

export const fileTestDeleteFile = async (name: string) => {
  await axios.delete(
    `${BASE_API_URL}/system/file-test/files/${encodeURIComponent(name)}`,
    {
      withCredentials: true,
    },
  );
};

export const fileTestUpload = async (file: File) => {
  const fd = new FormData();
  fd.append('file', file);
  const response = await axios.post(
    `${BASE_API_URL}/system/file-test/upload`,
    fd,
    {
      withCredentials: true,
    },
  );
  return response.data as { ok: boolean; name?: string };
};
