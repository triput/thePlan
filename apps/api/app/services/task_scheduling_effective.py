"""Read model for task scheduling provenance (S1: placer-active vs pending)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models import (
    AvailabilityPolicy,
    Epic,
    FocusWindow,
    Project,
    Task,
    User,
    UserSettings,
)
from app.models.enums import AvailabilityPolicySlug
from app.scheduler.task_effort import placement_effort_minutes
from app.scheduler.time_map_overrides import (
    applicable_override_payload,
    bands_for_day,
    effective_day_map,
    effective_local_date_for_scheduling_day,
    load_time_map_overrides_for_maps,
    select_override_for_scheduling_day,
)
from app.scheduler.windows import (
    effective_preferred_time_window_id,
    effective_preferred_time_window_source,
)
from app.schemas.availability import AvailabilityWindowOut, SCHEDULING_CONFIG_ONLY_COPY
from app.schemas.hierarchy import TimeMapBandOut
from app.schemas.task_scheduling import (
    DatedOverrideDetailOut,
    DatedOverrideReplacesOut,
    DatedResolutionOut,
    DurationEffectiveOut,
    LegacyWorkweekActiveOut,
    SavedAvailabilityPolicyOut,
    SchedulingSourceOut,
    TaskSchedulingEffectiveOut,
    TimeMapEffectiveOut,
    TimeMapEmptyKind,
    TimeMapOriginOut,
)
from app.services.auth_users import get_or_provision_user_settings


def _policy_for_slug(
    db: Session, user: User, slug: AvailabilityPolicySlug
) -> AvailabilityPolicy | None:
    return (
        db.query(AvailabilityPolicy)
        .options(joinedload(AvailabilityPolicy.windows))
        .filter(
            AvailabilityPolicy.owner_id == user.id,
            AvailabilityPolicy.slug == slug,
        )
        .one_or_none()
    )


@dataclass(frozen=True)
class _WorkingMirrorPreview:
    kind: Literal["empty", "mirrored", "config_only", "invalid"]
    workweek_days: int | None = None
    workday_start_local: time | None = None
    workday_minutes: int | None = None


def _preview_workweek_mirror_from_working_windows(windows: list) -> _WorkingMirrorPreview:
    """Read-only mirror preview (same rules as write sync). Never raises or mutates settings."""
    if not windows:
        return _WorkingMirrorPreview(kind="empty")
    by_weekday: dict[int, object] = {}
    for window in windows:
        if window.weekday in by_weekday:
            return _WorkingMirrorPreview(kind="invalid")
        by_weekday[window.weekday] = window
    weekdays = sorted(by_weekday)
    if weekdays != list(range(weekdays[0], weekdays[0] + len(weekdays))):
        return _WorkingMirrorPreview(kind="invalid")
    durations = {window.duration_minutes for window in by_weekday.values()}
    starts = {window.start_time for window in by_weekday.values()}
    if len(durations) != 1 or len(starts) != 1:
        return _WorkingMirrorPreview(kind="invalid")
    if weekdays != list(range(len(weekdays))):
        return _WorkingMirrorPreview(kind="config_only")
    anchor = by_weekday[weekdays[0]]
    return _WorkingMirrorPreview(
        kind="mirrored",
        workweek_days=len(weekdays),
        workday_start_local=anchor.start_time,
        workday_minutes=anchor.duration_minutes,
    )


def _working_divergence(
    settings: UserSettings,
    windows: list,
) -> tuple[bool, str | None]:
    preview = _preview_workweek_mirror_from_working_windows(windows)
    if preview.kind == "invalid":
        return (
            True,
            "Saved Working windows use a non-mirrorable pattern (ambiguous, gapped, or "
            "heterogeneous); placer uses legacy workweek_*.",
        )
    if preview.kind == "empty":
        if settings.workweek_days != 0:
            return (
                True,
                "Saved Working has no windows (workweek_days=0 when synced) but legacy "
                "workweek_* still shows open days; placer uses legacy workweek_*.",
            )
        return False, None
    if preview.kind == "config_only":
        return (
            True,
            "Saved Working weekdays or hours cannot mirror into legacy workweek_* (config-only "
            "until S2); placer uses legacy workweek_*.",
        )
    assert preview.workweek_days is not None
    assert preview.workday_start_local is not None
    assert preview.workday_minutes is not None
    diverges = (
        preview.workweek_days != settings.workweek_days
        or preview.workday_start_local != settings.workday_start_local
        or preview.workday_minutes != settings.workday_minutes
    )
    if diverges:
        return (
            True,
            "Saved Working mirrors a Monday-first pattern but legacy workweek_* "
            "differs (likely a direct settings edit). Placer uses legacy workweek_*.",
        )
    return False, None


def _bands_out(bands: list) -> list[TimeMapBandOut]:
    return [TimeMapBandOut.model_validate(band) for band in bands]


def _empty_kind_for_map(
    *,
    has_assignment: bool,
    strict_mode: bool,
    band_count: int,
) -> TimeMapEmptyKind:
    if not has_assignment:
        return TimeMapEmptyKind.no_assignment_fallback
    if band_count > 0:
        return TimeMapEmptyKind.not_applicable
    if strict_mode:
        return TimeMapEmptyKind.assigned_empty_strict
    return TimeMapEmptyKind.assigned_empty_nonstrict


def _saved_policy_out(
    policy: AvailabilityPolicy | None,
    *,
    slug: AvailabilityPolicySlug,
    default_note: str,
    settings: UserSettings | None = None,
    check_divergence: bool = False,
) -> SavedAvailabilityPolicyOut:
    if policy is None:
        return SavedAvailabilityPolicyOut(
            slug=slug.value,
            note=f"No {slug.value} policy row found for owner.",
        )
    diverges: bool | None = None
    divergence_note: str | None = None
    if check_divergence and settings is not None:
        diverges, divergence_note = _working_divergence(settings, list(policy.windows))
    return SavedAvailabilityPolicyOut(
        policy_id=policy.id,
        slug=policy.slug.value,
        name=policy.name,
        windows=[
            AvailabilityWindowOut.model_validate(row)
            for row in sorted(policy.windows, key=lambda w: (w.weekday, w.sort_order))
        ],
        placer_active=False,
        saved_but_unsupported=True,
        note=default_note,
        diverges_from_legacy=diverges,
        divergence_note=divergence_note,
    )


def _build_dated_resolution(
    db: Session,
    user: User,
    *,
    on: date | None,
    settings: UserSettings,
    focus_window: FocusWindow | None,
    window_source: str | None,
) -> DatedResolutionOut:
    operator_tz = settings.timezone
    if on is None:
        return DatedResolutionOut(
            performed=False,
            on=None,
            operator_timezone=operator_tz,
            override=None,
            replaces=None,
            note=(
                "Dated Time Map override resolution was not performed. Pass query "
                "parameter `on` (YYYY-MM-DD in operator timezone) to evaluate overrides "
                "for a scheduling day."
            ),
        )

    if focus_window is None:
        return DatedResolutionOut(
            performed=True,
            on=on,
            operator_timezone=operator_tz,
            override=None,
            replaces=None,
            note="No effective Time Map assignment; override resolution has no map scope.",
        )

    overrides_by_map = load_time_map_overrides_for_maps(
        db,
        user.id,
        {focus_window.id},
    )
    override_rows = overrides_by_map.get(focus_window.id, [])
    selected = select_override_for_scheduling_day(
        override_rows,
        day=on,
        settings=settings,
    )
    base_day_bands = bands_for_day(list(focus_window.bands), on)
    effective_bands, effective_strict = effective_day_map(focus_window, selected, on)

    if selected is None:
        return DatedResolutionOut(
            performed=True,
            on=on,
            operator_timezone=operator_tz,
            override=None,
            replaces=None,
            note="Dated override resolution performed; no override applies on this scheduling day.",
        )

    effective_local = effective_local_date_for_scheduling_day(on, settings, selected)
    payload = applicable_override_payload(selected, effective_local)
    payload["inheritance_source"] = window_source
    payload["base_map_id"] = str(focus_window.id)

    override_detail = DatedOverrideDetailOut(
        override_id=selected.id,
        map_id=selected.map_id,
        local_start_date=selected.local_start_date,
        local_end_date=selected.local_end_date,
        timezone=selected.timezone,
        strict_mode=selected.strict_mode,
        effective_local_date=effective_local,
        payload=payload,
    )
    replaces = DatedOverrideReplacesOut(
        base_map_id=focus_window.id,
        inheritance_source=window_source,
        operator_scheduling_day=on,
        base_strict_mode=focus_window.strict_mode,
        effective_strict_mode=effective_strict,
        base_day_band_count=len(base_day_bands),
        effective_day_band_count=len(effective_bands),
        base_day_bands=_bands_out(base_day_bands),
        effective_day_bands=_bands_out(effective_bands),
    )
    return DatedResolutionOut(
        performed=True,
        on=on,
        operator_timezone=operator_tz,
        override=override_detail,
        replaces=replaces,
        note="Override replaces this scheduling day's bands and strict_mode on the effective map.",
    )


def _build_sources(
    *,
    settings: UserSettings,
    window_id: UUID | None,
    window_source: str | None,
    map_label: str | None,
    working_saved: SavedAvailabilityPolicyOut,
    general_saved: SavedAvailabilityPolicyOut,
    personal_saved: SavedAvailabilityPolicyOut,
    time_map: TimeMapEffectiveOut,
) -> list[SchedulingSourceOut]:
    sources: list[SchedulingSourceOut] = []

    sources.append(
        SchedulingSourceOut(
            kind="legacy_workweek",
            label="Working hours (legacy workweek settings)",
            placer_active=True,
            detail=(
                f"workweek_days={settings.workweek_days}, "
                f"workday_start={settings.workday_start_local.strftime('%H:%M')}, "
                f"workday_minutes={settings.workday_minutes}, tz={settings.timezone}"
            ),
        )
    )

    if window_id is not None:
        sources.append(
            SchedulingSourceOut(
                kind="legacy_time_map",
                label=f"Time Map ({window_source or 'unknown'})",
                placer_active=True,
                detail=map_label or str(window_id),
            )
        )
    else:
        sources.append(
            SchedulingSourceOut(
                kind="legacy_unclassified",
                label="Unclassified eligibility (legacy global workweek)",
                placer_active=True,
                detail="General policy link is config-only until S2",
            )
        )

    sources.append(
        SchedulingSourceOut(
            kind="availability_general",
            label="General availability policy",
            placer_active=False,
            detail=general_saved.note or "Seeded/edited in Settings; not used by placer in S1",
        )
    )

    work_detail = working_saved.note or (
        "Mirrors workweek when edited; placer still reads workweek_* in S1"
    )
    if working_saved.diverges_from_legacy:
        work_detail = (
            f"{work_detail} Diverges from active legacy: {working_saved.divergence_note}"
        )
    sources.append(
        SchedulingSourceOut(
            kind="availability_work",
            label="Working availability policy",
            placer_active=False,
            detail=work_detail,
        )
    )
    sources.append(
        SchedulingSourceOut(
            kind="availability_personal",
            label="Personal availability policy",
            placer_active=False,
            detail=personal_saved.note or "Named policy; not unioned into General in S1",
        )
    )

    if time_map.empty_kind == TimeMapEmptyKind.assigned_empty_strict:
        sources.append(
            SchedulingSourceOut(
                kind="time_map_empty_strict",
                label="Assigned Time Map has no bands (strict)",
                placer_active=True,
                detail="Strict empty map: no eligible windows from this map",
            )
        )
    elif time_map.empty_kind == TimeMapEmptyKind.assigned_empty_nonstrict:
        sources.append(
            SchedulingSourceOut(
                kind="time_map_empty_nonstrict",
                label="Assigned Time Map has no bands (non-strict)",
                placer_active=True,
                detail="Non-strict empty map: neutral workday fallback within map context",
            )
        )

    return sources


def build_task_scheduling_effective(
    db: Session,
    user: User,
    task: Task,
    *,
    on: date | None = None,
) -> TaskSchedulingEffectiveOut:
    settings = get_or_provision_user_settings(db, user)
    project: Project | None = None
    epic: Epic | None = None
    if task.project_id is not None:
        project = db.get(Project, task.project_id)
        if project is not None and project.epic_id is not None:
            epic = db.get(Epic, project.epic_id)

    window_id = effective_preferred_time_window_id(task, project, epic)
    window_source = effective_preferred_time_window_source(task, project, epic)

    focus_window: FocusWindow | None = None
    if window_id is not None:
        focus_window = (
            db.query(FocusWindow)
            .options(joinedload(FocusWindow.bands))
            .filter(FocusWindow.id == window_id)
            .one_or_none()
        )

    dated = _build_dated_resolution(
        db,
        user,
        on=on,
        settings=settings,
        focus_window=focus_window,
        window_source=window_source,
    )

    map_strict = focus_window.strict_mode if focus_window is not None else False
    map_band_count = len(focus_window.bands) if focus_window is not None else 0

    if on is not None and focus_window is not None and dated.replaces is not None:
        display_bands = dated.replaces.effective_day_bands
        display_strict = dated.replaces.effective_strict_mode
        display_band_count = dated.replaces.effective_day_band_count
    elif on is not None and focus_window is not None:
        day_bands = bands_for_day(list(focus_window.bands), on)
        display_bands = _bands_out(day_bands)
        display_strict = focus_window.strict_mode
        display_band_count = len(day_bands)
    elif focus_window is not None:
        display_bands = _bands_out(list(focus_window.bands))
        display_strict = focus_window.strict_mode
        display_band_count = map_band_count
    else:
        display_bands = []
        display_strict = None
        display_band_count = 0

    has_assignment = window_id is not None
    empty_kind = _empty_kind_for_map(
        has_assignment=has_assignment,
        strict_mode=map_strict,
        band_count=map_band_count,
    )

    map_name = focus_window.name if focus_window is not None else None
    time_map = TimeMapEffectiveOut(
        assignment_status="assigned" if has_assignment else "unclassified_fallback",
        origin=TimeMapOriginOut(
            effective_source=window_source,
            task_preferred_time_window_id=task.preferred_time_window_id,
            project_preferred_time_window_id=(
                project.preferred_time_window_id if project is not None else None
            ),
            epic_preferred_time_window_id=epic.preferred_time_window_id if epic is not None else None,
        ),
        effective_map_id=window_id,
        map_name=map_name,
        strict_mode=display_strict,
        band_count=display_band_count,
        bands=display_bands,
        empty_kind=empty_kind,
        placer_active=True,
    )

    working_policy = _policy_for_slug(db, user, AvailabilityPolicySlug.work)
    general_policy = _policy_for_slug(db, user, AvailabilityPolicySlug.general)
    personal_policy = _policy_for_slug(db, user, AvailabilityPolicySlug.personal)

    working_saved = _saved_policy_out(
        working_policy,
        slug=AvailabilityPolicySlug.work,
        default_note=(
            "Saved Working availability; placer reads legacy workweek_* in S1. "
            "Monday-first same-hours PATCH may mirror into workweek_*."
        ),
        settings=settings,
        check_divergence=True,
    )
    general_saved = _saved_policy_out(
        general_policy,
        slug=AvailabilityPolicySlug.general,
        default_note="Saved General availability; not scheduling-effective until S2.",
    )
    personal_saved = _saved_policy_out(
        personal_policy,
        slug=AvailabilityPolicySlug.personal,
        default_note="Saved Personal availability; not unioned into placer eligibility in S1.",
    )

    working_hours_active = LegacyWorkweekActiveOut(
        workweek_days=settings.workweek_days,
        workday_start_local=settings.workday_start_local,
        workday_minutes=settings.workday_minutes,
        timezone=settings.timezone,
        placer_active=True,
    )

    effort = placement_effort_minutes(task)
    duration = DurationEffectiveOut(
        original_estimate_minutes=task.estimated_duration_minutes,
        worked_minutes=task.worked_minutes,
        remaining_minutes=task.remaining_minutes,
        placement_effort_minutes=effort,
        min_block_duration_minutes=task.min_block_duration_minutes,
        max_block_duration_minutes=task.max_block_duration_minutes,
        max_block_unbounded=task.max_block_unbounded,
        keep_in_one_block=task.keep_in_one_block,
    )

    sources = _build_sources(
        settings=settings,
        window_id=window_id,
        window_source=window_source,
        map_label=map_name,
        working_saved=working_saved,
        general_saved=general_saved,
        personal_saved=personal_saved,
        time_map=time_map,
    )

    return TaskSchedulingEffectiveOut(
        task_id=task.id,
        scheduling_effective_note=SCHEDULING_CONFIG_ONLY_COPY,
        placement_effort_minutes=effort,
        sources=sources,
        legacy_time_map_id=window_id,
        legacy_time_map_source=window_source,
        general_policy_scheduling_effective=False,
        working_hours_placer_active=True,
        time_map=time_map,
        working_hours_active=working_hours_active,
        working_policy_saved=working_saved,
        general_policy_saved=general_saved,
        personal_policy_saved=personal_saved,
        dated_resolution=dated,
        duration=duration,
    )
