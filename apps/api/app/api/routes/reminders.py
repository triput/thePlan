"""Reminder due/ack and reminder-id CRUD."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.db import get_db
from app.models import Reminder, Task, User
from app.schemas import ReminderDueOut, ReminderOut, ReminderUpdate

router = APIRouter(prefix="/reminders", tags=["reminders"])


def _get_owned_reminder(db: Session, reminder_id: UUID, user: User) -> Reminder:
    reminder = (
        db.query(Reminder)
        .filter(Reminder.id == reminder_id, Reminder.owner_id == user.id)
        .one_or_none()
    )
    if reminder is None:
        raise ApiError(404, "Reminder not found", "REMINDER_NOT_FOUND")
    return reminder


def reminder_to_out(reminder: Reminder) -> ReminderOut:
    return ReminderOut.model_validate(reminder)


@router.get("/due", response_model=list[ReminderDueOut])
def list_due_reminders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ReminderDueOut]:
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Reminder, Task.title)
        .join(Task, Task.id == Reminder.task_id)
        .filter(
            Reminder.owner_id == user.id,
            Reminder.is_fired.is_(False),
            Reminder.fire_at <= now,
        )
        .order_by(Reminder.fire_at.asc())
        .all()
    )
    return [
        ReminderDueOut(
            id=reminder.id,
            task_id=reminder.task_id,
            fire_at=reminder.fire_at,
            channel=reminder.channel,
            is_fired=reminder.is_fired,
            created_at=reminder.created_at,
            task_title=title,
        )
        for reminder, title in rows
    ]


@router.patch("/{reminder_id}", response_model=ReminderOut)
def update_reminder(
    reminder_id: UUID,
    body: ReminderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReminderOut:
    reminder = _get_owned_reminder(db, reminder_id, user)
    if reminder.is_fired:
        raise ApiError(409, "Reminder already fired", "REMINDER_FIRED")
    if body.fire_at is not None:
        reminder.fire_at = body.fire_at
    if body.channel is not None:
        reminder.channel = body.channel
    db.commit()
    db.refresh(reminder)
    return reminder_to_out(reminder)


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    reminder = _get_owned_reminder(db, reminder_id, user)
    db.delete(reminder)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{reminder_id}/ack", response_model=ReminderOut)
def ack_reminder(
    reminder_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReminderOut:
    reminder = _get_owned_reminder(db, reminder_id, user)
    if not reminder.is_fired:
        reminder.is_fired = True
        db.commit()
        db.refresh(reminder)
    return reminder_to_out(reminder)
