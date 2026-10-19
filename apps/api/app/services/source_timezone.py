"""Track 1 T1-B: source-zone provenance, Windows→IANA, DST-aware all-day bounds.

Never reinterpret a known source-local civil day in the owner timezone.
Provider display ``timeZone`` alone is not source provenance (MS Prefer header).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# CLDR windowsZones.xml territory "001" (default) mappings — Graph returns Windows IDs.
# Unsupported / unlisted names fail closed (source_zone_missing), not guessed.
_WINDOWS_TO_IANA: dict[str, str] = {
    "Afghanistan Standard Time": "Asia/Kabul",
    "Alaskan Standard Time": "America/Anchorage",
    "Aleutian Standard Time": "America/Adak",
    "Arabian Standard Time": "Asia/Dubai",
    "Argentina Standard Time": "America/Buenos_Aires",
    "Atlantic Standard Time": "America/Halifax",
    "AUS Eastern Standard Time": "Australia/Sydney",
    "Aus Central W. Standard Time": "Australia/Eucla",
    "Azerbaijan Standard Time": "Asia/Baku",
    "Azores Standard Time": "Atlantic/Azores",
    "Bangladesh Standard Time": "Asia/Dhaka",
    "Belarus Standard Time": "Europe/Minsk",
    "Canada Central Standard Time": "America/Regina",
    "Cape Verde Standard Time": "Atlantic/Cape_Verde",
    "Caucasus Standard Time": "Asia/Yerevan",
    "Cen. Australia Standard Time": "Australia/Adelaide",
    "Central America Standard Time": "America/Guatemala",
    "Central Asia Standard Time": "Asia/Almaty",
    "Central Brazilian Standard Time": "America/Cuiaba",
    "Central Europe Standard Time": "Europe/Budapest",
    "Central European Standard Time": "Europe/Warsaw",
    "Central Pacific Standard Time": "Pacific/Guadalcanal",
    "Central Standard Time": "America/Chicago",
    "Central Standard Time (Mexico)": "America/Mexico_City",
    "China Standard Time": "Asia/Shanghai",
    "E. Africa Standard Time": "Africa/Nairobi",
    "E. Australia Standard Time": "Australia/Brisbane",
    "E. Europe Standard Time": "Europe/Chisinau",
    "E. South America Standard Time": "America/Sao_Paulo",
    "Eastern Standard Time": "America/New_York",
    "Eastern Standard Time (Mexico)": "America/Cancun",
    "Egypt Standard Time": "Africa/Cairo",
    "Ekaterinburg Standard Time": "Asia/Yekaterinburg",
    "Fiji Standard Time": "Pacific/Fiji",
    "FLE Standard Time": "Europe/Kiev",
    "Georgian Standard Time": "Asia/Tbilisi",
    "GMT Standard Time": "Europe/London",
    "Greenland Standard Time": "America/Godthab",
    "Greenwich Standard Time": "Atlantic/Reykjavik",
    "GTB Standard Time": "Europe/Bucharest",
    "Hawaiian Standard Time": "Pacific/Honolulu",
    "India Standard Time": "Asia/Kolkata",
    "Iran Standard Time": "Asia/Tehran",
    "Israel Standard Time": "Asia/Jerusalem",
    "Jordan Standard Time": "Asia/Amman",
    "Korea Standard Time": "Asia/Seoul",
    "Libya Standard Time": "Africa/Tripoli",
    "Line Islands Standard Time": "Pacific/Kiritimati",
    "Magadan Standard Time": "Asia/Magadan",
    "Mauritius Standard Time": "Indian/Mauritius",
    "Middle East Standard Time": "Asia/Beirut",
    "Montevideo Standard Time": "America/Montevideo",
    "Morocco Standard Time": "Africa/Casablanca",
    "Mountain Standard Time": "America/Denver",
    "Mountain Standard Time (Mexico)": "America/Mazatlan",
    "Myanmar Standard Time": "Asia/Rangoon",
    "N. Central Asia Standard Time": "Asia/Novosibirsk",
    "Namibia Standard Time": "Africa/Windhoek",
    "Nepal Standard Time": "Asia/Katmandu",
    "New Zealand Standard Time": "Pacific/Auckland",
    "Newfoundland Standard Time": "America/St_Johns",
    "North Asia East Standard Time": "Asia/Irkutsk",
    "North Asia Standard Time": "Asia/Krasnoyarsk",
    "Pacific SA Standard Time": "America/Santiago",
    "Pacific Standard Time": "America/Los_Angeles",
    "Pacific Standard Time (Mexico)": "America/Tijuana",
    "Pakistan Standard Time": "Asia/Karachi",
    "Paraguay Standard Time": "America/Asuncion",
    "Romance Standard Time": "Europe/Paris",
    "Russian Standard Time": "Europe/Moscow",
    "SA Eastern Standard Time": "America/Cayenne",
    "SA Pacific Standard Time": "America/Bogota",
    "SA Western Standard Time": "America/La_Paz",
    "Samoa Standard Time": "Pacific/Apia",
    "SE Asia Standard Time": "Asia/Bangkok",
    "Singapore Standard Time": "Asia/Singapore",
    "South Africa Standard Time": "Africa/Johannesburg",
    "Sri Lanka Standard Time": "Asia/Colombo",
    "Syria Standard Time": "Asia/Damascus",
    "Taipei Standard Time": "Asia/Taipei",
    "Tasmania Standard Time": "Australia/Hobart",
    "Tokyo Standard Time": "Asia/Tokyo",
    "Tonga Standard Time": "Pacific/Tongatapu",
    "Turkey Standard Time": "Europe/Istanbul",
    "Ulaanbaatar Standard Time": "Asia/Ulaanbaatar",
    "US Eastern Standard Time": "America/Indianapolis",
    "US Mountain Standard Time": "America/Phoenix",
    "UTC": "Etc/UTC",
    "UTC+12": "Etc/GMT-12",
    "UTC+13": "Etc/GMT-13",
    "UTC-02": "Etc/GMT+2",
    "UTC-08": "Etc/GMT+8",
    "UTC-09": "Etc/GMT+9",
    "UTC-11": "Etc/GMT+11",
    "Venezuela Standard Time": "America/Caracas",
    "Vladivostok Standard Time": "Asia/Vladivostok",
    "W. Australia Standard Time": "Australia/Perth",
    "W. Central Africa Standard Time": "Africa/Lagos",
    "W. Europe Standard Time": "Europe/Berlin",
    "West Asia Standard Time": "Asia/Tashkent",
    "West Pacific Standard Time": "Pacific/Port_Moresby",
    "Yakutsk Standard Time": "Asia/Yakutsk",
}


@dataclass(frozen=True)
class ParsedEventBounds:
    """UTC busy bounds plus source-zone provenance for ingest."""

    start: datetime
    end: datetime
    is_all_day: bool
    source_timezone: str | None
    source_zone_missing: bool


def windows_to_iana(windows_id: str) -> str | None:
    """Map a Windows timezone id to IANA, or None if unsupported."""
    key = (windows_id or "").strip()
    if not key:
        return None
    return _WINDOWS_TO_IANA.get(key)


def resolve_iana_zone(raw: str | None) -> str | None:
    """Accept IANA or Windows zone names; return canonical IANA or None."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    # Common aliases Graph / Google may emit.
    if text.upper() in ("UTC", "GMT", "Z"):
        return "UTC"
    try:
        ZoneInfo(text)
        return text
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        pass
    mapped = windows_to_iana(text)
    if mapped is None:
        return None
    try:
        ZoneInfo(mapped)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return None
    return mapped


def local_midnight_utc(day: date, iana: str) -> datetime:
    """Source-local midnight of ``day`` as an aware UTC instant (DST-aware)."""
    tz = ZoneInfo(iana)
    local = datetime.combine(day, time.min, tzinfo=tz)
    return local.astimezone(timezone.utc)


def all_day_bounds_utc(
    start_day: date,
    end_day_exclusive: date,
    iana: str,
) -> tuple[datetime, datetime]:
    """Exclusive-end all-day interval in source zone → UTC.

    ``end_day_exclusive`` is the first civil day *not* covered (Google/MS shape).
    """
    if end_day_exclusive <= start_day:
        raise ValueError("all-day exclusive end must be after start day")
    start = local_midnight_utc(start_day, iana)
    end = local_midnight_utc(end_day_exclusive, iana)
    if end <= start:
        raise ValueError("all-day UTC bounds inverted after zone conversion")
    return start, end


def pick_consistent_zone(
    *candidates: str | None,
) -> tuple[str | None, bool]:
    """Resolve candidates to one IANA zone.

    Returns ``(iana, indeterminate)``. Indeterminate when two distinct resolved
    zones are present (fail closed). Missing when none resolve.
    """
    resolved: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        iana = resolve_iana_zone(raw)
        if iana is None:
            continue
        if iana not in seen:
            seen.add(iana)
            resolved.append(iana)
    if len(resolved) > 1:
        return None, True
    if not resolved:
        return None, False
    return resolved[0], False


def parse_civil_date(raw: str | date) -> date:
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    return date.fromisoformat(text[:10])


def utc_midnight_placeholder(start_day: date, end_day_exclusive: date) -> tuple[datetime, datetime]:
    """Untrusted storage placeholder when zone provenance is missing.

    Not a valid busy extent — callers must set ``source_zone_missing`` and keep
    the row out of trusted busy merge.
    """
    start = datetime.combine(start_day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(end_day_exclusive, time.min, tzinfo=timezone.utc)
    return start, end


__all__ = [
    "ParsedEventBounds",
    "all_day_bounds_utc",
    "local_midnight_utc",
    "parse_civil_date",
    "pick_consistent_zone",
    "resolve_iana_zone",
    "utc_midnight_placeholder",
    "windows_to_iana",
]
