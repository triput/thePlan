/** Interval-aware Time Map day segments (V3-D2). No Vite/api imports — safe for node tests. */

const WEEKDAY_SHORT_TO_BIT: Record<string, number> = {
  Mon: 1,
  Tue: 2,
  Wed: 4,
  Thu: 8,
  Fri: 16,
  Sat: 32,
  Sun: 64,
};

export type SegmentBand = {
  id?: string;
  tier: string;
  start_time: string;
  end_time: string;
  days_of_week: number;
  sort_order: number;
};

export type SegmentMapWindow = {
  strict_mode: boolean;
  bands: SegmentBand[];
};

export type SegmentOverride = {
  id: string;
  local_start_date: string;
  local_end_date: string;
  timezone: string;
  strict_mode: boolean;
  bands: SegmentBand[];
};

export type TimeMapDaySegment = {
  startUtc: Date;
  endUtc: Date;
  source: "base_map" | "override";
  bands: SegmentBand[];
  strictMode: boolean;
  override: SegmentOverride | null;
};

export function ymdInTimeZone(instant: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(instant);
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

export function schedulingDayYmd(day: Date, userTimezone: string): string {
  return ymdInTimeZone(day, userTimezone);
}

function weekdayBitForSchedulingDay(day: Date, userTimezone: string): number {
  const ymd = schedulingDayYmd(day, userTimezone);
  const [y, mo, d] = ymd.split("-").map(Number);
  const noonUtc = Date.UTC(y, mo - 1, d, 12, 0);
  const wd = new Intl.DateTimeFormat("en-US", {
    timeZone: userTimezone,
    weekday: "short",
  }).format(new Date(noonUtc));
  return WEEKDAY_SHORT_TO_BIT[wd] ?? 0;
}

function bandsForSchedulingDay(bands: SegmentBand[], day: Date, userTimezone: string) {
  const bit = weekdayBitForSchedulingDay(day, userTimezone);
  return bands.filter((band) => (band.days_of_week & bit) !== 0);
}

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

function selectOverrideAtInstant(
  overrides: SegmentOverride[] | undefined,
  instant: Date,
): SegmentOverride | null {
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

/** V3-D2 Fixed: split operator day at stored-zone override bounds (matches placer). */
export function effectiveTimeMapSegmentsForDay(
  baseWindow: SegmentMapWindow,
  overrides: SegmentOverride[] | undefined,
  day: Date,
  operatorTimezone: string,
): TimeMapDaySegment[] {
  const schedulingYmd = schedulingDayYmd(day, operatorTimezone);
  const dayStart = zonedDateTimeToUtc(schedulingYmd, 0, 0, operatorTimezone);
  const [y, mo, d] = schedulingYmd.split("-").map(Number);
  const nextYmd = new Date(Date.UTC(y, mo - 1, d + 1)).toISOString().slice(0, 10);
  const dayEndFixed = zonedDateTimeToUtc(nextYmd, 0, 0, operatorTimezone);

  const active =
    overrides?.filter((override) => {
      const { start, end } = overrideUtcBounds(override);
      return start.getTime() < dayEndFixed.getTime() && end.getTime() > dayStart.getTime();
    }) ?? [];

  const cuts = new Set<number>();
  for (const override of active) {
    const { start, end } = overrideUtcBounds(override);
    for (const cut of [start, end]) {
      const t = cut.getTime();
      if (dayStart.getTime() < t && t < dayEndFixed.getTime()) cuts.add(t);
    }
  }
  const points = [dayStart.getTime(), dayEndFixed.getTime(), ...cuts].sort((a, b) => a - b);
  const segments: TimeMapDaySegment[] = [];
  for (let i = 0; i < points.length - 1; i += 1) {
    const left = points[i];
    const right = points[i + 1];
    if (left === undefined || right === undefined || left >= right) continue;
    const instant = new Date(left);
    const override = selectOverrideAtInstant(active, instant);
    const bands = override
      ? bandsForSchedulingDay(override.bands, day, operatorTimezone)
      : bandsForSchedulingDay(baseWindow.bands, day, operatorTimezone);
    segments.push({
      startUtc: new Date(left),
      endUtc: new Date(right),
      source: override ? "override" : "base_map",
      bands,
      strictMode: override ? override.strict_mode : baseWindow.strict_mode,
      override,
    });
  }
  if (segments.length === 0) {
    return [
      {
        startUtc: dayStart,
        endUtc: dayEndFixed,
        source: "base_map",
        bands: bandsForSchedulingDay(baseWindow.bands, day, operatorTimezone),
        strictMode: baseWindow.strict_mode,
        override: null,
      },
    ];
  }
  return segments;
}
