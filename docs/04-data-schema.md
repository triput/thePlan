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
| Soft delete | Use `is_archived` (epics/projects) or status flags; no row-level soft delete in MVP |
| Naming | snake_case tables and columns |
| Colors | `#RRGGBB` hex strings, 7 chars |

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
        ├── saved_filters
        ├── calendar_accounts ── external_calendar_events
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

| Value | MVP usage | P2 usage |
|-------|-----------|----------|
| unscheduled | Default for new tasks | Awaiting scheduler |
| scheduled | Manual blocks exist | Auto-scheduled |
| pinned | Block flag set | Immovable in replan |
| completed | Task done | Task done |
| cancelled | Rare | Cancelled work |
| overbooked | Unused | Scheduler cannot fit before deadline |

### calendar_provider

`google`, `microsoft` — P2/P3 sync.

### reminder_channel

`in_app`, `browser` — P1.5 reminders.

---

## Tables

### users

Single-user MVP; table exists from day one for P1.5 login.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| email | VARCHAR(255) UNIQUE | Bootstrap local address |
| password_hash | VARCHAR(255) nullable | Set in P1.5 |
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
| inter_block_buffer_minutes | INT | 5 | P2 scheduler buffer |
| ups_weights | JSONB | Wp/Wu/Wd/We/k | P2 UPS tuning |
| upcoming_horizon_days | INT | 7 | Upcoming view |

### epics

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | |
| title | VARCHAR(255) | |
| description | TEXT | |
| color_hex | VARCHAR(7) | |
| start_date, target_date | DATE | Initiative bounds |
| sort_order | INT | |
| is_archived | BOOLEAN | |

**Indexes:** `(owner_id)`, `(owner_id, is_archived)`

### projects

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | |
| epic_id | UUID FK nullable | ON DELETE SET NULL |
| title, description | | |
| color_hex | VARCHAR(7) | |
| sort_order, is_archived | | |

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

P2 UI; table present from baseline.

| Column | Type | Notes |
|--------|------|-------|
| owner_id | UUID FK | |
| name | VARCHAR(100) | e.g. "Morning Deep Work" |
| start_time, end_time | TIME | Local wall time |
| days_of_week | SMALLINT | Bitset Mon=1 … Sun=64 |
| is_hard | BOOLEAN | Hard vs soft window |

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
| min_block_duration_minutes | INT | Default 15; P2 slices |
| max_block_duration_minutes | INT | Default 120 |
| due_at | TIMESTAMPTZ nullable | **MVP UI** |
| deadline_at | TIMESTAMPTZ nullable | Hard commit; **P2 UI** |
| soft_target_at | TIMESTAMPTZ nullable | **Plan-bound soft target; P2 UI** |
| preferred_time_window_id | UUID FK nullable | focus_windows |
| status | schedule_status | |
| is_completed | BOOLEAN | |
| completed_at | TIMESTAMPTZ nullable | |

**Nesting invariant:** Application validates `nesting_level = parent.nesting_level + 1` when parent exists; root tasks have `nesting_level = 0`.

**soft_target_at / Plans:** Reserved for Plan-bound soft targets in P2. When Plans ship, tasks linked to a Plan inherit or store `soft_target_at` as the flexible "do this around…" constraint distinct from `due_at` (user intent) and `deadline_at` (hard must-finish).

**Indexes:**

- `(owner_id, due_at)` — Today/Upcoming/calendar
- `(owner_id, deadline_at)` — P2 scheduler
- `(owner_id, is_completed)` — Active task lists
- `(owner_id, project_id, sort_order)` — Project views
- `(project_id)`, `(section_id)`, `(parent_task_id)`

### labels / task_labels

**labels:** `(owner_id, name)` unique.

**task_labels:** composite PK `(task_id, label_id)`.

**Indexes:** `(label_id)` on task_labels for label-filter queries.

### task_dependencies

Directed edges: `blocking_task_id` must complete before `dependent_task_id`.

Constraints: no self-edge; unique pair. Cycle prevention in application layer (optional DB trigger P2).

### scheduled_blocks

Manual in MVP; auto-populated by scheduler P2.

| Column | Type | Notes |
|--------|------|-------|
| task_id | UUID FK | |
| start_time, end_time | TIMESTAMPTZ | end > start |
| is_pinned | BOOLEAN | Immovable in P2 replan |

**Indexes:** `(task_id)`, `(owner_id, start_time, end_time)` for calendar range queries.

### recurrence_rules (stub)

One rule per task (`task_id UNIQUE`). `rrule` TEXT (iCal RRULE). `is_fixed` for Todoist `every!` semantics. Engine in P1.5.

### reminders (stub)

| Column | Type | Notes |
|--------|------|-------|
| task_id | UUID FK | |
| fire_at | TIMESTAMPTZ | |
| channel | reminder_channel | |
| is_fired | BOOLEAN | |

Partial index: `(owner_id, fire_at) WHERE is_fired = FALSE`.

### saved_filters

Smart views and future user filters. Fixed MVP views are `is_system = TRUE` rows seeded at bootstrap.

| Column | Type | Notes |
|--------|------|-------|
| name | VARCHAR(100) | Display name |
| slug | VARCHAR(100) | URL/API key; unique per owner |
| predicate_json | JSONB | Structured filter definition |
| is_system | BOOLEAN | TRUE for Inbox/Today/Upcoming |
| sort_order | INT | Sidebar ordering |

**Predicate model (forward-compatible):** JSON document with `op` (and/or) and `clauses` array. Each clause: `{field, op, value}`. System filters use ops like `is_null`, `is_today`, `within_days`, `eq`. P2 query language compiles to the same structure.

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

OAuth token storage (encrypted at rest in application layer). `sync_cursor` for incremental sync. P2.

### external_calendar_events

Mirrored busy events from providers. Linked optionally to `task_id` or `scheduled_block_id`. Unique on `(provider, external_event_id)`.

### schedule_runs

Audit log for P2 scheduler passes: timing, counts, errors, `stats_json`.

---

## Smart Views vs Code-Named Predicates

Smart views are **not** hard-coded only in application logic. They are persisted as `saved_filters` rows with `predicate_json`. MVP ships system seeds (Inbox, Today, Upcoming); API exposes them by slug. P2 adds user-authored filters using the same predicate schema, evolving into full query language without migration.

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
