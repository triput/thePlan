"""Track 1 T1-B: source-zone provenance, Windows→IANA, DST-aware bounds.

Never reinterpret a known source-local civil day in the owner timezone.
Provider display ``timeZone`` alone is not source provenance (MS Prefer header).

Windows→IANA map source
-----------------------
Territory ``001`` (default) entries from Unicode CLDR ``windowsZones.xml``:

- CLDR release tag: **release-48**
  (https://github.com/unicode-org/cldr/blob/release-48/common/supplemental/windowsZones.xml)
- ``mapTimezones otherVersion="7e11800" typeVersion="2021a"``
- Only ``territory="001"`` defaults are pinned here; unlisted / unsupported
  Windows ids fail closed (``source_zone_missing``), never guessed.

Microsoft Graph decode vs provenance (Dex / Track-1-Contracts §1.3)
-------------------------------------------------------------------
Official: Prefer ``outlook.timezone`` adjusts **returned** start/end display;
``originalStartTimeZone`` / ``originalEndTimeZone`` record creation-zone
provenance
(https://learn.microsoft.com/en-us/graph/api/event-get?view=graph-rest-1.0 —
"Support various time zones"). Without Prefer, Graph returns UTC.

Precedence for this client (Prefer UTC on calendarView):

1. **Decode zone** = response ``start/end.timeZone`` (or explicit offset/Z on
   ``dateTime``). Prefer/display UTC → attach/decode as UTC. Do **not** decode
   timed wall clocks through ``original*``.
2. **Provenance zone** = ``originalStartTimeZone`` / ``originalEndTimeZone``
   (must agree when both present; unsupported explicit values fail closed),
   **else** owning-calendar default. Do not pick originals and calendar
   simultaneously. Stored as ``source_timezone`` when resolved.
3. All-day: recover source-local civil midnights by converting decoded absolute
   instants into the provenance zone. If they are not midnights there, fail
   closed (do not slice the UTC calendar date and reattach provenance).
4. Explicit unsupported zone candidates are never silently skipped in favor of
   another candidate — fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# CLDR windowsZones.xml territory "001" (default) — see module docstring for
# release-48 / otherVersion=7e11800 / typeVersion=2021a citation.
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

# Pinned citation for tests / Dex packet (must match module docstring).
CLDR_WINDOWS_ZONES_RELEASE = "release-48"
CLDR_WINDOWS_ZONES_OTHER_VERSION = "7e11800"
CLDR_WINDOWS_ZONES_TYPE_VERSION = "2021a"
CLDR_WINDOWS_ZONES_URL = (
    "https://github.com/unicode-org/cldr/blob/release-48/"
    "common/supplemental/windowsZones.xml"
)


class IndeterminateLocalTime(ValueError):
    """Naive wall clock is ambiguous or nonexistent in the target zone."""


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


def attach_naive_wall_clock(naive: datetime, iana: str) -> datetime:
    """Attach ``iana`` to a naive wall clock → aware UTC.

    Detects DST gap and fold ambiguity (does **not** silently use ``fold=0``).
    Raises ``IndeterminateLocalTime`` when the local civil time is not unique.
    """
    if naive.tzinfo is not None:
        raise ValueError("attach_naive_wall_clock expects a naive datetime")
    tz = ZoneInfo(iana)
    fold0 = naive.replace(tzinfo=tz, fold=0)
    fold1 = naive.replace(tzinfo=tz, fold=1)
    if fold0.utcoffset() != fold1.utcoffset():
        raise IndeterminateLocalTime(
            f"ambiguous or nonexistent local time in {iana}: {naive.isoformat()}"
        )
    back = fold0.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)
    if back != naive:
        raise IndeterminateLocalTime(
            f"nonexistent local time in {iana}: {naive.isoformat()}"
        )
    return fold0.astimezone(timezone.utc)


def local_midnight_utc(day: date, iana: str) -> datetime:
    """Source-local midnight of ``day`` as an aware UTC instant (DST-aware)."""
    naive = datetime.combine(day, time.min)
    return attach_naive_wall_clock(naive, iana)


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

    Returns ``(iana, indeterminate)``.

    - Indeterminate when two distinct resolved zones are present, **or** when any
      non-empty candidate fails to resolve (unsupported must not be skipped in
      favor of another candidate).
    - Missing when no non-empty candidates were supplied.
    """
    resolved: list[str] = []
    seen: set[str] = set()
    had_explicit_unresolved = False
    for raw in candidates:
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        iana = resolve_iana_zone(text)
        if iana is None:
            had_explicit_unresolved = True
            continue
        if iana not in seen:
            seen.add(iana)
            resolved.append(iana)
    if had_explicit_unresolved:
        return None, True
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


def is_local_midnight(aware: datetime) -> bool:
    """True when ``aware`` is exactly civil midnight in its own tzinfo."""
    local = aware
    return local.hour == 0 and local.minute == 0 and local.second == 0 and local.microsecond == 0


__all__ = [
    "CLDR_WINDOWS_ZONES_OTHER_VERSION",
    "CLDR_WINDOWS_ZONES_RELEASE",
    "CLDR_WINDOWS_ZONES_TYPE_VERSION",
    "CLDR_WINDOWS_ZONES_URL",
    "IndeterminateLocalTime",
    "ParsedEventBounds",
    "all_day_bounds_utc",
    "attach_naive_wall_clock",
    "is_local_midnight",
    "local_midnight_utc",
    "parse_civil_date",
    "pick_consistent_zone",
    "resolve_iana_zone",
    "utc_midnight_placeholder",
    "windows_to_iana",
]
