# F3 — Scheduler explanations (W1 + W2)

**Status:** W1+W2 **Implemented** · **Quality:** targeted Dex W2 P2 suites green; full F3 pytest bundle re-run in progress · Dex recheck **pending** · push **held** · F3 **not** Closed/shipped — browser/manual checklist still open; W3 deferrals remain  
**Spec:** [NEXT-FEATURES-SPEC.md §6](../NEXT-FEATURES-SPEC.md#6-f3-scheduler-explanations)  
**Build:** pending commit (Dex W2 P2 fixes in working tree; no push until Dex recheck)
**Hygiene:** Alembic head **`023_schedule_outcome_provenance`** (after **`022_schedule_task_outcomes`**, revises **`021_task_workflow`**)

## Architecture note (F6 prep)

Replan now follows **`collect` → `calculate` → `apply`**: one calculation pass produces proposed blocks, per-task outcomes, structured reason facts, and optional **`placement_facts`**; apply persists blocks and `schedule_task_outcomes` (including **`placement_facts`** from the calculation result). This separation is the shared foundation for **F6 replan preview** (calculate + store without apply). **No preview UI** — only direct Update Schedule plus read-only explanation surfaces.

Module map: [apps/api/app/scheduler/README.md](../../apps/api/app/scheduler/README.md).

## Quality fix (2026-10-08, W1)

**`unplaced_horizon_exhausted` vs `unplaced_no_slot`:** Partial placement with remaining minutes inside the horizon must classify as **`unplaced_horizon_exhausted`**; **`unplaced_no_slot`** is reserved for cases where the placement loop recorded no suitable slot (e.g. past deadline with zero placement). Renee caught misclassification before exit; acceptance tests `test_partial_fit_is_horizon_exhausted` and `test_past_deadline_is_no_slot` lock the split.

## Dex W1 P2 corrections (2026-10-08)

Three holds from Dex recheck — fixed in working tree; remote push still held pending Dex sign-off (W2 reason + W2 P2 corrections share the same hold).

| # | Hold | Fix |
|---|------|-----|
| 1 | Stale **unpinned** prerequisite blocks delayed dependents even though apply wipes them | Prerequisite seed uses **pinned-only** block ends (`_seed_prerequisite_block_ends` in `calculate.py`). Proposed ends from the current pass still merge during calculate; old unpinned leftovers no longer push dependents. |
| 2 | `input_fingerprint` at persist could reflect **live** DB after collect/calculate; mid-collect **`live_snapshots_by_task`** re-queried deps | Snapshots built with **`snapshots_from_collected`** from the **same** `dependencies` list calculation uses (no second dep read). Persist writes that capture. **GET** stale compare stays **live**. Regression: poison deps after first `.all()` — snapshot stays empty. |
| 3 | Editing scheduling inputs did not refresh **Why this schedule?** | **`TaskDetailPanel`** `updateMutation` invalidates **`["schedule-explanation", taskId]`** after save of scheduling inputs. |

**Evidence:** `tests/test_f3_dex_w1_corrections.py` — prereq unpinned delay, persist capture, collect race (`test_collect_does_not_requery_deps_via_live_snapshots`), `snapshots_from_collected` exact edges.

## Dex W2 P2 corrections (2026-10-09)

Three holds from Dex W2 recheck — fixed in working tree; remote push still held pending Dex sign-off (same hold as W1 P2).

| # | Hold | Fix |
|---|------|-----|
| 1 | Immovable busy/pins could be loaded twice — fingerprint path re-queried external/pin state after calculate capture | **`load_immovable_busy_sources`** loads pinned blocks and external events **once** during collect; horizon **`busy`**, **`input_fingerprint`** `busy_external`, candidate pin minutes, and prerequisite seed all share that capture (no second external/pin reload for fingerprint). |
| 2 | **`cycle_groups` / `cycle_task_ids`** could include non-members or conflate separate cycles | Cycle membership via **Tarjan SCCs** (`dependencies.py`); **`cycle_task_ids`** lists true cycle members only; tasks **downstream** of a cycle get **`blocked_prerequisite`**; separate cycles keep distinct member lists. |
| 3 | Naive **`deadline_at`** during calculate raised **`NameError`** in **`_ensure_utc`** | **`calculate._ensure_utc`** imports **`timezone`** from **`datetime`**. |

**Evidence:** [apps/api/tests/test_f3_w2_dex_corrections.py](../../apps/api/tests/test_f3_w2_dex_corrections.py) — single immovable busy capture (`test_collect_captures_immovable_busy_once`, `test_snapshot_busy_uses_passed_capture_not_later_live`), horizon view from same capture (`test_busy_from_sources_derives_horizon_view_from_same_capture`), cycle vs prerequisite split (`test_downstream_of_cycle_gets_prerequisite_not_cycle`), naive deadline (`test_ensure_utc_accepts_naive_datetime`). Targeted suite green; full F3 bundle re-run pending.

## Scope

| Slice | Capability | W1 / W2 |
|-------|------------|---------|
| **F3-A** | Reason families + representative combinations | **W1 (landed):** `excluded_manual_or_bundle`, `excluded_duration_covered_by_pins`, `blocked_prerequisite`, `placed`, `unplaced_horizon_exhausted`, `unplaced_no_slot`. **W2 (landed):** lifecycle (`excluded_lifecycle_completed`, `excluded_lifecycle_trashed`, `excluded_lifecycle_archived`), `blocked_dependency_cycle`, `unplaced_no_time_map_interval`, `unplaced_red_exclusion`, `unplaced_busy_conflict`, `unplaced_pinned_conflict`, `unplaced_deadline_limit`, `unplaced_insufficient_min_block`, `unplaced_project_daily_cap` |
| **F3-B** | Inherited rules, map tier/source on placement, pinned prerequisites | **W1 (landed):** pin-full exclusion, prerequisite blocking, placed summary includes tier/window source. **W2 (landed):** **`placement_facts`** (timezone, horizon, effective style/window **source**, placed slice tier/window, `prerequisite_not_before`, optional placement-failure hints on unplaced); pinned/busy conflict reasons |
| **F3-C** | Stale vs current settings, never-evaluated, owner isolation | **W1 (landed):** `never_evaluated` without replan on GET; W1 stale categories; cross-owner **404** parity. **W2 (landed):** snapshot **v2** / **`algorithm_version` `f3-w2`**; extended stale categories (see below); live compare on GET only |
| **F3-D** | Human `summary_text` and JSON `reason_facts` from same facts as placement | **W1+W2 (landed):** formatter unit tests + acceptance asserts run list, task latest, and summaries match `format_summary_text`; W2 multi-fact summaries (primary = first fact) |

**Also in W1+W2 slice:** Alembic **`022_schedule_task_outcomes`** + **`023_schedule_outcome_provenance`**; `input_fingerprint` + read-time stale compare; API GET routes; CLI read-only `schedule` commands; web **Why this schedule?** panel in task scheduling detail (no run-summary page).

## W2 `primary_reason_code` values

Recorded on `schedule_task_outcomes` and returned on explanation GETs. W1 codes unchanged; W2 adds:

| Code | Typical `outcome` |
|------|-------------------|
| `excluded_lifecycle_completed` | `excluded` |
| `excluded_lifecycle_trashed` | `excluded` |
| `excluded_lifecycle_archived` | `excluded` |
| `blocked_dependency_cycle` | `blocked` |
| `unplaced_no_time_map_interval` | `unplaced` |
| `unplaced_red_exclusion` | `unplaced` |
| `unplaced_busy_conflict` | `unplaced` |
| `unplaced_pinned_conflict` | `unplaced` |
| `unplaced_deadline_limit` | `unplaced` |
| `unplaced_insufficient_min_block` | `unplaced` |
| `unplaced_project_daily_cap` | `unplaced` |

Full formatter coverage: [apps/api/app/scheduler/reasons.py](../../apps/api/app/scheduler/reasons.py).

## Snapshot v2, `f3-w2`, and stale categories

New replans persist **`input_snapshot`** with **`v`: 2** and **`algorithm_version`: `f3-w2`**. Older rows (missing snapshot or **`v` ≠ 2**) surface **`provenance`** in **`stale_categories`** on read — categories are not guessed across versions.

**Compared on GET** (never starts replan): `duration`, `deadline`, `map_style`, `deps`, `pins`, `project_daily_cap`, `timezone_horizon_workweek` (settings, not absolute horizon instants), `lifecycle`, `busy_external` (owner pinned blocks and non-mirror external events), `prerequisite_state` (blocker duration, completion, trash — edge membership stays on `deps`), `due_at_soft_target`.

**W3 — not compared:** `priority_ups`, `time_map_overrides` (F4). A matching v2 fingerprint is **not** proof those inputs are unchanged.

Implementation: [apps/api/app/scheduler/input_fingerprint.py](../../apps/api/app/scheduler/input_fingerprint.py). API mirror: [05-api-contract.md](../05-api-contract.md) § Schedule.

## `placement_facts` on apply

`calculate` builds per-task **`placement_facts`** (effective style/window provenance, horizon bounds, placed slice metadata, `prerequisite_not_before`, and for unplaced tasks optional **`last_failure`** / **`pass_hints`** from the placement loop). **`apply`** passes **`placement_facts_by_task`** into **`persist_calculation_outcomes`**, so persisted rows match the calculation pass (not a second live recompute). Read APIs expose the stored JSON on **`ScheduleExplanationOut.placement_facts`**.

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
.\.venv\Scripts\python.exe -m pytest tests/test_scheduler_reasons.py tests/test_schedule_replan.py tests/test_input_fingerprint.py tests/test_schedule_explanations.py tests/test_f3_w1_acceptance.py tests/test_f3_dex_w1_corrections.py tests/test_f3_w2_reasons.py tests/test_f3_w2_placement_telemetry.py tests/test_f3_w2_acceptance.py tests/test_f3_w2_dex_corrections.py -q
```

**Renee (2026-10-09, F3-W2 exit):** **75** passed — W1 tranche (**45** on **2026-10-08**, including Dex P2) plus W2 suites (`test_f3_w2_reasons.py`, `test_f3_w2_placement_telemetry.py`, `test_f3_w2_acceptance.py`). **Dex W2 P2 (2026-10-09):** `test_f3_w2_dex_corrections.py` green; full bundle including that file re-run pending before Dex recheck.

CLI contract (API venv + `PYTHONPATH` to `apps/api`):

```powershell
cd "F:\Code Repo\ThePlan\apps\cli"
$env:PYTHONPATH = "F:\Code Repo\ThePlan\apps\api"
..\api\.venv\Scripts\python.exe -m pytest tests/ -q
```

**Renee (2026-10-08):** **37** passed (includes `schedule explain` / `schedule runs` wiring in `test_main_commands.py`); unchanged for W2 (HTTP read-only surface only).

Apply migrations before live or manual checks:

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\alembic.exe upgrade head
```

**UI build:** production web build **green** (Andi — `tsc -b && vite build`; W2 did not require a new web slice beyond W1 panel).

## Manual checklist (Trish)

W1 items below still apply; W2 adds spot-checks for new reason families and v2 stale badges. **Not** a ship gate until Dex recheck + push policy — same as W1.

- [ ] `alembic upgrade head` → revision **`023_schedule_outcome_provenance`**
- [ ] **Update Schedule** on a project with mix of auto and manual/bundle tasks → run completes; manual/bundle tasks show exclusion explanations after replan
- [ ] Task with pinned blocks covering full estimate → exclusion “covered by pins”; replan does not add unpinned blocks for that task
- [ ] Dependent task with unfinished blocker → **blocked** prerequisite reason; after blocker completes and replan → dependent can show **placed**
- [ ] Task that partially fits in horizon → summary cites remaining minutes as **horizon exhausted**; task with past deadline and zero placement → **no suitable slot** (distinct from **`unplaced_deadline_limit`** when deadline blocks remaining work)
- [ ] Task never replanned → **Why this schedule?** shows never-evaluated copy (no fabricated placement)
- [ ] Change estimate or deadline after a run → stale badge and named categories on next panel load (no auto-replan)
- [ ] **W2:** Completed / trashed / archived (project or epic) tasks → lifecycle exclusion copy; manual/bundle on an **archived** project → **`excluded_lifecycle_archived`** (lifecycle wins over style exclusion)
- [ ] **W2:** Dependency cycle → **`blocked_dependency_cycle`**; deadline inside horizon → **`unplaced_deadline_limit`** when applicable
- [ ] **W2:** Explanation JSON shows **`algorithm_version`: `f3-w2`**, **`placement_facts`** on a placed task after replan
- [ ] `theplan schedule explain --task-id …` JSON includes `human_summary` alias matching `summary_text`
- [ ] `theplan schedule runs list` / `get --id …` / `explanations --id …` match API pagination and owner scope
- [ ] Second user cannot read another owner’s run or explanation (**404**)

## Known limitations (W3 and polish)

| Item | Notes |
|------|-------|
| **Stale compare deferrals** | **`priority_ups`**, **`time_map_overrides`** — not in v2 fingerprint; changing only those may not set **`is_stale`**. |
| **F6 preview** | No preview/async diff UI; calculate/apply split is in place for a later slice |
| **Run summary UI** | No dedicated schedule-run explanation browser in web — task panel + CLI/API only |
| **F3-B inheritance depth** | Fuller Time Map override provenance (F4 overlap) remains roadmap, not W2 exit scope |
| **Dex / push** | W1 **P2**, W2 reason/snapshot/`placement_facts`, and W2 **P2** (immovable busy capture, Tarjan cycle membership, naive deadline tz) in working tree — targeted Dex W2 P2 suite green; full F3 bundle re-run pending; Dex **recheck** and **push** still **held**. F3 stays **open** until Trish signs manual/browser checks and delivery policy. |

## Related documents

- Data: `schedule_task_outcomes` — [04-data-schema.md](../04-data-schema.md)
- Scheduler worker / dispatch — [apps/api/app/scheduler/README.md](../../apps/api/app/scheduler/README.md), ADR-005/006
