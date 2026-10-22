"""Covering-refresh pull window (Decision 2 §2.2).

Phase 1 freeze: ``window_effective`` is always the UTC-normalized requested
window. ``widened`` is always false. There is no pad branch.

``effective_covering_pull_window`` does not read settings, horizons, or stored
coverage. Scheduling pad (``required_coverage_window``) is a readiness concern
and must not be applied here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import NamedTuple

# Operator-visible span cap (§2.3). Exactly 42 days is allowed; longer is not.
COVERING_PULL_WINDOW_MAX = timedelta(days=42)

WINDOW_CODE_INVALID = "CALENDAR_WINDOW_INVALID"
WINDOW_CODE_TOO_LARGE = "CALENDAR_WINDOW_TOO_LARGE"

# Frozen response tokens. Not parameters.
COVERING_WINDOW_WIDENED = False
COVERING_WINDOW_WIDEN_REASON = "none"


class CoveringWindowError(Exception):
    """Typed window rejection. Justin maps ``code`` to HTTP 422.

    ``CALENDAR_WINDOW_TOO_LARGE`` is the over-cap code. ``CALENDAR_WINDOW_INVALID``
    covers non-datetimes and ``end <= start`` after UTC normalization.
    """

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class CoveringPullWindow(NamedTuple):
    """Tuple return: ``(effective_start, effective_end, widened, reason)``."""

    effective_start: datetime
    effective_end: datetime
    widened: bool
    reason: str


def _normalize_utc(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise CoveringWindowError(
            WINDOW_CODE_INVALID,
            f"{field_name} must be a datetime",
        )
    if value.tzinfo is None:
        # Same rule as calendar_coverage._ensure_utc: naive means UTC.
        # The route still owes timezone-aware ISO-8601; this helper will not
        # invent a host-local zone.
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def effective_covering_pull_window(
    requested_start: datetime,
    requested_end: datetime,
) -> CoveringPullWindow:
    """Return the Phase 1 covering pull bounds.

    ``(effective_start, effective_end, widened=False, reason="none")``.

    Effective bounds always equal the UTC-normalized request. A span longer
    than 42 days raises ``CoveringWindowError`` with code
    ``CALENDAR_WINDOW_TOO_LARGE``. ``end <= start`` raises
    ``CALENDAR_WINDOW_INVALID``.
    """
    start = _normalize_utc(requested_start, field_name="requested_start")
    end = _normalize_utc(requested_end, field_name="requested_end")
    if end <= start:
        raise CoveringWindowError(
            WINDOW_CODE_INVALID,
            "window_end must be after window_start",
        )
    if end - start > COVERING_PULL_WINDOW_MAX:
        raise CoveringWindowError(
            WINDOW_CODE_TOO_LARGE,
            "window span exceeds 42 days",
        )
    return CoveringPullWindow(
        effective_start=start,
        effective_end=end,
        widened=COVERING_WINDOW_WIDENED,
        reason=COVERING_WINDOW_WIDEN_REASON,
    )
