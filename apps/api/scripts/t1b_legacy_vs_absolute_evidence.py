"""Disposable-only: seed T1-B legacy/ambiguous/absolute rows; record trust from DB flags."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from app.scheduler.free_busy import (  # noqa: E402
    T1A_FIXTURE_ROOT,
    evaluate_busy_input_trust,
    events_for_busy_merge,
)
from app.services.google_calendar import parse_google_event_times  # noqa: E402
from app.services.microsoft_calendar import parse_microsoft_event_times  # noqa: E402
from support.t1a_pg import (  # noqa: E402
    assert_t1a_container_isolated,
    psql_t,
    seed_034_probe_row,
)

UTC = timezone.utc


def _row(parsed, *, eid: str, title: str, missing: bool) -> SimpleNamespace:
    return SimpleNamespace(
        transparency="opaque",
        free_busy_provenance="provider_explicit",
        start_time=parsed.start,
        end_time=parsed.end,
        calendar_id="cal-t1b",
        title=title,
        external_event_id=eid,
        provider_series_id=None,
        owner_id="o",
        provider="microsoft",
        source_zone_missing=missing,
        free_busy_pending_exception=False,
        scheduled_block_id=None,
        pending_deletion=False,
    )


def main() -> None:
    meta = assert_t1a_container_isolated()
    seed_034_probe_row()  # ensures owner/account FKs exist on disposable DB
    psql_t(
        "DELETE FROM external_calendar_events WHERE external_event_id LIKE 't1b-fix-%'"
    )

    legacy = parse_google_event_times(
        {"start": {"date": "2026-10-19"}, "end": {"date": "2026-10-20"}}
    )
    ambig = parse_microsoft_event_times(
        {
            "isAllDay": True,
            "originalStartTimeZone": "Eastern Standard Time",
            "originalEndTimeZone": "Pacific Standard Time",
            "start": {"dateTime": "2026-10-19T04:00:00.0000000", "timeZone": "UTC"},
            "end": {"dateTime": "2026-10-20T04:00:00.0000000", "timeZone": "UTC"},
        }
    )
    absolute = parse_microsoft_event_times(
        {
            "isAllDay": False,
            "originalStartTimeZone": "Pacific Standard Time",
            "originalEndTimeZone": "Pacific Standard Time",
            "start": {"dateTime": "2026-10-19T17:00:00.0000000", "timeZone": "UTC"},
            "end": {"dateTime": "2026-10-19T18:00:00.0000000", "timeZone": "UTC"},
        }
    )
    assert legacy and ambig and absolute

    fixtures = [
        ("t1b-fix-legacy", legacy, "legacy-date-only"),
        ("t1b-fix-ambig", ambig, "ambiguous-originals"),
        ("t1b-fix-abs", absolute, "absolute-offset-timed"),
    ]
    recorded = []
    for eid, parsed, title in fixtures:
        stz_sql = (
            f"'{parsed.source_timezone}'" if parsed.source_timezone else "NULL"
        )
        psql_t(
            "INSERT INTO external_calendar_events ("
            "id, owner_id, calendar_account_id, provider, external_event_id, calendar_id, "
            "title, start_time, end_time, is_all_day, pending_deletion, transparency, "
            "free_busy_provenance, source_zone_missing, source_timezone, "
            "free_busy_pending_exception"
            ") VALUES ("
            "uuid_generate_v4(), "
            "'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'::uuid, "
            "'bbbbbbbb-cccc-dddd-eeee-ffffffffffff'::uuid, "
            f"'google', '{eid}', 'cal-t1b', '{title}', "
            f"'{parsed.start.isoformat()}', '{parsed.end.isoformat()}', "
            f"{str(parsed.is_all_day).lower()}, false, 'opaque', 'provider_explicit', "
            f"{str(parsed.source_zone_missing).lower()}, {stz_sql}, false)"
        )
        szm = psql_t(
            "SELECT source_zone_missing::text FROM external_calendar_events "
            f"WHERE external_event_id='{eid}'"
        )
        stz = psql_t(
            "SELECT COALESCE(source_timezone, '<null>') FROM external_calendar_events "
            f"WHERE external_event_id='{eid}'"
        )
        row = _row(parsed, eid=eid, title=title, missing=(szm == "true"))
        trust = evaluate_busy_input_trust(
            [row],
            horizon_start=datetime(2026, 10, 19, 16, 0, tzinfo=UTC),
            horizon_end=datetime(2026, 10, 19, 19, 0, tzinfo=UTC),
        )
        recorded.append(
            {
                "eid": eid,
                "db_source_zone_missing": szm,
                "db_source_timezone": stz,
                "parsed_source_zone_missing": parsed.source_zone_missing,
                "parsed_source_timezone": parsed.source_timezone,
                "trust_ok": trust.ok,
                "causes": [d.cause for d in trust.blocking_diagnostics],
                "merge_count": len(events_for_busy_merge([row])),
            }
        )

    out = {
        "isolation": {
            "database": meta["database"],
            "host_port": meta["host_port"],
            "host_ip": meta["host_ip"],
        },
        "alembic": psql_t("SELECT version_num FROM alembic_version"),
        "note": (
            "source_zone_missing + trust from actual DB/parser flags; "
            "absolute timed may be trusted with null source_timezone provenance"
        ),
        "fixtures": recorded,
    }
    path = T1A_FIXTURE_ROOT / "t1b-035-legacy-vs-absolute-trust.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(path)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
