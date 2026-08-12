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
| Soft delete | MVP: `is_archived` (epics/projects) or status flags only; **tasks** hard-delete. W2 target: nullable `deleted_at` on `tasks` (+ optional on `scheduled_blocks`) for session restore fidelity — see [Future: task soft-delete](#future-task-soft-delete-w2) |
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
        ├── focus_windows
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

`standalone` (default for new tasks), `time_block`, `bundle` — W2b scheduler default style on user settings (not yet on tasks).

---

## Tables

### users

Single-user MVP; table exists from day one for W1.5 login.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| email | VARCHAR(255) UNIQUE | Bootstrap local address |
| password_hash | VARCHAR(255) nullable | Set in W1.5 |
| display_name | VARCHAR(255) | |
| created_at, updated_at | TIMESTAMPTZ | |

### user_settings

One row per user.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| owner_id | UUID FK UNIQUE | | |
| timezone | VARCHAR(64) | UTC | IANA zone |
| locale | VARCHAR(16) | en-US | |
| workday_minutes | INT | 480 | 8 h baseline |
| workweek_days | INT | 5 | |
| inter_block_buffer_minutes | INT | 5 | W2 scheduler buffer |
| ups_weights | JSONB | Wp/Wu/Wd/We/k | W2 UPS tuning |
| upcoming_horizon_days | INT | 7 | Upcoming view |
| default_estimated_duration_minutes | INT | 30 | Task create default when omitted |
| default_min_block_duration_minutes | INT | 15 | MBL default (matches task min_block) |
| default_schedule_style | schedule_style | standalone | Block/bundle opt-in |
| auto_defer_enabled | BOOLEAN | true | Missed plan windows may slide |

**Checks:** `workday_minutes > 0`, `workweek_days` 1–7, `inter_block_buffer_minutes >= 0`, `upcoming_horizon_days > 0`, duration defaults `> 0`.

### epics

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | |
| title | VARCHAR(255) | |
| description | TEXT | |
| color_hex | VARCHAR(7) | Default `#6D3FC9` — see [08-color-palette.md](./08-color-palette.md) |
| sort_order | INT | |
| is_archived | BOOLEAN | |

**Indexes:** `(owner_id)`, `(owner_id, is_archived)`

### projects

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | |
| epic_id | UUID FK nullable | ON DELETE SET NULL |
| title, description | | |
| color_hex | VARCHAR(7) | Default `#0A8558` |

**Indexes:** `(owner_id)`, `(epic_id)`, `(owner_id, is_archived)`

### sections

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | |
| project_id | UUID FK | ON DELETE CASCADE |
| title | VARCHAR(255) | |
| sort_order | INT | |

**Indexes:** `(project_id)`, `(owner_id)`

### focus_windows (Time Maps)

W2 UI; table present from baseline.

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | |
| name | VARCHAR(100) | e.g. "Morning Deep Work" |
| start_time, end_time | TIME | Local wall time |
| days_of_week | SMALLINT | Bitset Mon=1 … Sun=64 |
| is_hard | BOOLEAN | Hard vs soft window |

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
| preferred_time_window_id | UUID FK nullable | focus_windows |
| status | schedule_status | |
| is_completed | BOOLEAN | |
| completed_at | TIMESTAMPTZ nullable | |

**Nesting invariant:** Application validates `nesting_level = parent.nesting_level + 1` when parent exists; root tasks have `nesting_level = 0`.

**Plans bind:** Setting `plan_id` copies `plans.soft_target_at` onto the task when present; unbind leaves `soft_target_at`; explicit task `soft_target_at` patch does not clear `plan_id`. Distinct from `due_at` (user intent) and `deadline_at` (hard must-finish).

**Indexes:**

- `(owner_id, due_at)` — Today/Upcoming/calendar
- `(owner_id, deadline_at)` — W2 scheduler
- `(owner_id, plan_id)` — Plan rollups / list badges
- `(owner_id, is_completed)` — Active task lists
- `(owner_id, project_id, sort_order)` — Project views
- `(project_id)`, `(section_id)`, `(parent_task_id)`

### Future: task soft-delete (W2)

**Target:** end of Wave 2 (optional W1.5 if cheap during auth work). Not MVP.

**Recommended approach:** Add nullable `deleted_at TIMESTAMPTZ` on `tasks` (or boolean `is_deleted`). Optionally same on `scheduled_blocks`. `DELETE` becomes soft-set; list/search queries filter `deleted_at IS NULL`. Restore/undo clears the flag and returns the same UUID with children if soft-cascade is applied.

**Cascade policy:** On parent soft-delete, soft-delete descendant tasks and linked `scheduled_blocks` in one transaction (or defer via application logic). Prefer soft-delete over forever-hard-delete for session restore fidelity.

**Alternative:** `deleted_tasks` staging table holding serialized task trees — heavier; prefer column on `tasks` unless audit retention needs differ.

**Client impact:** MVP undo stack remains useful for complete/uncomplete; delete undo becomes a restore API call instead of recreate-via-POST.

### labels / task_labels

**labels:** `(owner_id, name)` unique; `color_hex` default `#635F75` (charcoal).

**Name rules:** `name` is always stored lowercase. Enforce with `CHECK (name = lower(name))` and application/API normalization on create and rename. Uniqueness on `(owner_id, name)` then prevents case variants (`Waiting` / `WAITING` / `waiting`) from coexisting.

**task_labels:** composite PK `(task_id, label_id)`. Deleting a label cascades attachments.

**Indexes:** `(label_id)` on task_labels for label-filter queries; optional `(owner_id, name)` already covered by unique constraint.

### task_dependencies

Directed edges: `blocking_task_id` must complete before `dependent_task_id`.

Constraints: no self-edge; unique pair. Cycle prevention in application layer (optional DB trigger W2).

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
| predicate_json | JSONB | Structured filter definition |
| is_system | BOOLEAN | TRUE for Inbox/Today/Upcoming |
| sort_order | INT | Sidebar ordering |

**Predicate model (forward-compatible):** JSON document with `op` (and/or) and `clauses` array. Each clause: `{field, op, value}`. System filters use ops like `is_null`, `is_today`, `within_days`, `eq`. W2 query language compiles to the same structure.

Example Inbox predicate:

```json
{
  "op": "and",
  "clauses": [
    {"field": "project_id", "op": "is_null"},
    {"field": "is_completed", "op": "eq", "value": false}
  ]
}
```

### calendar_accounts

OAuth token storage (encrypted at rest in application layer). `mirror_blocks_to_google` toggles pushing `scheduled_blocks` to the primary Google calendar (best-effort). `last_synced_at` records the last successful multi-subscription sync. Legacy `sync_cursor` on the account is unused; per-subscription `sync_cursor` stores Google `nextSyncToken`.

### calendar_subscriptions

Per-account Google calendar selection: `external_calendar_id`, `role` (`primary` | `informational`), `is_enabled`, and `sync_cursor` (Google incremental sync token). Unique on `(calendar_account_id, external_calendar_id)`.

### external_calendar_events

Mirrored busy events from providers. Linked optionally to `task_id` or `scheduled_block_id`. Unique on `(provider, external_event_id)`.

### schedule_runs

Audit log for W2 scheduler passes: timing, counts, errors, `stats_json`.

---

## Smart Views vs Code-Named Predicates

Smart views are **not** hard-coded only in application logic. They are persisted as `saved_filters` rows with `predicate_json`. MVP ships system seeds (Inbox, Today, Upcoming); API exposes them by slug. W2 adds user-authored filters using the same predicate schema, evolving into full query language without migration.

---

## Application-Level Invariants

1. **Nesting depth:** `nesting_level <= 2`; must match parent chain.
2. **Section consistency:** `section_id` implies non-null `project_id` matching section's project.
3. **Dependency DAG:** No cycles (validated on insert).
4. **Owner scoping:** All queries filter by authenticated `owner_id`.
5. **Completion:** Setting `is_completed = TRUE` sets `completed_at = now()`; uncomplete clears it.
6. **Timezone:** "Today" and calendar boundaries computed in `user_settings.timezone`.

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
