"""F1 planning handoff routes — propose, apply, receipt lookup."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.db import get_db
from app.models import HandoffReceipt, User
from app.models.handoff import HANDOFF_APPLY_KIND
from app.schemas.handoffs import (
    HandoffApplyRequest,
    HandoffApplyResult,
    HandoffGraphPayload,
    HandoffProposeResponse,
    HandoffReceiptOut,
)
from app.services.handoff_apply import apply_handoff, propose_handoff

router = APIRouter(prefix="/handoffs", tags=["handoffs"])


def _receipt_out(receipt: HandoffReceipt) -> HandoffReceiptOut:
    return HandoffReceiptOut(
        id=receipt.id,
        operation_kind=receipt.operation_kind,
        idempotency_key=receipt.idempotency_key,
        payload_hash=receipt.payload_hash,
        receipt_json=HandoffApplyResult.model_validate(receipt.receipt_json),
        created_at=receipt.created_at,
    )


@router.post("/propose", response_model=HandoffProposeResponse)
def handoffs_propose(
    body: HandoffGraphPayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HandoffProposeResponse:
    return propose_handoff(db, user, body)


@router.post("/apply", response_model=HandoffApplyResult)
def handoffs_apply(
    body: HandoffApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HandoffApplyResult:
    result = apply_handoff(db, user, body)
    db.commit()
    return result


@router.get("/receipts/{receipt_id}", response_model=HandoffReceiptOut)
def handoffs_receipt_by_id(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HandoffReceiptOut:
    receipt = db.get(HandoffReceipt, receipt_id)
    if receipt is None or receipt.owner_id != user.id:
        raise ApiError(404, "Receipt not found", "RECEIPT_NOT_FOUND")
    return _receipt_out(receipt)


@router.get("/receipts/by-key/{idempotency_key}", response_model=HandoffReceiptOut)
def handoffs_receipt_by_key(
    idempotency_key: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HandoffReceiptOut:
    receipt = (
        db.query(HandoffReceipt)
        .filter(
            HandoffReceipt.owner_id == user.id,
            HandoffReceipt.operation_kind == HANDOFF_APPLY_KIND,
            HandoffReceipt.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if receipt is None:
        raise ApiError(404, "Receipt not found", "RECEIPT_NOT_FOUND")
    return _receipt_out(receipt)


@router.get("/receipts", response_model=HandoffReceiptOut)
def handoffs_receipt_lookup(
    idempotency_key: UUID = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HandoffReceiptOut:
    return handoffs_receipt_by_key(idempotency_key, db, user)
