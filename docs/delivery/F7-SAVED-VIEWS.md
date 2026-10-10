# F7 — Saved views

**Latest manual gate, Dex 2026-10-10:** 23 checklist rows passed; list/board continuation, server mode persistence, saved peer sort and equal-rank sidebar reorder verified. **M1/M2 verified closed** in isolated browser retest; 14 web unit tests and build passed. [Execution report](DEX-F7-CHECKLIST-2026-10-10.md). **F7 remains Open.** Earlier implementation-status notes below are historical where superseded by this gate.

**Dex review 2026-10-10:** **R1–R6 verified closed** in the focused isolated retest. API **64**, CLI + main smoke **32**, adapter **6**, frontend build green; browser moves/counts, date validation, and completion/rename paths passed. **W3 completion gaps (2026-10-10):** saved-view **load-more** (list **200**, board **500**), **List/Board toggle → `presentation_json.mode` PATCH** (server shallow-merge) + allowlisted task **sort** from `?sort=` or `presentation_json.sort`, sidebar user-view **reorder** via `sort_order` — **Retested:** pagination and mode persistence pass; browser sort and sidebar reorder now pass (M1/M2 retest). **F7 Open:** automated W3 tests, representative existing-data migration, human sign-off. See [Dex findings and evidence](DEX-F7-MANUAL-2026-10-10.md). Not Closed/shipped.

**Status:** **W1** Quality green (**64** API pytest; Renee **2026-10-10**) · **W2 Implemented** (CLI `theplan views`; CLI tests green — `test_views_commands.py` + main smoke **~32**) · **W3 Implemented** (web filter builder, sidebar user views, List/Board via `queryViewTasks`; load-more, presentation PATCH/sort, sidebar reorder **retested; M1/M2 closed**; `npm run build` green) · F7 **Open / in-progress** — remaining acceptance + human sign-off remain; **not** Closed/shipped
**Spec:** [NEXT-FEATURES-SPEC.md §10](../NEXT-FEATURES-SPEC.md#10-f7-saved-views) · API table row F7  
**Build:** migration **`027_saved_filter_presentation`**; engine `saved_filter_predicate` / `saved_filter_query` / `saved_filter_v1`; routes `/api/v1/views`  
**Hygiene:** Head after W1 is **`027_saved_filter_presentation`**. Do **not** commit `uv.lock`.

## Wave map

| Wave | Scope | Owner | Status |
|------|--------|--------|--------|
| **W1** | Versioned predicate engine + SQLAlchemy apply; migration extending `saved_filters`; full `/views` CRUD + `/{id}/tasks` (and system slug read path); backfill system predicates to v1; Renee API tests for F7-A/C/D foundations + F7-B timezone | **Tesla** (predicate validate/compile/apply) + **Jules** (migration, schemas, routes, CRUD, system backfill) | **Quality green** — **64** pytest (Renee **2026-10-10**) |
| **W2** | CLI `theplan views` list/get/create/patch/delete/query — same API + engine; pagination + truthful totals | **Jules** | **Implemented** — CLI tests green (`test_views_commands.py`; **~32** with main smoke) |
| **W3** | Web filter builder + Save view + sidebar user entries; List/Board via saved-view task query; repair banner; F2 board hook where wired | **Andi** (UI) + **Jules** (api.ts / ViewSelection) | **Implemented** — `npm run build` green; **no automated W3 tests**; three former Dex gaps **implemented, pending Dex** (see table) |

### W3 gaps (Dex / follow-up — do not mark F7 Closed)

| Gap | Status |
|-----|--------|
| Sidebar reorder | **Implemented, pending Dex** — user views: up/down controls PATCH `sort_order` ([`Sidebar.tsx`](../../apps/web/src/components/Sidebar.tsx)). |
| `presentation_json` on toggle | **Implemented, pending Dex** — List/Board toggle PATCHes `{ mode }`; server **shallow-merges** `presentation_json`; task query sort from allowlisted `?sort=` or `presentation_json.sort` ([`05-api-contract.md`](../05-api-contract.md)). |
| Load-more on saved views | **Implemented, pending Dex** — list page size **200**, board **500**; **Load more** continues `offset` on saved-view task query ([`TaskList.tsx`](../../apps/web/src/components/TaskList.tsx), [`TaskBoard.tsx`](../../apps/web/src/components/TaskBoard.tsx)). |
| Automated W3 tests | **Open** — manual/Dex only for web slice. |

Parallelism: W1 Tesla (`services/saved_filter_*.py`, predicate tests) and Jules (`routes/views.py`, schemas, migration, model) may run in parallel once the **predicate v1 JSON shape** in this brief is treated as locked.

## Discovery inventory (baseline — do not invent a second store)

### Persistence

| Item | Location | Notes |
|------|----------|--------|
| **`SavedFilter`** | [`apps/api/app/models/user.py`](../../apps/api/app/models/user.py) | `id`, `owner_id`, `name`, `slug`, `predicate_json` (JSONB), **`presentation_json`** (JSONB, default `{}`), `is_system`, `sort_order`, timestamps. Unique `(owner_id, slug)`. |
| Table | `saved_filters` since [`001_baseline`](../../apps/api/alembic/versions/001_baseline.py) | **`027_saved_filter_presentation`** adds `presentation_json`. |
| System seeds | [`bootstrap.py`](../../apps/api/app/bootstrap.py) + [`saved_filter_v1.py`](../../apps/api/app/services/saved_filter_v1.py) + migration backfill | Inbox / Today / Upcoming per owner; runtime predicates are **v1 dimension bags** (`"v": 1`). Legacy `op`/`clauses` rejected at API boundary. |

### API (W1 live)

Router [`views.py`](../../apps/api/app/api/routes/views.py) mounted at **`/api/v1/views`**. Canonical task query: **`GET /views/{id}/tasks`** and **`GET /views/by-slug/{slug}/tasks`**. User CRUD + system read-only mutate guard. **`GET /tasks?view=`** is **not** implemented — use view task paths so all clients share one engine.

**Ad hoc task list (unchanged):** `GET /tasks` still supports `inbox`, `project_id`, `epic_id`, `label_id` (single), `is_completed`, `workflow`, `board_order`, `due_from` / `due_to`, `trashed`, pagination. Saved-view dimensions (multi-label any/all, priority, schedule fields, v1 due rolling) are **view predicate only** in W1.

### Predicate engine

[`saved_filter_predicate.py`](../../apps/api/app/services/saved_filter_predicate.py) (validate/normalize) + [`saved_filter_query.py`](../../apps/api/app/services/saved_filter_query.py) (SQLAlchemy apply, owner TZ rolling windows). No raw SQL from JSON.

### Web (W3 landed — gaps in wave map)

| Surface | Behavior |
|---------|----------|
| Sidebar | Built-ins unchanged; **user saved views** from `GET /views` — [`Sidebar.tsx`](../../apps/web/src/components/Sidebar.tsx). **Reorder** up/down via `sort_order` PATCH (pending Dex). |
| Filter / save | [`SavedViewFilterModal`](../../apps/web/src/components/SavedViewFilterModal.tsx) — builder + Save view. |
| Task list/board | User saved views load tasks via **`queryViewTasks`** (view id path); repair banner when API returns `invalid_references`. |
| Presentation | Saved views: **`presentation_json.mode`** patched on List/Board toggle; **`presentation_json.sort`** + optional `?sort=` on view tasks (allowlist; **`board_order=true`** ignores presentation sort). Hardcoded views may still use [`taskPresentation.ts`](../../apps/web/src/taskPresentation.ts) local prefs. Pending Dex. |
| Built-in Today/Upcoming | May still differ from pure predicate semantics where legacy client paths remain (see locked default on due-only engine). |

### CLI (W2 landed)

[`theplan views`](../../apps/cli/theplan/commands/views.py): **`list`**, **`get`**, **`create`**, **`patch`**, **`delete`**, **`query`** (`--id` or `--slug`, pagination, `--board-order`). Maps to `/api/v1/views` and `…/tasks`. Ad hoc **`tasks list`** filters unchanged ([`commands/tasks.py`](../../apps/cli/theplan/commands/tasks.py)).

### Tests

[`test_e10_schema.py`](../../apps/api/tests/test_e10_schema.py) asserts system slugs seed. **W1 Quality:** `test_f7_w1_views.py`, `test_f7_w1_predicate.py`, `test_f7_w1_quality.py` (**64** pytest green, Renee **2026-10-10**).

---

## Gap analysis vs F7-A–D

| Acceptance | Spec intent | Gap vs baseline |
|------------|-------------|-----------------|
| **F7-A** | GUI/CLI parity; mixed filters; labels any/all; persistence | No CRUD, no engine, no CLI, no filter builder. List API lacks multi-dimension filters. |
| **F7-B** | Rolling dates + timezone boundaries | Seeds use `is_today` / `within_days` but unused. Web uses **browser** local TZ; settings have `user_settings.timezone`. Upcoming half-open must be documented and evaluated **server-side at query time**. |
| **F7-C** | Missing refs → invalid/empty + repair; invalid predicates rejected; owner isolation; delete view ≠ delete tasks | No reference-resolution or repair signals. No owner-scoped views API (404 vs leak). |
| **F7-D** | Built-in views + pagination remain correct | System rows exist but are unused by UI/API. Pagination on `/tasks` is fine; `/{id}/tasks` must reuse same totals contract. Today/Upcoming **semantic drift** (due-only seed vs web “due OR on calendar”) must be resolved by design default below. |

---

## Locked design defaults (routine — do not invent alternatives)

From the spec unless a material Trish callout applies:

1. **Extend `SavedFilter`** — one store; no task-id snapshot collections.
2. **Live query** — evaluate predicate at read time; presentation is preference only.
3. **Predicate tree:** AND across dimensions; OR among selected values within a dimension; labels **`match`: `any` \| `all`**.
4. **No free-form query language** — structured builder fields only.
5. **Supported dimensions (W1 engine):** project (incl. Inbox = `project_id` null), epic, labels, priority, open workflow state, completion, schedule status, schedule style, due-date (fixed range, rolling, no-due, unbounded).
6. **Archive/trash:** remain excluded unless an explicit supported filter requests them — do not broaden visibility via predicate.
7. **System views:** preserve Inbox/Today/Upcoming (`is_system`); user cannot delete/mutate system rows (rename/edit/reorder/delete = user views only). Reorder among user views via `sort_order`.
8. **Delete view:** never deletes tasks.
9. **Missing project/label/epic refs:** view stays persisted; query returns **empty or flagged invalid** with a repair payload — **never** silently drop the clause and show all tasks.
10. **Never raw SQL** from predicate JSON — only validated AST → SQLAlchemy expressions.
11. **Complexity bounds:** max dimensions, max OR fan-out per dimension, max nesting depth 1 (dimension bag, not arbitrary trees). Reject over-complex with **422**.
12. **Rolling dates:** `today`, `next_7_days`, `this_calendar_week` (and keep `within_days` for Upcoming seed) evaluated in **`user_settings.timezone`** at query time. Fixed ranges stay absolute timestamptz.
13. **Upcoming half-open:** `[start_of_tomorrow_tz, start_of_day_tz + (horizon+1) days)` matching current web Upcoming intent (tomorrow through day+7), documented in API contract. System Upcoming may keep `within_days: 7` compiled to that half-open window in owner TZ (exclude “today”).
14. **Presentation:** persist `presentation_json` on `saved_filters` — at minimum `{ "mode": "list"|"board", "sort": ... }` (sort key TBD within engine-supported task orderings; default existing `sort_order`/`created_at` or board_rank when board).
15. **API identity:** primary task query path is **`GET /views/{id}/tasks`** (UUID). Also **`GET /views/by-slug/{slug}/tasks`** for system slugs (`inbox`/`today`/`upcoming`) and user slugs. List returns both `id` and `slug`.
16. **Work board:** stays client chrome (not a system `SavedFilter`) unless Trish later asks otherwise.
17. **F2:** board may open a saved view by id and apply the same task query; no duplicate workflow persistence.
18. **Convenience** `GET /tasks?view=` — optional W1 nicety; prefer `/views/.../tasks` as source of truth so clients share one engine path.

### Material Trish callout (only if she objects)

**Today / Upcoming vs calendar enrichment.** Seeded + F7 due-date dimensions are **due_at-based**. Current TaskList also includes tasks with **scheduled blocks** in the window. **Default locked for F7:** system Today/Upcoming through the predicate engine are **due_at (and Inbox project_id) only**. Calendar-day enrichment remains optional web chrome for hardcoded Today/Upcoming until a later “on calendar today” dimension — **not** in W1. Raise only if Trish insists built-in Today must keep block-overlap semantics in the saved-view path.

No other Trish blockers identified for starting W1.

---

## Scope / non-goals

### In scope (F7 overall)

- Versioned predicate + presentation on `SavedFilter`
- User CRUD + reorder; system views read-only
- Server-side query engine with pagination + truthful `total`
- CLI + web filter builder / Save view / sidebar (waves 2–3)
- F2 board consumption of saved view ids

### Non-goals

- Free-form / NL query language
- Snapshot collections of task IDs
- Second filter store or Plans-as-views
- Making Work / Calendar / Trash into `SavedFilter` rows in W1
- Silent widening when refs delete
- Raw SQL or string-concat SQL
- Closing F7 docs as shipped before Renee Quality exit

---

## W1 Implementation brief (actionable)

### Owners

| Owner | Owns |
|-------|------|
| **Tesla (lead)** | Predicate v1 schema validation; compile → SQLAlchemy `Query` filters; rolling-date evaluation in owner TZ; complexity bounds; missing-ref detection; unit tests for engine (F7-B/C foundations). Prefer Grok per model policy when dispatched. |
| **Jules** | Alembic **`027_saved_filter_presentation`** (name flexible); model + Pydantic schemas; `routes/views.py` + wire in `main.py`; CRUD semantics; system predicate backfill to v1; `GET …/tasks` orchestration calling Tesla’s apply; integrate archived/trash defaults. Prefer Composer. |
| **Renee (after W1 code)** | Integration pytest matrix below — Quality gate before Page closes docs. Prefer Grok. |
| **Page** | W1–W3 + three W3 completion gaps reflected **2026-10-10**; F7 remains **Open** until Dex retest on pagination/presentation/reorder, automated W3 tests, and sign-off. |
| **Andi** | Not W1. |

### Migration (`027_*`, after head `026_pending_deletion`)

Additive only:

- `saved_filters.presentation_json` JSONB NOT NULL default `'{}'` (or server default).
- Optional: `predicate_version` INT — **prefer embedding `"v": 1` inside `predicate_json`** to avoid dual sources; if a column is added, keep it in sync with JSON `v`.
- Data backfill: rewrite system `predicate_json` for all owners to **v1** shape (below) while preserving slug/name/`is_system`/`sort_order`. User rows (if any empty-state) none expected.

### Predicate v1 shape (locked for W1)

```json
{
  "v": 1,
  "dimensions": {
    "inbox": true,
    "project_ids": ["uuid", "..."],
    "epic_ids": ["uuid", "..."],
    "labels": { "ids": ["uuid"], "match": "any" },
    "priorities": ["p1", "p2"],
    "workflow_states": ["ready", "in_progress", "waiting"],
    "completion": "open",
    "schedule_statuses": ["unscheduled", "scheduled", "overbooked"],
    "schedule_styles": ["standalone", "time_block", "manual", "bundle"],
    "due": { "kind": "rolling", "rolling": "today" }
  }
}
```

**Rules:**

- Omit a dimension key → no constraint on that axis.
- Present keys AND together; arrays OR within the dimension.
- `inbox: true` ⇒ `project_id IS NULL`. If `inbox` and `project_ids` both set → **422**.
- `completion`: `open` \| `done` \| `any` (default for system views: `open`).
- `due.kind`: `none` (no due date), `unbounded` (any due including null — rare; document), `fixed` `{ "from": ISO, "to": ISO }` half-open `[from, to)`, `rolling` `{ "rolling": "today"|"next_7_days"|"this_calendar_week"|"within_days", "days"?: n }`.
- Legacy seed clauses (`op`/`clauses`) accepted **only** in a one-shot migration normalizer — runtime API accepts **v1 only** (422 otherwise).
- System Today ≡ `due.rolling=today` + `completion=open`. System Upcoming ≡ `due.rolling=within_days` + `days=7` (compiled as Upcoming half-open in owner TZ) + `completion=open`. System Inbox ≡ `inbox=true` + `completion=open`.

### Endpoints (W1)

| Method | Path | Behavior |
|--------|------|----------|
| `GET` | `/api/v1/views` | System + owner user views; ordered by `sort_order`, system first or stable documented order. |
| `POST` | `/api/v1/views` | Create user view: name, slug (or server-slugify from name), predicate v1, presentation. `is_system=false`. |
| `GET` | `/api/v1/views/{id}` | Owner-scoped; foreign → **404**. |
| `PATCH` | `/api/v1/views/{id}` | User views only; system → **403/422** with stable code. Rename, predicate, presentation, `sort_order`. |
| `DELETE` | `/api/v1/views/{id}` | User only; tasks untouched. |
| `GET` | `/api/v1/views/{id}/tasks` | Apply predicate + default archive/trash exclusion; `limit`/`offset`; `{ items, total, limit, offset }`. Optional `board_order` query for F2. |
| `GET` | `/api/v1/views/by-slug/{slug}/tasks` | Same engine; resolves owner slug (system or user). |

Error envelope: existing patterns. Invalid predicate → **422** with field paths. Over-complexity → **422**. Foreign id → **404** (no cross-owner metadata).

### Files (expected touch list)

| Area | Paths |
|------|--------|
| Migration | `apps/api/alembic/versions/027_*.py` |
| Model | `apps/api/app/models/user.py` |
| Schemas | `apps/api/app/schemas/saved_views.py` (new) + `__init__.py` |
| Engine | `apps/api/app/services/saved_filter_predicate.py` (validate + normalize) · `saved_filter_query.py` (apply to query) |
| Routes | `apps/api/app/api/routes/views.py` (new) · `main.py` include |
| Seeds | `bootstrap.py` / `auth_users.py` — emit v1 predicates for new users; migration backfills existing |
| Tests | `apps/api/tests/test_f7_w1_views.py` (and/or `test_f7_predicate_engine.py`) |

### Tests Renee will need (W1 exit bar)

| ID | Cases |
|----|--------|
| **F7-A (API)** | Create/list/get/patch/delete user view; mixed dimensions; labels `any` vs `all`; persistence round-trip; query returns matching set only. |
| **F7-B** | Rolling `today` / week / within_days boundaries vs `user_settings.timezone` (fixture TZ ≠ UTC); fixed range unchanged by TZ wall clock. |
| **F7-C** | Deleted project/label id → invalid flag or empty + repair hint, **not** full task list; bad predicate 422; foreign owner view 404; delete view leaves tasks. |
| **F7-D** | System inbox/today/upcoming still listed `is_system`; slug task query works; pagination `total` truthful; system mutate/delete rejected. |
| Safety | No string SQL built from user JSON; archive/trash still excluded by default. |

Suggested local command (Quality phase):

```powershell
cd "F:\Code Repo\ThePlan\apps/api"
.\.venv\Scripts\python.exe -m pytest tests/test_f7_w1_views.py tests/test_f7_w1_predicate.py tests/test_f7_w1_quality.py -q
```

### Acceptance mapping

| Slice | W1 | W2 | W3 |
|-------|----|----|-----|
| **F7-A** | API persistence + mixed filters + labels any/all | CLI parity | GUI builder + Save + sidebar |
| **F7-B** | Engine TZ + rolling | CLI query uses same | UI sends rolling kinds (no client TZ recompute for saved views) |
| **F7-C** | Refs / isolation / delete-safe | CLI errors | Repair UX affordance |
| **F7-D** | System views + pagination via engine | CLI list system | Sidebar keeps built-ins; user section additive |

---

## Risks

| Risk | Mitigation |
|------|------------|
| **Raw SQL injection** via creative JSON | Validate allowlisted fields/ops only; bind parameters through SQLAlchemy; Renee tests. |
| **Deleted project/label/epic refs** silently widen results | Resolve refs at query/list time; if missing → treat dimension as unsatisfiable **or** return `invalid_references[]` and empty items — never drop filter. |
| **Owner isolation** | All queries filter `owner_id`; foreign UUID → 404 identical to missing. |
| **Doc/API fiction** | Resolved for W1 — [05-api-contract.md](../05-api-contract.md) Smart Views section matches live CRUD + task query paths. |
| **Today semantic drift** | Locked default: due_at-only in engine; document; optional later dimension for “has block today”. |
| **Browser vs settings TZ** | Saved-view queries use settings TZ only; W3 must not re-filter in browser local for saved views. |
| **Alembic head race** | Confirm head at Implementation start (`026` expected; if another migration landed, use next). |
| **Dual filter paths** | Prefer `/views/.../tasks` over growing ad hoc `GET /tasks` params for F7 dimensions; keep existing task list params for non-saved contexts. |

---

## W1 go / no-go

**GO** for W1 Implementation.

- Baseline store exists; no competing design.
- Spec acceptance and design defaults are sufficient; one soft product callout (Today block-overlap) locked by default without blocking.
- Alembic successor clear: **`027` after `026_pending_deletion`**.
- **First Implementation owner: Tesla** (predicate engine + query apply). Jules starts migration/CRUD in parallel against this locked v1 shape.

Parent dispatches builders after reviewing this Discovery — **do not** treat this doc as Closed/shipped.
