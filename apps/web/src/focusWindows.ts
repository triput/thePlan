import type { TimeMapBand, TimeMapBandTier } from "./api";

/** Mon=1 … Sun=64 bitset for focus window days_of_week. */
export const DAY_BITS = [
  { label: "Mon", bit: 1 },
  { label: "Tue", bit: 2 },
  { label: "Wed", bit: 4 },
  { label: "Thu", bit: 8 },
  { label: "Fri", bit: 16 },
  { label: "Sat", bit: 32 },
  { label: "Sun", bit: 64 },
] as const;

export const WEEKDAY_BITSET = 31;

/** JS getDay() → DAY_BITS bit (Sun=0 … Sat=6). */
const JS_DAY_TO_BIT = [64, 1, 2, 4, 8, 16, 32] as const;

export const TIME_MAP_TIER_LABELS: Record<TimeMapBandTier, string> = {
  green: "Green",
  yellow: "Yellow",
  red: "Red",
};

/** Tier fill colors for calendar band overlays (traffic-light, not accent purple).
 *  Calendar CSS uses color-mix / hatch for red so it stays readable over stacked greens. */
export const TIME_MAP_TIER_COLORS: Record<TimeMapBandTier, string> = {
  green: "#22c55e",
  yellow: "#eab308",
  red: "#ef4444",
};
export const TIME_MAP_TIER_CLASS: Record<TimeMapBandTier, string> = {
  green: "cal-time-map-band--green",
  yellow: "cal-time-map-band--yellow",
  red: "cal-time-map-band--red",
};

export function decodeDays(bitset: number): boolean[] {
  return DAY_BITS.map(({ bit }) => (bitset & bit) !== 0);
}

export function encodeDays(selected: boolean[]): number {
  let value = 0;
  for (let i = 0; i < DAY_BITS.length; i++) {
    if (selected[i]) value |= DAY_BITS[i].bit;
  }
  return value;
}

export function dayMatchesBitset(day: Date, bitset: number): boolean {
  const bit = JS_DAY_TO_BIT[day.getDay()];
  return (bitset & bit) !== 0;
}

export function formatDaysSummary(bitset: number): string {
  const labels = DAY_BITS.filter(({ bit }) => (bitset & bit) !== 0).map(({ label }) => label);
  if (labels.length === 0) return "No days";
  if (labels.length === 7) return "Every day";
  if (bitset === WEEKDAY_BITSET) return "Mon–Fri";
  if (bitset === 96) return "Sat–Sun";
  return labels.join(", ");
}

export function formatTimeRange(start: string, end: string): string {
  return `${start}–${end}`;
}

export function formatBandsSummary(bands: TimeMapBand[]): string {
  const counts: Record<TimeMapBandTier, number> = { green: 0, yellow: 0, red: 0 };
  for (const band of bands) {
    counts[band.tier] += 1;
  }
  const parts: string[] = [];
  if (counts.green > 0) parts.push(`${counts.green} green`);
  if (counts.yellow > 0) parts.push(`${counts.yellow} yellow`);
  if (counts.red > 0) parts.push(`${counts.red} red`);
  return parts.length > 0 ? parts.join(", ") : "No bands";
}

export function defaultGreenBand(sortOrder = 0): TimeMapBand {
  return {
    tier: "green",
    start_time: "09:00",
    end_time: "12:00",
    days_of_week: WEEKDAY_BITSET,
    sort_order: sortOrder,
  };
}

export function parseHHMM(hhmm: string): { hours: number; minutes: number } {
  const [h, m] = hhmm.split(":").map(Number);
  return { hours: h ?? 0, minutes: m ?? 0 };
}

export function combineDayAndHHMM(day: Date, hhmm: string): Date {
  const { hours, minutes } = parseHHMM(hhmm);
  const result = new Date(day);
  result.setHours(hours, minutes, 0, 0);
  return result;
}

export function isValidBandTimeRange(start: string, end: string): boolean {
  return start.length > 0 && end.length > 0 && end > start;
}
