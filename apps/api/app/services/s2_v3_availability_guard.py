"""S2-V3 Working/General cutover gates (API/CLI reject + effective-read honesty).

Flips with Tesla placer + fingerprint in one release (V3-P2). Set False only for
emergency rollback in dev — targeted tests assume True at tip.
"""

from __future__ import annotations

from app.api.errors import ApiError

# ---------------------------------------------------------------------------
# Cutover live (V3-P2). Tesla placer + fingerprint ship in the same release.
# ---------------------------------------------------------------------------
S2_V3_AVAILABILITY_CUTOVER_LIVE: bool = True

_DEPRECATED_SETTINGS_FIELDS = frozenset(
    {
        "workweek_days",
        "workday_start_local",
        "workday_minutes",
    }
)

LEGACY_WORKWEEK_REJECT_CODE = "LEGACY_WORKWEEK_SETTINGS_REJECTED"

_LEGACY_WORKWEEK_REJECT_MESSAGE = (
    "workweek_days, workday_start_local, and workday_minutes are no longer "
    "writable on settings. Edit Working hours with PATCH "
    "/api/v1/availability-policies/work and General availability with PATCH "
    "/api/v1/availability-policies/general (CLI: theplan availability patch). "
    "nominal_workday_minutes remains on settings for effort conversion."
)

V3_SCHEDULING_EFFECTIVE_NOTE = (
    "Working and General availability policies are scheduling-effective after "
    "the S2-V3 cutover. Legacy workweek_* mirrors are read-only provenance."
)

V3_DIVERGENCE_ACTIVATION_NOTE = (
    "Saved Working availability drives global clip; legacy workweek_* is "
    "inactive provenance until you align or ignore it."
)

V3_NEW_RULE_INACTIVE_NOTE = (
    "Saved availability policy rows are stored; May/Must/Prefer composition "
    "activates in S2-V4 — not scheduling-effective yet."
)


def s2_v3_availability_cutover_live() -> bool:
    return S2_V3_AVAILABILITY_CUTOVER_LIVE


def reject_legacy_workweek_settings_writes(updates: dict[str, object]) -> None:
    """Reject deprecated placement workweek fields on PATCH /settings."""
    if not s2_v3_availability_cutover_live():
        return
    touched = _DEPRECATED_SETTINGS_FIELDS.intersection(updates)
    if not touched:
        return
    raise ApiError(
        422,
        _LEGACY_WORKWEEK_REJECT_MESSAGE,
        LEGACY_WORKWEEK_REJECT_CODE,
        rejected_fields=sorted(touched),
    )


def policy_scheduling_effective_for_slug(slug_value: str) -> bool:
    if not s2_v3_availability_cutover_live():
        return False
    return slug_value in ("work", "general")


def scheduling_effective_note_for_surface() -> str:
    if s2_v3_availability_cutover_live():
        return V3_SCHEDULING_EFFECTIVE_NOTE
    from app.schemas.availability import SCHEDULING_CONFIG_ONLY_COPY

    return SCHEDULING_CONFIG_ONLY_COPY
