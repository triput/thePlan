# API Contract (MVP)

Versioned REST API served by FastAPI. Base path: `/api/v1`.

**Auth (W1.5):** Session cookie (Starlette `SessionMiddleware`, signed HttpOnly, SameSite=Lax). First run claims bootstrap user via `POST /auth/register`; household users added by admin only. See [ADR-003-local-first-auth.md](./adr/ADR-003-local-first-auth.md).

**Performance contract:** CRUD endpoints p95 < 50ms on LAN for single-entity writes. CRUD never waits on scheduler.

**Future:** Optional WebSocket channel for cache invalidation events (W2); not required for MVP.

---

## Conventions

| Topic | Rule |
|-------|------|
| Content-Type | `application/json` |
| IDs | UUID strings |
| Timestamps | ISO-8601 UTC (`2026-08-11T15:00:00Z`) |
| Errors | `{ "detail": "...", "code": "..." }` with appropriate HTTP status |
| Pagination | `?limit=50&offset=0` on list endpoints; default limit 50, max 200 |
| Sorting | `?sort=sort_order` or `?sort=-due_at` (prefix `-` = DESC) |
| Filtering | Named smart views via `/views/{slug}/tasks` or `?view=today` |

All list endpoints scope to authenticated `owner_id`.

---

## Resources

### Epics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/epics` | List epics (`?archived=false` default) |
| POST | `/epics` | Create epic |
| GET | `/epics/{id}` | Get epic |
| PATCH | `/epics/{id}` | Update epic |
| DELETE | `/epics/{id}` | Delete epic (cascade projects per FK) |
| POST | `/epics/{id}/archive` | Set `is_archived=true` |
| POST | `/epics/{id}/unarchive` | Set `is_archived=false` |

**Create body example:**

```json
{
  "title": "Q3 Infrastructure",
  "description": "Platform hardening",
  "color_hex": "#6D3FC9",
  "start_date": "2026-07-01",
  "target_date": "2026-09-30"
}
```

---

### Projects

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects` | List (`?epic_id=`, `?archived=false`) |
| POST | `/projects` | Create |
| GET | `/projects/{id}` | Get with section summary |
| PATCH | `/projects/{id}` | Update |
| DELETE | `/projects/{id}` | Delete |
| POST | `/projects/{id}/archive` | Archive |
| POST | `/projects/{id}/unarchive` | Unarchive |
| PATCH | `/projects/reorder` | Batch `{ "items": [{"id": "...", "sort_order": 0}] }` |

---

### Sections

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects/{project_id}/sections` | List sections |
| POST | `/projects/{project_id}/sections` | Create |
| GET | `/sections/{id}` | Get |
| PATCH | `/sections/{id}` | Update |
| DELETE | `/sections/{id}` | Delete |
| PATCH | `/sections/reorder` | Batch reorder |

---

### Tasks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tasks` | List with filters (see Smart Views) |
| POST | `/tasks` | Create |
| GET | `/tasks/{id}` | Get with labels, subtasks summary |
| PATCH | `/tasks/{id}` | Update |
| DELETE | `/tasks/{id}` | Delete (cascade subtasks) |
| POST | `/tasks/{id}/complete` | Mark complete |
| POST | `/tasks/{id}/uncomplete` | Mark incomplete |
| PATCH | `/tasks/reorder` | Batch reorder |

**Complete body:**

```json
{
  "bulk_children": false
}
```

When completing a parent with open children and `bulk_children` omitted, API returns `409` with `{ "code": "OPEN_CHILDREN", "open_count": 3 }` unless `?force=parent_only` or body specifies choice:

- `"bulk_children": false` — complete parent only
- `"bulk_children": true` — complete parent and all descendants

**Create/update body (subset):**

```json
{
  "title": "Review architecture spec",
  "description": "",
  "project_id": "uuid-or-null",
  "section_id": "uuid-or-null",
  "parent_task_id": "uuid-or-null",
  "priority": "p1",
  "due_at": "2026-08-11T09:00:00Z",
  "estimated_duration_minutes": 90,
  "preferred_time_window_id": "uuid-or-null",
  "plan_id": "uuid-or-null",
  "label_ids": ["uuid"]
}
```

`estimated_duration_minutes` optional on create: omit or `null` → `user_settings.default_estimated_duration_minutes`; explicit value wins (including `30`).

`deadline_at` and `soft_target_at` accepted on write and surfaced in task detail + list UI (Plans A, W2b). `deadline_at` enforced in W2 scheduler. `preferred_time_window_id` must reference an owned focus window; cleared with `null`.

`plan_id` optional on create/update; must reference an owned plan; cleared with `null`. **Plan bind:** setting `plan_id` copies the plan's `soft_target_at` onto the task when the plan has one; clearing `plan_id` leaves `soft_target_at` unchanged; patching `soft_target_at` alone does not clear `plan_id`. When both `plan_id` and `soft_target_at` appear in the same request, explicit `soft_target_at` wins after bind.

`TaskOut` includes `plan_id` and denormalized `plan_name` (null when unbound).

---

### Plans

| Method | Path | Description |
|--------|------|-------------|
| GET | `/plans` | List owner plans ordered by name |
| POST | `/plans` | Create |
| GET | `/plans/{id}` | Get |
| PATCH | `/plans/{id}` | Update |
| DELETE | `/plans/{id}` | Delete (204); `tasks.plan_id` SET NULL via FK |

**Create body:**

```json
{
  "name": "Finish Q3 report",
  "soft_target_at": "2026-08-15T17:00:00Z"
}
```

`name` trimmed; empty → 422 `PLAN_NAME_EMPTY`. `soft_target_at` optional flexible frame for bound tasks.

---

### Focus Windows (Time Maps)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/focus-windows` | List owner windows ordered by name |
| POST | `/focus-windows` | Create |
| GET | `/focus-windows/{id}` | Get |
| PATCH | `/focus-windows/{id}` | Update |
| DELETE | `/focus-windows/{id}` | Delete (204); `tasks.preferred_time_window_id` SET NULL via FK |

**Default seeds** (inserted on user provision / bootstrap when user has zero windows): Morning 08:00–12:00, Afternoon 12:00–17:00, Evening 17:00–21:00 — soft (`is_hard=false`), Mon–Sun (`days_of_week=127`).

**Create body:**

```json
{
  "name": "Morning",
  "start_time": "08:00",
  "end_time": "12:00",
  "days_of_week": 127,
  "is_hard": false
}
```

`days_of_week` is a bitset (Mon=1 … Sun=64); valid range 1–127. Times accept `HH:MM` or `HH:MM:SS`; response serializes times as `HH:MM`. `end_time` must be after `start_time` (422 `FOCUS_WINDOW_INVALID_RANGE`).

Quick-add `@morning`, `@afternoon`, `@evening` resolve to the seeded window IDs by case-insensitive name match; unknown token → `unresolved` entry `time_window:{token}`.

---

### Labels

| Method | Path | Description |
|--------|------|-------------|
| GET | `/labels` | List all labels (include optional `task_count` for prune UI) |
| POST | `/labels` | Create (name lowercased; 409 on duplicate) |
| POST | `/labels/batch` | Create multiple labels in one request (optional convenience; each name lowercased) |
| GET | `/labels/{id}` | Get |
| PATCH | `/labels/{id}` | Update name/color (name lowercased; 409 on duplicate) |
| DELETE | `/labels/{id}` | Delete label; optional body `{ "reassign_to": ["uuid", ...] }` bulk-applies surviving labels to affected tasks before remove |
| POST | `/tasks/{task_id}/labels/{label_id}` | Attach label |
| DELETE | `/tasks/{task_id}/labels/{label_id}` | Detach label |

**Normalization:** Request bodies may send mixed-case names; API stores `lower(trim(name))`. Empty name rejected.

---

### Scheduled Blocks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/scheduled-blocks` | List (`?start=`, `?end=` ISO range) |
| POST | `/scheduled-blocks` | Create manual block |
| GET | `/scheduled-blocks/{id}` | Get |
| PATCH | `/scheduled-blocks/{id}` | Update times / pin |
| DELETE | `/scheduled-blocks/{id}` | Delete |

**Create body:**

```json
{
  "task_id": "uuid",
  "start_time": "2026-08-11T09:00:00Z",
  "end_time": "2026-08-11T10:30:00Z",
  "is_pinned": false
}
```

Calendar view uses range query: `GET /scheduled-blocks?start=2026-08-11T00:00:00Z&end=2026-08-18T00:00:00Z`.

---

### Smart Views (Saved Filters)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/views` | List saved_filters (system + user) |
| GET | `/views/{slug}/tasks` | Tasks matching predicate |

MVP: read-only system views (`inbox`, `today`, `upcoming`). User-created filters and query language in W2.

Optional convenience aliases:

- `GET /tasks?view=inbox`
- `GET /tasks?view=today`
- `GET /tasks?view=upcoming`
- `GET /tasks?project_id={uuid}`
- `GET /tasks?epic_id={uuid}`
- `GET /tasks?label_id={uuid}`

---

### Quick-Add Parse

| Method | Path | Description |
|--------|------|-------------|
| POST | `/quick-add/parse` | Parse NL string → structured task draft |

**Request:**

```json
{
  "input": "Review architecture spec 1.5h p1 next Tue at 9am !!Organon #Dev/Backend"
}
```

**Response:**

```json
{
  "title": "Review architecture spec",
  "priority": "p1",
  "estimated_duration_minutes": 90,
  "due_at": "2026-08-11T09:00:00Z",
  "epic_id": "uuid-if-resolved",
  "project_id": "uuid-if-resolved",
  "section_id": "uuid-if-resolved",
  "preferred_time_window_id": "uuid-if-resolved",
  "unresolved": []
}
```

Unresolved tokens (unknown project name, missing time window) returned in `unresolved` array; client may prompt or create task with partial metadata.

Does not persist — client calls `POST /tasks` with parsed fields.

---

### Search

| Method | Path | Description |
|--------|------|-------------|
| GET | `/search` | `?q=architecture&limit=20` (limit default 20, max 50) |

Returns tasks matching title/description (case-insensitive ILIKE; `%`/`_` escaped). Response is paginated `TaskOut` rows plus `project_title` and embedded `labels` (`id`, `name`, `color_hex`) for context.

---

### Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/settings` | Get `user_settings` for owner (provisions row if missing) |
| PATCH | `/settings` | Partial update of editable fields |

**Response / PATCH fields:**

| Field | Type | Default | Validation |
|-------|------|---------|------------|
| timezone | string | UTC | Non-empty IANA name (length check) |
| locale | string | en-US | |
| workday_minutes | int | 480 | > 0 |
| workweek_days | int | 5 | 1–7 |
| inter_block_buffer_minutes | int | 5 | >= 0 |
| ups_weights | object | Wp/Wu/Wd/We/k | JSON object |
| upcoming_horizon_days | int | 7 | >= 1 |
| default_estimated_duration_minutes | int | 30 | > 0 |
| default_min_block_duration_minutes | int | 15 | > 0 |
| default_schedule_style | enum | standalone | `standalone`, `time_block`, `bundle` |
| auto_defer_enabled | bool | true | |

**Task create duration:** `estimated_duration_minutes` on `POST /tasks` is optional. Omit or send `null` to use `user_settings.default_estimated_duration_minutes`; an explicit value (including `30`) is stored as-is.

**Quick-add parse:** When the parser finds no duration token, `estimated_duration_minutes` in the parse response is filled from `user_settings.default_estimated_duration_minutes` before return.

---

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | `{ "status": "ok" }` — unversioned or `/api/v1/health` |

---

## Response Shapes

### Task (list item)

```json
{
  "id": "uuid",
  "title": "Review architecture spec",
  "project_id": "uuid",
  "section_id": "uuid",
  "parent_task_id": null,
  "nesting_level": 0,
  "priority": "p1",
  "due_at": "2026-08-11T09:00:00Z",
  "deadline_at": null,
  "soft_target_at": null,
  "plan_id": null,
  "plan_name": null,
  "estimated_duration_minutes": 90,
  "is_completed": false,
  "completed_at": null,
  "status": "unscheduled",
  "sort_order": 0,
  "label_ids": ["uuid"],
  "open_subtask_count": 2
}
```

### Error (open children on complete)

```json
{
  "detail": "Task has 2 open subtasks",
  "code": "OPEN_CHILDREN",
  "open_count": 2
}
```

HTTP 409 — client shows warn-and-allow dialog and retries with chosen `bulk_children` flag.

---

## Auth Endpoints (W1.5)

Session cookie stores `user_id`. Password/passphrase: 12–128 characters, spaces allowed, no complexity rules. Login accepts **username or email** in `identifier`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | First-run only (`SETUP_REQUIRED`); claims bootstrap UUID; starts session |
| POST | `/auth/login` | Body `{ "identifier", "password" }`; generic `401 INVALID_CREDENTIALS` |
| POST | `/auth/logout` | Clears session; `204` |
| GET | `/auth/me` | Current user; `401 SETUP_REQUIRED` or `401 UNAUTHENTICATED` |
| GET | `/auth/users` | Admin: list household users |
| POST | `/auth/users` | Admin: create household user |
| PATCH | `/auth/users/{id}` | Admin: update `display_name`, `is_disabled`, `password` (cannot disable self) |
| GET/PUT/DELETE | `/tasks/{id}/recurrence` | Get, set, or clear recurrence (`rrule`, `is_fixed`, `timezone`, `starts_on`, `ends_on`, optional `text`) |
| GET/POST | `/tasks/{id}/reminders` | List / create absolute-time reminders (`fire_at`, `channel`) |
| GET | `/reminders/due` | Unfired reminders with `fire_at <= now` (includes `task_title`) |
| PATCH/DELETE | `/reminders/{id}` | Update unfired reminder or delete |
| POST | `/reminders/{id}/ack` | Mark fired (idempotent) |

**Complete + recurrence:** `POST /tasks/{id}/complete` advances `due_at` when a next occurrence exists (`recurrence_advanced: true`, `previous_due_at` set, task stays open). When the frame is exhausted (or no rule), completes normally and marks that task’s unfired reminders fired.

**Reminders:** Absolute `fire_at` only (no relative-to-due). Channels: `in_app`, `browser`. Web client polls `/reminders/due`, shows toast (and optional Notification), then acks.

**Register body:**

```json
{
  "username": "trish",
  "email": "you@example.com",
  "password": "correct horse battery staple",
  "display_name": "Trish"
}
```

**`GET /auth/me` response:**

```json
{
  "id": "00000000-0000-0000-0000-000000000001",
  "username": "trish",
  "email": "you@example.com",
  "display_name": "Trish",
  "is_admin": true
}
```

**Error codes:** `SETUP_REQUIRED`, `SETUP_COMPLETE`, `UNAUTHENTICATED`, `INVALID_CREDENTIALS`, `USERNAME_TAKEN`, `EMAIL_TAKEN`, `FORBIDDEN`, `CANNOT_DISABLE_SELF`

---

## Wave 2 Endpoints

### Calendar (W2a — Slice 2)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/calendar/oauth/google/start` | Session auth; 302 to Google |
| GET | `/calendar/oauth/google/callback` | OAuth return; upserts `calendar_accounts` + primary subscription; initial sync; 302 to `FRONTEND_ORIGIN` |
| GET | `/calendar/accounts` | List connected accounts (`mirror_blocks_to_google`, `last_synced_at`) |
| PATCH | `/calendar/accounts/{id}` | Update `mirror_blocks_to_google` / `is_enabled` |
| GET | `/calendar/calendars?account_id=` | Proxy Google calendarList |
| GET | `/calendar/accounts/{id}/subscriptions` | Local calendar subscriptions |
| PUT | `/calendar/accounts/{id}/subscriptions` | Replace selection; exactly one `primary`; rest `informational` |
| DELETE | `/calendar/accounts/{id}` | Disconnect + cascade subscriptions/events |
| POST | `/calendar/accounts/{id}/sync` | Optional `?start=&end=`; full or incremental pull per subscription |
| GET | `/calendar/events?start=&end=` | Busy overlays only (excludes rows linked to `scheduled_block_id`) |
| GET | `/calendar/conflicts?start=&end=` | Schedule conflicts in range (422 if `end <= start`) |

**`GET /calendar/conflicts` response:**

```json
{
  "items": [
    {
      "kind": "block_busy",
      "block_id": "…",
      "other_block_id": null,
      "external_event_id": "…",
      "external_title": "Team standup",
      "start_time": "2026-08-11T10:00:00Z",
      "end_time": "2026-08-11T10:30:00Z",
      "is_pinned": true
    },
    {
      "kind": "block_block",
      "block_id": "…",
      "other_block_id": "…",
      "external_event_id": null,
      "external_title": null,
      "start_time": "2026-08-11T14:00:00Z",
      "end_time": "2026-08-11T14:30:00Z",
      "is_pinned": false
    }
  ],
  "count": 2
}
```

Overlap rule: `a.start < b.end AND a.end > b.start`. Busy sources are `external_calendar_events` with `scheduled_block_id IS NULL` only (mirrored push rows are excluded). Does **not** mutate `tasks.status` — visual flags only (W2a Slice 3); scheduler sets `schedule_status.overbooked` in W2b.

Scopes default: `calendar.events` + `calendar.calendarlist.readonly`. When mirror is on, create/update/delete of `/scheduled-blocks` best-effort pushes to the primary Google calendar (local CRUD never fails on Google errors).

### Schedule (W2b — Update Schedule thin)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/schedule/replan` | Start explicit replan ([ADR-006](./adr/ADR-006-fuzzy-scheduling.md)). Returns **202** with `ScheduleRunOut` (`status: running`). **409** `SCHEDULE_RUN_IN_PROGRESS` if another run is active. Stale `running` rows older than **15 minutes** are reclaimed as `failed` before enqueue. CRUD never waits on the worker ([ADR-005](./adr/ADR-005-scheduler-decoupling.md)). |
| GET | `/schedule/runs/{id}` | Poll run status and stats. **404** if missing or not owned. |

**`ScheduleRunOut`:** `id`, `status` (`running` \| `completed` \| `failed`), `started_at`, `finished_at`, `tasks_scheduled`, `blocks_created`, `overbooked_count`, `error_message`, `stats_json`.

Worker behavior: wipe unpinned blocks intersecting horizon, rewrite from open tasks per ADR-006; pins and external busy immovable.

### Reserved (W2b+)

| Resource | Path prefix |
|----------|-------------|
| User saved filters (write) | `POST /views` |

---

## WebSocket (Optional, W2+)

Channel: `/ws/v1/events`

Events: `task.updated`, `scheduled_block.created`, `schedule_run.completed`

Client invalidates React Query cache on events. MVP uses polling or mutation invalidation only.

---

## Related Documents

- [04-data-schema.md](./04-data-schema.md)
- [02-functional-spec.md](./02-functional-spec.md)
- [06-mvp-backlog.md](./06-mvp-backlog.md)
- [adr/ADR-005-scheduler-decoupling.md](./adr/ADR-005-scheduler-decoupling.md)
