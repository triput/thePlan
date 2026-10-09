# F3 — Scheduler explanations (W1)

**Status:** Implemented (W1) · **Quality:** Renee green for W1 tranche (**2026-10-08**); Dex recheck **pending**; push **held**; F3 **not** Closed/shipped — remaining reason families **W2**  
**Spec:** [NEXT-FEATURES-SPEC.md §6](../NEXT-FEATURES-SPEC.md#6-f3-scheduler-explanations)  
**Build:** pending commit (working tree on `47c99a7`; F3-W1 changes uncommitted)  
**Hygiene:** Alembic head **`023_schedule_outcome_provenance`** (after **`022_schedule_task_outcomes`**, revises **`021_task_workflow`**)

## Architecture note (F6 prep)

Replan now follows **`collect` → `calculate` → `apply`**: one calculation pass produces proposed blocks, per-task outcomes, and structured reason facts; apply persists blocks and `schedule_task_outcomes`. This separation is the shared foundation for **F6 replan preview** (calculate + store without apply). **W1 has no preview UI** — only direct Update Schedule plus read-only explanation surfaces.

Module map: [apps/api/app/scheduler/README.md](../../apps/api/app/scheduler/README.md).

## Quality fix (2026-10-08)

**`unplaced_horizon_exhausted` vs `unplaced_no_slot`:** Partial placement with remaining minutes inside the horizon must classify as **`unplaced_horizon_exhausted`**; **`unplaced_no_slot`** is reserved for cases where the placement loop recorded no suitable slot (e.g. past deadline with zero placement). Renee caught misclassification before exit; acceptance tests `test_partial_fit_is_horizon_exhausted` and `test_past_deadline_is_no_slot` lock the split.

## Scope

| Slice | Capability | W1 / W2 |
|-------|------------|---------|
| **F3-A** | Reason families + representative combinations | **W1:** `excluded_manual_or_bundle`, `excluded_duration_covered_by_pins`, `blocked_prerequisite`, `placed`, `unplaced_horizon_exhausted`, `unplaced_no_slot` (past deadline collapses here until **`deadline_limit`** in W2). **W2:** completed/trashed/archived, dependency cycle, no allowed Time Map interval, red exclusion, busy/pinned conflict, **`deadline_limit`**, insufficient contiguous minimum block, project daily cap |
| **F3-B** | Inherited rules, map tier/source on placement, pinned prerequisites | **W1:** pin-full exclusion, prerequisite blocking, placed summary includes tier/window source. **W2:** fuller inheritance / override provenance (F4 overlap), pinned busy conflicts |
| **F3-C** | Stale vs current settings, never-evaluated, owner isolation | **W1:** `never_evaluated` without replan on GET; stale categories `duration`, `deadline`, `map_style`, `deps`, `provenance`; cross-owner **404** parity |
| **F3-D** | Human `summary_text` and JSON `reason_facts` from same facts as placement | **W1:** formatter unit tests + acceptance asserts run list, task latest, and summaries match `format_summary_text` |

**Also in W1 slice:** Alembic **`022_schedule_task_outcomes`** + **`023_schedule_outcome_provenance`**; `input_fingerprint` + read-time stale compare; API GET routes; CLI read-only `schedule` commands; web **Why this schedule?** panel in task scheduling detail (no run-summary page).

## Integration

| Layer | Contract |
|-------|----------|
| **API** | `POST /schedule/replan` (unchanged 202 contract; worker persists outcomes on complete). Read-only: `GET /schedule/runs`, `GET /schedule/runs/{id}`, `GET /schedule/runs/{id}/explanations`, `GET /tasks/{task_id}/schedule-explanation` — [05-api-contract.md](../05-api-contract.md) |
| **CLI** | `theplan schedule explain --task-id UUID`; `theplan schedule runs list`; `theplan schedule runs get --id UUID`; `theplan schedule runs explanations --id UUID` [`--task-id`, pagination] — [CLI.md](../CLI.md) |
| **Web** | Task detail → Scheduling → **Why this schedule?** (`fetchTaskScheduleExplanation`); stale badge + reason list; run id reference; read-only hint |
| **Auth** | Owner-scoped; explanation GETs never start replan |

## Automated evidence

From repo root, with API venv active (`apps/api/.venv`):

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\python.exe -m pytest tests/test_scheduler_reasons.py tests/test_schedule_replan.py tests/test_input_fingerprint.py tests/test_schedule_explanations.py tests/test_f3_w1_acceptance.py -q
```

**Renee (2026-10-08, F3-W1 exit):** **42** passed — reason formatter, replan integration, fingerprint/stale, explanation HTTP contract, W1 acceptance (reason families + summary parity).

CLI contract (API venv + `PYTHONPATH` to `apps/api`):

```powershell
cd "F:\Code Repo\ThePlan\apps\cli"
$env:PYTHONPATH = "F:\Code Repo\ThePlan\apps\api"
..\api\.venv\Scripts\python.exe -m pytest tests/ -q
```

**Renee (2026-10-08):** **37** passed (includes `schedule explain` / `schedule runs` wiring in `test_main_commands.py`).

Apply migrations before live or manual checks:

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\alembic.exe upgrade head
```

**UI build:** production web build **green** (Andi — `tsc -b && vite build`).

## Manual checklist (Trish)

- [ ] `alembic upgrade head` → revision **`023_schedule_outcome_provenance`**
- [ ] **Update Schedule** on a project with mix of auto and manual/bundle tasks → run completes; manual/bundle tasks show exclusion explanations after replan
- [ ] Task with pinned blocks covering full estimate → exclusion “covered by pins”; replan does not add unpinned blocks for that task
- [ ] Dependent task with unfinished blocker → **blocked** prerequisite reason; after blocker completes and replan → dependent can show **placed**
- [ ] Task that partially fits in horizon → summary cites remaining minutes as **horizon exhausted**; task with past deadline and zero placement → **no suitable slot**
- [ ] Task never replanned → **Why this schedule?** shows never-evaluated copy (no fabricated placement)
- [ ] Change estimate or deadline after a run → stale badge and named categories on next panel load (no auto-replan)
- [ ] `theplan schedule explain --task-id …` JSON includes `human_summary` alias matching `summary_text`
- [ ] `theplan schedule runs list` / `get --id …` / `explanations --id …` match API pagination and owner scope
- [ ] Second user cannot read another owner’s run or explanation (**404**)

## Known limitations (W1 → W2)

| Item | Notes |
|------|-------|
| **Reason families** | Spec §6 families not listed under F3-A W1 above are **deferred to W2** (see scope table). Past deadline uses **`unplaced_no_slot`** until **`deadline_limit`** is distinct. |
| **Stale compare** | W1 compares duration, deadline, map/style, deps, and missing snapshot (`provenance`). Not yet: pins, daily cap, timezone/horizon/workweek, priority/UPS, lifecycle, external busy, map overrides, prerequisite state beyond edge set, `due_at` / soft target — [05-api-contract.md](../05-api-contract.md) |
| **F6 preview** | No preview/async diff UI; calculate/apply split is in place for a later slice |
| **Run summary UI** | No dedicated schedule-run explanation browser in web — task panel + CLI/API only |
| **Dex / push** | Implementation and Quality green for W1; delivery sign-off and remote push still pending |

## Related documents

- Data: `schedule_task_outcomes` — [04-data-schema.md](../04-data-schema.md)
- Scheduler worker / dispatch — [apps/api/app/scheduler/README.md](../../apps/api/app/scheduler/README.md), ADR-005/006
