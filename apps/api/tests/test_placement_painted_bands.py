"""Scheduler placement tests for painted time map bands."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.models import FocusWindow, TimeMapBand, UserSettings
from app.models.enums import TimeMapBandTier
from app.scheduler.placement import _search_windows_for_day, place_task


def _settings(**overrides: object) -> UserSettings:
    settings = UserSettings(owner_id=uuid4())
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def _map(*bands: tuple[TimeMapBandTier, time, time], strict_mode: bool = False) -> FocusWindow:
    window = FocusWindow(owner_id=uuid4(), name="Test Map", strict_mode=strict_mode)
    for index, (tier, start, end) in enumerate(bands):
        window.bands.append(
            TimeMapBand(
                tier=tier,
                start_time=start,
                end_time=end,
                days_of_week=127,
                sort_order=index,
            )
        )
    return window


def _window_starts(windows: list[tuple[datetime, datetime]]) -> list[datetime]:
    return [start for start, _ in windows]


def test_green_preferred_before_yellow() -> None:
    settings = _settings(
        timezone="UTC",
        workday_start_local=time(8, 0),
        workday_minutes=600,
        workweek_days=7,
    )
    tz = ZoneInfo("UTC")
    day = date(2026, 8, 11)
    preferred = _map(
        (TimeMapBandTier.green, time(9, 0), time(12, 0)),
        (TimeMapBandTier.yellow, time(12, 0), time(17, 0)),
    )

    windows = _search_windows_for_day(day, settings, tz, preferred)
    starts = _window_starts(windows)

    assert starts[0] == datetime(2026, 8, 11, 9, 0, tzinfo=timezone.utc)
    assert starts[1] == datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    assert len(windows) >= 3


def test_red_excluded_from_neutral() -> None:
    settings = _settings(
        timezone="UTC",
        workday_start_local=time(8, 0),
        workday_minutes=540,
        workweek_days=7,
    )
    tz = ZoneInfo("UTC")
    day = date(2026, 8, 11)
    preferred = _map((TimeMapBandTier.red, time(10, 0), time(14, 0)))

    windows = _search_windows_for_day(day, settings, tz, preferred)
    starts = _window_starts(windows)
    ends = [end for _, end in windows]

    assert datetime(2026, 8, 11, 8, 0, tzinfo=timezone.utc) in starts
    assert datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc) in starts
    assert not any(
        start < datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc)
        and end > datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)
        for start, end in windows
    )


def test_strict_mode_no_neutral_spill() -> None:
    settings = _settings(
        timezone="UTC",
        workday_start_local=time(8, 0),
        workday_minutes=540,
        workweek_days=7,
    )
    tz = ZoneInfo("UTC")
    day = date(2026, 8, 11)
    preferred = _map(
        (TimeMapBandTier.green, time(9, 0), time(10, 0)),
        strict_mode=True,
    )

    windows = _search_windows_for_day(day, settings, tz, preferred)
    assert len(windows) == 1
    assert windows[0] == (
        datetime(2026, 8, 11, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc),
    )


def test_multi_band_morning_evening_green() -> None:
    settings = _settings(
        timezone="UTC",
        workday_start_local=time(8, 0),
        workday_minutes=780,
        workweek_days=7,
    )
    tz = ZoneInfo("UTC")
    day = date(2026, 8, 11)
    preferred = _map(
        (TimeMapBandTier.green, time(8, 0), time(12, 0)),
        (TimeMapBandTier.green, time(17, 0), time(21, 0)),
    )

    windows = _search_windows_for_day(day, settings, tz, preferred)
    starts = _window_starts(windows)

    assert datetime(2026, 8, 11, 8, 0, tzinfo=timezone.utc) in starts
    assert datetime(2026, 8, 11, 17, 0, tzinfo=timezone.utc) in starts


def test_place_task_uses_green_before_yellow(
    db_session,
    client,
    monkeypatch,
) -> None:
    import app.scheduler.placement as placement_mod

    fixed_now = datetime(2026, 8, 11, 7, 0, tzinfo=timezone.utc)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            if tz is not None:
                return fixed_now.astimezone(tz)
            return fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(placement_mod, "datetime", FixedDatetime)

    client.patch(
        "/api/v1/settings",
        json={
            "timezone": "UTC",
            "workweek_days": 7,
            "upcoming_horizon_days": 1,
            "inter_block_buffer_minutes": 0,
            "workday_start_local": "08:00",
            "workday_minutes": 600,
        },
    )

    created = client.post(
        "/api/v1/focus-windows",
        json={
            "name": "Painted",
            "bands": [
                {
                    "tier": "yellow",
                    "start_time": "08:00",
                    "end_time": "17:00",
                    "days_of_week": 127,
                    "sort_order": 1,
                },
                {
                    "tier": "green",
                    "start_time": "14:00",
                    "end_time": "16:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    window_id = created.json()["id"]

    from uuid import UUID

    from sqlalchemy.orm import joinedload

    from app.models import Task

    owner_id = UUID(client.get("/api/v1/auth/me").json()["id"])
    task = Task(
        owner_id=owner_id,
        title="Band order task",
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=120,
        preferred_time_window_id=UUID(window_id),
    )
    db_session.add(task)
    db_session.flush()

    settings = _settings(
        timezone="UTC",
        workday_start_local=time(8, 0),
        workday_minutes=600,
        workweek_days=7,
        inter_block_buffer_minutes=0,
        default_min_block_duration_minutes=15,
    )
    preferred = (
        db_session.query(FocusWindow)
        .options(joinedload(FocusWindow.bands))
        .filter(FocusWindow.id == UUID(window_id))
        .one()
    )

    horizon_start = fixed_now
    horizon_end = fixed_now.replace(hour=23, minute=59)

    result, _ = place_task(
        db_session,
        task=task,
        owner_id=owner_id,
        settings=settings,
        remaining_minutes=30,
        busy=[],
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        preferred_windows={preferred.id: preferred},
        now_utc=fixed_now,
    )
    assert result.blocks_created == 1
    block = task.scheduled_blocks[0]
    assert block.start_time == datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc)
