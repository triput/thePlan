# F2 — Kanban for work in progress

**Status:** Implemented · **Quality:** Renee API **32** green this pass (**2026-10-08**); Dex recheck **pending**; push **held**; F2-D browser/manual **open** (Trish)  
**Spec:** [NEXT-FEATURES-SPEC.md §5](../NEXT-FEATURES-SPEC.md#5-f2-kanban-for-work-in-progress)  
**Build:** *pending commit* (fixes in working tree; no push until Dex recheck)
**Hygiene:** Alembic head **`021_task_workflow`** (after F1 **`020_task_source_refs`**)

## Dex review corrections (2026-10-08)

| # | Fix | Layer |
|---|-----|-------|
| 1 | `board_revision` bumps on `/complete`, `/uncomplete`, bulk child complete, and recurrence advance (column change), not only workflow POST | API |
| 2 | Workflow transition re-loads task **`SELECT … FOR UPDATE`** before revision check + apply (atomic under concurrency) | API |
| 3 | `insert_before_id` / `insert_after_id` assign ascending `board_rank`; exhausted integer gap **re-gaps** neighbor; **`POST /tasks`** sets `board_rank` via `next_board_rank` | API |
| 4–5 | Open columns paginate per column; **Done** paginates; Today/Upcoming use API **`total`** for load-more while headers show **filtered** counts (`N+` while more pages exist) | Web |
| 6 | Default **`GET /tasks`** (non-trash) excludes tasks under **archived** project or epic — including **`epic_id`**, **`ids`**, and smart/board fetches; explicit **`project_id`** still returns that project’s tasks (archived project detail) | API + Web |

**Also in follow-up:** Work board **epic / project** filter dropdowns (non-archived projects only); within-column drag sends insert hints; **Waiting** drop preserves hints through the note prompt.

## Dex residual fixes (2026-10-08 — second hold)

Five P2s from Dex recheck; implemented in working tree (not yet committed/shipped).

| # | Fix | Layer |
|---|-----|-------|
| 1 | Exhausted rank gaps: `_resolve_board_rank` in `task_workflow.py` rebalances the suffix preserving relative order, creates a genuine insertion slot, and bumps `board_revision` on shifted neighbors via `_rebalance_suffix` | API |
| 2 | Completing a **Ready** recurring task: `complete_task` in `task_helpers.py` always calls `bump_board_revision` on occurrence advance even when column stays **Ready** | API |
| 3 | Board accumulators: `TaskBoard.tsx` `moveMutation` `onSuccess` resets `openOffsets` / `openAccum` / `openServerTotals`, `smartOpenOffset` / `smartOpenAccum`, and **Done** pagination — not only Done | Web |
| 4 | `scheduledOpenQuery` `queryKey` includes `workFilters.projectId` and `workFilters.epicId` | Web |
| 5 | Explicit **Work** view: `view.type === "work"` in `view.ts` / Sidebar **Work**; `buildScopeParams` for work with **All** filters returns owner-wide scope (no `inbox=true`, no date constraints). **Inbox** still sends `inbox=true`; **Today** / **Upcoming** still apply due ranges | Web |

## Scope

| Slice | Capability | Automated |
|-------|------------|-----------|
| **F2-A** | Board/list/CLI agree on workflow column, rank, revision after moves, complete/uncomplete/bulk, recurrence rollover; create `board_rank`; insert rank hints | `test_task_workflow.py` (moves, revision on complete, insert before/after, recurrence → Ready), list `workflow` + `board_order` |
| **F2-B** | Column moves preserve scheduling fields; Waiting does not alter `schedule_style` | `test_waiting_does_not_change_schedule_style` |
| **F2-C** | Done via workflow honors open-children policy (409 / bulk); nested tasks on board with parent context | `test_done_open_children_409_without_bulk`, `test_done_bulk_children_via_workflow` |
| **F2-D** | Keyboard/menu moves, pagination, empty/error, optimistic rollback — **partial** | API revision + archived-list exclusion covered; full browser matrix **manual** |

**Also in slice:** Alembic **`021_task_workflow`** (`workflow_state`, `waiting_note`, `board_rank`, `board_revision` on tasks; backfill rank from `sort_order`); `POST /api/v1/tasks/{id}/workflow`; list filters `workflow`, `board_order`; web List/Board toggle + `TaskBoard` (project, inbox, epic, label, today, upcoming; work-board epic/project filters; in-column drag rank hints); CLI `tasks workflow` + list `--workflow` / `--board-order`.

## Integration

| Layer | Contract |
|-------|----------|
| **API** | `POST /tasks/{id}/workflow`; `GET /tasks?workflow=&board_order=`; `TaskOut` board fields — [05-api-contract.md](../05-api-contract.md) |
| **CLI** | `theplan tasks workflow`, `tasks list --workflow …` — [CLI.md](../CLI.md) |
| **Web** | List/Board per view (`taskPresentation` localStorage); roots-only toggle; WIP summary line (In progress + Waiting); epic/project filters on work board; paginated columns + Done |
| **Auth** | Owner-scoped; same session boundary as other task routes |

## Automated evidence

From repo root, with API venv active (`apps/api/.venv`):

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\python.exe -m pytest tests/test_task_workflow.py tests/test_task_complete.py tests/test_recurrence.py tests/test_complete_task_unit.py -q
```

**Renee (2026-10-08, second Dex hold pass):** **32** passed — `test_task_workflow.py`, `test_task_complete.py`, `test_complete_task_unit.py`, `test_recurrence.py` (includes exhausted-gap order + Ready recurrence revision bump).

**Renee follow-up (2026-10-08, first pass):** **30** passed (`test_task_workflow.py` **13**, plus completion/recurrence/unit coverage).

Workflow-only smoke:

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\python.exe -m pytest tests/test_task_workflow.py -q
```

CLI contract (Renee exit count; re-run when CLI venv has pytest):

```powershell
cd "F:\Code Repo\ThePlan\apps\cli"
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

**33** passed at prior exit; not re-run on this doc pass.

Apply migrations before live or manual checks:

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\alembic.exe upgrade head
```

**UI build:** production web build **green** this pass (`tsc -b && vite build`).

## Manual checklist (Trish)

- [ ] `alembic upgrade head` → revision **`021_task_workflow`**
- [ ] Project view: toggle **Board**; columns Ready / In progress / Waiting / Done; WIP summary line matches In progress + Waiting totals
- [ ] Work board: epic / project filters narrow cards; archived containers not offered in project picker
- [ ] **Move to…** menu moves a card; CLI `theplan tasks get --id …` shows matching `workflow_state`, `board_column`, `board_revision`
- [ ] Drag card within a column (insert before/after peer); drag to another column (Waiting prompts for note, then applies saved insert hints); drop on **Done** runs completion policy when parent has open children
- [ ] **Load more** on an open column and on **Done** when totals exceed page size
- [ ] Complete recurring task on board → toast “next occurrence”; card lands in **Ready**, not Done
- [ ] Move completed task to In progress → uncomplete + workflow in one step; list view shows same state
- [ ] **Roots only** toggle hides subtasks but column headers still show API totals (known quirk)
- [ ] Today / Upcoming board: scheduled-but-not-due tasks still appear when blocks overlap the smart range
- [ ] Stale board: complete in one session → workflow with stale revision in another → **409** `BOARD_REVISION_CONFLICT`; same for concurrent workflow moves
- [ ] Default task list / board hides tasks in archived project or epic; opening archived **project** detail still lists its tasks
- [ ] `theplan tasks workflow --id … --column waiting --expected-revision N --waiting-note "…"` then list with `--workflow waiting --board-order`

## Known limitations

| Item | Notes |
|------|-------|
| **Thin optimistic UI** | Board mutation snapshots cache for rollback on error; no full optimistic column reorder ahead of server response |
| **Roots-only counts** | With **Roots only**, visible cards are filtered client-side; column **totals** still reflect full API `total` on non-smart views (includes subtasks) |
| **F2-D browser** | Touch, pagination edge cases, and full accessibility matrix not exhaustively automated — exercise manually |
| **Smart views on board** | Today/Upcoming: open columns show **filtered** card counts (`N+` while API has more pages); load-more uses server **`total`**. **Done** header uses loaded/filtered count on smart views — completed tasks with schedule overlap but outside the smart date window may affect **Done** `total` vs visible cards (schedule-only edge) |
