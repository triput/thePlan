"""Read model for task scheduling provenance (S1: placer-active vs pending)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
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
    EffectiveSchedulingDaySegment,
    applicable_override_payload,
    bands_for_day,
    effective_local_date_for_scheduling_day,
    effective_scheduling_day_segments,
    load_time_map_overrides_for_maps,
    segments_cover_full_scheduling_day_with_single_override,
)
from app.scheduler.assignment_resolve import resolve_task_scheduling_assignment
from app.scheduler.windows import (
    effective_preferred_time_window_id,
    effective_preferred_time_window_source,
)
from app.schemas.availability import AvailabilityWindowOut
from app.schemas.hierarchy import TimeMapBandOut
from app.schemas.task_scheduling import (
    DatedOverrideDetailOut,
    DatedOverrideReplacesOut,
    DatedResolutionOut,
    DatedSchedulingSegmentOut,
    DurationEffectiveOut,
    InheritedBlockBoundsPreview,
    LegacyWorkweekActiveOut,
    SavedAvailabilityPolicyOut,
    SchedulingSourceOut,
    TaskSchedulingEffectiveOut,
    TimeMapEffectiveOut,
    TimeMapEmptyKind,
    TimeMapOriginOut,
)
from app.services.auth_users import get_or_provision_user_settings
from app.services.chunking_effective import resolve_block_bounds
from app.services.keep_in_one_conflicts import keep_in_one_scheduling_conflicts
from app.services.s2_v3_availability_guard import (
    V3_DIVERGENCE_ACTIVATION_NOTE,
    V3_NEW_RULE_INACTIVE_NOTE,
    s2_v3_availability_cutover_live,
    scheduling_effective_note_for_surface,
)
from app.services.task_chunking_guard import chunking_cutover_writes_unlocked


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
    v3 = s2_v3_availability_cutover_live()
    if preview.kind == "invalid":
        if v3:
            return (
                True,
                "Saved Working windows use a non-mirrorable pattern (ambiguous, gapped, or "
                "heterogeneous). Placer reads saved Working after S2-V3; legacy workweek_* "
                "is inactive provenance.",
            )
        return (
            True,
            "Saved Working windows use a non-mirrorable pattern (ambiguous, gapped, or "
            "heterogeneous); placer uses legacy workweek_*.",
        )
    if preview.kind == "empty":
        if settings.workweek_days != 0:
            if v3:
                return (
                    True,
                    "Saved Working has no windows but legacy workweek_* still shows open days. "
                    f"{V3_DIVERGENCE_ACTIVATION_NOTE}",
                )
            return (
                True,
                "Saved Working has no windows (workweek_days=0 when synced) but legacy "
                "workweek_* still shows open days; placer uses legacy workweek_*.",
            )
        return False, None
    if preview.kind == "config_only":
        if v3:
            return (
                True,
                "Saved Working weekdays or hours do not mirror legacy workweek_* (expected "
                "after S2-V3). Placer reads saved Working; legacy mirror is inactive "
                "provenance.",
            )
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
        if v3:
            return (
                True,
                f"Saved Working differs from legacy workweek_* mirror. {V3_DIVERGENCE_ACTIVATION_NOTE}",
            )
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


def _empty_kind_from_segments(
    *,
    has_assignment: bool,
    segments: list[EffectiveSchedulingDaySegment],
) -> TimeMapEmptyKind:
    if not has_assignment:
        return TimeMapEmptyKind.no_assignment_fallback
    if any(segment.bands for segment in segments):
        return TimeMapEmptyKind.not_applicable
    if segments and all(segment.strict_mode for segment in segments):
        return TimeMapEmptyKind.assigned_empty_strict
    return TimeMapEmptyKind.assigned_empty_nonstrict


def _unique_bands_out(segments: list[EffectiveSchedulingDaySegment]) -> list[TimeMapBandOut]:
    seen: set[str] = set()
    ordered: list[TimeMapBandOut] = []
    for segment in segments:
        for band in segment.bands:
            key = str(getattr(band, "id", None) or id(band))
            if key in seen:
                continue
            seen.add(key)
            ordered.append(TimeMapBandOut.model_validate(band))
    return ordered


def _segments_out(
    segments: list[EffectiveSchedulingDaySegment],
) -> list[DatedSchedulingSegmentOut]:
    return [
        DatedSchedulingSegmentOut(
            start=segment.start,
            end=segment.end,
            source=segment.source,
            override_id=segment.day_override.id if segment.day_override is not None else None,
            strict_mode=segment.strict_mode,
            day_bands=_bands_out(segment.bands),
        )
        for segment in segments
    ]


def _saved_policy_out(
    policy: AvailabilityPolicy | None,
    *,
    slug: AvailabilityPolicySlug,
    default_note: str,
    settings: UserSettings | None = None,
    check_divergence: bool = False,
    personal_consumed: bool = False,
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
    v3 = s2_v3_availability_cutover_live()
    if slug == AvailabilityPolicySlug.work and v3:
        placer_active = True
        saved_but_unsupported = False
        note = (
            "Saved Working availability drives global clip after S2-V3. "
            "Legacy workweek_* is read-only provenance."
        )
    elif slug == AvailabilityPolicySlug.general and v3:
        placer_active = True
        saved_but_unsupported = False
        note = (
            "Saved General availability drives unclassified eligibility after S2-V3."
        )
    elif slug == AvailabilityPolicySlug.personal:
        # V4: Personal is placer-active on this task ONLY when a resolved
        # new-rule assignment consumes the Personal policy. Never globally.
        if personal_consumed:
            placer_active = True
            saved_but_unsupported = False
            note = (
                "Personal availability is scheduling-effective for this task "
                "because a new-rule assignment references it."
            )
        else:
            placer_active = False
            saved_but_unsupported = True
            note = (
                default_note
                if not v3
                else (
                    "Saved Personal availability; not scheduling-effective for "
                    "this task (no assignment consumes it)."
                )
            )
    else:
        placer_active = False
        saved_but_unsupported = True
        note = default_note
    return SavedAvailabilityPolicyOut(
        policy_id=policy.id,
        slug=policy.slug.value,
        name=policy.name,
        windows=[
            AvailabilityWindowOut.model_validate(row)
            for row in sorted(policy.windows, key=lambda w: (w.weekday, w.sort_order))
        ],
        placer_active=placer_active,
        saved_but_unsupported=saved_but_unsupported,
        note=note,
        diverges_from_legacy=diverges,
        divergence_note=divergence_note,
    )


def _resolved_assignment_out(resolved) -> "ResolvedSchedulingOut":
    from app.schemas.scheduling_assignment import (
        MaySpecOut,
        ResolvedSchedulingOut,
        SchedulingRuleOut,
    )

    def _rules(rows):
        return [
            SchedulingRuleOut(
                name=row.name,
                kind=row.kind,
                policy_id=row.policy_id,
                empty_set=row.empty_set,
                source_scope=row.source_scope,
                origin=row.origin,
            )
            for row in rows
        ]

    may_note = None
    if resolved.may_presence == "omit":
        may_note = "Local May omitted at winning scope — should not appear here."
    elif resolved.may_presence == "explicit" and not resolved.may_rules:
        may_note = "Explicit empty May — no fall-through to General."
    elif resolved.may_presence == "absent":
        may_note = "No May assignment resolved — General baseline (V4-P3)."
    else:
        may_note = "Explicit May sources — union at composition."

    conflict = None
    if resolved.conflict is not None:
        conflict = {
            "scope": resolved.conflict.scope,
            "scope_id": str(resolved.conflict.scope_id),
            "preferred_time_window_id": str(resolved.conflict.preferred_time_window_id),
            "assignment_id": str(resolved.conflict.assignment_id),
            "guidance": resolved.conflict.guidance,
        }

    placer_active = resolved.family == "new_rule" and resolved.conflict is None
    note = None
    if resolved.family == "legacy":
        note = "Legacy Time Map family — map ∩ Working; no May/Must composition."
    elif resolved.family == "none":
        note = "No assignment — unclassified → General after V3."
    elif placer_active:
        note = (
            "New-rule family placer-active for composition (Tesla May∪/Must∩/Prefer). "
            "Saved-inactive layers remain on non-winning scopes."
        )
    elif conflict is not None:
        note = "Repairable same-scope family conflict — no arbitrary winner."

    return ResolvedSchedulingOut(
        family=resolved.family,
        winning_scope=resolved.winning_scope,
        winning_scope_id=resolved.winning_scope_id,
        legacy_map_id=resolved.legacy_map_id,
        legacy_source=resolved.legacy_source,
        may=MaySpecOut(
            presence=resolved.may_presence,
            rules=_rules(resolved.may_rules),
            note=may_note,
        ),
        must=_rules(resolved.must_rules),
        prefer=_rules(resolved.prefer_rules),
        exceptions_applied=[
            {
                "operation": exc.operation,
                "target_rule_name": exc.target_rule_name,
                "target_rule_kind": exc.target_rule_kind,
                "scope": exc.scope,
            }
            for exc in resolved.exceptions_applied
        ],
        conflict=conflict,
        consumes_personal_policy=resolved.consumes_personal_policy,
        placer_active=placer_active,
        note=note,
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
    base_day_bands = bands_for_day(list(focus_window.bands), on)
    segments = effective_scheduling_day_segments(focus_window, override_rows, on, settings)
    segments_payload = _segments_out(segments)
    effective_bands = _unique_bands_out(segments)
    effective_strict = all(segment.strict_mode for segment in segments) if segments else focus_window.strict_mode

    override_rows_in_day = [
        segment.day_override
        for segment in segments
        if segment.day_override is not None
    ]
    selected = override_rows_in_day[0] if override_rows_in_day else None

    if selected is None:
        return DatedResolutionOut(
            performed=True,
            on=on,
            operator_timezone=operator_tz,
            override=None,
            replaces=None,
            segments=segments_payload,
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
    full_day_override = segments_cover_full_scheduling_day_with_single_override(
        segments,
        on,
        settings,
    )
    replaces_note = (
        "Override replaces this scheduling day's Time Map bands and strict_mode only "
        "(not workweek settings or the base map row)."
        if full_day_override
        else (
            "Override applies for part of this scheduling day; each segment lists the "
            "bands and strict_mode in effect for that UTC interval (matches placer bounds)."
        )
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
        effective_day_bands=effective_bands,
        note=replaces_note,
    )
    resolution_note = (
        "Override replaces this scheduling day's bands and strict_mode on the effective map."
        if full_day_override
        else (
            "Override applies for part of this scheduling day; see segments for interval "
            "boundaries and per-portion bands (stored-zone start/end, not a full-day replacement)."
        )
    )
    return DatedResolutionOut(
        performed=True,
        on=on,
        operator_timezone=operator_tz,
        override=override_detail,
        replaces=replaces,
        segments=segments_payload,
        note=resolution_note,
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
    v3 = s2_v3_availability_cutover_live()

    sources.append(
        SchedulingSourceOut(
            kind="legacy_workweek",
            label="Working hours (legacy workweek settings)",
            placer_active=not v3,
            detail=(
                f"workweek_days={settings.workweek_days}, "
                f"workday_start={settings.workday_start_local.strftime('%H:%M')}, "
                f"workday_minutes={settings.workday_minutes}, tz={settings.timezone}"
                + ("; inactive after S2-V3" if v3 else "")
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
                placer_active=not v3,
                detail=(
                    "General policy link drives unclassified eligibility after S2-V3"
                    if v3
                    else "General policy link is config-only until S2"
                ),
            )
        )

    sources.append(
        SchedulingSourceOut(
            kind="availability_general",
            label="General availability policy",
            placer_active=general_saved.placer_active,
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
            placer_active=working_saved.placer_active,
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

    personal_policy_early = _policy_for_slug(db, user, AvailabilityPolicySlug.personal)
    resolved = resolve_task_scheduling_assignment(
        db,
        task,
        project,
        epic,
        personal_policy_id=(
            personal_policy_early.id if personal_policy_early is not None else None
        ),
    )

    # Legacy map chain for Time Map effective-read. When new_rule wins, do not
    # present an inherited legacy map as the effective assignment (cutover §4.1).
    if resolved.family == "new_rule":
        window_id = None
        window_source = None
    elif resolved.family == "legacy":
        window_id = resolved.legacy_map_id
        window_source = resolved.legacy_source
    else:
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

    if on is not None and focus_window is not None and dated.segments:
        display_bands = dated.replaces.effective_day_bands if dated.replaces else []
        display_strict = dated.replaces.effective_strict_mode if dated.replaces else focus_window.strict_mode
        display_band_count = len(display_bands)
    elif on is not None and focus_window is not None and dated.replaces is not None:
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
    if on is not None and focus_window is not None and dated.segments:
        empty_kind = _empty_kind_from_segments(
            has_assignment=has_assignment,
            segments=[
                EffectiveSchedulingDaySegment(
                    start=row.start,
                    end=row.end,
                    source=row.source,
                    day_override=None,
                    bands=list(row.day_bands),
                    strict_mode=row.strict_mode,
                )
                for row in dated.segments
            ],
        )
    elif on is not None:
        empty_kind = _empty_kind_for_map(
            has_assignment=has_assignment,
            strict_mode=display_strict if display_strict is not None else False,
            band_count=display_band_count,
        )
    else:
        empty_kind = _empty_kind_for_map(
            has_assignment=has_assignment,
            strict_mode=map_strict,
            band_count=map_band_count,
        )

    map_name = focus_window.name if focus_window is not None else None
    if resolved.family == "new_rule":
        map_status = "superseded_by_new_rule"
        map_placer_active = False
    elif has_assignment:
        map_status = "assigned"
        map_placer_active = True
    else:
        map_status = "unclassified_fallback"
        map_placer_active = True  # unclassified → General after V3
    time_map = TimeMapEffectiveOut(
        assignment_status=map_status,
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
        placer_active=map_placer_active,
    )

    working_policy = _policy_for_slug(db, user, AvailabilityPolicySlug.work)
    general_policy = _policy_for_slug(db, user, AvailabilityPolicySlug.general)
    personal_policy = personal_policy_early

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
        personal_consumed=resolved.consumes_personal_policy,
    )

    v3 = s2_v3_availability_cutover_live()
    working_hours_active = LegacyWorkweekActiveOut(
        workweek_days=settings.workweek_days,
        workday_start_local=settings.workday_start_local,
        workday_minutes=settings.workday_minutes,
        timezone=settings.timezone,
        placer_active=not v3,
    )

    effort = placement_effort_minutes(task)
    remaining = task.remaining_minutes
    if remaining is None:
        remaining = task.estimated_duration_minutes
    chunking_live = chunking_cutover_writes_unlocked()
    bounds = resolve_block_bounds(task, settings)
    inherited_preview = None
    if not chunking_live and (
        task.min_block_duration_minutes is None or task.max_block_duration_minutes is None
    ):
        inherited_preview = InheritedBlockBoundsPreview(
            min_block_duration_minutes=settings.default_min_block_duration_minutes
            if task.min_block_duration_minutes is None
            else None,
            max_block_duration_minutes=settings.default_max_block_duration_minutes
            if task.max_block_duration_minutes is None
            else None,
            max_block_unbounded=settings.default_max_block_unbounded
            if task.max_block_duration_minutes is None
            else task.max_block_unbounded,
        )
    duration_note = (
        "Chunking bounds and keep-in-one are scheduling-effective for placement "
        "and fingerprint v4. "
        "estimated_duration_minutes is the original-estimate alias. "
        "placement_effort_minutes follows remaining estimate when set. "
        "keep_in_one_scheduling_conflicts lists pin/scheduling mismatches without "
        "blocking save (§0.1 saving vs scheduling)."
        if chunking_live
        else (
            "estimated_duration_minutes is the original-estimate alias. "
            "placement_effort_minutes follows remaining estimate when set, else that alias. "
            "Stored inherit / No limit / keep-in-one are preview-only until S2 cutover. "
            "Pin-adjusted placement effort is not computed on this read."
        )
    )
    pin_conflicts = []
    if chunking_live and bounds.keep_in_one_block:
        pin_conflicts = keep_in_one_scheduling_conflicts(
            db,
            owner_id=user.id,
            task=task,
            run_now=datetime.now(timezone.utc),
        )
    duration = DurationEffectiveOut(
        original_estimate_minutes=task.estimated_duration_minutes,
        estimated_duration_minutes=task.estimated_duration_minutes,
        time_worked_minutes=task.worked_minutes,
        remaining_estimate_minutes=remaining,
        placement_effort_minutes=effort,
        min_block_duration_minutes=task.min_block_duration_minutes,
        max_block_duration_minutes=task.max_block_duration_minutes,
        max_block_unbounded=task.max_block_unbounded,
        keep_in_one_block=task.keep_in_one_block,
        inherited_bounds_preview=inherited_preview,
        chunking_scheduling_effective=chunking_live,
        effective_min_block_duration_minutes=bounds.effective_min_minutes,
        effective_max_block_duration_minutes=bounds.effective_max_minutes,
        min_block_source=bounds.min_source,
        max_block_source=bounds.max_source,
        effective_bounds_conflict=bounds.bounds_conflict(),
        keep_in_one_scheduling_conflicts=pin_conflicts,
        note=duration_note,
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
    if resolved.family == "new_rule" and resolved.conflict is None:
        sources.append(
            SchedulingSourceOut(
                kind="new_rule_assignment",
                label="New-rule May/Must/Prefer assignment",
                placer_active=True,
                detail=(
                    f"Winning scope={resolved.winning_scope}; "
                    f"may={resolved.may_presence}; "
                    f"must={len(resolved.must_rules)}; prefer={len(resolved.prefer_rules)}"
                ),
            )
        )
    elif resolved.conflict is not None:
        sources.append(
            SchedulingSourceOut(
                kind="scheduling_family_conflict",
                label="Same-scope legacy/new-rule conflict",
                placer_active=False,
                detail=resolved.conflict.guidance,
            )
        )

    effective_note = scheduling_effective_note_for_surface()
    return TaskSchedulingEffectiveOut(
        task_id=task.id,
        scheduling_effective_note=effective_note,
        placement_effort_minutes=effort,
        sources=sources,
        legacy_time_map_id=window_id,
        legacy_time_map_source=window_source,
        general_policy_scheduling_effective=v3,
        working_hours_placer_active=not v3,
        time_map=time_map,
        working_hours_active=working_hours_active,
        working_policy_saved=working_saved,
        general_policy_saved=general_saved,
        personal_policy_saved=personal_saved,
        new_rule_assignment=_resolved_assignment_out(resolved),
        dated_resolution=dated,
        duration=duration,
    )
