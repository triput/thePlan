"""Read model for task scheduling provenance (S1: placer-active vs pending)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Epic, FocusWindow, Project, Task, User
from app.scheduler.task_effort import placement_effort_minutes
from app.scheduler.windows import (
    effective_preferred_time_window_id,
    effective_preferred_time_window_source,
)
from app.schemas.task_scheduling import SchedulingSourceOut, TaskSchedulingEffectiveOut
from app.services.auth_users import get_or_provision_user_settings


def build_task_scheduling_effective(db: Session, user: User, task: Task) -> TaskSchedulingEffectiveOut:
    settings = get_or_provision_user_settings(db, user)
    project: Project | None = None
    epic: Epic | None = None
    if task.project_id is not None:
        project = db.get(Project, task.project_id)
        if project is not None and project.epic_id is not None:
            epic = db.get(Epic, project.epic_id)

    window_id = effective_preferred_time_window_id(task, project, epic)
    window_source = effective_preferred_time_window_source(task, project, epic)
    sources: list[SchedulingSourceOut] = []

    sources.append(
        SchedulingSourceOut(
            kind="legacy_workweek",
            label="Working hours (legacy workweek settings)",
            placer_active=True,
            detail=(
                f"workweek_days={settings.workweek_days}, "
                f"workday_start={settings.workday_start_local.strftime('%H:%M')}, "
                f"workday_minutes={settings.workday_minutes}"
            ),
        )
    )

    if window_id is not None:
        window = db.get(FocusWindow, window_id)
        map_label = window.name if window is not None else str(window_id)
        sources.append(
            SchedulingSourceOut(
                kind="legacy_time_map",
                label=f"Time Map ({window_source or 'unknown'})",
                placer_active=True,
                detail=map_label,
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
                detail="Seeded/edited in Settings; not used by placer in S1",
            )
        )

    sources.append(
        SchedulingSourceOut(
            kind="availability_work",
            label="Working availability policy",
            placer_active=False,
            detail="Mirrors workweek when edited; placer still reads workweek_* in S1",
        )
    )
    sources.append(
        SchedulingSourceOut(
            kind="availability_personal",
            label="Personal availability policy",
            placer_active=False,
            detail="Named policy with zero windows; not unioned into General",
        )
    )

    return TaskSchedulingEffectiveOut(
        task_id=task.id,
        placement_effort_minutes=placement_effort_minutes(task),
        sources=sources,
        legacy_time_map_id=window_id,
        legacy_time_map_source=window_source,
        general_policy_scheduling_effective=False,
        working_hours_placer_active=True,
    )
