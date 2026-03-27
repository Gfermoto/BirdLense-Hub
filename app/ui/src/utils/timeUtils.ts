import type { Dayjs } from 'dayjs';

export type TimeOfDay = 'all' | 'night' | 'morning' | 'day' | 'afternoon' | 'evening';

/** Форматирует секунды в короткий вид: 45s, 5m, 1.5h */
export function formatDuration(seconds: number): string {
  if (seconds < 0 || !Number.isFinite(seconds)) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

/** Форматирует секунды как mm:ss для таймлайна видео */
export function formatTimeMmSs(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s < 10 ? '0' : ''}${s}`;
}

export const TIME_RANGES: Record<Exclude<TimeOfDay, 'all'>, [number, number]> = {
  night: [22, 6],    // 22–06 (через полночь)
  morning: [6, 10],  // 6–10
  day: [10, 14],     // 10–14
  afternoon: [14, 18], // 14–18
  evening: [18, 22],  // 18–22
};

/** Возвращает start/end для API по дате и времени суток. */
export function getTimeRange(date: Dayjs, timeOfDay: TimeOfDay): { start: Dayjs; end: Dayjs } {
  const startOfDay = date.startOf('date');
  if (timeOfDay === 'all') {
    return { start: startOfDay, end: date.endOf('date') };
  }
  const [startHour, endHour] = TIME_RANGES[timeOfDay];
  if (timeOfDay === 'night') {
    return {
      start: startOfDay.hour(startHour).minute(0).second(0).millisecond(0),
      end: startOfDay.add(1, 'day').hour(endHour).minute(0).second(0).millisecond(0).subtract(1, 'millisecond'),
    };
  }
  return {
    start: startOfDay.hour(startHour).minute(0).second(0).millisecond(0),
    end: startOfDay.hour(endHour).minute(0).second(0).millisecond(0).subtract(1, 'millisecond'),
  };
}

/** Один календарный час (локальное время) для суточного паттерна → таймлайн. */
export function getHourTimeRange(date: Dayjs, hour: number): { start: Dayjs; end: Dayjs } {
  const startOfDay = date.startOf('date');
  const h = ((hour % 24) + 24) % 24;
  return {
    start: startOfDay.hour(h).minute(0).second(0).millisecond(0),
    end: startOfDay.hour(h).minute(59).second(59).millisecond(999),
  };
}
