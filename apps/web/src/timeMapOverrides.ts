import type { FocusWindow, TimeMapBand, TimeMapOverride, UserSettings } from "./api";
import { ApiError } from "./api";
const WEEKDAY_SHORT_TO_BIT: Record<string, number> = {
  Mon: 1,
  Tue: 2,
  Wed: 4,
  Thu: 8,
  Fri: 16,
  Sat: 32,
  Sun: 64,
};

export function ymdInTimeZone(instant: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(instant);
}

export function schedulingDayYmd(day: Date, userTimezone: string): string {
  return ymdInTimeZone(day, userTimezone);
}

function parseHm(hm: string): { h: number; m: number } {
  const [h, m] = hm.split(":").map(Number);
  return { h: h ?? 0, m: m ?? 0 };
}

function getTimeZoneOffsetMs(utcMs: number, timeZone: string): number {
  const d = new Date(utcMs);
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(d);
  const map: Record<string, number> = {};
  for (const part of parts) {
    if (part.type !== "literal") map[part.type] = Number(part.value);
  }
  const asUtc = Date.UTC(
    map.year,
    map.month - 1,
    map.day,
    map.hour,
    map.minute,
    map.second ?? 0,
  );
  return asUtc - utcMs;
}

/** Wall clock in IANA zone → UTC instant (mirrors scheduler DST behavior). */
export function zonedDateTimeToUtc(
  ymd: string,
  hour: number,
  minute: number,
  timeZone: string,
): Date {
  const [y, mo, d] = ymd.split("-").map(Number);
  let ms = Date.UTC(y, mo - 1, d, hour, minute);
  for (let i = 0; i < 4; i++) {
    ms = Date.UTC(y, mo - 1, d, hour, minute) - getTimeZoneOffsetMs(ms, timeZone);
  }
  return new Date(ms);
}

/** Mirror API ``effective_local_date_for_scheduling_day`` (S2-V3 stored-zone civil day). */
export function effectiveLocalDateForSchedulingDay(
  schedulingDayYmd: string,
  settings: Pick<UserSettings, "timezone">,
  overrideTimezone: string,
): string {
  const instant = zonedDateTimeToUtc(schedulingDayYmd, 0, 0, settings.timezone);
  return ymdInTimeZone(instant, overrideTimezone);
}

export function weekdayBitForSchedulingDay(day: Date, userTimezone: string): number {
  const ymd = schedulingDayYmd(day, userTimezone);
  const [y, mo, d] = ymd.split("-").map(Number);
  const noonUtc = Date.UTC(y, mo - 1, d, 12, 0);
  const wd = new Intl.DateTimeFormat("en-US", {
    timeZone: userTimezone,
    weekday: "short",
  }).format(new Date(noonUtc));
  return WEEKDAY_SHORT_TO_BIT[wd] ?? 0;
}

export function selectOverrideForSchedulingDay(
  overrides: TimeMapOverride[] | undefined,
  day: Date,
  settings: Pick<UserSettings, "timezone">,
): TimeMapOverride | null {
  if (!overrides?.length) return null;
  const schedulingYmd = schedulingDayYmd(day, settings.timezone);
  const matches = overrides.filter((override) => {
    const effective = effectiveLocalDateForSchedulingDay(
      schedulingYmd,
      settings,
      override.timezone,
    );
    return override.local_start_date <= effective && effective <= override.local_end_date;
  });
  if (matches.length === 0) return null;
  matches.sort(
    (a, b) =>
      a.local_start_date.localeCompare(b.local_start_date) || a.id.localeCompare(b.id),
  );
  return matches[0] ?? null;
}

export function bandsForSchedulingDay(bands: TimeMapBand[], day: Date, userTimezone: string) {
  const bit = weekdayBitForSchedulingDay(day, userTimezone);
  return bands.filter((band) => (band.days_of_week & bit) !== 0);
}

export function effectiveTimeMapBandsForDay(
  baseWindow: FocusWindow,
  overrides: TimeMapOverride[] | undefined,
  day: Date,
  settings: Pick<UserSettings, "timezone">,
): { bands: TimeMapBand[]; strictMode: boolean; override: TimeMapOverride | null } {
  const override = selectOverrideForSchedulingDay(overrides, day, settings);
  if (!override) {
    return {
      bands: bandsForSchedulingDay(baseWindow.bands, day, settings.timezone),
      strictMode: baseWindow.strict_mode,
      override: null,
    };
  }
  return {
    bands: bandsForSchedulingDay(override.bands, day, settings.timezone),
    strictMode: override.strict_mode,
    override,
  };
}

/** Wall-clock band time on a local YMD in IANA zone → instant for calendar positioning. */
export function bandWallClockToInstant(ymd: string, hhmm: string, timeZone: string): Date {
  const { h, m } = parseHm(hhmm);
  return zonedDateTimeToUtc(ymd, h, m, timeZone);
}

export type TimeMapBandWallClockContext = { localYmd: string; timeZone: string };

/**
 * Local date + zone for painting bands on a scheduling-day column.
 * Matches API ``placement.band_bounds``: band HH:MM on the scheduling YMD in
 * ``settings.timezone``. Override IANA zone only selects date applicability
 * (``selectOverrideForSchedulingDay`` / ``effectiveLocalDateForSchedulingDay``).
 */
export function bandWallClockContextForSchedulingDay(
  day: Date,
  settings: Pick<UserSettings, "timezone">,
  _override: TimeMapOverride | null,
): TimeMapBandWallClockContext {
  return {
    localYmd: schedulingDayYmd(day, settings.timezone),
    timeZone: settings.timezone,
  };
}

export function sortTimeMapBandsForOverlay(bands: TimeMapBand[]): TimeMapBand[] {
  const tierOrder: Record<string, number> = { green: 0, yellow: 1, red: 2 };
  return [...bands].sort(
    (a, b) =>
      (tierOrder[a.tier] ?? 0) - (tierOrder[b.tier] ?? 0) || a.sort_order - b.sort_order,
  );
}

export function formatOverrideDateRange(start: string, end: string): string {
  if (start === end) return start;
  return `${start} – ${end}`;
}

/** Stored-zone midnight → next midnight after ``local_end_date`` (exclusive). */
export function overrideUtcBounds(override: {
  local_start_date: string;
  local_end_date: string;
  timezone: string;
}): { start: Date; end: Date } {
  const start = zonedDateTimeToUtc(override.local_start_date, 0, 0, override.timezone);
  const [y, m, d] = override.local_end_date.split("-").map(Number);
  const endUtc = new Date(Date.UTC(y, (m ?? 1) - 1, d ?? 1));
  endUtc.setUTCDate(endUtc.getUTCDate() + 1);
  const endYmd = endUtc.toISOString().slice(0, 10);
  const end = zonedDateTimeToUtc(endYmd, 0, 0, override.timezone);
  return { start, end };
}

export function overrideIntersectsHorizon(
  override: { local_start_date: string; local_end_date: string; timezone: string },
  horizonStart: Date,
  horizonEnd: Date,
): boolean {
  if (horizonEnd.getTime() <= horizonStart.getTime()) return false;
  const { start, end } = overrideUtcBounds(override);
  return start.getTime() < horizonEnd.getTime() && end.getTime() > horizonStart.getTime();
}

/** Instant is inside the override's stored-zone civil span. Not a whole schedule-day pick. */
export function selectOverrideAtInstant(
  overrides: TimeMapOverride[] | undefined,
  instant: Date,
): TimeMapOverride | null {
  if (!overrides?.length) return null;
  const t = instant.getTime();
  const matches = overrides.filter((override) => {
    const { start, end } = overrideUtcBounds(override);
    return start.getTime() <= t && t < end.getTime();
  });
  if (matches.length === 0) return null;
  matches.sort(
    (a, b) =>
      a.local_start_date.localeCompare(b.local_start_date) || a.id.localeCompare(b.id),
  );
  return matches[0] ?? null;
}

export function isOverrideExpired(override: TimeMapOverride, now = new Date()): boolean {
  const { end } = overrideUtcBounds(override);
  return now.getTime() >= end.getTime();
}

export function formatTimeMapOverrideError(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return err instanceof Error ? err.message : "Couldn't save override";
  }
  switch (err.code) {
    case "TIME_MAP_OVERRIDE_OVERLAP": {
      const start = err.body.conflicting_local_start_date;
      const end = err.body.conflicting_local_end_date;
      if (start && end) {
        return `Date range overlaps another override (${formatOverrideDateRange(start, end)}). Change these dates or edit the existing override.`;
      }
      return err.message;
    }
    case "TIME_MAP_OVERRIDE_BAND_CROSSES_MIDNIGHT": {
      const index = err.body.band_index;
      if (typeof index === "number") {
        return `Band ${index + 1} crosses midnight. Split it into two bands that each stay within one local day.`;
      }
      return err.message;
    }
    case "TIME_MAP_OVERRIDE_TIMEZONE":
      return "Timezone must be a valid IANA name (for example America/Los_Angeles).";
    case "TIME_MAP_OVERRIDE_INVALID_RANGE":
      return "End date must be on or after the start date.";
    default:
      return err.message;
  }
}

/** Client-side midnight check before POST (API returns 422 with band_index). */
export function bandCrossesMidnight(start: string, end: string): boolean {
  return start.length > 0 && end.length > 0 && end <= start;
}

export function describeOverrideStatus(override: TimeMapOverride): string {
  const range = formatOverrideDateRange(override.local_start_date, override.local_end_date);
  const tz = override.timezone;
  return `${range} (${tz})`;
}
