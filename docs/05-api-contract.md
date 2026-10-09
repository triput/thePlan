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
  "target_date": "2026-09-30",
  "preferred_time_window_id": "uuid-or-null",
  "schedule_style": null
}
```

`preferred_time_window_id` optional on create/PATCH: owned focus window, or `null`. Omit on PATCH leaves the current value; `null` clears. Parent bind is **not** copied onto tasks — scheduler uses the **effective** id at replan (task → project → epic → unbound).

`schedule_style` optional on create/PATCH: `standalone`, `time_block`, `bundle`, `manual`, or `null`. Omit on PATCH leaves the current value; `null` clears (inherit user default). Parent style is **not** copied onto tasks — scheduler uses the **effective** style at replan (task → project → epic → user default). Effective `manual` and `bundle` are excluded from auto-placement per [ADR-006](./adr/ADR-006-fuzzy-scheduling.md).

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

`preferred_time_window_id` optional on create/PATCH: owned focus window, or `null`. Omit on PATCH leaves the current value; `null` clears. Same live-inherit semantics as epics (task override wins; parent id is not stamped onto tasks).

`schedule_style` optional on create/PATCH: `standalone`, `time_block`, `bundle`, `manual`, or `null`. Omit on PATCH leaves the current value; `null` clears (inherit epic, else user default). Same live-inherit semantics as Time Maps (task override wins; parent style is not stamped onto tasks).

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
| GET | `/tasks` | List with filters (see Smart Views); `?ids=`; `?trashed=true` for soft-deleted only. Default excludes trashed and tasks under **archived** project or epic (inbox tasks kept). Explicit `?project_id=` returns that project's tasks even when the project is archived. |
| POST | `/tasks` | Create |
| PATCH | `/tasks/batch` | Batch patch / add labels (`task_ids` + `patch` and/or `add_label_ids`). Patch may include `due_at`, `project_id` (move clears orphan `section_id`), schedule style, etc. |
| DELETE | `/tasks/trash` | Hard-purge trashed tasks. Optional `?older_than_days=N` (N≥1) — only rows with `deleted_at` older than N days. Omit to empty all. 204 even if nothing matched. |
| GET | `/tasks/{id}` | Get with labels, subtasks summary (includes trashed) |
| PATCH | `/tasks/{id}` | Update. **`parent_task_id`** that would create a parent/child cycle → **422** `PARENT_CYCLE` |
| DELETE | `/tasks/{id}` | Soft-delete task + live descendants (`deleted_at`); unpinned blocks removed. `?hard=true` permanently purges an **already trashed** subtree (409 `NOT_TRASHED` if live). |
| POST | `/tasks/{id}/restore` | Clear `deleted_at` for same delete-wave subtree. If the parent is still trashed, live restored tasks **reparent** to nearest live ancestor or inbox root. **409** if task is not trashed |
| POST | `/tasks/{id}/workflow` | Kanban column transition (F2); body below |
| POST | `/tasks/{id}/complete` | Mark complete |
| POST | `/tasks/{id}/uncomplete` | Mark incomplete |
| GET | `/tasks/{task_id}/dependencies` | List dependencies where path task is blocking or dependent (owner-scoped) |
| POST | `/tasks/{task_id}/dependencies` | Add edge (**201**). Body: `{ "blocking_task_id", "dependent_task_id" }`. Path task must be one endpoint. Duplicate edge returns existing row. **422** `DEPENDENCY_CYCLE`, `DEPENDENCY_TASK_MISMATCH` |
| DELETE | `/tasks/{task_id}/dependencies/{dependency_id}` | Remove edge (**204**). Path task must touch the edge |
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
  "schedule_style": null,
  "label_ids": ["uuid"]
}
```

`estimated_duration_minutes` optional on create: omit or `null` → `user_settings.default_estimated_duration_minutes`; explicit value wins (including `30`).

`deadline_at` and `soft_target_at` accepted on write and surfaced in task detail + list UI (Plans A, W2b). `deadline_at` enforced in W2 scheduler. `preferred_time_window_id` must reference an owned focus window; cleared with `null`.

`plan_id` optional on create/update; must reference an owned plan; cleared with `null`. **Plan bind:** setting `plan_id` copies the plan's `soft_target_at` onto the task when the plan has one; clearing `plan_id` leaves `soft_target_at` unchanged; patching `soft_target_at` alone does not clear `plan_id`. When both `plan_id` and `soft_target_at` appear in the same request, explicit `soft_target_at` wins after bind.

`schedule_style` optional on create/update: omit or `null` → inherit live (`task` → `project` → `epic` → `user_settings.default_schedule_style`); inbox is task or user default only. Explicit `standalone`, `time_block`, `bundle`, or `manual` overrides. Effective **bundle** and **manual** exclude the task from auto-placement per [ADR-006](./adr/ADR-006-fuzzy-scheduling.md).

`TaskOut` includes `plan_id`, denormalized `plan_name` (null when unbound), `schedule_style` (null when inheriting), and optional `source_refs` (handoff graft provenance).

**Kanban / board (F2):** `workflow_state` (`ready` \| `in_progress` \| `waiting` for open tasks), denormalized `board_column` (`ready` \| `in_progress` \| `waiting` \| `done` — **done** when `is_completed`), optional `waiting_note` (max 500 chars; cleared when leaving Waiting), `board_rank` (bigint; independent of list `sort_order`; new tasks allocate via `next_board_rank`), `board_revision` (monotonic; required on workflow transitions; also bumps when board **column** changes via `/complete`, `/uncomplete`, or bulk child complete). New tasks default **ready**, revision **0**. Completing via workflow or `/complete` aligns with existing completion service; recurring advance resets open workflow to **ready** (`recurrence_advanced`, `previous_due_at` on response when applicable). Workflow POST re-reads the row **`FOR UPDATE`** before applying revision + rank.

**List filters (F2):** `workflow` — column filter (`done` = completed; open columns require incomplete + matching `workflow_state`). `board_order=true` sorts by `board_rank`, then `created_at` (default sort when `workflow` is set). Pagination `total` is full match count for the filter, not only the returned page. Archived project/epic exclusion (above) still applies when filtering by `epic_id` or `ids`.

**Workflow transition body:**

```json
{
  "column": "in_progress",
  "expected_revision": 0,
  "waiting_note": "Blocked on review",
  "board_rank": 42,
  "insert_before_id": "uuid-or-null",
  "insert_after_id": "uuid-or-null",
  "bulk_children": false,
  "force_parent_only": false
}
```

`column`: `ready` \| `in_progress` \| `waiting` \| `done`. `expected_revision` must match current `board_revision` or **409** `BOARD_REVISION_CONFLICT`. `waiting_note` is applied only when moving to **waiting** (omit field to leave note unchanged on other columns; explicit `null` clears when entering Waiting). Rank: set `board_rank`, or `insert_before_id` / `insert_after_id` (owned tasks; ascending order; re-gap neighbor when the integer gap is exhausted), or omit to change column/state only. **Done** uses the same open-children rules as `/complete` (**409** `OPEN_CHILDREN` when omitted and descendants open). Moving an open column on a completed task uncompletes then sets workflow atomically.

Spec: [NEXT-FEATURES-SPEC.md §5](./NEXT-FEATURES-SPEC.md#5-f2-kanban-for-work-in-progress). Delivery: [delivery/F2-KANBAN.md](./delivery/F2-KANBAN.md).

---

### Planning handoff (F1)

Bulk create epics, projects, sections, and tasks from a versioned graph with optional dependencies between new or existing tasks. Separate from [outline ingest](./OUTLINE-INGEST.md) (outline re-import is not idempotent). Spec: [NEXT-FEATURES-SPEC.md §4](./NEXT-FEATURES-SPEC.md#4-f1-cli-planning-handoff).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/handoffs/propose` | Validate graph; return canonical **`payload`** (defaults **embedded** on entities and root `schedule_policy` when omitted), plus `resolved_defaults`, `warnings` (**200**) |
| POST | `/handoffs/apply` | Atomic create + receipt in one transaction (**200**). Body: graph fields + `idempotency_key` (UUID). Same owner/kind/key + same payload → replay (`replayed: true`). Same key + different payload → **409** `IDEMPOTENCY_KEY_REUSE`. Validation → **422** `HANDOFF_VALIDATION` |
| GET | `/handoffs/receipts/{receipt_id}` | Stored receipt envelope + embedded apply result (**404** `RECEIPT_NOT_FOUND` if not owned) |
| GET | `/handoffs/receipts/by-key/{idempotency_key}` | Receipt by apply key |
| GET | `/handoffs/receipts?idempotency_key=` | Alias lookup by query param |

**Graph payload (subset):** `schema_version` (1), optional `source_refs` (`system`, `id`, optional `url`), optional root `schedule_policy` (`manual` \| `inherited` \| `automatic`), `entities[]` (`key`, `kind`, `title`, `parent_key` **or** `parent: { kind, id }`, task fields), `dependencies[]`.

**Dependency edge:** each object must specify exactly one blocking side (`blocking_key` **or** `blocking_task_id`) and exactly one dependent side (`dependent_key` **or** `dependent_task_id`). Keys refer to entities in the same graph; task IDs must be owned, live tasks. Mixed edges (e.g. existing blocker UUID + new `dependent_key`) are supported. Cycles are rejected (**422** `HANDOFF_VALIDATION` or task API **422** `DEPENDENCY_CYCLE`).

**Apply result:** `receipt_id`, `idempotency_key`, `replayed`, `entities` (key/kind/id), `dependencies_created`, `created_counts`, `defaulted_fields`, `warnings`, `source_refs`.

**Persistence:** Alembic `019_handoff_receipts` — table `handoff_receipts`; `source_refs` JSONB on **epics** and **projects** for created roots. Alembic `020_task_source_refs` — `source_refs` JSONB on **tasks** (task-only grafts). Epic/project/task reads expose `source_refs` when set.

---

### Coursera templates (F5)

Versioned **built-in** catalog (no DB template CRUD). Outline JSON → F1 handoff graph → transactional apply with **`template_apply`** receipts (separate idempotency namespace from **`handoff_apply`**). Legacy **`/outlines/*`** ingest unchanged — see [OUTLINE-INGEST.md](./OUTLINE-INGEST.md). Spec: [NEXT-FEATURES-SPEC.md §8](./NEXT-FEATURES-SPEC.md#8-f5-coursera-templates). Delivery: [delivery/F5-COURSERA-TEMPLATES.md](./delivery/F5-COURSERA-TEMPLATES.md).

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/templates` | — | List builtins: `id`, `version`, `title`, `description`, `attach_modes[]` |
| GET | `/templates/{template_id}` | — | Detail + `outline_pack`, `example_outline`, `is_scaffold` |
| POST | `/templates/{template_id}/propose` | session | Validate outline → canonical handoff **`payload`**, `summary` (entity counts, `optional_skipped`), `resolved_defaults`, `warnings`, `template_id` / `template_version`, `is_scaffold` (**200**) |
| POST | `/templates/{template_id}/apply` | session | Atomic create + receipt (**200**). Body: proposed graph fields + **`idempotency_key`** (UUID). Same owner + `template_apply` + key + same payload → replay (`replayed: true`). Same key + different payload → **409** `IDEMPOTENCY_KEY_REUSE`. Validation → **422** (`TEMPLATE_OUTLINE_INVALID`, `TEMPLATE_ATTACH_*`, or handoff codes) |
| GET | `/templates/receipts/by-key/{idempotency_key}` | session | Template apply receipt (**404** `RECEIPT_NOT_FOUND` if not owned or not a template receipt) |

**Template IDs (v1):** `coursera_specialization`, `coursera_course`, `coursera_module`.

**Propose body:**

```json
{
  "outline": { },
  "skip_optional": false,
  "attach_under": { "kind": "epic", "id": "uuid-or-omit" },
  "source_refs": [{ "system": "coursera", "id": "…", "url": "https://…" }]
}
```

| Template | `attach_under` |
|----------|----------------|
| `coursera_specialization` | Omit → new epic; `{ "kind": "epic", "id" }` → graft courses onto existing epic |
| `coursera_course` | Omit → standalone project; `{ "kind": "epic", "id" }` → project under epic |
| `coursera_module` | **Required** `{ "kind": "project", "id" }` (new section + tasks) or `{ "kind": "section", "id" }` (tasks only) |

**Apply result:** Same fields as F1 handoff apply, plus **`template_id`** and **`template_version`** from receipt metadata. Lookup under **`/handoffs/receipts/*`** returns **404** for template keys.

**Errors (additions):** **404** `TEMPLATE_NOT_FOUND`; **422** `TEMPLATE_ATTACH_REQUIRED` / `TEMPLATE_ATTACH_INVALID`; **404** `OUTLINE_ATTACH_NOT_FOUND` for unknown/unowned attach target; **400** `OUTLINE_INVALID` for wrong outline shape (e.g. certificate JSON on `coursera_course`).

**Persistence:** Reuses `handoff_receipts` with `operation_kind = template_apply` and JSON metadata `{ "template_id", "template_version" }`. No new Alembic revision for F5.

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
| GET | `/focus-windows` | List owner windows ordered by name (includes nested `bands`) |
| POST | `/focus-windows` | Create |
| GET | `/focus-windows/{id}` | Get |
| PATCH | `/focus-windows/{id}` | Update |
| DELETE | `/focus-windows/{id}` | Delete (204); SET NULL via FK on `tasks.preferred_time_window_id`, `epics.preferred_time_window_id`, and `projects.preferred_time_window_id` |

**Default seeds** (inserted on user provision / bootstrap when user has zero windows): Morning 08:00–12:00, Afternoon 12:00–17:00, Evening 17:00–21:00 — each one **green** band, `strict_mode=false`, Mon–Sun (`days_of_week=127`).

**Create body (multi-band):**

```json
{
  "name": "Study",
  "strict_mode": false,
  "bands": [
    {
      "tier": "green",
      "start_time": "08:00",
      "end_time": "10:00",
      "days_of_week": 127,
      "sort_order": 0
    },
    {
      "tier": "yellow",
      "start_time": "19:00",
      "end_time": "21:00",
      "days_of_week": 127,
      "sort_order": 1
    },
    {
      "tier": "red",
      "start_time": "12:00",
      "end_time": "13:00",
      "days_of_week": 127,
      "sort_order": 2
    }
  ]
}
```

**Legacy create body** (still accepted — synthesizes one green band):

```json
{
  "name": "Morning",
  "start_time": "08:00",
  "end_time": "12:00",
  "days_of_week": 127,
  "is_hard": false
}
```

`strict_mode` on the map replaces legacy `is_hard`. PATCH accepts `strict_mode` or legacy `is_hard` (alias). When `bands` is omitted on PATCH, legacy `start_time`/`end_time`/`days_of_week` may update a single existing band.

**Band fields:** `tier` is `green`, `yellow`, or `red`. `days_of_week` is a bitset (Mon=1 … Sun=64); valid range 1–127. Times accept `HH:MM` or `HH:MM:SS`; response serializes times as `HH:MM`. Each band's `end_time` must be after `start_time` (422 `FOCUS_WINDOW_INVALID_RANGE`). Same-tier bands must not overlap on shared days (422 `TIME_MAP_BAND_OVERLAP`).

**Response shape:** `FocusWindowOut` includes `id`, `name`, `strict_mode`, `bands[]` (`id`, `tier`, `start_time`, `end_time`, `days_of_week`, `sort_order`), timestamps.

**Scheduler placement (bound map):** green bands first, then yellow, then neutral workday minus red bands — unless `strict_mode=true`, in which case neutral spill is forbidden. Red bands are never auto-placement targets.

Scheduler uses the **effective** Time Map id at replan — `task.preferred_time_window_id` → else `project.preferred_time_window_id` → else `epic.preferred_time_window_id` → else unbound — not the task column alone. Tier selection is resolved from that map's bands, unless a Time Map override covers that local date (below).

---

### Time Map overrides

Nested under one owned focus window. Creating, editing, or deleting an override does **not** replan. Those writes change live override data on the task's **effective** map, so the next read of **Why this schedule?** can show **`is_stale`** with **`stale_categories`** including **`time_map_overrides`** (snapshot **v3** compare; no auto-replan). Expired overrides stay in the list until deleted. Dates are inclusive calendar dates in the override's stored IANA `timezone`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/focus-windows/{id}/overrides` | List, including expired, ordered by `local_start_date` |
| POST | `/focus-windows/{id}/overrides` | Create (201) |
| GET | `/focus-windows/{id}/overrides/{override_id}` | Get |
| PATCH | `/focus-windows/{id}/overrides/{override_id}` | Update dates, timezone, `strict_mode`, and/or `bands` |
| DELETE | `/focus-windows/{id}/overrides/{override_id}` | Delete (204) |

Unknown window, another owner's window, or an override that is not on that window → 404. The body does not describe the other owner's map.

**Create body:**

```json
{
  "local_start_date": "2026-10-12",
  "local_end_date": "2026-10-14",
  "timezone": "America/Los_Angeles",
  "strict_mode": true,
  "bands": [
    {
      "tier": "green",
      "start_time": "14:00",
      "end_time": "17:00",
      "days_of_week": 127,
      "sort_order": 0
    }
  ]
}
```

`strict_mode` is required. `bands` may be omitted or `[]`. Empty bands with `strict_mode: true` mean unavailable all day. `timezone` must be an IANA name (422 `TIME_MAP_OVERRIDE_TIMEZONE`). `local_end_date` before `local_start_date` → 422 `TIME_MAP_OVERRIDE_INVALID_RANGE`. A band with `end_time` not after `start_time` crosses midnight → 422 `TIME_MAP_OVERRIDE_BAND_CROSSES_MIDNIGHT` (split it into two same-day bands). Same-tier overlap on shared days → 422 `TIME_MAP_BAND_OVERLAP`.

Overlapping inclusive dates on the **same** map → 409 `TIME_MAP_OVERRIDE_OVERLAP` with `conflicting_override_id` and that row's local dates. Another map may use the same dates. Adjacent ranges (next start is the day after this end) are not an overlap.

**Response:** `id`, `map_id`, `local_start_date`, `local_end_date`, `timezone`, `strict_mode`, `bands[]` (same shape as Time Map bands), timestamps.

Deleting the focus window deletes its overrides (ON DELETE CASCADE). The base map's bands are not rewritten.

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
| POST | `/scheduled-blocks/clear-unpinned` | Delete unpinned blocks overlapping `{ start, end }` (DEF-020) |
| GET | `/scheduled-blocks/{id}` | Get |
| PATCH | `/scheduled-blocks/{id}` | Update times / pin |
| POST | `/scheduled-blocks/{id}/release-remainder` | Truncate unused tail to `at` (default now); delete if &lt; 1m left (DEF-020) |
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

**Clear unpinned body:** `{ "start": ISO, "end": ISO }` → `{ "deleted_count": n }`. Pinned blocks are never removed.

**Release remainder body (optional):** `{ "at": ISO }` → `{ "block": ScheduledBlock | null, "deleted": bool }`.

Calendar view uses range query: `GET /scheduled-blocks?start=2026-08-11T00:00:00Z&end=2026-08-18T00:00:00Z`. Task hydrate for calendar labels: `GET /tasks?ids=uuid,uuid`.

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
- `GET /tasks?workflow=ready|in_progress|waiting|done&board_order=true` (Kanban column filter + board sort — F2)

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

### Assist (W3+ SLM — ADR-010)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/assist/status` | Ollama/OpenAI-compat reachability + configured model/base URL |
| POST | `/assist/propose` | Free text → structured `create_task` actions (no DB writes) |
| POST | `/assist/apply` | Apply **approved** action list (create tasks + labels) |

**Propose errors:** `503 ASSIST_UNAVAILABLE` when the model host is down/disabled; `502 ASSIST_BAD_RESPONSE` on unusable model JSON.

**Apply:** each action returns `{ok, task_id?, error?, created_labels}`; unknown project names fall back to inbox; labels create-if-missing.

Does not replace `/quick-add/parse`. Voice/STT out of cut.

---

### Outline ingest (W3+ Theme F — ADR-011)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/outlines/propose` | Validate outline JSON + template pack → structured create actions (no DB writes). Optional `attach_under: { kind, id }` grafts under an existing epic/project/section. |
| POST | `/outlines/apply` | Apply **approved** epic/project/section/task (+ label) actions (may reference existing parent ids when grafting) |

Templates: `coursera_specialization` (default) and `hierarchy_v1` (same mapper). Deterministic (no LLM). Operator-owned file only — no Coursera client. Unknown/unowned attach target → 404 `OUTLINE_ATTACH_NOT_FOUND`. **Apply is not idempotent** (re-import duplicates). For idempotent curriculum apply with F1 receipts, use **§ Coursera templates (F5)** `/templates/{id}/propose|apply`. See [OUTLINE-INGEST.md](./OUTLINE-INGEST.md), [delivery/F5-COURSERA-TEMPLATES.md](./delivery/F5-COURSERA-TEMPLATES.md), [09-technical-architecture.md](./09-technical-architecture.md).

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
| workday_start_local | time | 08:00 | HH:MM local workday start |
| workweek_days | int | 5 | 1–7 |
| inter_block_buffer_minutes | int | 5 | >= 0 |
| ups_weights | object | Wp/Wu/Wd/We/k | JSON object |
| upcoming_horizon_days | int | 7 | >= 1 |
| default_estimated_duration_minutes | int | 30 | > 0 |
| default_min_block_duration_minutes | int | 15 | > 0 |
| default_schedule_style | enum | standalone | `standalone`, `time_block`, `bundle`, `manual` |
| auto_defer_enabled | bool | true | |
| max_auto_schedule_minutes_per_project_per_day | int \| null | null | > 0 when set; NULL = no daily cap per project during auto-schedule |

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
  "schedule_style": null,
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

## Auth Endpoints (W1.5 + W3 Slice 1)

Session cookie stores `user_id`. Password/passphrase: 12–128 characters, spaces allowed, no complexity rules. Login accepts **username or email** in `identifier`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | First-run only (`SETUP_REQUIRED`); claims bootstrap UUID; starts session |
| POST | `/auth/login` | Body `{ "identifier", "password" }`; generic `401 INVALID_CREDENTIALS` |
| POST | `/auth/logout` | Clears session; `204` |
| GET | `/auth/me` | Current user; includes `must_change_password` (W3); `401 SETUP_REQUIRED` or `401 UNAUTHENTICATED` |
| PATCH | `/auth/me` | **W3 Slice 1** — self-service: optional `password`, `email`, `display_name`. Clears `must_change_password` when `password` is set. `422 EMAIL_TAKEN` on conflict. Username not accepted. |
| GET | `/auth/users` | Admin: list household users |
| POST | `/auth/users` | Admin: create household user |
| PATCH | `/auth/users/{id}` | Admin: update `display_name`, `email` (W3), `is_disabled`, `password`, optional `must_change_password`. Setting `password` **always** sets `must_change_password=true`. Cannot disable self. Username immutable. |
| GET/PUT/DELETE | `/tasks/{id}/recurrence` | Get, set, or clear recurrence (`rrule`, `is_fixed`, `timezone`, `starts_on`, `ends_on`, optional `text`) |
| GET/POST | `/tasks/{id}/reminders` | List / create absolute-time reminders (`fire_at`, `channel`) |
| GET | `/reminders/due` | Unfired reminders with `fire_at <= now` (includes `task_title`) |
| PATCH/DELETE | `/reminders/{id}` | Update unfired reminder or delete |
| POST | `/reminders/{id}/ack` | Mark fired (idempotent) |

**Complete + recurrence:** `POST /tasks/{id}/complete` advances `due_at` when a next occurrence exists (`recurrence_advanced: true`, `previous_due_at` set, task stays open). When the frame is exhausted (or no rule), completes normally and marks that task’s unfired reminders fired.

**Reminders:** Absolute `fire_at` only (no relative-to-due). Channels: `in_app`, `browser`. Web client polls `/reminders/due`, shows toast (and optional Notification), then acks. **`/reminders/due` excludes trashed tasks** (`tasks.deleted_at IS NULL`) — **2026-10-08**.

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
  "is_admin": true,
  "must_change_password": false
}
```

**`PATCH /auth/me` body (all fields optional; at least one required):**

```json
{
  "password": "new correct horse battery staple",
  "email": "new@example.com",
  "display_name": "Trish"
}
```

**Forced password change (W3 Slice 1 — [ADR-007](./adr/ADR-007-account-self-service.md)):**

- `users.must_change_password` — set when admin PATCHes `password`; cleared when user PATCHes own `password` via `/auth/me`.
- Client: blocking change-password sheet while flag is true.
- Optional API: mutating domain routes return `403 PASSWORD_CHANGE_REQUIRED` while flag is true (`GET/PATCH /auth/me` still allowed).

**UI sketch (W3 Slice 1):**

- **Settings → Account** (all users): edit display name, email, password.
- **Settings → Household** (admin): add email field on user edit; copy that setting a password forces change on next login.
- **App shell:** if `must_change_password`, modal/sheet until password updated — no task/calendar chrome underneath.

**Error codes:** `SETUP_REQUIRED`, `SETUP_COMPLETE`, `UNAUTHENTICATED`, `INVALID_CREDENTIALS`, `USERNAME_TAKEN`, `EMAIL_TAKEN`, `FORBIDDEN`, `CANNOT_DISABLE_SELF`, `PASSWORD_CHANGE_REQUIRED` (W3)

---

## Wave 2 Endpoints

### Calendar (W2a Google + W3 Slice 2 Microsoft)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/calendar/oauth/google/start` | Session auth; 302 to Google |
| GET | `/calendar/oauth/google/callback` | OAuth return; upserts account + primary subscription; initial sync; 302 `FRONTEND_ORIGIN/?gcal=…` |
| GET | `/calendar/oauth/microsoft/start` | **W3** — Session auth; 302 to Entra (`tenant` default `common`) |
| GET | `/calendar/oauth/microsoft/callback` | **W3** — upserts `provider=microsoft`; initial sync; 302 `FRONTEND_ORIGIN/?mcal=…` |
| GET | `/calendar/accounts` | List connected accounts (`provider`, `mirror_blocks`, `last_synced_at`) |
| PATCH | `/calendar/accounts/{id}` | Update `mirror_blocks` / `is_enabled` (legacy write alias `mirror_blocks_to_google` OK) |
| GET | `/calendar/calendars?account_id=` | Provider-aware calendar list (Google calendarList or Graph `/me/calendars`) |
| GET | `/calendar/accounts/{id}/subscriptions` | Local calendar subscriptions |
| PUT | `/calendar/accounts/{id}/subscriptions` | Replace selection; exactly one `primary`; rest `informational` |
| DELETE | `/calendar/accounts/{id}` | Disconnect + cascade subscriptions/events |
| POST | `/calendar/accounts/{id}/sync` | Optional `?start=&end=`; full or incremental pull per subscription (Google syncToken or Graph delta) |
| GET | `/calendar/events?start=&end=` | Busy overlays only (excludes rows linked to `scheduled_block_id`) |
| GET | `/calendar/conflicts?start=&end=` | Schedule conflicts in range (422 if `end <= start`) |

**Mirror:** `mirror_blocks` pushes local `scheduled_blocks` to the account’s enabled **primary** calendar (Google or Microsoft). See [ADR-008](./adr/ADR-008-microsoft-calendar.md).

**Microsoft env:** `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_REDIRECT_URI`, optional `MICROSOFT_TENANT_ID` (default `common`). Scopes: `Calendars.ReadWrite`, `offline_access`, `User.Read`. Shared `TOKEN_ENCRYPTION_KEY` / `FRONTEND_ORIGIN`.

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

### Schedule (W2b — Update Schedule thin; F3-W1+W2 explanations)

**F3-W1+W2 (+ F4-W2 fingerprint):** Completed replans persist per-task rows in `schedule_task_outcomes` (Alembic `022` / `023`) with **`algorithm_version` `f3-w2`**, snapshot **v3** (placement contract unchanged; **`v`** is the fingerprint schema only), and optional **`placement_facts`**. Explanation routes below are **read-only** and never enqueue replan. Internal pipeline: `collect` → `calculate` → `apply` ([scheduler README](../apps/api/app/scheduler/README.md)); F6 preview will reuse `calculate` without `apply`. Delivery: [delivery/F3-SCHEDULER-EXPLANATIONS.md](./delivery/F3-SCHEDULER-EXPLANATIONS.md), [delivery/F4-TIME-MAP-OVERRIDES.md](./delivery/F4-TIME-MAP-OVERRIDES.md).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/schedule/replan` | Start explicit replan ([ADR-006](./adr/ADR-006-fuzzy-scheduling.md)). Inserts `schedule_runs` and returns **202** with `ScheduleRunOut` (`status: running`). **409** `SCHEDULE_RUN_IN_PROGRESS` if another non-stale run is active (Alembic `018` partial unique index). Stale `running` rows older than **15 minutes** are reclaimed as `failed` before enqueue. **Compose (default):** `SCHEDULE_DISPATCH=external` — replan runs in the **`scheduler`** service ([ADR-005](./adr/ADR-005-scheduler-decoupling.md), [apps/api/app/scheduler/README.md](../apps/api/app/scheduler/README.md)). **Bare uvicorn / Tauri:** poller or `SCHEDULE_DISPATCH=thread`, else run stays `running` until stale reclaim. CRUD never waits on the worker. |
| GET | `/schedule/runs` | List the owner's runs, newest `started_at` first. Paginated (`limit`, `offset`). Does not start a replan. |
| GET | `/schedule/runs/{id}` | Poll run status and stats. **404** if missing or not owned. |
| GET | `/schedule/runs/{id}/explanations` | Recorded per-task explanations for that run. Paginated. Optional `task_id` filter (unknown ids yield an empty page, not a leak). **404** if the run is missing or not owned. Does not start a replan. Each item includes `reason_facts`, `summary_text` (deterministic formatter), and read-time `is_stale` / `stale_categories`. |
| GET | `/tasks/{task_id}/schedule-explanation` | Latest explanation from the most recent **completed** run that evaluated the task. **200** `evaluation_state: never_evaluated` when this owner has no such row (no fabricated placement). **404** `Task not found` for a missing or other-owner task, same body either way. Does not start a replan. |

**`ScheduleRunOut`:** `id`, `status` (`running` \| `completed` \| `failed`), `started_at`, `finished_at`, `tasks_scheduled`, `blocks_created`, `overbooked_count`, `error_message`, `stats_json`.

**`ScheduleExplanationOut`:** `id`, `schedule_run_id`, `task_id`, `evaluated_at`, `outcome` (`placed` \| `unplaced` \| `excluded` \| `blocked` \| `recorded`), `primary_reason_code`, `requested_minutes`, `pinned_minutes`, `placed_minutes`, `remaining_minutes`, `reason_facts` (`code`, `params`), `summary_text`, `placement_facts`, `algorithm_version`, `input_fingerprint`, `input_snapshot`, `is_stale`, `stale_categories`.

Stale compare (snapshot **v3** / placement **`f3-w2`**, on read only, never starts a replan): `duration`, `deadline`, `map_style`, `deps`, `pins`, `project_daily_cap`, `timezone_horizon_workweek` (settings, not the absolute horizon instants), `lifecycle`, `busy_external` (owner pinned blocks and non-mirror external events, not horizon-clipped), `prerequisite_state` (blocker duration, completion, trash — edge membership stays on `deps`), `due_at_soft_target`, **`time_map_overrides`** (every override on the task's effective map — ids, inclusive local dates, stored timezone, strict mode, bands; not horizon-clipped; unbound tasks have none). `provenance` means the stored snapshot is missing or **`v` ≠ 3** (including legacy v2 rows) — categories are not guessed across versions. Not compared: **`priority_ups`** only.

**W2 `primary_reason_code` values** (additive to W1: `excluded_manual_or_bundle`, `excluded_duration_covered_by_pins`, `blocked_prerequisite`, `placed`, `unplaced_horizon_exhausted`, `unplaced_no_slot`): `excluded_lifecycle_completed`, `excluded_lifecycle_trashed`, `excluded_lifecycle_archived`, `blocked_dependency_cycle`, `unplaced_no_time_map_interval`, `unplaced_red_exclusion`, `unplaced_busy_conflict`, `unplaced_pinned_conflict`, `unplaced_deadline_limit`, `unplaced_insufficient_min_block`, `unplaced_project_daily_cap`. Formatter and params: [reasons.py](../apps/api/app/scheduler/reasons.py).

Worker behavior: wipe unpinned blocks intersecting horizon (cancel Google/MS mirrors + drop local mirror rows for those blocks), rewrite from open tasks per ADR-006; pins and external busy immovable. **Residual:** failed remote delete may leave a provider event that re-imports as busy. Placement uses the **effective** Time Map id (task → project → epic → unbound) and **effective** schedule style (task → project → epic → user default). Effective `manual` and `bundle` are excluded from auto-placement. Bound maps honor painted tiers (green → yellow → neutral minus red; red subtracts from green/yellow clips; `strict_mode` forbids neutral spill). Dependencies: topo order with max-UPS ready queue; **`prerequisite_not_before`** from blockers' latest block end. Slice placement tries decreasing slice sizes down to MBL.

### Reserved (W2c / W3+)

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
