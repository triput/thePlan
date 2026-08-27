/**
 * IANA timezone catalog for Settings scheduling defaults.
 * Prefer Intl.supportedValuesOf('timeZone'); fall back when unavailable.
 */

/** Common IANA zones for engines without Intl.supportedValuesOf('timeZone'). */
export const FALLBACK_IANA_TIMEZONES: readonly string[] = [
  "Africa/Cairo",
  "Africa/Casablanca",
  "Africa/Johannesburg",
  "Africa/Lagos",
  "Africa/Nairobi",
  "America/Anchorage",
  "America/Argentina/Buenos_Aires",
  "America/Bogota",
  "America/Caracas",
  "America/Chicago",
  "America/Denver",
  "America/Halifax",
  "America/Indiana/Indianapolis",
  "America/Jamaica",
  "America/Lima",
  "America/Los_Angeles",
  "America/Mexico_City",
  "America/New_York",
  "America/Phoenix",
  "America/Santiago",
  "America/Sao_Paulo",
  "America/St_Johns",
  "America/Toronto",
  "America/Vancouver",
  "Asia/Bangkok",
  "Asia/Dhaka",
  "Asia/Dubai",
  "Asia/Hong_Kong",
  "Asia/Jakarta",
  "Asia/Jerusalem",
  "Asia/Karachi",
  "Asia/Kolkata",
  "Asia/Manila",
  "Asia/Seoul",
  "Asia/Shanghai",
  "Asia/Singapore",
  "Asia/Taipei",
  "Asia/Tokyo",
  "Atlantic/Azores",
  "Atlantic/Reykjavik",
  "Australia/Adelaide",
  "Australia/Brisbane",
  "Australia/Melbourne",
  "Australia/Perth",
  "Australia/Sydney",
  "Europe/Amsterdam",
  "Europe/Athens",
  "Europe/Berlin",
  "Europe/Brussels",
  "Europe/Budapest",
  "Europe/Dublin",
  "Europe/Helsinki",
  "Europe/Istanbul",
  "Europe/Lisbon",
  "Europe/London",
  "Europe/Madrid",
  "Europe/Moscow",
  "Europe/Oslo",
  "Europe/Paris",
  "Europe/Prague",
  "Europe/Rome",
  "Europe/Stockholm",
  "Europe/Vienna",
  "Europe/Warsaw",
  "Europe/Zurich",
  "Pacific/Auckland",
  "Pacific/Fiji",
  "Pacific/Guam",
  "Pacific/Honolulu",
  "Pacific/Midway",
  "UTC",
];

let cachedZones: string[] | null = null;

function readSupportedTimeZones(): string[] | null {
  const intl = Intl as typeof Intl & {
    supportedValuesOf?: (key: string) => string[];
  };
  if (typeof intl.supportedValuesOf !== "function") return null;
  try {
    const zones = intl.supportedValuesOf("timeZone");
    if (!Array.isArray(zones) || zones.length === 0) return null;
    return [...zones].sort((a, b) => a.localeCompare(b));
  } catch {
    return null;
  }
}

/** Sorted unique IANA zone names (Intl when available, else fallback). */
export function listIanaTimeZones(): string[] {
  if (cachedZones) return cachedZones;
  cachedZones = readSupportedTimeZones() ?? [...FALLBACK_IANA_TIMEZONES];
  return cachedZones;
}

/**
 * Catalog plus `current` when it is exotic / missing from the engine list,
 * so an already-saved value stays selectable.
 */
export function listIanaTimeZonesWithCurrent(current: string): string[] {
  const zones = listIanaTimeZones();
  const trimmed = current.trim();
  if (!trimmed || zones.includes(trimmed)) return zones;
  return [trimmed, ...zones].sort((a, b) => a.localeCompare(b));
}

export function filterIanaTimeZones(zones: readonly string[], query: string): string[] {
  const q = query.trim().toLowerCase().replace(/\s+/g, "_");
  if (!q) return [...zones];
  return zones.filter((z) => z.toLowerCase().includes(q));
}
