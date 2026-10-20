"""T1-C: per-subscription coverage evidence and refresh generation/atomicity.

In-process refreshes for the same subscription are serialized (``subscription_refresh_lock``).
Mid-refresh failure clears success evidence at refresh start; ``coverage_last_failure_*``
keeps the subscription not-ready even if cache rows roll back to a prior generation.
"""

from __future__ import annotations

import hashlib
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator
from uuid import UUID

from app.models import CalendarSubscription

_lock_guard = threading.Lock()
_subscription_locks: dict[UUID, threading.Lock] = {}


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def token_fingerprint(token: str | None) -> str | None:
    if not token:
        return None
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


@contextmanager
def subscription_refresh_lock(subscription_id: UUID) -> Iterator[None]:
    with _lock_guard:
        lock = _subscription_locks.setdefault(subscription_id, threading.Lock())
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


def begin_subscription_refresh(subscription: CalendarSubscription, *, now: datetime) -> int:
    """Bump active generation and clear success evidence before cache mutation."""
    now = _ensure_utc(now)
    generation = int(subscription.coverage_active_generation or 0) + 1
    subscription.coverage_active_generation = generation
    subscription.coverage_success_at = None
    subscription.coverage_fetched_at = None
    subscription.coverage_success_generation = None
    subscription.coverage_pagination_complete = False
    subscription.coverage_window_start = None
    subscription.coverage_window_end = None
    subscription.coverage_mode = None
    subscription.coverage_show_deleted = None
    subscription.coverage_single_events = None
    subscription.coverage_page_count = None
    subscription.coverage_item_count = None
    subscription.coverage_token_fingerprint = None
    return generation


def commit_subscription_coverage_success(
    subscription: CalendarSubscription,
    *,
    now: datetime,
    window_start: datetime,
    window_end: datetime,
    mode: str,
    pagination_complete: bool,
    page_count: int,
    item_count: int,
    show_deleted: bool | None,
    single_events: bool | None,
    sync_token: str | None,
    generation: int,
) -> None:
    now = _ensure_utc(now)
    subscription.coverage_window_start = _ensure_utc(window_start)
    subscription.coverage_window_end = _ensure_utc(window_end)
    subscription.coverage_mode = mode
    subscription.coverage_fetched_at = now
    subscription.coverage_success_at = now
    subscription.coverage_pagination_complete = pagination_complete
    subscription.coverage_success_generation = generation
    subscription.coverage_show_deleted = show_deleted
    subscription.coverage_single_events = single_events
    subscription.coverage_page_count = page_count
    subscription.coverage_item_count = item_count
    subscription.coverage_token_fingerprint = token_fingerprint(sync_token)
    subscription.coverage_last_failure_at = None
    subscription.coverage_last_failure_cause = None


def record_subscription_refresh_failure(
    subscription: CalendarSubscription,
    *,
    now: datetime,
    cause: str,
) -> None:
    subscription.coverage_last_failure_at = _ensure_utc(now)
    subscription.coverage_last_failure_cause = cause[:128]


def invalidate_subscription_coverage(
    subscription: CalendarSubscription,
    *,
    now: datetime,
    cause: str,
    clear_sync_cursor: bool = False,
) -> None:
    """Clear success freshness (410, horizon widen, etc.) without minting new success."""
    begin_subscription_refresh(subscription, now=now)
    record_subscription_refresh_failure(subscription, now=now, cause=cause)
    if clear_sync_cursor:
        subscription.sync_cursor = None


def coverage_window_wider_than(
    subscription: CalendarSubscription,
    *,
    required_start: datetime,
    required_end: datetime,
) -> bool:
    start = subscription.coverage_window_start
    end = subscription.coverage_window_end
    if start is None or end is None:
        return True
    rs = _ensure_utc(required_start)
    re = _ensure_utc(required_end)
    return rs < _ensure_utc(start) or re > _ensure_utc(end)
