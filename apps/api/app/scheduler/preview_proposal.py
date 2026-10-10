"""Serialize scheduling calculation output for immutable preview storage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ScheduledBlock
from app.scheduler.calculate import CalculationResult
from app.scheduler.collect import SchedulingInputs
from app.scheduler.placement import ProposedBlock
from app.scheduler.reasons import ReasonFact, TaskSchedulingOutcome
from app.scheduler.calculate import CalculationResult


PROPOSAL_VERSION = 1


def _block_identity(task_id: UUID, start: datetime, end: datetime) -> dict[str, Any]:
    return {
        "task_id": str(task_id),
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
    }


def capture_before_blocks(
    db: Session,
    *,
    owner_id: UUID,
    horizon_start: datetime,
    horizon_end: datetime,
) -> list[dict[str, Any]]:
    """Normalized live blocks in horizon (pinned and unpinned). IDs omitted on purpose."""
    rows = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.owner_id == owner_id,
            ScheduledBlock.start_time >= horizon_start,
            ScheduledBlock.start_time < horizon_end,
        )
        .order_by(ScheduledBlock.start_time.asc(), ScheduledBlock.task_id.asc())
        .all()
    )
    return [
        {
            **_block_identity(row.task_id, row.start_time, row.end_time),
            "is_pinned": bool(row.is_pinned),
        }
        for row in rows
    ]


def _proposed_block_payload(block: ProposedBlock) -> dict[str, Any]:
    return {
        "task_id": str(block.task_id),
        "start_time": block.start_time.isoformat(),
        "end_time": block.end_time.isoformat(),
        "slice_minutes": block.slice_minutes,
        "tier": block.tier,
        "preferred_window_id": str(block.preferred_window_id)
        if block.preferred_window_id
        else None,
    }


def _outcome_payload(outcome: TaskSchedulingOutcome) -> dict[str, Any]:
    return {
        "task_id": str(outcome.task_id),
        "requested_minutes": outcome.requested_minutes,
        "pinned_minutes": outcome.pinned_minutes,
        "placed_minutes": outcome.placed_minutes,
        "remaining_minutes": outcome.remaining_minutes,
        "reason_facts": [fact.to_json() for fact in outcome.reason_facts],
        "placement_facts": outcome.placement_facts,
        "primary_reason_code": outcome.primary_code,
    }


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def calculation_result_from_proposal(proposal: dict[str, Any]) -> CalculationResult:
    """Rebuild in-memory calculation output stored on a preview row."""
    proposed_blocks: list[ProposedBlock] = []
    for row in proposal.get("proposed_blocks") or []:
        proposed_blocks.append(
            ProposedBlock(
                task_id=UUID(row["task_id"]),
                start_time=_parse_utc(row["start_time"]),
                end_time=_parse_utc(row["end_time"]),
                slice_minutes=int(row["slice_minutes"]),
                tier=row.get("tier"),
                preferred_window_id=UUID(row["preferred_window_id"])
                if row.get("preferred_window_id")
                else None,
            )
        )

    outcomes: list[TaskSchedulingOutcome] = []
    remaining_by_task: dict[UUID, int] = {}
    task_had_blocks: dict[UUID, bool] = {}
    placement_facts_by_task: dict[UUID, dict[str, Any]] = {}
    for row in proposal.get("outcomes") or []:
        task_id = UUID(row["task_id"])
        facts = [
            ReasonFact(code=fact["code"], params=dict(fact.get("params") or {}))
            for fact in row.get("reason_facts") or []
        ]
        outcome = TaskSchedulingOutcome(
            task_id=task_id,
            requested_minutes=int(row["requested_minutes"]),
            pinned_minutes=int(row["pinned_minutes"]),
            placed_minutes=int(row["placed_minutes"]),
            remaining_minutes=int(row["remaining_minutes"]),
            reason_facts=facts,
            placement_facts=row.get("placement_facts"),
        )
        outcomes.append(outcome)
        remaining_by_task[task_id] = outcome.remaining_minutes
        task_had_blocks[task_id] = outcome.placed_minutes > 0 or outcome.pinned_minutes > 0
        if outcome.placement_facts is not None:
            placement_facts_by_task[task_id] = outcome.placement_facts

    stats = dict(proposal.get("stats") or {})
    return CalculationResult(
        proposed_blocks=proposed_blocks,
        outcomes=outcomes,
        stats=stats,
        remaining_by_task=remaining_by_task,
        task_had_blocks=task_had_blocks,
        placement_facts_by_task=placement_facts_by_task,
        tasks_scheduled=int(proposal.get("tasks_scheduled") or 0),
        blocks_created=int(proposal.get("blocks_created") or 0),
        overbooked_count=int(proposal.get("overbooked_count") or 0),
    )


def build_proposal_json(
    *,
    inputs: SchedulingInputs,
    result: CalculationResult,
    before_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "v": PROPOSAL_VERSION,
        "horizon_start": inputs.horizon_start.isoformat(),
        "horizon_end": inputs.horizon_end.isoformat(),
        "before_blocks": before_blocks,
        "proposed_blocks": [_proposed_block_payload(block) for block in result.proposed_blocks],
        "outcomes": [_outcome_payload(outcome) for outcome in result.outcomes],
        "stats": dict(result.stats),
        "tasks_scheduled": result.tasks_scheduled,
        "blocks_created": result.blocks_created,
        "overbooked_count": result.overbooked_count,
    }
