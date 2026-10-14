"""One-shot scheduling_revision bump when S2-V4 composition cutover activates.

Operator procedure for household ``theplan`` (do not run from an agent session):

1. Deploy the release that contains placer composition, the ``composition``
   fingerprint category, effective-read honesty, writers, and activation token
   ``s2-v4-may-must-prefer-composition`` together.
2. Previews captured before that token are already stale via
   ``owner_snapshot_predates_activation``. This bump is the matching
   ``scheduling_revision`` step (S0 §0.1).
3. Run ``bump_all_owners_for_composition_cutover`` once on the release
   database. It does not rewrite historical explanation JSON and does not
   move blocks.
4. Trish authorizes the household run. Disposable ``theplan_s1_test`` is the
   only database agents should touch. Do not run this against household
   ``theplan`` from an agent session.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import UserSettings
from app.services.scheduling_revision import increment_scheduling_revision, lock_owner_scheduling

ACTIVATION_TOKEN = "s2-v4-may-must-prefer-composition"


def composition_activation_revision(current: int) -> int:
    """One revision step for the S2-V4 May/Must/Prefer activation."""
    return int(current) + 1


def bump_all_owners_for_composition_cutover(db: Session) -> int:
    """Bump every owner's scheduling_revision once. Not a request-path hook."""
    bumped = 0
    owner_ids = [row[0] for row in db.query(UserSettings.owner_id).all()]
    for owner_id in owner_ids:
        settings = lock_owner_scheduling(db, owner_id)
        increment_scheduling_revision(db, settings)
        bumped += 1
    db.flush()
    return bumped
