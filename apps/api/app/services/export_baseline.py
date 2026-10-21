# ==============================================================================
#  File: apps/api/app/services/export_baseline.py
#  Description: Export comparison baseline capture for mirror push (Track 1 T1-11).
#  Component: Calendar mirror / export baseline
#  Version: 1.0
#  Created: 2026-10-20
#  Last Update: 2026-10-20
# ==============================================================================

"""Export-only comparison baseline for successful mirror pushes (T1-11).

Ingest upsert paths must not write these columns. ``sync_hash`` is untouched.

Remote write vs local commit is not distributed-atomic; this module does not
add reconciliation or retry policy when a transaction rolls back after a
successful provider API call.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.models.enums import CalendarProvider

EXPORT_BASELINE_SCHEMA_VERSION = 1

GOOGLE_MIRROR_PUSH_SOURCE = "google_mirror_push"
MICROSOFT_MIRROR_PUSH_SOURCE = "microsoft_mirror_push"


def _optional_revision_string(value: Any) -> str | None:
    """Accept provider revision tokens; reject malformed shapes without fabricating evidence."""
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _parse_rfc3339_instant(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _ensure_aware_utc(dt: datetime) -> datetime:
    """Naive datetimes are explicit UTC wall clock (mirror writer convention)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def google_mirror_datetime_token(dt: datetime) -> str:
    """ISO-8601 UTC with ``Z`` suffix — matches Google mirror ``dateTime`` bodies."""
    return _ensure_aware_utc(dt).isoformat().replace("+00:00", "Z")


def microsoft_mirror_datetime_token(dt: datetime) -> str:
    """Whole-second UTC local token — matches Graph ``dateTime`` when ``timeZone`` is UTC."""
    return _ensure_aware_utc(dt).strftime("%Y-%m-%dT%H:%M:%S")


def _fingerprint_datetime_tokens(
    *,
    provider: CalendarProvider,
    start: datetime,
    end: datetime,
) -> tuple[str, str]:
    if provider == CalendarProvider.microsoft:
        return (
            microsoft_mirror_datetime_token(start),
            microsoft_mirror_datetime_token(end),
        )
    return (
        google_mirror_datetime_token(start),
        google_mirror_datetime_token(end),
    )


def compute_export_baseline_fingerprint(
    *,
    provider: CalendarProvider,
    title: str,
    start: datetime,
    end: datetime,
    is_all_day: bool,
) -> str:
    """Hash normalized scheduling payload mirror writers send (schema v1)."""
    start_token, end_token = _fingerprint_datetime_tokens(
        provider=provider,
        start=start,
        end=end,
    )
    payload = {
        "v": EXPORT_BASELINE_SCHEMA_VERSION,
        "title": title,
        "start": start_token,
        "end": end_token,
        "is_all_day": bool(is_all_day),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _google_revision_from_response(response: dict[str, Any]) -> tuple[str | None, datetime | None]:
    etag = _optional_revision_string(response.get("etag"))
    updated = _parse_rfc3339_instant(response.get("updated"))
    return etag, updated


def _microsoft_revision_from_response(
    response: dict[str, Any],
) -> tuple[str | None, str | None, datetime | None]:
    etag = _optional_revision_string(response.get("@odata.etag"))
    change_key = _optional_revision_string(response.get("changeKey"))
    updated = _parse_rfc3339_instant(response.get("lastModifiedDateTime"))
    return etag, change_key, updated


def apply_export_baseline_after_mirror_push(
    row: Any,
    *,
    source: str,
    export_calendar_id: str,
    title: str,
    start: datetime,
    end: datetime,
    is_all_day: bool,
    provider: CalendarProvider,
    api_response: dict[str, Any],
    exported_at: datetime,
) -> None:
    """Persist single latest export baseline on successful mirror create/patch."""
    row.export_baseline_at = exported_at
    row.export_baseline_source = source
    row.export_calendar_id = export_calendar_id
    row.export_baseline_fingerprint = compute_export_baseline_fingerprint(
        provider=provider,
        title=title,
        start=start,
        end=end,
        is_all_day=is_all_day,
    )
    row.export_baseline_schema_version = EXPORT_BASELINE_SCHEMA_VERSION

    if provider == CalendarProvider.google:
        etag, updated = _google_revision_from_response(api_response)
        row.export_baseline_etag = etag
        row.export_baseline_change_key = None
        row.export_baseline_updated = updated
    elif provider == CalendarProvider.microsoft:
        etag, change_key, updated = _microsoft_revision_from_response(api_response)
        row.export_baseline_etag = etag
        row.export_baseline_change_key = change_key
        row.export_baseline_updated = updated
    else:
        row.export_baseline_etag = None
        row.export_baseline_change_key = None
        row.export_baseline_updated = None
