# F2 — Kanban for work in progress

**Status:** Implemented · **Quality:** Renee exit **2026-10-08** (API green; F2-D partial — browser/manual trails) · **Manual verification:** pending (Trish)  
**Spec:** [NEXT-FEATURES-SPEC.md §5](../NEXT-FEATURES-SPEC.md#5-f2-kanban-for-work-in-progress)  
**Build:** WIP  
**Hygiene:** Alembic head **`021_task_workflow`** (after F1 **`020_task_source_refs`**)

## Scope

| Slice | Capability | Automated |
|-------|------------|-----------|
| **F2-A** | Board/list/CLI agree on workflow column, rank, revision after moves, complete/uncomplete, recurrence rollover | `test_task_workflow.py` (moves, done/back, recurrence → Ready), list `workflow` + `board_order` |
| **F2-B** | Column moves preserve scheduling fields; Waiting does not alter `schedule_style` | `test_waiting_does_not_change_schedule_style` |
| **F2-C** | Done via workflow honors open-children policy (409 / bulk); nested tasks on board with parent context | `test_done_open_children_409_without_bulk`, `test_done_bulk_children_via_workflow` |
| **F2-D** | Keyboard/menu moves, pagination, empty/error, optimistic rollback — **partial** | API revision conflict covered; full browser matrix **manual** |

**Also in slice:** Alembic **`021_task_workflow`** (`workflow_state`, `waiting_note`, `board_rank`, `board_revision` on tasks; backfill rank from `sort_order`); `POST /api/v1/tasks/{id}/workflow`; list filters `workflow`, `board_order`; web List/Board toggle + `TaskBoard` (project, inbox, epic, label, today, upcoming); CLI `tasks workflow` + list `--workflow` / `--board-order`.

## Integration

| Layer | Contract |
|-------|----------|
| **API** | `POST /tasks/{id}/workflow`; `GET /tasks?workflow=&board_order=`; `TaskOut` board fields — [05-api-contract.md](../05-api-contract.md) |
| **CLI** | `theplan tasks workflow`, `tasks list --workflow …` — [CLI.md](../CLI.md) |
| **Web** | List/Board per view (`taskPresentation` localStorage); roots-only toggle; WIP summary (In progress + Waiting) |
| **Auth** | Owner-scoped; same session boundary as other task routes |

## Automated evidence

From repo root, with API venv active (`apps/api/.venv`):

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\python.exe -m pytest tests/test_task_workflow.py -q
```

**Renee quality exit (2026-10-08):** `test_task_workflow.py` **9** passed.

Completion + recurrence interactions (same exit batch):

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\python.exe -m pytest tests/test_task_workflow.py tests/test_task_complete.py tests/test_recurrence.py -q
```

**23** passed at exit (`9` + `6` + `8`).

CLI contract (Renee exit count; re-run when CLI venv has pytest):

```powershell
cd "F:\Code Repo\ThePlan\apps\cli"
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

**33** passed at exit; not re-run on this doc pass.

Apply migrations before live or manual checks:

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\alembic.exe upgrade head
```

**UI build:** production web build green at Quality exit; not re-run on this doc pass.

## Manual checklist (Trish)

- [ ] `alembic upgrade head` → revision **`021_task_workflow`**
- [ ] Project view: toggle **Board**; columns Ready / In progress / Waiting / Done; WIP line matches In progress + Waiting totals
- [ ] **Move to…** menu moves a card; CLI `theplan tasks get --id …` shows matching `workflow_state`, `board_column`, `board_revision`
- [ ] Drag card to another open column (Waiting prompts for note); drop on **Done** runs completion policy when parent has open children
- [ ] Complete recurring task on board → toast “next occurrence”; card lands in **Ready**, not Done
- [ ] Move completed task to In progress → uncomplete + workflow in one step; list view shows same state
- [ ] **Roots only** toggle hides subtasks but column headers still show API totals (known quirk)
- [ ] Today / Upcoming board: scheduled-but-not-due tasks still appear when blocks overlap the smart range
- [ ] Stale board: second session move → first session gets conflict toast and refresh (`BOARD_REVISION_CONFLICT`)
- [ ] `theplan tasks workflow --id … --column waiting --expected-revision N --waiting-note "…"` then list with `--workflow waiting --board-order`

## Known limitations

| Item | Notes |
|------|-------|
| **Drag drop position** | Column drop moves workflow only; UI does not pass `insert_before_id` / `insert_after_id` — cards keep prior `board_rank` and sort among peers (not “drop at visual end”). Precise reorder: CLI/API rank hints or future in-column drag |
| **Thin optimistic UI** | Board mutation snapshots cache for rollback on error; no full optimistic column reorder ahead of server response |
| **Roots-only counts** | With **Roots only**, visible cards are filtered client-side; column **totals** still reflect full API `total` (includes subtasks) |
| **F2-D browser** | Touch, filtered in-column reorder, pagination edge cases, and full accessibility matrix not exhaustively automated — exercise manually |
| **Smart views on board** | Today/Upcoming fetch an open bundle then client-filter; Done column totals may include tasks filtered out of the visible set |
