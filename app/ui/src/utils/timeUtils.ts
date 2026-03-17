import type { Dayjs } from 'dayjs';

export type TimeOfDay = 'all' | 'night' | 'morning' | 'day' | 'afternoon' | 'evening';

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
