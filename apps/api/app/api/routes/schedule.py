from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import SchedulePreview, ScheduleRun, Task, User
from app.schemas import (
    PaginatedResponse,
    ScheduleExplanationPage,
    SchedulePreviewApplyReceipt,
    SchedulePreviewOut,
    ScheduleRunOut,
    ScheduleRunStaleSummary,
    TaskScheduleExplanationOut,
)
from app.services.schedule_dispatch import admit_replan, dispatch_replan
from app.services.schedule_explanations import latest_for_task, page_for_run, stale_summary_for_run
from app.services.schedule_preview_dispatch import admit_preview, dispatch_preview
from app.services.schedule_preview_apply import apply_schedule_preview
from app.services.schedule_previews import preview_to_dict, refresh_preview_staleness
from app.schemas.task_scheduling import TaskSchedulingEffectiveOut
from app.services.task_scheduling_effective import build_task_scheduling_effective

router = APIRouter(prefix="/schedule", tags=["schedule"])
task_schedule_router = APIRouter(prefix="/tasks", tags=["schedule"])


def _get_owned_run(db: Session, run_id: UUID, user: User) -> ScheduleRun:
    run = db.get(ScheduleRun, run_id)
    if run is None or run.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule run not found")
    return run


def _get_owned_preview(db: Session, preview_id: UUID, user: User) -> SchedulePreview:
    preview = db.get(SchedulePreview, preview_id)
    if preview is None or preview.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule preview not found")
    return preview


@router.post("/previews", response_model=SchedulePreviewOut, status_code=status.HTTP_202_ACCEPTED)
def create_schedule_preview(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SchedulePreviewOut:
    """Start an async replan preview. Never writes live schedule rows."""
    preview = admit_preview(db, user.id)
    dispatch_preview(preview.id)
    return SchedulePreviewOut.model_validate(preview_to_dict(preview))


@router.post(
    "/previews/{preview_id}/apply",
    response_model=SchedulePreviewApplyReceipt,
    status_code=status.HTTP_200_OK,
)
def apply_schedule_preview_route(
    preview_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SchedulePreviewApplyReceipt:
    """Apply a ready preview atomically; idempotent while status stays applied."""
    preview = _get_owned_preview(db, preview_id, user)
    receipt = apply_schedule_preview(db, user, preview)
    db.commit()
    return SchedulePreviewApplyReceipt.model_validate(receipt)


@router.get("/previews/{preview_id}", response_model=SchedulePreviewOut)
def get_schedule_preview(
    preview_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SchedulePreviewOut:
    preview = _get_owned_preview(db, preview_id, user)
    refresh_preview_staleness(db, preview)
    db.flush()
    return SchedulePreviewOut.model_validate(preview_to_dict(preview))


@router.post("/replan", response_model=ScheduleRunOut, status_code=status.HTTP_202_ACCEPTED)
def replan_schedule(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduleRunOut:
    run = admit_replan(db, user.id)
    dispatch_replan(run.id)
    return ScheduleRunOut.model_validate(run)


@router.get("/runs", response_model=PaginatedResponse)
def list_schedule_runs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    """Owner's schedule runs, newest first. Does not start a replan."""
    query = db.query(ScheduleRun).filter(ScheduleRun.owner_id == user.id)
    total = query.count()
    items = (
        query.order_by(ScheduleRun.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return PaginatedResponse(
        items=[ScheduleRunOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}", response_model=ScheduleRunOut)
def get_schedule_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduleRunOut:
    run = _get_owned_run(db, run_id, user)
    return ScheduleRunOut.model_validate(run)


@router.get("/runs/{run_id}/explanations", response_model=ScheduleExplanationPage)
def list_run_explanations(
    run_id: UUID,
    task_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduleExplanationPage:
    """Recorded explanations for one run. Optional task filter. Does not replan.

    Staleness is computed on read for duration, deadline, map/style, and deps.
    """
    run = _get_owned_run(db, run_id, user)
    return page_for_run(db, run, task_id=task_id, limit=limit, offset=offset)


@router.get("/runs/{run_id}/stale-summary", response_model=ScheduleRunStaleSummary)
def get_run_stale_summary(
    run_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduleRunStaleSummary:
    """Stale count and categories for every explanation on the run.

    Owner-scoped: a missing or foreign run is 404. Does not start a replan.
    Unlike the explanations list, this is not paginated and does not stop at 200.
    """
    run = _get_owned_run(db, run_id, user)
    return stale_summary_for_run(db, run)


@task_schedule_router.get(
    "/{task_id}/scheduling/effective",
    response_model=TaskSchedulingEffectiveOut,
)
def get_task_scheduling_effective(
    task_id: UUID,
    on: date | None = Query(
        default=None,
        description=(
            "Scheduling day (YYYY-MM-DD) in operator timezone for dated Time Map override "
            "resolution; omit to skip dated override lookup."
        ),
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskSchedulingEffectiveOut:
    task = db.get(Task, task_id)
    if task is None or task.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return build_task_scheduling_effective(db, user, task, on=on)


@task_schedule_router.get(
    "/{task_id}/schedule-explanation",
    response_model=TaskScheduleExplanationOut,
)
def get_task_schedule_explanation(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskScheduleExplanationOut:
    """Latest explanation from the newest completed run that evaluated this task.

    200 ``never_evaluated`` when this owner has no completed evaluation.
    404 when the task is missing or belongs to someone else (same body either way).
    Does not start a replan.
    """
    task = db.get(Task, task_id)
    if task is None or task.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return latest_for_task(db, task)
