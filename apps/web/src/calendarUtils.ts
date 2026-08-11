/** Local-time calendar helpers (ISO weeks = Monday-start). */

export const CALENDAR_HOUR_START = 6;
export const CALENDAR_HOUR_END = 22;
export const CALENDAR_HOURS = CALENDAR_HOUR_END - CALENDAR_HOUR_START;

export type CalendarMode = "day" | "week";

export function startOfDay(d: Date): Date {
  const r = new Date(d);
  r.setHours(0, 0, 0, 0);
  return r;
}

export function endOfDay(d: Date): Date {
  const r = new Date(d);
  r.setHours(23, 59, 59, 999);
  return r;
}

export function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

/** Monday 00:00 local for the week containing `d`. */
export function startOfWeekMonday(d: Date): Date {
  const r = startOfDay(d);
  const day = r.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  r.setDate(r.getDate() + diff);
  return r;
}

export function daysInYear(year: number): number {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0 ? 366 : 365;
}

/** Day of year 1–365/366 in local timezone. */
export function getDayOfYear(d: Date): number {
  const start = new Date(d.getFullYear(), 0, 0);
  const diff = d.getTime() - start.getTime();
  return Math.floor(diff / 86_400_000);
}

/** ISO week number (1–53), Monday-start weeks. */
export function getISOWeek(d: Date): number {
  const date = startOfDay(d);
  date.setDate(date.getDate() + 3 - ((date.getDay() + 6) % 7));
  const week1 = new Date(date.getFullYear(), 0, 4);
  return (
    1 +
    Math.round(
      ((date.getTime() - week1.getTime()) / 86_400_000 -
        3 +
        ((week1.getDay() + 6) % 7)) /
        7,
    )
  );
}

export function toISO(d: Date): string {
  return d.toISOString();
}

export function visibleRange(anchor: Date, mode: CalendarMode): { start: Date; end: Date } {
  if (mode === "day") {
    const start = startOfDay(anchor);
    return { start, end: addDays(start, 1) };
  }
  const start = startOfWeekMonday(anchor);
  return { start, end: addDays(start, 7) };
}

export function weekDays(anchor: Date): Date[] {
  const monday = startOfWeekMonday(anchor);
  return Array.from({ length: 7 }, (_, i) => addDays(monday, i));
}

export function formatHour(hour: number): string {
  const d = new Date();
  d.setHours(hour, 0, 0, 0);
  return d.toLocaleTimeString(undefined, { hour: "numeric" });
}

export function formatShortDate(d: Date): string {
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function formatWeekday(d: Date): string {
  return d.toLocaleDateString(undefined, { weekday: "short" });
}

export function formatDayHeader(d: Date): string {
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function isToday(d: Date): boolean {
  return isSameDay(d, new Date());
}

/** Minutes from midnight local. */
export function minutesFromMidnight(d: Date): number {
  return d.getHours() * 60 + d.getMinutes();
}

export function topPercentForTime(d: Date): number {
  const mins = minutesFromMidnight(d) - CALENDAR_HOUR_START * 60;
  const total = CALENDAR_HOURS * 60;
  return Math.max(0, Math.min(100, (mins / total) * 100));
}

export function heightPercentForDuration(minutes: number): number {
  const total = CALENDAR_HOURS * 60;
  return Math.max(2, (minutes / total) * 100);
}

export function slotFromClick(
  day: Date,
  offsetY: number,
  rowHeightPx: number,
): { start: Date; end: Date } {
  const hourIndex = Math.floor(offsetY / rowHeightPx);
  const hour = Math.max(CALENDAR_HOUR_START, Math.min(CALENDAR_HOUR_END - 1, CALENDAR_HOUR_START + hourIndex));
  const start = new Date(day);
  start.setHours(hour, 0, 0, 0);
  const end = new Date(start);
  end.setHours(hour + 1, 0, 0, 0);
  return { start, end };
}

export const CALENDAR_SNAP_MINUTES = 15;
export const CALENDAR_MIN_BLOCK_MINUTES = 15;

/** Convert a vertical pixel delta into calendar minutes for the visible hour window. */
export function minutesFromDeltaY(deltaY: number, rowHeightPx: number): number {
  return (deltaY / rowHeightPx) * 60;
}

export function snapMinutes(minutes: number, step = CALENDAR_SNAP_MINUTES): number {
  return Math.round(minutes / step) * step;
}

/** Clamp a Date's clock into the visible calendar window on its calendar day. */
export function clampToCalendarWindow(d: Date, durationMinutes = 0): Date {
  const day = startOfDay(d);
  const windowStart = new Date(day);
  windowStart.setHours(CALENDAR_HOUR_START, 0, 0, 0);
  const windowEnd = new Date(day);
  windowEnd.setHours(CALENDAR_HOUR_END, 0, 0, 0);
  const maxStart = new Date(windowEnd.getTime() - durationMinutes * 60_000);
  if (d < windowStart) return windowStart;
  if (d > maxStart) return maxStart < windowStart ? windowStart : maxStart;
  return d;
}

/** Keep time-of-day from `time`, calendar date from `day`. */
export function combineDateAndTime(day: Date, time: Date): Date {
  const result = startOfDay(day);
  result.setHours(time.getHours(), time.getMinutes(), time.getSeconds(), 0);
  return result;
}

export function addMinutes(d: Date, minutes: number): Date {
  return new Date(d.getTime() + minutes * 60_000);
}

export function getISOWeekYear(d: Date): number {
  const date = startOfDay(d);
  // Thursday of this ISO week determines the ISO year
  date.setDate(date.getDate() + 3 - ((date.getDay() + 6) % 7));
  return date.getFullYear();
}

export function dayViewTitle(d: Date): string {
  const year = d.getFullYear();
  const doy = getDayOfYear(d);
  const week = getISOWeek(d);
  return `${formatDayHeader(d)}  •  Year ${year}: Day ${doy}  •  Week ${week}`;
}

export function weekViewTitle(anchor: Date): string {
  const days = weekDays(anchor);
  const first = days[0];
  const last = days[6];
  const year = getISOWeekYear(first);
  const week = getISOWeek(first);
  const doyStart = getDayOfYear(first);
  const doyEnd = getDayOfYear(last);
  return `${formatShortDate(first)}–${formatShortDate(last)}  •  Year ${year}: Week ${week}  •  Days ${doyStart}–${doyEnd}`;
}
