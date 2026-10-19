"""Track 1 T1-A: Google free/busy trust, diagnostics, and exception identity.

BusyInputTrust is a collect-time input check only — ok=True does not mean
overall scheduling readiness (deps, caps, freshness, etc.).

Fail-closed: calculate/replan/preview must refuse placement when ok=False.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Sequence

FreeBusyKind = Literal["busy", "free", "unknown"]
ProvenanceLabel = Literal[
    "provider_explicit",
    "provider_default_omitted",
    "unknown_legacy",
    "unknown_projection",
    "manual_resolve",
    "unknown_missing",
]

T1A_FIXTURE_ROOT = Path(r"F:\thePlan-imports\investigation-2026-10-19\t1a-fixtures")
DISPOSABLE_TARGET_DB = "theplan_t1a_test"
REQUIRED_SNAPSHOT_ARTIFACTS = ("db.dump", "manifest.json", "checksums.sha256")

# Exception policies: owner / provider / calendar / series (never title alone).
_EXCEPTION_POLICIES: dict[tuple[str, str, str, str], FreeBusyKind] = {}


class BusyInputTrustError(RuntimeError):
    """Raised when BusyInputTrust.ok is false — blocks calculate/apply."""

    def __init__(self, trust: "BusyInputTrust") -> None:
        self.trust = trust
        super().__init__(
            "BusyInputTrust.ok=false: unresolved free/busy or related input "
            "blocks placement (cannot prove non-intersection)."
        )


@dataclass(frozen=True)
class ExceptionIdentity:
    owner_id: str
    provider: str
    calendar_id: str
    series_id: str

    def key(self) -> tuple[str, str, str, str]:
        return (
            str(self.owner_id),
            str(self.provider),
            str(self.calendar_id),
            str(self.series_id),
        )


@dataclass(frozen=True)
class FreeBusyDiagnostic:
    cause: str
    calendar_name: str
    event_title: str
    event_id: str
    start: datetime | None
    end: datetime | None
    blocking_current_proposal: bool
    affected_horizon: str
    provenance: str | None = None

    def display_line(self) -> str:
        when = "unknown time"
        if self.start is not None and self.end is not None:
            when = f"{self.start.isoformat()} – {self.end.isoformat()}"
        return (
            f'{self.cause}: calendar "{self.calendar_name}", '
            f'title "{self.event_title}", {when}, id={self.event_id}'
        )

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "cause": self.cause,
            "calendar_name": self.calendar_name,
            "event_title": self.event_title,
            "event_id": self.event_id,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "blocking_current_proposal": self.blocking_current_proposal,
            "affected_horizon": self.affected_horizon,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class DiagnosticRollup:
    calendar_name: str
    cause: str
    count: int
    recovery: str

    def display_line(self) -> str:
        return f'{self.recovery}: {self.count} events with {self.cause}'

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "calendar_name": self.calendar_name,
            "cause": self.cause,
            "count": self.count,
            "recovery": self.recovery,
        }


@dataclass
class BusyInputTrust:
    ok: bool
    blocking_diagnostics: list[FreeBusyDiagnostic] = field(default_factory=list)
    affected_horizon: dict[str, str] | Literal["unknown_extent"] | None = None
    rollups: list[DiagnosticRollup] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe (datetimes already ISO in diagnostics)."""
        return {
            "ok": self.ok,
            "blocking_diagnostics": [d.to_jsonable() for d in self.blocking_diagnostics],
            "affected_horizon": self.affected_horizon,
            "rollups": [r.to_jsonable() for r in self.rollups],
        }


def register_exception_policy(identity: ExceptionIdentity, mapping: FreeBusyKind) -> None:
    if not identity.series_id or not str(identity.series_id).strip():
        raise ValueError("exception policy requires verified provider series id")
    if not identity.calendar_id or not identity.provider or not identity.owner_id:
        raise ValueError("exception policy requires owner, provider, and calendar")
    _EXCEPTION_POLICIES[identity.key()] = mapping


def clear_exception_policies() -> None:
    _EXCEPTION_POLICIES.clear()


def lookup_exception_policy(identity: ExceptionIdentity | None) -> FreeBusyKind | None:
    if identity is None or not identity.series_id:
        return None
    return _EXCEPTION_POLICIES.get(identity.key())


def resolve_google_transparency(
    event: Mapping[str, Any],
    *,
    complete_representation: bool = True,
    field_projected: bool = False,
) -> tuple[str | None, ProvenanceLabel, FreeBusyKind]:
    if field_projected or not complete_representation:
        return None, "unknown_projection", "unknown"

    if "transparency" in event:
        raw = event.get("transparency")
        if raw in ("opaque", "transparent"):
            kind: FreeBusyKind = "busy" if raw == "opaque" else "free"
            return str(raw), "provider_explicit", kind
        return None, "unknown_projection", "unknown"

    return "opaque", "provider_default_omitted", "busy"


def effective_free_busy_kind(
    *,
    transparency: str | None,
    provenance: str | None,
    identity: ExceptionIdentity | None = None,
    pending_exception: bool = False,
) -> FreeBusyKind:
    if pending_exception:
        return "unknown"
    policy = lookup_exception_policy(identity)
    if policy is not None:
        return policy

    if provenance in ("unknown_legacy", "unknown_projection", "unknown_missing") or (
        transparency is None and provenance is None
    ):
        return "unknown"
    if transparency == "transparent":
        return "free"
    if transparency == "opaque":
        return "busy"
    return "unknown"


def _ranges_overlap(
    a_start: datetime | None,
    a_end: datetime | None,
    b_start: datetime,
    b_end: datetime,
) -> bool | None:
    if a_start is None or a_end is None:
        return None
    return a_start < b_end and a_end > b_start


def _event_identity(event: Any) -> ExceptionIdentity | None:
    series = getattr(event, "provider_series_id", None)
    if not series:
        return None
    owner = getattr(event, "owner_id", None)
    provider = getattr(event, "provider", None)
    calendar = getattr(event, "calendar_id", None)
    if owner is None or provider is None or not calendar:
        return None
    provider_s = getattr(provider, "value", None) or str(provider)
    return ExceptionIdentity(
        owner_id=str(owner),
        provider=str(provider_s),
        calendar_id=str(calendar),
        series_id=str(series),
    )


def evaluate_busy_input_trust(
    events: Sequence[Any],
    *,
    horizon_start: datetime,
    horizon_end: datetime,
    calendar_name_by_id: Mapping[str, str] | None = None,
) -> BusyInputTrust:
    """Build BusyInputTrust. Cannot prove non-intersection ⇒ ok=False."""
    names = calendar_name_by_id or {}
    blocking: list[FreeBusyDiagnostic] = []
    unknown_extent = False

    for event in events:
        transparency = getattr(event, "transparency", None)
        provenance = getattr(event, "free_busy_provenance", None)
        identity = _event_identity(event)
        pending = bool(getattr(event, "free_busy_pending_exception", False))
        missing_zone = bool(getattr(event, "source_zone_missing", False))
        kind = effective_free_busy_kind(
            transparency=transparency,
            provenance=provenance,
            identity=identity,
            pending_exception=pending,
        )
        start = getattr(event, "start_time", None)
        end = getattr(event, "end_time", None)
        cal_id = getattr(event, "calendar_id", "") or ""
        cal_name = names.get(cal_id, cal_id or "(unknown calendar)")
        title = getattr(event, "title", None) or "(untitled)"
        eid = getattr(event, "external_event_id", None) or str(getattr(event, "id", ""))

        def _block(cause: str, *, extent_unknown: bool) -> None:
            nonlocal unknown_extent
            if extent_unknown:
                unknown_extent = True
                horizon_label = "unknown_extent"
            else:
                horizon_label = f"{horizon_start.isoformat()}/{horizon_end.isoformat()}"
            blocking.append(
                FreeBusyDiagnostic(
                    cause=cause,
                    calendar_name=cal_name,
                    event_title=title,
                    event_id=str(eid),
                    start=start,
                    end=end,
                    blocking_current_proposal=True,
                    affected_horizon=horizon_label,
                    provenance=provenance,
                )
            )

        if missing_zone:
            # §3.1: missing source zone is always blocking — stored bounds are
            # untrusted, so "outside horizon" is not a positive proof of irrelevance.
            _block("missing_source_zone", extent_unknown=True)
            continue

        if pending:
            # Pending policy: cannot treat as busy or free until resolved.
            _block("pending_exception_policy", extent_unknown=True)
            continue

        if kind in ("busy", "free"):
            overlap = _ranges_overlap(start, end, horizon_start, horizon_end)
            if overlap is None:
                # Known kind but unknown bounds — cannot prove irrelevance.
                _block(f"unknown_extent:{kind}", extent_unknown=True)
            # known busy/free with known bounds: occupancy handled in busy_map; not a trust fail
            continue

        # unknown free/busy
        overlap = _ranges_overlap(start, end, horizon_start, horizon_end)
        if overlap is False:
            continue
        cause = "unknown_free_busy"
        if provenance:
            cause = f"unknown_free_busy:{provenance}"
        _block(cause, extent_unknown=overlap is None)

    rollups = group_diagnostics(blocking)
    ok = len(blocking) == 0
    if unknown_extent:
        affected: dict[str, str] | Literal["unknown_extent"] | None = "unknown_extent"
    else:
        affected = {
            "start": horizon_start.isoformat(),
            "end": horizon_end.isoformat(),
        }
    return BusyInputTrust(
        ok=ok,
        blocking_diagnostics=blocking,
        affected_horizon=affected,
        rollups=rollups,
    )


def require_busy_input_trust(trust: BusyInputTrust | None) -> None:
    """Shared fail-closed gate for calculate / replan / preview.

    ``None`` means the check was never established — fail closed (not a pass).
    """
    if trust is None:
        missing = BusyInputTrust(
            ok=False,
            blocking_diagnostics=[
                FreeBusyDiagnostic(
                    cause="missing_busy_input_trust",
                    calendar_name="(none)",
                    event_title="(trust not evaluated)",
                    event_id="-",
                    start=None,
                    end=None,
                    blocking_current_proposal=True,
                    affected_horizon="unknown_extent",
                    provenance=None,
                )
            ],
            affected_horizon="unknown_extent",
            rollups=[
                DiagnosticRollup(
                    calendar_name="(none)",
                    cause="missing_busy_input_trust",
                    count=1,
                    recovery="re-run collect_inputs before calculate",
                )
            ],
        )
        raise BusyInputTrustError(missing)
    if not trust.ok:
        raise BusyInputTrustError(trust)


def group_diagnostics(diagnostics: Iterable[FreeBusyDiagnostic]) -> list[DiagnosticRollup]:
    counts: dict[tuple[str, str], int] = {}
    for d in diagnostics:
        key = (d.calendar_name, d.cause)
        counts[key] = counts.get(key, 0) + 1
    rollups: list[DiagnosticRollup] = []
    for (cal, cause), n in sorted(counts.items()):
        rollups.append(
            DiagnosticRollup(
                calendar_name=cal,
                cause=cause,
                count=n,
                recovery=f'refresh "{cal}"',
            )
        )
    return rollups


def format_cli_listing(trust: BusyInputTrust) -> str:
    lines = [
        f"BusyInputTrust.ok={trust.ok}",
        f"affected_horizon={trust.affected_horizon!r}",
        "",
        "Rollups:",
    ]
    if not trust.rollups:
        lines.append("  (none)")
    else:
        for r in trust.rollups:
            lines.append(f"  {r.display_line()}")
    lines.append("")
    lines.append("Diagnostics:")
    if not trust.blocking_diagnostics:
        lines.append("  (none)")
    else:
        for d in trust.blocking_diagnostics:
            lines.append(f"  {d.display_line()}")
    return "\n".join(lines)


def events_for_busy_merge(events: Sequence[Any]) -> list[Any]:
    """Opaque/busy only. Unknowns are excluded from occupancy (trust blocks instead)."""
    out = []
    for event in events:
        if bool(getattr(event, "free_busy_pending_exception", False)):
            continue
        if bool(getattr(event, "source_zone_missing", False)):
            continue
        kind = effective_free_busy_kind(
            transparency=getattr(event, "transparency", None),
            provenance=getattr(event, "free_busy_provenance", None),
            identity=_event_identity(event),
        )
        if kind == "busy":
            start = getattr(event, "start_time", None)
            end = getattr(event, "end_time", None)
            if start is None or end is None:
                continue  # unknown extent → trust blocks; do not invent occupancy
            out.append(event)
    return out


def apply_transparency_update(
    row: Any,
    *,
    stored: str | None,
    provenance: str,
    sync_run_id: str,
) -> None:
    """Persist new free/busy values with append-only change history (§4.2)."""
    prior_t = getattr(row, "transparency", None)
    prior_p = getattr(row, "free_busy_provenance", None)
    changed_at = datetime.now(timezone.utc)
    if prior_t != stored or prior_p != provenance:
        row.free_busy_prior_transparency = prior_t
        row.free_busy_prior_provenance = prior_p
        row.free_busy_changed_at = changed_at
        history = list(getattr(row, "free_busy_change_history", None) or [])
        history.append(
            {
                "at": changed_at.replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "sync_run_id": sync_run_id,
                "from_transparency": prior_t,
                "from_provenance": prior_p,
                "to_transparency": stored,
                "to_provenance": provenance,
            }
        )
        row.free_busy_change_history = history
    row.transparency = stored
    row.free_busy_provenance = provenance
    row.free_busy_sync_run_id = sync_run_id


def write_isolated_snapshot(
    *,
    run_id: str | None = None,
    target_db: str = DISPOSABLE_TARGET_DB,
    alembic_head: str | None = None,
    git_tip: str | None = None,
    captured_unchanged: Sequence[Mapping[str, Any]] | None = None,
    db_dump_bytes: bytes,
    root: Path | None = None,
) -> Path:
    """Write immutable isolated snapshot. Refuses household targets and overwrites."""
    if target_db != DISPOSABLE_TARGET_DB:
        raise ValueError(
            f"target_db must be {DISPOSABLE_TARGET_DB!r} (got {target_db!r})"
        )
    if not db_dump_bytes:
        raise ValueError("db_dump_bytes required; dummy dumps are not accepted")

    base = root or T1A_FIXTURE_ROOT
    base.mkdir(parents=True, exist_ok=True)
    rid = run_id or (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    )
    run_dir = base / rid
    if run_dir.exists():
        raise FileExistsError(f"snapshot run folder already exists (immutable): {run_dir}")

    run_dir.mkdir(parents=True, exist_ok=False)
    dump_path = run_dir / "db.dump"
    dump_path.write_bytes(db_dump_bytes)

    manifest = {
        "run_id": rid,
        "utc_timestamp": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "target_db": target_db,
        "alembic_head": alembic_head,
        "git_tip": git_tip,
        "captured_unchanged": list(captured_unchanged or []),
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    checksum_lines = []
    for name in ("db.dump", "manifest.json"):
        path = run_dir / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checksum_lines.append(f"{digest}  {name}")
    checksum_path = run_dir / "checksums.sha256"
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    if not verify_snapshot_checksums(run_dir):
        shutil.rmtree(run_dir, ignore_errors=True)
        raise RuntimeError("snapshot checksum verification failed immediately after write")
    return run_dir


def verify_snapshot_checksums(run_dir: Path) -> bool:
    checksum_path = run_dir / "checksums.sha256"
    if not checksum_path.is_file():
        return False
    lines = [
        line.strip()
        for line in checksum_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not lines:
        return False
    required = set(REQUIRED_SNAPSHOT_ARTIFACTS) - {"checksums.sha256"}
    named: set[str] = set()
    for line in lines:
        digest, _, name = line.partition("  ")
        if not name or not digest:
            return False
        named.add(name)
        path = run_dir / name
        if not path.is_file():
            return False
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return False
    return required.issubset(named)


def restore_isolated_snapshot(run_dir: Path, *, restore_to: Path) -> Path:
    """Restore db.dump into a disposable path after checksum verify. Never household."""
    if not verify_snapshot_checksums(run_dir):
        raise RuntimeError("snapshot checksum failed; refuse restore / mutation")
    dump = run_dir / "db.dump"
    restore_to.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(dump, restore_to)
    return restore_to


def mutate_with_snapshot_gate(
    run_dir: Path,
    *,
    mutate_fn,
) -> Any:
    """Run mutate_fn only if snapshot verifies; on failure do not call mutate_fn."""
    if not verify_snapshot_checksums(run_dir):
        raise RuntimeError("snapshot failure → stop; do not write")
    return mutate_fn()
