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
