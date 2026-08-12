from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.db import get_db
from app.models import ScheduleRun, User
from app.schemas import ScheduleRunOut
from app.services.schedule_dispatch import dispatch_replan, has_running_run, reclaim_stale_runs

router = APIRouter(prefix="/schedule", tags=["schedule"])


def _get_owned_run(db: Session, run_id: UUID, user: User) -> ScheduleRun:
    run = db.get(ScheduleRun, run_id)
    if run is None or run.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule run not found")
    return run


@router.post("/replan", response_model=ScheduleRunOut, status_code=status.HTTP_202_ACCEPTED)
def replan_schedule(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduleRunOut:
    reclaim_stale_runs(db, user.id)
    if has_running_run(db, user.id):
        raise ApiError(
            409,
            "A schedule run is already in progress",
            "SCHEDULE_RUN_IN_PROGRESS",
        )

    run = ScheduleRun(owner_id=user.id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    dispatch_replan(run.id)
    return ScheduleRunOut.model_validate(run)


@router.get("/runs/{run_id}", response_model=ScheduleRunOut)
def get_schedule_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduleRunOut:
    run = _get_owned_run(db, run_id, user)
    return ScheduleRunOut.model_validate(run)
