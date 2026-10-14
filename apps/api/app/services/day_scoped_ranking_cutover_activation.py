"""One-shot scheduling_revision bump when S2-V4b day-scoped ranking activates.

Operator procedure for household ``theplan`` (do not run from an agent session):

1. Deploy the release that contains day-scoped resolution, A14c ranking
   protection, the composition fingerprint inputs, and activation token
   ``s2-v4b-day-scoped-ranking-protection`` together. The V4 token
   ``s2-v4-may-must-prefer-composition`` stays in the tuple.
2. Previews captured before this token are already stale via
   ``owner_snapshot_predates_activation``. This bump is the matching
   ``scheduling_revision`` step (S0 §0.1).
3. Run ``bump_all_owners_for_day_scoped_ranking_cutover`` once on the release
   database after Trish authorizes it. It does not rewrite historical
   explanation JSON and does not move blocks.
4. Disposable ``theplan_s1_test`` is the only database agents should touch.
   Do not run this against household ``theplan`` from an agent session.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import UserSettings
from app.services.scheduling_revision import increment_scheduling_revision, lock_owner_scheduling

ACTIVATION_TOKEN = "s2-v4b-day-scoped-ranking-protection"


def day_scoped_ranking_activation_revision(current: int) -> int:
    """One revision step for the S2-V4b day-scoped ranking activation."""
    return int(current) + 1


def bump_all_owners_for_day_scoped_ranking_cutover(db: Session) -> int:
    """Bump every owner's scheduling_revision once. Not a request-path hook.

    Do not call this from an agent session against household ``theplan``.
    """
    bumped = 0
    owner_ids = [row[0] for row in db.query(UserSettings.owner_id).all()]
    for owner_id in owner_ids:
        settings = lock_owner_scheduling(db, owner_id)
        increment_scheduling_revision(db, settings)
        bumped += 1
    db.flush()
    return bumped
