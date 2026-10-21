# ==============================================================================
#  File: apps/api/app/services/microsoft_series_identity.py
#  Description: T1-4-MS Graph series identity ternary extractor (§4.0–§4.5).
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

SeriesIdentityState = Literal[
    "verified_series", "verified_non_recurring", "incomplete"
]

SERIES_IDENTITY_VERIFIED_SERIES: SeriesIdentityState = "verified_series"
SERIES_IDENTITY_VERIFIED_NON_RECURRING: SeriesIdentityState = "verified_non_recurring"
SERIES_IDENTITY_INCOMPLETE: SeriesIdentityState = "incomplete"

SeriesSource = Literal["occurrence", "exception", "seriesMaster"]


@dataclass(frozen=True)
class KnownSeries:
    series_id: str
    source: SeriesSource


@dataclass(frozen=True)
class KnownNonRecurring:
    pass


@dataclass(frozen=True)
class IncompleteIdentity:
    reason: str


@dataclass(frozen=True)
class MalformedIdentity:
    reason: str


MicrosoftSeriesIdentity = (
    KnownSeries | KnownNonRecurring | IncompleteIdentity | MalformedIdentity
)


class MicrosoftSeriesIdentityError(Exception):
    """Malformed / unresolvable Graph identity — fail outer refresh (E1)."""

    def __init__(self, reason: str, *, detail: str | None = None) -> None:
        self.reason = reason
        self.detail = detail or reason
        super().__init__(self.detail)


class MicrosoftSeriesMasterInBatchError(Exception):
    """seriesMaster in expanded calendarView / apply batch — fail closed (§4.9)."""

    def __init__(self, event_id: str) -> None:
        self.event_id = event_id
        super().__init__(f"seriesMaster item {event_id} forbidden in apply batch")


def _normalize_optional_id(value: Any) -> str | None | Literal["__malformed__"]:
    """Absent/null/blank ⇒ None; non-null non-str ⇒ malformed sentinel; else strip."""
    if value is None:
        return None
    if not isinstance(value, str):
        return "__malformed__"
    stripped = value.strip()
    if not stripped:
        return None
    return stripped


def extract_microsoft_series_identity(event: dict[str, Any]) -> MicrosoftSeriesIdentity:
    """Frozen §4.0 precedence — contradictions before KnownSeries promotion."""
    if not isinstance(event, dict):
        return MalformedIdentity("missing_event_id")

    raw_id = event.get("id") if "id" in event else None
    if "id" not in event:
        return MalformedIdentity("missing_event_id")
    event_id = _normalize_optional_id(raw_id)
    if event_id is None:
        return MalformedIdentity("missing_event_id")
    if event_id == "__malformed__":
        return MalformedIdentity("non_string_id")

    raw_master = event.get("seriesMasterId") if "seriesMasterId" in event else None
    # Key absent and JSON null both absent; only evaluate when key present or via get.
    if "seriesMasterId" in event:
        master = _normalize_optional_id(raw_master)
    else:
        master = None
    if master == "__malformed__":
        return MalformedIdentity("non_string_series_master_id")

    raw_type = event.get("type")
    if raw_type is None or (isinstance(raw_type, str) and not raw_type.strip()):
        type_s: str | None = None
    elif isinstance(raw_type, str):
        type_s = raw_type.strip()
    else:
        type_s = str(raw_type)

    # Step 2 — contradictions (exact table §4.5)
    if type_s == "singleInstance" and master is not None:
        return MalformedIdentity("contradiction_single_with_master")
    if type_s == "seriesMaster" and master is not None and master != event_id:
        return MalformedIdentity("contradiction_master_foreign_series")
    if type_s in ("occurrence", "exception") and master is not None and master == event_id:
        return MalformedIdentity("contradiction_instance_master_eq_self")

    # Step 3 — occurrence / exception
    if type_s in ("occurrence", "exception"):
        source: SeriesSource = "occurrence" if type_s == "occurrence" else "exception"
        if master is not None:
            return KnownSeries(master, source=source)
        return IncompleteIdentity("missing_series_master")

    # Step 4 — seriesMaster
    if type_s == "seriesMaster":
        return KnownSeries(event_id, source="seriesMaster")

    # Step 5 — singleInstance
    if type_s == "singleInstance":
        return KnownNonRecurring()

    # Step 6 — omitted / unrecognized type
    if master is not None:
        return IncompleteIdentity("unrecognized_type_with_master")
    return IncompleteIdentity("unrecognized_or_omitted_type")


def decided_series_id_for_write(
    identity: MicrosoftSeriesIdentity,
    *,
    old_series_id: str | None,
) -> tuple[str | None, SeriesIdentityState, str | None]:
    """Return (provider_series_id, state, incomplete_reason) for durable write.

    KnownSeries(source=seriesMaster) must not be written — caller raises first.
    """
    if isinstance(identity, KnownSeries):
        if identity.source == "seriesMaster":
            raise MicrosoftSeriesMasterInBatchError(identity.series_id)
        return identity.series_id, SERIES_IDENTITY_VERIFIED_SERIES, None
    if isinstance(identity, KnownNonRecurring):
        return None, SERIES_IDENTITY_VERIFIED_NON_RECURRING, None
    if isinstance(identity, IncompleteIdentity):
        # Retain prior series when present; new row keeps NULL.
        retained = old_series_id
        return retained, SERIES_IDENTITY_INCOMPLETE, identity.reason
    raise MicrosoftSeriesIdentityError(
        getattr(identity, "reason", "malformed"),
        detail="malformed identity must not write",
    )
