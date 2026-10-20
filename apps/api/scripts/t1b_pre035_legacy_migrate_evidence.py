"""Disposable-only: true pre-035 legacy rows → migrate → trust without reparsing.

Seeds representative 034-shaped date-only / ambiguous / absolute-timed rows
(source_zone_missing at 034 server default false; no source_timezone column),
upgrades to 035, then evaluates **persisted** DB bounds/flags through the trust
path without reparsing provider payloads.

Absolute control is Z-offset timed with **null named provenance** (Julie).

Writes evidence under T1A_FIXTURE_ROOT; records git tip. Does not push/deploy
or touch household Postgres.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

# Disposable DSN must be set before app settings bind.
os.environ["T1A_REQUIRE_DISPOSABLE_DSN"] = "1"
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://t1a@127.0.0.1:5433/theplan_t1a_test"
)

from app.scheduler.free_busy import (  # noqa: E402
    T1A_FIXTURE_ROOT,
    evaluate_busy_input_trust,
    events_for_busy_merge,
    source_zone_untrusted,
)
from support.t1a_pg import (  # noqa: E402
    assert_t1a_container_isolated,
    psql_t,
    seed_034_probe_row,
)

UTC = timezone.utc
HORIZON_START = datetime(2026, 10, 19, 16, 0, tzinfo=UTC)
HORIZON_END = datetime(2026, 10, 19, 19, 0, tzinfo=UTC)


def _git_tip() -> str:
    # ROOT = apps/api → repo root is parents[1] from apps/api.
    repo = ROOT.parent.parent if (ROOT.parent.parent / ".git").exists() else ROOT.parent
    got = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    return (got.stdout or "").strip()


def _alembic(*args: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = os.environ["DATABASE_URL"]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic {' '.join(args)} failed rc={result.returncode}\n"
            f"stdout:\n{result.stdout[-1500:]}\nstderr:\n{result.stderr[-1500:]}"
        )


def _row_from_db(eid: str) -> SimpleNamespace:
    """Load persisted columns only — no provider payload reparse."""
    cols = psql_t(
        "SELECT start_time::text, end_time::text, is_all_day::text, "
        "COALESCE(source_timezone, '<null>'), source_zone_missing::text, "
        "transparency, free_busy_provenance, title "
        f"FROM external_calendar_events WHERE external_event_id = '{eid}'"
    )
    parts = cols.split("|")
    if len(parts) != 8:
        raise RuntimeError(f"unexpected row shape for {eid}: {cols!r}")
    start_s, end_s, is_all_day_s, stz, szm, transparency, provenance, title = parts
    start = datetime.fromisoformat(start_s.replace(" ", "T"))
    end = datetime.fromisoformat(end_s.replace(" ", "T"))
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    source_timezone = None if stz == "<null>" else stz
    return SimpleNamespace(
        transparency=transparency or None,
        free_busy_provenance=provenance or None,
        start_time=start,
        end_time=end,
        calendar_id="cal-t1b-pre035",
        title=title,
        external_event_id=eid,
        provider_series_id=None,
        owner_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        provider="google",
        is_all_day=(is_all_day_s == "true"),
        source_zone_missing=(szm == "true"),
        source_timezone=source_timezone,
        free_busy_pending_exception=False,
        scheduled_block_id=None,
        pending_deletion=False,
    )


def _flag_only_would_trust(row: SimpleNamespace) -> bool:
    """What trust would conclude if only the boolean flag mattered (pre-containment)."""
    if row.source_zone_missing:
        return False
    if row.transparency != "opaque":
        return False
    return True


def _seed_034_shaped_rows() -> None:
    """Insert rows as they exist at alembic 034 (no source_timezone column)."""
    version = psql_t("SELECT version_num FROM alembic_version")
    if version != "034_external_event_free_busy":
        raise RuntimeError(f"expected 034 head for seed, got {version!r}")
    has_stz = psql_t(
        "SELECT count(*)::text FROM information_schema.columns "
        "WHERE table_name='external_calendar_events' AND column_name='source_timezone'"
    )
    if has_stz != "0":
        raise RuntimeError("source_timezone must not exist at 034 seed time")

    seed_034_probe_row()  # owner + account FKs
    psql_t(
        "DELETE FROM external_calendar_events WHERE external_event_id LIKE 't1b-pre035-%'"
    )

    # Legacy date-only: pre-T1-B UTC-midnight placeholder; 034 default flag=false.
    psql_t(
        "INSERT INTO external_calendar_events ("
        "id, owner_id, calendar_account_id, provider, external_event_id, calendar_id, "
        "title, start_time, end_time, is_all_day, pending_deletion, transparency, "
        "free_busy_provenance, source_zone_missing, free_busy_pending_exception"
        ") VALUES ("
        "uuid_generate_v4(), "
        "'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'::uuid, "
        "'bbbbbbbb-cccc-dddd-eeee-ffffffffffff'::uuid, "
        "'google', 't1b-pre035-legacy', 'cal-t1b-pre035', "
        "'legacy-date-only-utc-midnight', "
        "'2026-10-19 00:00:00+00', '2026-10-20 00:00:00+00', "
        "true, false, 'opaque', 'provider_explicit', false, false)"
    )
    # Ambiguous / uncertain all-day shape: same 034 defaults (flag false, UTC bounds).
    psql_t(
        "INSERT INTO external_calendar_events ("
        "id, owner_id, calendar_account_id, provider, external_event_id, calendar_id, "
        "title, start_time, end_time, is_all_day, pending_deletion, transparency, "
        "free_busy_provenance, source_zone_missing, free_busy_pending_exception"
        ") VALUES ("
        "uuid_generate_v4(), "
        "'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'::uuid, "
        "'bbbbbbbb-cccc-dddd-eeee-ffffffffffff'::uuid, "
        "'microsoft', 't1b-pre035-ambig', 'cal-t1b-pre035', "
        "'ambiguous-all-day-uncertain-extent', "
        "'2026-10-19 00:00:00+00', '2026-10-20 00:00:00+00', "
        "true, false, 'opaque', 'provider_explicit', false, false)"
    )
    # Absolute timed control: Z-offset, null named provenance after 035, flag false.
    psql_t(
        "INSERT INTO external_calendar_events ("
        "id, owner_id, calendar_account_id, provider, external_event_id, calendar_id, "
        "title, start_time, end_time, is_all_day, pending_deletion, transparency, "
        "free_busy_provenance, source_zone_missing, free_busy_pending_exception"
        ") VALUES ("
        "uuid_generate_v4(), "
        "'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'::uuid, "
        "'bbbbbbbb-cccc-dddd-eeee-ffffffffffff'::uuid, "
        "'microsoft', 't1b-pre035-abs', 'cal-t1b-pre035', "
        "'absolute-z-offset-null-provenance', "
        "'2026-10-19 17:00:00+00', '2026-10-19 18:00:00+00', "
        "false, false, 'opaque', 'provider_explicit', false, false)"
    )


def main() -> None:
    tip = _git_tip()
    meta = assert_t1a_container_isolated()
    before = psql_t("SELECT version_num FROM alembic_version")

    # Restore a true 034 schema on disposable only.
    if before != "034_external_event_free_busy":
        _alembic("downgrade", "034_external_event_free_busy")
    at_034 = psql_t("SELECT version_num FROM alembic_version")
    if at_034 != "034_external_event_free_busy":
        raise RuntimeError(f"downgrade failed; still at {at_034!r}")

    _seed_034_shaped_rows()
    seeded_flags = {
        eid: psql_t(
            "SELECT source_zone_missing::text FROM external_calendar_events "
            f"WHERE external_event_id='{eid}'"
        )
        for eid in ("t1b-pre035-legacy", "t1b-pre035-ambig", "t1b-pre035-abs")
    }

    _alembic("upgrade", "035_source_timezone")
    at_035 = psql_t("SELECT version_num FROM alembic_version")
    if at_035 != "035_source_timezone":
        raise RuntimeError(f"upgrade failed; at {at_035!r}")

    recorded = []
    for eid in ("t1b-pre035-legacy", "t1b-pre035-ambig", "t1b-pre035-abs"):
        row = _row_from_db(eid)
        trust = evaluate_busy_input_trust(
            [row], horizon_start=HORIZON_START, horizon_end=HORIZON_END
        )
        recorded.append(
            {
                "eid": eid,
                "is_all_day": row.is_all_day,
                "db_source_zone_missing": row.source_zone_missing,
                "db_source_timezone": row.source_timezone
                if row.source_timezone is not None
                else "<null>",
                "db_start": row.start_time.isoformat(),
                "db_end": row.end_time.isoformat(),
                "reparsed_provider_payload": False,
                "flag_only_would_trust": _flag_only_would_trust(
                    SimpleNamespace(
                        source_zone_missing=(seeded_flags[eid] == "true"),
                        transparency=row.transparency,
                    )
                ),
                "seeded_source_zone_missing_at_034": seeded_flags[eid],
                "source_zone_untrusted": source_zone_untrusted(row),
                "trust_ok": trust.ok,
                "causes": [d.cause for d in trust.blocking_diagnostics],
                "merge_count": len(events_for_busy_merge([row])),
            }
        )

    hole = any(
        r["eid"] != "t1b-pre035-abs"
        and r["seeded_source_zone_missing_at_034"] == "false"
        and r["flag_only_would_trust"]
        for r in recorded
    )
    # Prove schema-only 035: legacy all-day keeps flag=false; read path blocks.
    for r in recorded:
        if r["eid"] == "t1b-pre035-abs":
            if r["db_source_zone_missing"] is not False:
                raise RuntimeError(
                    f"absolute control must keep source_zone_missing=false: {r}"
                )
            if r["source_zone_untrusted"] or not r["trust_ok"] or r["merge_count"] != 1:
                raise RuntimeError(f"absolute control must stay trusted: {r}")
            continue
        if r["db_source_zone_missing"] is not False:
            raise RuntimeError(
                "035 must not mutate source_zone_missing; "
                f"legacy/ambig expected false after schema-only upgrade: {r}"
            )
        if (
            not r["source_zone_untrusted"]
            or r["trust_ok"]
            or r["merge_count"] != 0
            or "missing_source_zone" not in r["causes"]
        ):
            raise RuntimeError(
                "read-path source_zone_untrusted must block legacy/ambig "
                f"despite flag=false: {r}"
            )
    out = {
        "git_tip": tip,
        "isolation": {
            "database": meta["database"],
            "host_port": meta["host_port"],
            "host_ip": meta["host_ip"],
            "container": meta["container"],
        },
        "alembic_before": before,
        "alembic_seed": "034_external_event_free_busy",
        "alembic_after": at_035,
        "method": (
            "seed at 034 without source_timezone column; alembic upgrade 035 "
            "(schema only, no flag UPDATE); trust path on persisted columns "
            "only (no provider reparse)"
        ),
        "absolute_control": (
            "t1b-pre035-abs is Z-offset timed with null named provenance "
            "(source_timezone null); must remain trusted"
        ),
        "containment": {
            "needed_if_flag_only_trusts_uncertain_all_day": hole,
            "sole_rule": (
                "read-path source_zone_untrusted: all-day + null "
                "source_timezone → missing_source_zone (flag may stay false). "
                "035 adds columns only — no data UPDATE. "
                "Timed absolute null provenance stays trusted."
            ),
            "implemented": True,
        },
        "fixtures": recorded,
    }
    path = T1A_FIXTURE_ROOT / f"t1b-pre035-migrate-trust-{tip[:12]}.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(path)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
