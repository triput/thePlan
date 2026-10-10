"""Preview collect clock — immutable proposals must stay apply-able after review."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Ceil wall time to the next UTC minute, then add this lead so the first proposed
# block start remains strictly in the future through a typical review + apply.
PREVIEW_PLANNING_LEAD_SECONDS = 90


def preview_collection_time(wall_now: datetime) -> datetime:
    """Deterministic planning boundary for preview calculate (not apply slide)."""
    utc = wall_now.astimezone(timezone.utc)
    minute_floor = utc.replace(microsecond=0, second=0)
    if utc > minute_floor:
        minute_floor += timedelta(minutes=1)
    return minute_floor + timedelta(seconds=PREVIEW_PLANNING_LEAD_SECONDS)
