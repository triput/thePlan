"""One-shot scheduling_revision bump when S2 chunking cutover activates (S0 §0.1 / A5)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import UserSettings
from app.services.scheduling_revision import increment_scheduling_revision, lock_owner_scheduling


def chunking_activation_revision(current: int) -> int:
    """One revision step for the S2 chunking/pin activation (A5)."""
    return int(current) + 1


def bump_all_owners_for_chunking_cutover(db: Session) -> int:
    """Bump every owner's scheduling_revision once for the cutover (A5).

    Not called from request paths. Run **only on the release database at deploy**
    when the write guard flips (operator / migration step). **Do not** invoke
    from agent sessions or against household ``theplan`` — stale protection for
    v3 previews is already ``provenance`` + ``scheduling_activation`` tokens.
    Does not rewrite historical explanation JSON.
    """
    bumped = 0
    owner_ids = [row[0] for row in db.query(UserSettings.owner_id).all()]
    for owner_id in owner_ids:
        settings = lock_owner_scheduling(db, owner_id)
        increment_scheduling_revision(db, settings)
        bumped += 1
    db.flush()
    return bumped
