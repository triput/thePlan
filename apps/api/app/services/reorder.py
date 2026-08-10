from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.schemas import ReorderItem


def batch_reorder_sort_order(
    db: Session,
    model: type,
    owner_id: UUID,
    items: list[ReorderItem],
    *,
    not_found_detail: str,
) -> None:
    """Update sort_order for owned entities in a single transaction."""
    if not items:
        return

    ids = [item.id for item in items]
    entities = db.query(model).filter(model.owner_id == owner_id, model.id.in_(ids)).all()
    by_id = {entity.id: entity for entity in entities}

    missing = [str(item.id) for item in items if item.id not in by_id]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{not_found_detail}: {', '.join(missing)}",
        )

    for item in items:
        by_id[item.id].sort_order = item.sort_order

    db.commit()
