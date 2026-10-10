# F7 existing-data migration verify

<!--
==============================================================================
  File: docs/delivery/F7-MIGRATION-VERIFY.md
  Description: Runbook to verify Alembic 027 on pre-migration Postgres (not daily-driver).
  Component: Docs/Delivery
  Version: 1.0
  Created: 2026-10-10
  Last Update: 2026-10-10 (Page — B-F7-1 closed disposition, Trish fresh+synthetic)
==============================================================================
-->

**Status:** **B-F7-1 closed (disposition, Trish 2026-10-10):** Migration verification accepts **fresh disposable migrate** (Dex) plus **synthetic pre-027 dry-run** (Tesla **2026-10-10**). A household dump restore is **not** required for this bucket. Daily-driver was not touched. F7 feature sign-off remains **Open** elsewhere ([MANUAL-CHECKLIST.md](./MANUAL-CHECKLIST.md)); Dex **F4 Wave 1** and **F6 P1 R1** retests still in flight — unrelated to this runbook.

Dex verified a **fresh** migrate: empty/bootstrap database, `alembic upgrade head` → **`027_saved_filter_presentation`**, system views with **`predicate_json.v = 1`**. The synthetic dry-run below exercised **`026 → 027`** on legacy-shaped rows. The **Household path** section remains an optional operator runbook if someone wants a real dump on disposable Postgres.

## Do not

- Do not run this against Compose project `compose`, container `compose-postgres-1`, host port **5432**, or volume `pgdata`.
- Do not `docker compose -f infra/compose/compose.yaml up` for this check. That file publishes **5432** and uses the daily-driver volume.
- Do not run `alembic` from `apps/api` without an explicit `DATABASE_URL` for this process. `app.config.Settings` reads `apps/api/.env`, and the code default is `127.0.0.1:5432`.
- Do not treat `alembic downgrade 026_pending_deletion` as a data rollback. It drops `presentation_json` and leaves the v1 predicates in place (confirmed on the synthetic dry-run below).

## What 027 does

Revision [`027_saved_filter_presentation`](../../apps/api/alembic/versions/027_saved_filter_presentation.py):

- Adds `saved_filters.presentation_json` `JSONB NOT NULL` with server default `'{}'::jsonb`. Existing rows receive `{}`.
- Replaces `predicate_json` where `is_system = true` and `slug` is `inbox`, `today`, or `upcoming`. The replace is unconditional. It does not insert missing system rows. It does not rewrite `is_system = false` rows or any other slug.
- The `UPDATE` is not limited to the bootstrap user. Every owner’s matching system rows are rewritten.

Expected system predicates after upgrade (jsonb equality; key order does not matter):

| slug | `predicate_json` |
|------|------------------|
| `inbox` | `{"v": 1, "dimensions": {"inbox": true, "completion": "open"}}` |
| `today` | `{"v": 1, "dimensions": {"due": {"kind": "rolling", "rolling": "today"}, "completion": "open"}}` |
| `upcoming` | `{"v": 1, "dimensions": {"due": {"kind": "rolling", "rolling": "within_days", "days": 7}, "completion": "open"}}` |

`presentation_json` on those rows is `{}` unless something later patches it. 027 itself only applies the column default.

Pre-027 system seeds (original bootstrap) were legacy `op` / `clauses` trees, not v1:

- **inbox** — `project_id` `is_null` and `is_completed` `eq` false
- **today** — `due_at` `is_today` and `is_completed` `eq` false
- **upcoming** — `due_at` `within_days` 7 and `is_completed` `eq` false

## Household path (optional)

Not required after Trish **2026-10-10** accepted fresh + synthetic coverage. Use only if you want a real pre-027 dump on disposable Postgres (never the daily-driver).

### 0. Dump

Prefer an existing `backups/theplan-*.sql` taken while `alembic_version` was still **`026_pending_deletion`** or earlier. `backups/` is gitignored.

A fresh dump is a **read** of the live database. Do not follow it with `alembic upgrade` on that same database.

```powershell
docker compose -f infra/compose/compose.yaml exec -T postgres pg_dump -U theplan theplan > backups/f7-pre-027.sql
```

`scripts/backup-postgres.ps1` writes the same kind of plain SQL dump (`backups/theplan-<stamp>.sql`). If `alembic_version` inside the dump is already `027_saved_filter_presentation`, this procedure is the wrong test.

### 1. Disposable Postgres

```powershell
docker run -d --name theplan-f7-mig-verify --rm `
  -e POSTGRES_USER=theplan -e POSTGRES_PASSWORD=theplan -e POSTGRES_DB=theplan `
  -p 127.0.0.1:55432:5432 `
  postgres:16-alpine
```

Refuse to continue unless all of these are true:

- `docker ps --filter name=theplan-f7-mig-verify` shows that name
- `docker port theplan-f7-mig-verify 5432` prints `127.0.0.1:55432`
- `compose-postgres-1` is still the container published on host **5432**
- the target name is not `compose-postgres-1`

Wait until this accepts connections:

```powershell
docker exec theplan-f7-mig-verify pg_isready -U theplan -d theplan
```

### 2. Restore into the empty database

Do not migrate to head and then restore. Restore first.

Plain SQL (default `pg_dump` and `backup-postgres.ps1`):

```powershell
Get-Content -Raw backups\f7-pre-027.sql | docker exec -i theplan-f7-mig-verify psql -U theplan -d theplan -v ON_ERROR_STOP=1
```

Custom format (`pg_dump -Fc`):

```powershell
cmd /c "docker exec -i theplan-f7-mig-verify pg_restore -U theplan -d theplan --no-owner --no-acl < backups\f7-pre-027.dump"
```

### 3. Pre-upgrade snapshot

```sql
SELECT version_num FROM alembic_version;
-- Not 027. 026_pending_deletion is the expected pre-F7 head.
-- Older is fine: upgrade head still applies 027 last.

SELECT column_name
  FROM information_schema.columns
 WHERE table_schema = 'public'
   AND table_name = 'saved_filters'
   AND column_name = 'presentation_json';
-- 0 rows

SELECT owner_id, slug, is_system, sort_order, predicate_json
  FROM saved_filters
 ORDER BY owner_id, sort_order;
```

Keep that result. User rows (`is_system = false`) must still match after upgrade. System `inbox` / `today` / `upcoming` will not. Row count of `saved_filters` must not change: 027 updates; it does not insert. A missing system slug stays missing. That is not a failure of this migration. A system slug that is still a legacy `op` / `clauses` tree after upgrade is a failure.

### 4. Upgrade

From `apps/api`. Force `DATABASE_URL` onto the disposable port for this process.

```powershell
$env:DATABASE_URL = "postgresql+psycopg://theplan:theplan@127.0.0.1:55432/theplan"
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

`current` before upgrade must be the restored revision. The upgrade log must show `026_pending_deletion -> 027_saved_filter_presentation` (plus any earlier revisions the dump was behind). If the log is talking to port **5432**, stop.

### 5. SQL checks

```sql
SELECT version_num FROM alembic_version;
-- 027_saved_filter_presentation

SELECT COUNT(*) AS missing_presentation
  FROM saved_filters
 WHERE presentation_json IS NULL;
-- 0

SELECT COUNT(*) AS system_not_v1
  FROM saved_filters
 WHERE is_system
   AND slug IN ('inbox', 'today', 'upcoming')
   AND (
     (predicate_json->>'v') IS DISTINCT FROM '1'
     OR presentation_json IS NULL
   );
-- 0

SELECT owner_id, slug
  FROM saved_filters
 WHERE is_system AND slug = 'inbox'
   AND predicate_json IS DISTINCT FROM
       '{"v":1,"dimensions":{"inbox":true,"completion":"open"}}'::jsonb
UNION ALL
SELECT owner_id, slug
  FROM saved_filters
 WHERE is_system AND slug = 'today'
   AND predicate_json IS DISTINCT FROM
       '{"v":1,"dimensions":{"due":{"kind":"rolling","rolling":"today"},"completion":"open"}}'::jsonb
UNION ALL
SELECT owner_id, slug
  FROM saved_filters
 WHERE is_system AND slug = 'upcoming'
   AND predicate_json IS DISTINCT FROM
       '{"v":1,"dimensions":{"due":{"kind":"rolling","rolling":"within_days","days":7},"completion":"open"}}'::jsonb;
-- 0 rows

SELECT owner_id, slug, predicate_json
  FROM saved_filters
 WHERE is_system = false
 ORDER BY owner_id, slug;
-- must match the pre-upgrade snapshot (presentation_json is new and {})
```

### 6. Rollback and cleanup

Put the predicates back by restoring the pre-upgrade dump into a **new** disposable database. `alembic downgrade 026_pending_deletion` only:

- drops `saved_filters.presentation_json`
- stamps `026_pending_deletion`
- leaves system `predicate_json` at v1

Cleanup:

```powershell
docker rm -f theplan-f7-mig-verify
```

`--rm` also removes the container on stop. Do not `docker volume rm` anything that belongs to the daily-driver project (`compose_pgdata` / `pgdata`).

Delete `backups/f7-pre-027.sql` when finished if it is a full household copy you do not want left on disk.

## Synthetic dry-run (2026-10-10)

No household dump and no household secrets. Container `theplan-f7-mig-dryrun`, image `postgres:16-alpine`, publish `127.0.0.1:55432:5432`, user/database/password `theplan` (the compose dev defaults, not a household credential). Alembic from `apps/api/.venv` with `DATABASE_URL` forced to that port.

1. `alembic upgrade 026_pending_deletion` on an empty database. Stamp `026_pending_deletion`. `presentation_json` absent.
2. Two synthetic owners. Each received `inbox` / `today` / `upcoming` with the original bootstrap `op` / `clauses` trees. Owner A also received user view `p1-open` (`is_system = false`) with a legacy priority clause. Seven rows.
3. `alembic upgrade head` ran only `026_pending_deletion -> 027_saved_filter_presentation`.
4. Checks: `missing_presentation = 0`, `system_not_v1 = 0`. All six system rows matched the v1 shapes above with `presentation_json = {}`. `p1-open` stayed the legacy `op` / `clauses` tree and gained `presentation_json = {}` from the column default. Both owners were rewritten, so the backfill is not bootstrap-user-only.
5. `alembic downgrade 026_pending_deletion`: column gone, system predicates still `v = 1`, user row still `op = and`.
6. Container removed. `compose-postgres-1` was still healthy on host **5432**.

Together with Dex **fresh** migrate to **027**, this closes **B-F7-1** (disposition, Trish **2026-10-10**). It shows **027** on pre-027 shaped rows (multi-owner system backfill + user row `presentation_json` default). Household restore remains optional per [Household path](#household-path-optional).

### Seed used

Run only after the disposable database is at `026_pending_deletion` and before `upgrade head`.

```sql
INSERT INTO users (id, email, display_name)
VALUES
  ('00000000-0000-0000-0000-0000000000a1', 'owner-a@dryrun.invalid', 'Owner A'),
  ('00000000-0000-0000-0000-0000000000b2', 'owner-b@dryrun.invalid', 'Owner B');

INSERT INTO saved_filters (id, owner_id, name, slug, predicate_json, is_system, sort_order)
VALUES
  ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'Inbox', 'inbox',
   '{"op":"and","clauses":[{"field":"project_id","op":"is_null"},{"field":"is_completed","op":"eq","value":false}]}'::jsonb,
   true, 1),
  ('10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000a1', 'Today', 'today',
   '{"op":"and","clauses":[{"field":"due_at","op":"is_today"},{"field":"is_completed","op":"eq","value":false}]}'::jsonb,
   true, 2),
  ('10000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-0000000000a1', 'Upcoming', 'upcoming',
   '{"op":"and","clauses":[{"field":"due_at","op":"within_days","value":7},{"field":"is_completed","op":"eq","value":false}]}'::jsonb,
   true, 3),
  ('10000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-0000000000a1', 'P1 open', 'p1-open',
   '{"op":"and","clauses":[{"field":"priority","op":"eq","value":"p1"},{"field":"is_completed","op":"eq","value":false}]}'::jsonb,
   false, 10),
  ('10000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-0000000000b2', 'Inbox', 'inbox',
   '{"op":"and","clauses":[{"field":"project_id","op":"is_null"},{"field":"is_completed","op":"eq","value":false}]}'::jsonb,
   true, 1),
  ('10000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-0000000000b2', 'Today', 'today',
   '{"op":"and","clauses":[{"field":"due_at","op":"is_today"},{"field":"is_completed","op":"eq","value":false}]}'::jsonb,
   true, 2),
  ('10000000-0000-0000-0000-000000000013', '00000000-0000-0000-0000-0000000000b2', 'Upcoming', 'upcoming',
   '{"op":"and","clauses":[{"field":"due_at","op":"within_days","value":7},{"field":"is_completed","op":"eq","value":false}]}'::jsonb,
   true, 3);
```
