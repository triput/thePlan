# Data Schema

PostgreSQL relational schema for the application. Executable DDL: [sql/001_baseline.sql](./sql/001_baseline.sql). Migrations via Alembic should reproduce this baseline.

---

## Conventions

| Convention | Rule |
|------------|------|
| Primary keys | UUID v4 via `uuid_generate_v4()` |
| Timestamps | `TIMESTAMPTZ`, stored UTC |
| Durations | Integer minutes |
| Ownership | `owner_id UUID NOT NULL` on all domain tables |
| Soft delete | `is_archived` on epics/projects. **Tasks:** nullable `deleted_at` (Alembic `015`) — soft-delete + Trash restore ([DEF-024](./DEFECTS.md#def-024--trash-can-soft-delete-with-retention)); hard purge via `DELETE /tasks/trash` |
| Naming | snake_case tables and columns |
| Colors | `#RRGGBB` hex strings, 7 chars; presets in [08-color-palette.md](./08-color-palette.md) |

---

## Entity Relationship Overview

```
users ──┬── user_settings
        ├── epics ── projects ── sections
        │              └── tasks ──┬── subtasks (self-FK)
        │                          ├── task_labels ── labels
        │                          ├── task_dependencies
        │                          ├── scheduled_blocks
        │                          ├── recurrence_rules
        │                          └── reminders
        ├── focus_windows ── time_map_bands
        │                 └── time_map_overrides ── time_map_override_bands
        ├── plans
        ├── saved_filters
        ├── calendar_accounts ── calendar_subscriptions
        │                    └── external_calendar_events
        └── schedule_runs
```

---

## ENUM Types

### task_priority

| Value | Meaning |
|-------|---------|
| p1 | Highest |
| p2 | High |
| p3 | Medium |
| p4 | Default / lowest |

### schedule_status

| Value | MVP usage | W2 usage |
|-------|-----------|----------|
| unscheduled | Default for new tasks | Awaiting scheduler |
| scheduled | Manual blocks exist | Auto-scheduled |
| pinned | Block flag set | Immovable in replan |
| completed | Task done | Task done |
| cancelled | Rare | Cancelled work |
| overbooked | Unused | Scheduler cannot fit before deadline |

### calendar_provider

`google`, `microsoft` — W2/W3 sync.

### calendar_subscription_role

`primary` (busy source + optional mirror write target), `informational` (see-only overlay).

### reminder_channel

`in_app`, `browser` — W1.5 reminders.

### schedule_style

`standalone` (default for new tasks), `time_block`, `bundle`, `manual` — W2b scheduler + DEF-014. Nullable on **tasks**, **projects**, and **epics**. Null inherits live at schedule time: `task.schedule_style` → else `project.schedule_style` → else `epic.schedule_style` → else `user_settings.default_schedule_style`. Inbox (no project) is task or user default only. Effective `manual` and `bundle` are excluded from Update Schedule auto-placement ([ADR-006](./adr/ADR-006-fuzzy-scheduling.md)). Alembic `013_schedule_style_manual` adds the enum value and the epic/project columns. Postgres cannot cheaply drop an enum value; downgrade drops the columns only and leaves `manual` on the type.

### time_map_band_tier

`green`, `yellow`, `red` — W2b Painted Time Maps preference tiers on `time_map_bands`. Scheduler fills green first, then yellow, then neutral workday minus red; red is never auto-placed. `strict_mode` on the parent map forbids neutral spill.

---

## Tables

### users

Household personal accounts (W1.5+). One session → one `users` row; domain data scoped by `owner_id`.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| username | VARCHAR(64) UNIQUE nullable | Immutable after create ([ADR-007](./adr/ADR-007-account-self-service.md)) |
| email | VARCHAR(255) UNIQUE | Login identifier; self-service + admin editable (W3) |
| password_hash | VARCHAR(255) nullable | Set in W1.5 |
| display_name | VARCHAR(255) | |
| is_admin | BOOLEAN | Default false; bootstrap register → true |
| is_disabled | BOOLEAN | Default false; admin cannot disable self |
| must_change_password | BOOLEAN | **W3 Slice 1** — default false; set when admin sets password; cleared on self-service password change ([ADR-007](./adr/ADR-007-account-self-service.md)) |
| created_at, updated_at | TIMESTAMPTZ | |

### user_settings

One row per user.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| owner_id | UUID FK UNIQUE | | |
| timezone | VARCHAR(64) | UTC | IANA zone |
| locale | VARCHAR(16) | en-US | |
| workday_minutes | INT | 480 | 8 h baseline |
| workday_start_local | TIME | 08:00:00 | Local workday start for placement |
| workweek_days | INT | 5 | Monday-first count; `0` = no Working days (Alembic **`029`**) |
| inter_block_buffer_minutes | INT | 5 | W2 scheduler buffer |
| ups_weights | JSONB | Wp/Wu/Wd/We/k | W2 UPS tuning |
| upcoming_horizon_days | INT | 7 | Upcoming view |
| default_estimated_duration_minutes | INT | 30 | Task create default when omitted |
| default_min_block_duration_minutes | INT | 15 | MBL default (matches task min_block) |
| default_schedule_style | schedule_style | standalone | Block / bundle / manual opt-in |
| auto_defer_enabled | BOOLEAN | true | Missed plan windows may slide |
| max_auto_schedule_minutes_per_project_per_day | INT NULL | NULL | Optional daily auto-schedule cap per project (NULL = unlimited). Alembic `014_project_daily_schedule_cap` |
| scheduling_revision | INT | 0 | Owner SoT for stale-state protection on scheduling writes (F6 / S1 progress); not `board_revision` |

**Checks:** `workday_minutes > 0`, `workweek_days` 0–7 (widened from 1–7 by Alembic **`029_workweek_days_allow_zero`**; DBs still on **`028`** keep 1–7 until migrate), `inter_block_buffer_minutes >= 0`, `upcoming_horizon_days > 0`, duration defaults `> 0`, `max_auto_schedule_minutes_per_project_per_day IS NULL OR > 0`.

### epics

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | |
| title | VARCHAR(255) | |
| description | TEXT | |
| color_hex | VARCHAR(7) | Default `#6D3FC9` — see [08-color-palette.md](./08-color-palette.md) |
| sort_order | INT | |
| is_archived | BOOLEAN | |
| preferred_time_window_id | UUID FK nullable | focus_windows; ON DELETE SET NULL. Alembic `012_hierarchy_time_maps` |
| schedule_style | schedule_style nullable | NULL = inherit user default. Alembic `013_schedule_style_manual` |

**Indexes:** `(owner_id)`, `(owner_id, is_archived)`

### projects

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | |
| epic_id | UUID FK nullable | ON DELETE SET NULL |
| title, description | | |
| color_hex | VARCHAR(7) | Default `#0A8558` |
| preferred_time_window_id | UUID FK nullable | focus_windows; ON DELETE SET NULL. Alembic `012_hierarchy_time_maps` |
| schedule_style | schedule_style nullable | NULL = inherit epic, else user default. Alembic `013_schedule_style_manual` |

**Indexes:** `(owner_id)`, `(epic_id)`, `(owner_id, is_archived)`

**Hierarchy Time Maps:** Parent window is **not** copied onto tasks. Scheduler resolves live at replan: `task.preferred_time_window_id` → else `project.preferred_time_window_id` → else `epic.preferred_time_window_id` → else unbound.

**Hierarchy schedule style:** Parent style is **not** copied onto tasks. Scheduler resolves live at replan: `task.schedule_style` → else `project.schedule_style` → else `epic.schedule_style` → else `user_settings.default_schedule_style`. Inbox (no project) is task or user default only.

### sections

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | |
| project_id | UUID FK | ON DELETE CASCADE |
| title | VARCHAR(255) | |
| sort_order | INT | |

**Indexes:** `(project_id)`, `(owner_id)`

### focus_windows (Time Maps)

Named map header; painted bands live in `time_map_bands`. Alembic `009_painted_time_maps` slimmed the header and migrated legacy `is_hard` → `strict_mode`.

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | |
| name | VARCHAR(100) | e.g. "Morning Deep Work" |
| strict_mode | BOOLEAN | When true, scheduler may not spill to neutral (non-tier) workday slots |

**Migration 009 backfill:** existing rows with `start_time`/`end_time`/`days_of_week`/`is_hard` became one **green** band per map; `strict_mode` copied from `is_hard`.

### time_map_bands

Painted preference bands on a Time Map. A map may have multiple bands (e.g. morning green + evening yellow on the same map).

| Column | Type | Notes |
|--------|------|-------|
| map_id | UUID FK | focus_windows; ON DELETE CASCADE |
| tier | time_map_band_tier | green, yellow, or red |
| start_time, end_time | TIME | Local wall time; `end_time > start_time` |
| days_of_week | SMALLINT | Bitset Mon=1 … Sun=64 |
| sort_order | INT | Stable band ordering in API/UI |

**Indexes:** `(map_id)` — `idx_time_map_bands_map`

**Validation:** same-tier bands must not overlap on shared days (application layer). Cross-tier overlap is allowed (red can carve forbidden zones inside green/yellow).

**Scheduler semantics:** green → yellow → neutral workday minus red; red never receives auto-placement; `strict_mode` on the parent map suppresses neutral spill.

### time_map_overrides

Dated replacement for one Time Map. Alembic `024_time_map_overrides`. The weekly map is unchanged. Outside the inclusive local dates the scheduler uses the base map again; nothing runs in the background to restore it. Expired rows stay until deleted. Deleting the focus window cascades the override and its bands.

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | users; ON DELETE CASCADE |
| map_id | UUID FK | focus_windows; ON DELETE CASCADE |
| local_start_date, local_end_date | DATE | Inclusive calendar dates in `timezone` |
| timezone | VARCHAR(64) | Stored IANA name. Not reinterpreted if `user_settings.timezone` changes |
| strict_mode | BOOLEAN | Explicit. Empty bands + true = unavailable all day |

**Indexes:** `(map_id)`, `(owner_id)`

**Overlap:** same `map_id` with inclusive date ranges that touch is a conflict (`409` `TIME_MAP_OVERRIDE_OVERLAP`). Different maps may overlap. Writes do not replan.

### time_map_override_bands

Replacement bands for an override. Same tier/time/weekday shape as `time_map_bands`. `end_time > start_time` — a band may not cross midnight.

| Column | Type | Notes |
|--------|------|-------|
| override_id | UUID FK | time_map_overrides; ON DELETE CASCADE |
| tier | time_map_band_tier | green, yellow, or red |
| start_time, end_time | TIME | Local wall time in the override timezone |
| days_of_week | SMALLINT | Bitset Mon=1 … Sun=64; default 127 |
| sort_order | INT | |

**Indexes:** `(override_id)`

Empty band list is valid. With `strict_mode`, that is all-day unavailable for those dates.

### plans

Named reusable soft time frames (Plans B, W2b). Alembic `007_plans`.

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | ON DELETE CASCADE |
| name | VARCHAR(100) | Trimmed; non-empty |
| soft_target_at | TIMESTAMPTZ nullable | Flexible "do around…" frame for bound tasks |

**Indexes:** `(owner_id)`, `(owner_id, name)`

### tasks

Central entity. Supports nesting via `parent_task_id` and `nesting_level`.

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | |
| project_id | UUID FK nullable | NULL = Inbox |
| section_id | UUID FK nullable | Requires project_id |
| parent_task_id | UUID FK nullable | Self-reference |
| title | VARCHAR(500) | |
| description | TEXT | |
| priority | task_priority | Default p4 |
| nesting_level | INT CHECK 0–2 | 0=task, 1=subtask, 2=nested |
| sort_order | INT | |
| estimated_duration_minutes | INT | Default 30 |
| min_block_duration_minutes | INT | Default 15; W2 slices |
| max_block_duration_minutes | INT | Default 120 |
| due_at | TIMESTAMPTZ nullable | **MVP UI** |
| deadline_at | TIMESTAMPTZ nullable | Hard commit; **W2 UI** |
| soft_target_at | TIMESTAMPTZ nullable | Flexible target; may copy from bound plan |
| plan_id | UUID FK nullable | plans; ON DELETE SET NULL |
| schedule_style | schedule_style nullable | NULL = inherit project → epic → `user_settings.default_schedule_style` |
| preferred_time_window_id | UUID FK nullable | focus_windows (map header; bands resolved at schedule time) |
| status | schedule_status | |
| is_completed | BOOLEAN | |
| completed_at | TIMESTAMPTZ nullable | |
| deleted_at | TIMESTAMPTZ nullable | Soft-delete; NULL = live. Alembic `015_task_deleted_at` |

**Nesting invariant:** Application validates `nesting_level = parent.nesting_level + 1` when parent exists; root tasks have `nesting_level = 0`.

**Plans bind:** Setting `plan_id` copies `plans.soft_target_at` onto the task when present; unbind leaves `soft_target_at`; explicit task `soft_target_at` patch does not clear `plan_id`. Distinct from `due_at` (user intent) and `deadline_at` (hard must-finish).

**Indexes:**

- `(owner_id, due_at)` — Today/Upcoming/calendar
- `(owner_id, deadline_at)` — W2 scheduler
- `(owner_id, plan_id)` — Plan rollups / list badges
- `(owner_id, is_completed)` — Active task lists
- `(owner_id, project_id, sort_order)` — Project views
- `(project_id)`, `(section_id)`, `(parent_task_id)`

### Task soft-delete (shipped — DEF-024)

- **`deleted_at`** on `tasks` (Alembic `015`). `DELETE /tasks/{id}` soft-sets the subtree; lists default to `deleted_at IS NULL`.
- **Restore:** `POST /tasks/{id}/restore` clears the same delete-wave subtree. If the parent is still trashed, restored children **reparent** to the nearest live ancestor or inbox root (**2026-10-08**).
- **Empty trash:** `DELETE /tasks/trash` hard-purges trashed rows only; does not cascade-delete live descendants of a purged parent (**2026-10-08**).
- **Client undo** still recreates via POST (new IDs); Trash restore is the true same-UUID undelete path.

### labels / task_labels

**labels:** `(owner_id, name)` unique; `color_hex` default `#635F75` (charcoal).

**Name rules:** `name` is always stored lowercase. Enforce with `CHECK (name = lower(name))` and application/API normalization on create and rename. Uniqueness on `(owner_id, name)` then prevents case variants (`Waiting` / `WAITING` / `waiting`) from coexisting.

**task_labels:** composite PK `(task_id, label_id)`. Deleting a label cascades attachments.

**Indexes:** `(label_id)` on task_labels for label-filter queries; optional `(owner_id, name)` already covered by unique constraint.

### task_dependencies

Directed edges: `blocking_task_id` must complete before `dependent_task_id`.

Constraints: no self-edge; unique pair. **Reparent cycle prevention:** PATCH `parent_task_id` that would make a task its own descendant returns **422** `PARENT_CYCLE` (application layer).

### scheduled_blocks

Manual in MVP; auto-populated by scheduler W2.

| Column | Type | Notes |
|--------|------|-------|
| task_id | UUID FK | |
| start_time, end_time | TIMESTAMPTZ | end > start |
| is_pinned | BOOLEAN | Immovable in W2 replan |

**Indexes:** `(task_id)`, `(owner_id, start_time, end_time)` for calendar range queries.

### recurrence_rules

One rule per task (`task_id UNIQUE`). Pattern-only iCal `rrule` (`FREQ` / `INTERVAL` / `BYDAY`). `is_fixed` = Todoist `every!` (calendar-fixed) vs `every` (slides from completion). Nullable `starts_on` / `ends_on` (DATE) bound the series window inclusively. Engine advances `due_at` on complete while occurrences remain; exhausts to a true complete at frame end.

### reminders

Absolute fire times (no relative-to-due in W1.5). Client polls due reminders and acks after display.

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | |
| task_id | UUID FK | CASCADE delete with task |
| fire_at | TIMESTAMPTZ | When to surface |
| channel | reminder_channel | `in_app` or `browser` |
| is_fired | BOOLEAN | Set on ack or true task complete |

Partial index: `(owner_id, fire_at) WHERE is_fired = FALSE`. True complete (not recurrence advance) marks unfired reminders fired.

### saved_filters

Smart views and future user filters. Fixed MVP views are `is_system = TRUE` rows seeded at bootstrap.

| Column | Type | Notes |
|--------|------|-------|
| name | VARCHAR(100) | Display name |
| slug | VARCHAR(100) | URL/API key; unique per owner |
| predicate_json | JSONB | F7 v1 dimension bag (`"v": 1`); validated at write/query |
| presentation_json | JSONB | List/board preference (default `{}`); Alembic **`027_saved_filter_presentation`** |
| is_system | BOOLEAN | TRUE for Inbox/Today/Upcoming |
| sort_order | INT | Sidebar ordering |

**Predicate model (F7 W1):** versioned JSON with `"v": 1` and `"dimensions"` — AND across keys, OR within array-valued dimensions. Runtime rejects legacy `op`/`clauses` trees. System seeds and migration backfill use v1 (see [`saved_filter_v1.py`](../apps/api/app/services/saved_filter_v1.py)). API contract: [05-api-contract.md](./05-api-contract.md#smart-views-saved-filters).

Example Inbox predicate (v1):

```json
{
  "v": 1,
  "dimensions": {
    "inbox": true,
    "completion": "open"
  }
}
```

### calendar_accounts

OAuth token storage (encrypted at rest in application layer). **`mirror_blocks`** (renamed from `mirror_blocks_to_google` in W3 Slice 2 — [ADR-008](./adr/ADR-008-microsoft-calendar.md)) toggles pushing `scheduled_blocks` to this account’s enabled **primary** calendar (Google or Microsoft; best-effort). `last_synced_at` records the last successful multi-subscription sync. Legacy `sync_cursor` on the account is unused; per-subscription `sync_cursor` stores Google `nextSyncToken` or Graph delta token.

### calendar_subscriptions

Per-account calendar selection: `external_calendar_id`, `role` (`primary` | `informational`), `is_enabled`, and `sync_cursor` (provider incremental token). Unique on `(calendar_account_id, external_calendar_id)`.

### external_calendar_events

Mirrored busy events from providers. Linked optionally to `task_id` or `scheduled_block_id`. Unique on `(provider, external_event_id)`.

### schedule_runs

Audit log for W2 scheduler passes: timing, counts, errors, `stats_json`.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| owner_id | UUID FK | |
| started_at, finished_at | TIMESTAMPTZ | |
| status | VARCHAR(32) | `running`, `completed`, `failed` |
| tasks_scheduled, blocks_created, overbooked_count | INT | Run counters |
| error_message | TEXT nullable | |
| stats_json | JSONB nullable | e.g. `minutes_by_project` (DEF-017) |

**Indexes:** `(owner_id, started_at DESC)` — list/history per owner.

**Concurrency (Alembic `018_one_running_schedule_run`, 2026-10-08):** partial unique index **`uq_schedule_runs_one_running_per_owner`** on `(owner_id) WHERE status = 'running'` — at most one active replan per owner. API returns **409** `SCHEDULE_RUN_IN_PROGRESS` when a non-stale run is already active. Stale `running` rows older than **15 minutes** are reclaimed as `failed` before admit.

Greenfield [001_baseline.sql](./sql/001_baseline.sql) predates migration-only indexes; Alembic `018` is the source of truth for the partial unique index.

### schedule_task_outcomes

One row per task evaluated by a schedule run (F3). Alembic `022_schedule_task_outcomes` creates the table; `023_schedule_outcome_provenance` adds calculation time and input provenance. Unique on `(schedule_run_id, task_id)`.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| schedule_run_id | UUID FK | `schedule_runs`, cascade delete |
| owner_id | UUID FK | |
| task_id | UUID FK | `tasks`, cascade delete |
| requested_minutes, pinned_minutes, placed_minutes, remaining_minutes | INT | |
| primary_reason_code | VARCHAR(64) | Jules' reason code |
| reason_facts | JSONB | `[{code, params}, ...]` |
| summary_text | TEXT | Stored formatter output; reads re-derive from `reason_facts` |
| created_at | TIMESTAMPTZ | Row insert |
| evaluated_at | TIMESTAMPTZ | Calculation time (`023`) |
| outcome | VARCHAR(32) nullable | `placed`, `unplaced`, `excluded`, `blocked`, `recorded` |
| placement_facts | JSONB nullable | Optional placement detail |
| input_snapshot | JSONB nullable | W1 fingerprint categories |
| input_fingerprint | VARCHAR(64) nullable | sha256 of `input_snapshot` |
| algorithm_version | VARCHAR(64) nullable | `f3-w1` when stamped by `persist_calculation_outcomes` |

**Indexes:** `(schedule_run_id)`; `(owner_id, task_id, created_at DESC)`; `(owner_id, task_id, evaluated_at DESC)` for latest-by-task.

---

## Smart Views vs Code-Named Predicates

Smart views are **not** hard-coded only in application logic. They are persisted as `saved_filters` rows with `predicate_json` and `presentation_json`. System seeds (Inbox, Today, Upcoming) plus user-authored views share the v1 predicate schema; **`GET /api/v1/views`** and predicate-backed task queries are live (F7 W1). CLI and web builder consume the same store in later F7 waves.

---

## Application-Level Invariants

1. **Nesting depth:** `nesting_level <= 2`; must match parent chain.
2. **Section consistency:** `section_id` implies non-null `project_id` matching section's project.
3. **Dependency DAG:** No cycles on dependency edges (validated on insert). **Parent reparent:** no `parent_task_id` cycles (**422** `PARENT_CYCLE`).
4. **Owner scoping:** All queries filter by authenticated `owner_id`.
5. **Completion:** Setting `is_completed = TRUE` sets `completed_at = now()`; uncomplete clears it.
6. **Timezone:** "Today" and calendar boundaries computed in `user_settings.timezone`.
7. **Time Map overrides:** inclusive dates belong to the override's stored IANA timezone. Same-map ranges that overlap are rejected. Bands cannot cross midnight.

---

## Migration Strategy

1. Apply [001_baseline.sql](./sql/001_baseline.sql) for greenfield bootstrap.
2. Alembic revision `001_baseline` reproduces this DDL for application-driven migrations.
3. Future phases add columns via additive migrations only where possible (deadline UI, Plans table, etc.).

---

## Related Documents

- [02-functional-spec.md](./02-functional-spec.md) — field semantics and behaviors
- [05-api-contract.md](./05-api-contract.md) — REST exposure
- [adr/ADR-005-scheduler-decoupling.md](./adr/ADR-005-scheduler-decoupling.md) — scheduler vs CRUD
