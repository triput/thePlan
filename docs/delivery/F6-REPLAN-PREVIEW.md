# F6 — Replan preview

**Latest Dex gate, 2026-10-10:** F6 **P1 R1** verified closed (**37** API integration tests incl. concurrent reparent). F4 Wave 1 **verified closed** incl. **W1-R1** volume stale (`GET …/stale-summary`). Web **36** + CLI **36** green. [Evidence](DEX-WAVE1-RETEST-2026-10-10.md). Trish Done sign-off **2026-10-10** ([sign-off](./MANUAL-CHECKLIST.md#sign-off)); F6 **not Closed** (F6-B–D).

<!--
==============================================================================
  File: docs/delivery/F6-REPLAN-PREVIEW.md
  Description: F6 replan preview delivery tracker — worker, apply, W3 modal/CLI status.
  Component: Docs/Delivery
  Version: 1.0
  Created: 2026-10-09
  Last Update: 2026-10-10
==============================================================================
-->

**Status:** **W1–W2 Quality green** — **24** F6 pytest (**W1 9** + **W2 15**, Renee **2026-10-09**) · **W3 conditional go** (Calendar **Preview changes** modal — Andi; CLI preview create/get/apply — Tesla) · **F6-B–D** not fully accepted · push **not requested** · Trish Done **2026-10-10** — **not** Closed/shipped ([manual checklist](./MANUAL-CHECKLIST.md), [sign-off](./MANUAL-CHECKLIST.md#sign-off); F6-B–D) · **Dex:** three P2s + archive P1 + **P1 R1 Verified closed** (Wave 1 retest **2026-10-10**) — [DEX-F6 evidence](./DEX-F6-MANUAL-2026-10-09.md)

**Spec:** [NEXT-FEATURES-SPEC.md §9](../NEXT-FEATURES-SPEC.md#9-f6-replan-preview)  
**Build:** working tree on `cursor` `main` (F6 API + scheduler preview worker extension; uncommitted)  
**Hygiene:** Alembic head **`025_schedule_previews`** (after F4 **`024_time_map_overrides`**) — adds `schedule_previews` and `user_settings.scheduling_revision`

## Wave map

| Wave | Scope | Status |
|------|--------|--------|
| **W1** | Migration **`025`**; `POST/GET /schedule/previews`; worker `collect` → `calculate` only; immutable `proposal_json` + owner input fingerprint/snapshot; **15-minute** TTL when **ready**; read-time **stale** / **expired** promotion; diff counts (identity-based); **no** live block/task/mirror writes during calculate; preview admission **independent** of migration **018** one-running-replan | **Quality green** — **9** pytest (`test_f6_w1_preview.py`, F6-A + staleness/read paths) |
| **W2** | `POST /schedule/previews/{id}/apply` → shared `apply_calculation`; per-owner **`scheduling_revision`** bumps on scheduling-relevant writes; apply-time **`PREVIEW_*`** conflicts; idempotent receipt on **`applied`** retry; serializes with **`SCHEDULE_RUN_IN_PROGRESS`** | **Quality green** — **15** pytest (`test_f6_w2_preview_apply.py`, Renee **2026-10-09**); **F6-B–D** slice acceptance **not** fully closed |
| **W3+** | Web **Preview changes** modal; CLI `theplan schedule preview` create/get/apply; F6-E operator-readable before/after; hypothetical unsaved overrides | **In progress** — web modal + CLI create/get/apply **landed** (local); operator manual + remaining UX **open** |

## Scope — acceptance mapping

| Slice | Capability | W1 / later |
|-------|------------|------------|
| **F6-A** | Preview calculate never mutates domain tables (`scheduled_blocks`, tasks, deps, mirrors, etc.); failed calculate rolls back | **W1 (landed):** table guard + failure path in pytest |
| **F6-B** | Same inputs → preview proposal matches direct replan output | **W2:** parity pytest green — slice **not fully accepted** |
| **F6-C** | Stale inputs, expiry, clock passage, apply rejects without silent recalc | **W1:** read-time stale/expiry; revision during calculate. **W2:** apply **`PREVIEW_*`** pytest green — slice **not fully accepted** |
| **F6-D** | Idempotent apply receipt; foreign owner **404**; apply blocked while replan **running** | **W2:** pytest green — slice **not fully accepted** |
| **F6-E** | Meaningful **`diff_counts`**; proposal **`before_blocks`** / **`proposed_blocks`** / per-task **`outcomes`** for UI | **W1 (foundation):** API fields + identity diff; **W3 (partial):** Calendar **Preview changes** modal (Andi); full operator readability **open** |

**Also in W1 slice:** Preview worker polled by Compose **`scheduler`** service (same dispatch model as replan — [apps/api/app/scheduler/README.md](../../apps/api/app/scheduler/README.md)); **`SCHEDULE_DISPATCH=thread`** runs preview inline for bare uvicorn.

## Architecture

1. **Direct replan (unchanged):** `POST /schedule/replan` → `schedule_runs` → worker `collect` → `calculate` → **`apply`** (live blocks + F3 outcomes).
2. **Preview:** `POST /schedule/previews` → `schedule_previews` → worker **`collect` → `calculate` only** → store **`proposal_json`** (algorithm **`f3-w2`**, v3-shaped owner snapshot).
3. **Apply preview:** `POST /schedule/previews/{id}/apply` rehydrates proposal → **`apply_calculation`** under owner advisory lock → new **`schedule_run`** row (completed) + receipt embedded in preview **`stats_json`**.

Preview jobs do **not** consume the **one running replan per owner** index; apply and direct replan still serialize via **`SCHEDULE_RUN_IN_PROGRESS`** and scheduling revision checks.

## Integration

| Layer | Contract | W1 / W2 |
|-------|----------|---------|
| **API** | `/schedule/previews`, `/schedule/previews/{id}`, `/schedule/previews/{id}/apply` — [05-api-contract.md](../05-api-contract.md) § Schedule · Replan preview | Automated pytest |
| **Scheduler** | [preview.py](../../apps/api/app/scheduler/preview.py), [preview_proposal.py](../../apps/api/app/scheduler/preview_proposal.py), worker preview poll | W1 calculate path |
| **Revision** | `user_settings.scheduling_revision` bumped on scheduling-relevant CRUD (tasks, deps, blocks, settings fields, time-map overrides, etc.); Kanban-only / title-only edits do **not** bump | W2 apply validation |
| **Web** | Calendar **Preview changes** modal (before/after, diff counts entry) | **W3 landed (Andi, local)** — manual + F6-E polish **open** |
| **CLI** | `theplan schedule preview` create, get, apply | **W3 landed (Tesla, local)** — operator manual **open** |
| **Auth** | Owner-scoped; foreign preview → **404** `PREVIEW_NOT_FOUND` (same body as missing) | Automated |

## Automated evidence

From repo root, API venv active (`apps/api/.venv`):

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\python.exe -m pytest tests/test_f6_w1_preview.py -q
```

**Renee (2026-10-09, F6-W1 / F6-A exit):** **9** passed — zero domain writes, failure rollback, read staleness/expiry, revision race during calculate, preview allowed while replan running, ownership.

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\python.exe -m pytest tests/test_f6_w1_preview.py tests/test_f6_w2_preview_apply.py -q
```

**Renee (2026-10-09, F6-W2 exit):** **24** passed combined — **W2 15** covers parity (**F6-B**), apply stale/expired/past blocks (**F6-C**), idempotent apply / foreign owner / replan conflict (**F6-D**), revision bump rules.

Apply migrations before live or manual checks:

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\alembic.exe upgrade head
```

Expect head **`025_schedule_previews`**.

## Manual checklist (Trish)

Canonical checkboxes: **[MANUAL-CHECKLIST.md](./MANUAL-CHECKLIST.md)** § F6. Do not maintain a second full list here.

## Known limitations (by wave)

| Item | Notes |
|------|-------|
| **Web / CLI** | Preview modal + CLI create/get/apply **landed locally** — operator [manual checklist](./MANUAL-CHECKLIST.md) § F6; Trish Done **2026-10-10**; F6-B–D **not Closed** |
| **Selective apply** | Whole proposal only ([spec design default](../NEXT-FEATURES-SPEC.md#9-f6-replan-preview)) |
| **Hypothetical inputs** | Preview uses persisted DB state only — unsaved override drafts deferred |
| **Mirror atomicity** | Apply uses ordinary replan mirror path; provider failures do not roll back local apply ([spec](../NEXT-FEATURES-SPEC.md#9-f6-replan-preview)) |
| **GET vs apply** | GET may promote **ready** → **stale** / **expired** without commit; apply re-validates fingerprint, revision, expiry, and past blocks |
| **Close policy** | F6 stays **Open / in-progress** until **F6-B–D** acceptance, operator manual, remaining W3 UX, and delivery policy — **not** Closed/shipped on API pytest alone |

## Related documents

- F3 calculate/apply split — [F3-SCHEDULER-EXPLANATIONS.md](./F3-SCHEDULER-EXPLANATIONS.md) (Architecture note · F6 prep)
- Stale category vocabulary (apply **`PREVIEW_STALE`**) — [05-api-contract.md](../05-api-contract.md) § Schedule explanations (snapshot v3 compare)
- Combined scenario **Disrupted week** — [NEXT-FEATURES-SPEC.md §12](../NEXT-FEATURES-SPEC.md#12-implementation-slices-and-verification-handoff)
