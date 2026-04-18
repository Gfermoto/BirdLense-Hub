import 'dayjs/locale/en';
import 'dayjs/locale/ru';
import 'dayjs/locale/zh-cn';

export interface StorageDay {
  date: string;
  fileCount: number;
  totalSize: number;
}

export const formatBytes = (bytes: number): string => {
  if (!Number.isFinite(bytes) || bytes < 0) return '0 B';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

export function getDayjsLocale(language: string | undefined): string {
  const raw = String(language || 'en').toLowerCase();
  if (raw.startsWith('ru')) return 'ru';
  if (raw.startsWith('zh')) return 'zh-cn';
  return 'en';
}
