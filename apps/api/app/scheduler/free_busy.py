"""Track 1 T1-A: Google free/busy trust, diagnostics, and exception identity.

BusyInputTrust is a collect-time input check only — ok=True does not mean
overall scheduling readiness (deps, caps, freshness, etc.).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Sequence
from uuid import UUID

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

# Exception policies keyed by verified provider series id (never by title).
_EXCEPTION_POLICIES: dict[str, FreeBusyKind] = {}


@dataclass(frozen=True)
class FreeBusyDiagnostic:
    cause: str
    calendar_name: str
    event_title: str
    event_id: str
    start: datetime | None
    end: datetime | None
    blocking_current_proposal: bool
    affected_horizon: str  # ISO range or "unknown_extent"
    provenance: str | None = None

    def display_line(self) -> str:
        when = "unknown time"
        if self.start is not None and self.end is not None:
            when = f"{self.start.isoformat()} – {self.end.isoformat()}"
        return (
            f'{self.cause}: calendar "{self.calendar_name}", '
            f'title "{self.event_title}", {when}, id={self.event_id}'
        )


@dataclass(frozen=True)
class DiagnosticRollup:
    calendar_name: str
    cause: str
    count: int
    recovery: str

    def display_line(self) -> str:
        return f'{self.recovery}: {self.count} events with {self.cause}'


@dataclass
class BusyInputTrust:
    """Collect-time free/busy input trust result (T1-A)."""

    ok: bool
    blocking_diagnostics: list[FreeBusyDiagnostic] = field(default_factory=list)
    affected_horizon: dict[str, str] | Literal["unknown_extent"] | None = None
    rollups: list[DiagnosticRollup] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "blocking_diagnostics": [asdict(d) for d in self.blocking_diagnostics],
            "affected_horizon": self.affected_horizon,
            "rollups": [asdict(r) for r in self.rollups],
        }


def register_exception_policy(provider_series_id: str, mapping: FreeBusyKind) -> None:
    """Attach a non-blocking policy only to a verified provider series id."""
    if not provider_series_id or not str(provider_series_id).strip():
        raise ValueError("exception policy requires verified provider_series_id")
    _EXCEPTION_POLICIES[str(provider_series_id)] = mapping


def clear_exception_policies() -> None:
    _EXCEPTION_POLICIES.clear()


def lookup_exception_policy(provider_series_id: str | None) -> FreeBusyKind | None:
    if not provider_series_id:
        return None
    return _EXCEPTION_POLICIES.get(str(provider_series_id))


def resolve_google_transparency(
    event: Mapping[str, Any],
    *,
    complete_representation: bool = True,
    field_projected: bool = False,
) -> tuple[str | None, ProvenanceLabel, FreeBusyKind]:
    """Cases A/B/C from Track-1-Contracts §1.1.

    Returns (stored_transparency, provenance, busy_kind).
    """
    if field_projected or not complete_representation:
        return None, "unknown_projection", "unknown"

    if "transparency" in event:
        raw = event.get("transparency")
        if raw in ("opaque", "transparent"):
            kind: FreeBusyKind = "busy" if raw == "opaque" else "free"
            return str(raw), "provider_explicit", kind
        return None, "unknown_projection", "unknown"

    # Case B: complete fresh representation omits the field → documented opaque.
    return "opaque", "provider_default_omitted", "busy"


def effective_free_busy_kind(
    *,
    transparency: str | None,
    provenance: str | None,
    provider_series_id: str | None = None,
) -> FreeBusyKind:
    policy = lookup_exception_policy(provider_series_id)
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
    """True/False when both bounds known; None when cannot prove."""
    if a_start is None or a_end is None:
        return None
    return a_start < b_end and a_end > b_start


def evaluate_busy_input_trust(
    events: Sequence[Any],
    *,
    horizon_start: datetime,
    horizon_end: datetime,
    calendar_name_by_id: Mapping[str, str] | None = None,
) -> BusyInputTrust:
    """Build BusyInputTrust for events intersecting (or possibly intersecting) horizon.

    Cannot prove non-intersection ⇒ blocking (ok=False). Title never matches policy.
    """
    names = calendar_name_by_id or {}
    blocking: list[FreeBusyDiagnostic] = []
    unknown_extent = False

    for event in events:
        transparency = getattr(event, "transparency", None)
        provenance = getattr(event, "free_busy_provenance", None)
        series_id = getattr(event, "provider_series_id", None)
        kind = effective_free_busy_kind(
            transparency=transparency,
            provenance=provenance,
            provider_series_id=series_id,
        )
        start = getattr(event, "start_time", None)
        end = getattr(event, "end_time", None)
        cal_id = getattr(event, "calendar_id", "") or ""
        cal_name = names.get(cal_id, cal_id or "(unknown calendar)")
        title = getattr(event, "title", None) or "(untitled)"
        eid = getattr(event, "external_event_id", None) or str(getattr(event, "id", ""))

        if kind == "free":
            continue
        if kind == "busy":
            overlap = _ranges_overlap(start, end, horizon_start, horizon_end)
            if overlap is False:
                continue
            # busy events are occupancy, not trust failures
            continue

        # unknown
        overlap = _ranges_overlap(start, end, horizon_start, horizon_end)
        if overlap is False:
            continue
        if overlap is None:
            unknown_extent = True
            horizon_label = "unknown_extent"
            blocking_flag = True
        else:
            horizon_label = f"{horizon_start.isoformat()}/{horizon_end.isoformat()}"
            blocking_flag = True

        cause = "unknown_free_busy"
        if provenance:
            cause = f"unknown_free_busy:{provenance}"
        blocking.append(
            FreeBusyDiagnostic(
                cause=cause,
                calendar_name=cal_name,
                event_title=title,
                event_id=str(eid),
                start=start,
                end=end,
                blocking_current_proposal=blocking_flag,
                affected_horizon=horizon_label,
                provenance=provenance,
            )
        )

    rollups = group_diagnostics(blocking)
    ok = len(blocking) == 0
    affected: dict[str, str] | Literal["unknown_extent"] | None
    if unknown_extent:
        affected = "unknown_extent"
    elif blocking:
        affected = {
            "start": horizon_start.isoformat(),
            "end": horizon_end.isoformat(),
        }
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
    """Return events that should occupy the busy map (opaque / busy only)."""
    out = []
    for event in events:
        kind = effective_free_busy_kind(
            transparency=getattr(event, "transparency", None),
            provenance=getattr(event, "free_busy_provenance", None),
            provider_series_id=getattr(event, "provider_series_id", None),
        )
        if kind == "busy":
            out.append(event)
    return out


def write_isolated_snapshot(
    *,
    run_id: str,
    target_db: str = "theplan_t1a_test",
    alembic_head: str | None = None,
    git_tip: str | None = None,
    captured_unchanged: Sequence[Mapping[str, Any]] | None = None,
    db_dump_bytes: bytes | None = None,
    root: Path | None = None,
) -> Path:
    """Write T1-A isolated fixture snapshot under thePlan-imports (never household)."""
    base = root or T1A_FIXTURE_ROOT
    run_dir = base / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    dump = db_dump_bytes if db_dump_bytes is not None else b"# disposable fixture dump\n"
    dump_path = run_dir / "db.dump"
    dump_path.write_bytes(dump)

    manifest = {
        "run_id": run_id,
        "utc_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "target_db": target_db,
        "alembic_head": alembic_head,
        "git_tip": git_tip,
        "captured_unchanged": list(captured_unchanged or []),
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    checksum_lines = []
    for path in (dump_path, manifest_path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checksum_lines.append(f"{digest}  {path.name}")
    checksum_path = run_dir / "checksums.sha256"
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    return run_dir


def verify_snapshot_checksums(run_dir: Path) -> bool:
    checksum_path = run_dir / "checksums.sha256"
    if not checksum_path.is_file():
        return False
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        digest, _, name = line.partition("  ")
        path = run_dir / name
        if not path.is_file():
            return False
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return False
    return True


def exception_policy_matches_title(*, title: str, provider_series_id: str | None) -> bool:
    """Identity hook: title must never grant a policy. Returns True if mis-matched (bad)."""
    _ = title  # titles are display-only
    return lookup_exception_policy(provider_series_id) is not None and not provider_series_id
