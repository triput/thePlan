# API Contract (MVP)

Versioned REST API served by FastAPI. Base path: `/api/v1`.

**Auth (MVP):** Local session stub — single bootstrap user; session cookie optional for CSRF. No remote IdP. See [ADR-003-local-first-auth.md](./adr/ADR-003-local-first-auth.md).

**Performance contract:** CRUD endpoints p95 < 50ms on LAN for single-entity writes. CRUD never waits on scheduler.

**Future:** Optional WebSocket channel for cache invalidation events (P2); not required for MVP.

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
  "label_ids": ["uuid"]
}
```

`deadline_at` and `soft_target_at` accepted on write but not surfaced in MVP UI. `deadline_at` enforced in P2 scheduler.

---

### Labels

| Method | Path | Description |
|--------|------|-------------|
| GET | `/labels` | List all labels |
| POST | `/labels` | Create |
| GET | `/labels/{id}` | Get |
| PATCH | `/labels/{id}` | Update |
| DELETE | `/labels/{id}` | Delete |
| POST | `/tasks/{task_id}/labels/{label_id}` | Attach label |
| DELETE | `/tasks/{task_id}/labels/{label_id}` | Detach label |

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

MVP: read-only system views (`inbox`, `today`, `upcoming`). User-created filters and query language in P2.

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
  "preferred_time_window_id": null,
  "unresolved": []
}
```

Unresolved tokens (unknown project name) returned in `unresolved` array; client may prompt or create task with partial metadata.

Does not persist — client calls `POST /tasks` with parsed fields.

---

### Search

| Method | Path | Description |
|--------|------|-------------|
| GET | `/search` | `?q=architecture&limit=20` |

Returns tasks matching title/description (case-insensitive). Response includes project name, due_at, labels for context.

---

### Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/settings` | Get user_settings for owner |
| PATCH | `/settings` | Update timezone, workday_minutes, etc. |

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

## Auth Endpoints (P1.5 Stub)

Reserved paths; return `501 Not Implemented` in MVP or no-op local bootstrap:

| Method | Path | Phase |
|--------|------|-------|
| POST | `/auth/login` | P1.5 |
| POST | `/auth/logout` | P1.5 |
| GET | `/auth/me` | MVP returns bootstrap user |

MVP `GET /auth/me` response:

```json
{
  "id": "uuid",
  "email": "local@localhost",
  "display_name": "Local User"
}
```

---

## P2 Endpoints (Reserved)

Not implemented in MVP; documented for contract stability:

| Resource | Path prefix |
|----------|-------------|
| Focus windows | `/focus-windows` |
| Schedule runs | `/schedule/runs` |
| Update Schedule | `POST /schedule/replan` |
| Calendar accounts | `/calendar/accounts` |
| External events | `/calendar/events` |
| Recurrence | `/tasks/{id}/recurrence` |
| Reminders | `/tasks/{id}/reminders` |
| User saved filters (write) | `POST /views` |

---

## WebSocket (Optional, P2+)

Channel: `/ws/v1/events`

Events: `task.updated`, `scheduled_block.created`, `schedule_run.completed`

Client invalidates React Query cache on events. MVP uses polling or mutation invalidation only.

---

## Related Documents

- [04-data-schema.md](./04-data-schema.md)
- [02-functional-spec.md](./02-functional-spec.md)
- [06-mvp-backlog.md](./06-mvp-backlog.md)
- [adr/ADR-005-scheduler-decoupling.md](./adr/ADR-005-scheduler-decoupling.md)
