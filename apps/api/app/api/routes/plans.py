"""Named Plans (reusable soft time frames) CRUD."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.db import get_db
from app.models import Plan, User
from app.schemas import PlanCreate, PlanOut, PlanUpdate

router = APIRouter(prefix="/plans", tags=["plans"])


def _get_owned_plan(db: Session, plan_id: UUID, user: User) -> Plan:
    plan = db.get(Plan, plan_id)
    if plan is None or plan.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan


def _validate_plan_name(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        raise ApiError(422, "Plan name cannot be empty", "PLAN_NAME_EMPTY")
    return stripped


@router.get("", response_model=list[PlanOut])
def list_plans(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PlanOut]:
    rows = (
        db.query(Plan)
        .filter(Plan.owner_id == user.id)
        .order_by(Plan.name)
        .all()
    )
    return [PlanOut.model_validate(row) for row in rows]


@router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(
    body: PlanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlanOut:
    plan = Plan(
        owner_id=user.id,
        name=_validate_plan_name(body.name),
        soft_target_at=body.soft_target_at,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return PlanOut.model_validate(plan)


@router.get("/{plan_id}", response_model=PlanOut)
def get_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlanOut:
    plan = _get_owned_plan(db, plan_id, user)
    return PlanOut.model_validate(plan)


@router.patch("/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: UUID,
    body: PlanUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlanOut:
    plan = _get_owned_plan(db, plan_id, user)
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        updates["name"] = _validate_plan_name(updates["name"])

    for field, value in updates.items():
        setattr(plan, field, value)
    db.commit()
    db.refresh(plan)
    return PlanOut.model_validate(plan)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    plan = _get_owned_plan(db, plan_id, user)
    db.delete(plan)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
