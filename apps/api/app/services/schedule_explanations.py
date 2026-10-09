"""Owner-scoped explanation reads. Never starts a replan."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ScheduleRun, ScheduleTaskOutcome, Task
from app.scheduler.input_fingerprint import STALE_PROVENANCE, diff_stale_categories, outcome_family
from app.scheduler.outcomes import live_snapshots_by_task, summary_text_for_facts
from app.schemas.schedule import (
    ReasonFactOut,
    ScheduleExplanationOut,
    ScheduleExplanationPage,
    TaskScheduleExplanationOut,
)


def _facts_out(raw: list | None) -> list[ReasonFactOut]:
    facts: list[ReasonFactOut] = []
    for item in raw or []:
        if not isinstance(item, dict) or not item.get("code"):
            continue
        params = item.get("params") or {}
        facts.append(ReasonFactOut(code=str(item["code"]), params=dict(params)))
    return facts


def _summary(row: ScheduleTaskOutcome) -> str:
    if row.reason_facts:
        return summary_text_for_facts(row.reason_facts)
    if row.summary_text:
        return row.summary_text
    return summary_text_for_facts([])


def _explanation_out(
    row: ScheduleTaskOutcome,
    live: dict | None,
) -> ScheduleExplanationOut:
    if row.input_snapshot is None or live is None:
        categories = [STALE_PROVENANCE]
    else:
        categories = diff_stale_categories(row.input_snapshot, live)
    facts = _facts_out(row.reason_facts)
    return ScheduleExplanationOut(
        id=row.id,
        schedule_run_id=row.schedule_run_id,
        task_id=row.task_id,
        evaluated_at=row.evaluated_at,
        outcome=row.outcome or outcome_family(row.primary_reason_code),
        primary_reason_code=row.primary_reason_code,
        requested_minutes=row.requested_minutes,
        pinned_minutes=row.pinned_minutes,
        placed_minutes=row.placed_minutes,
        remaining_minutes=row.remaining_minutes,
        reason_facts=facts,
        summary_text=_summary(row),
        placement_facts=row.placement_facts,
        algorithm_version=row.algorithm_version,
        input_fingerprint=row.input_fingerprint,
        input_snapshot=row.input_snapshot,
        is_stale=bool(categories),
        stale_categories=categories,
    )


def _live_for_rows(
    db: Session,
    rows: list[ScheduleTaskOutcome],
) -> dict[UUID, dict]:
    if not rows:
        return {}
    task_ids = {row.task_id for row in rows}
    owner_id = rows[0].owner_id
    tasks = (
        db.query(Task)
        .filter(Task.owner_id == owner_id, Task.id.in_(task_ids))
        .all()
    )
    return live_snapshots_by_task(db, tasks)


def page_for_run(
    db: Session,
    run: ScheduleRun,
    *,
    task_id: UUID | None,
    limit: int,
    offset: int,
) -> ScheduleExplanationPage:
    query = db.query(ScheduleTaskOutcome).filter(
        ScheduleTaskOutcome.schedule_run_id == run.id,
        ScheduleTaskOutcome.owner_id == run.owner_id,
    )
    if task_id is not None:
        query = query.filter(ScheduleTaskOutcome.task_id == task_id)
    total = query.count()
    rows = (
        query.order_by(ScheduleTaskOutcome.task_id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    live = _live_for_rows(db, rows)
    return ScheduleExplanationPage(
        items=[_explanation_out(row, live.get(row.task_id)) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def latest_for_task(db: Session, task: Task) -> TaskScheduleExplanationOut:
    """Latest explanation from the most recent completed run that evaluated the task.

    No history is ``never_evaluated`` with empty facts. This does not insert a run.
    """
    row = (
        db.query(ScheduleTaskOutcome)
        .join(ScheduleRun, ScheduleRun.id == ScheduleTaskOutcome.schedule_run_id)
        .filter(
            ScheduleTaskOutcome.owner_id == task.owner_id,
            ScheduleTaskOutcome.task_id == task.id,
            ScheduleRun.owner_id == task.owner_id,
            ScheduleRun.status == "completed",
        )
        .order_by(
            ScheduleTaskOutcome.evaluated_at.desc(),
            ScheduleRun.finished_at.desc().nulls_last(),
        )
        .first()
    )
    if row is None:
        empty = summary_text_for_facts([])
        return TaskScheduleExplanationOut(
            task_id=task.id,
            evaluation_state="never_evaluated",
            summary_text=empty,
            is_stale=False,
            stale_categories=[],
            explanation=None,
        )
    live = _live_for_rows(db, [row])
    explanation = _explanation_out(row, live.get(task.id))
    return TaskScheduleExplanationOut(
        task_id=task.id,
        evaluation_state="evaluated",
        summary_text=explanation.summary_text,
        is_stale=explanation.is_stale,
        stale_categories=explanation.stale_categories,
        explanation=explanation,
    )
