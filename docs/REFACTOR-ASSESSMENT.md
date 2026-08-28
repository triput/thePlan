# Refactor assessment (DEF-011)

**Date:** 2026-08-27 (Round 4)  
**Mode:** Assessment + **greenlit cut wave** — structure-only extracts (#1–#5); no mega-rewrite  
**Status:** Cuts **#1–#5 implemented** 2026-08-27; **hardening wave** on **#1, #3, #4, #5** 2026-08-27 (Cut #2 skipped); Cuts **#6–#8 held**  
**Pairs with:** [09-technical-architecture.md](./09-technical-architecture.md), [DEF-011](./DEFECTS.md#def-011--refactor-assessment-modularize--de-mix-layers), [DEF-012](./DEFECTS.md#def-012--living-technical-architecture--diagrams-catch-up)

Operator gut after Theme F / Assist / smash rounds: some modules hold too many vectors (UI + orchestration + domain), and business rules may be leaking into the wrong layer. This doc inventories real hotspots, classifies them, and proposes an **ordered cut list**. It is not a rewrite ticket.

---

## Size inventory (approx bytes, 2026-08-27)

Measured under `apps/web/src` and `apps/api/app` (excluding `__pycache__` / `node_modules`). **Pre-cut baseline** — parent files shrank after Cut wave #1–#5 (2026-08-27); exact re-measure deferred.

| Bytes | Path | Notes |
|------:|------|-------|
| ~59k | `apps/web/src/components/SettingsPanel.tsx` | Largest UI surface — many settings domains in one file |
| ~53k | `apps/web/src/App.css` | Global stylesheet; batch/trash/calendar/detail all piled in |
| ~48k | `apps/web/src/components/TaskDetailPanel.tsx` | Detail form + promote + labels + recurrence + deps |
| ~43k | `apps/web/src/components/CalendarView.tsx` | Grid + block menus + release/clear + bundle gray |
| ~40k | `apps/web/src/components/TaskList.tsx` | Forest, batch bar, DnD-ish reorder, complete, bundles |
| ~35k | `apps/web/src/api.ts` | HTTP client + DTO types (acceptable as a client kit) |
| ~32k | `apps/api/app/services/microsoft_calendar.py` | OAuth + sync + mirror — integration density |
| ~27k | `apps/api/app/models/__init__.py` | Monolith model module |
| ~26k | `apps/api/app/schemas/__init__.py` | Monolith Pydantic schemas |
| ~25k | `apps/api/app/services/google_calendar.py` | Parallel to Microsoft |
| ~22k | `apps/api/app/api/routes/tasks.py` | CRUD + batch + trash + complete + promote hooks |
| ~18k | `apps/web/src/components/OutlineImportPanel.tsx` | Theme F propose/review/apply UI |
| ~17k | `apps/api/app/api/routes/calendar.py` | Calendar routes |
| ~17k | `apps/api/app/services/outline_templates.py` | Pack/propose templates |
| ~14k | `apps/api/app/scheduler/placement.py` | Fuzzy placement |
| ~13k | `apps/web/src/components/HouseholdPanel.tsx` | Household admin |
| ~12k | `apps/web/src/components/Sidebar.tsx` | Nav + epic expand |
| ~12k | `apps/api/app/services/quick_add.py` | NL parse |
| ~12k | `apps/api/app/services/recurrence.py` | RRULE helpers |
| ~11k | `apps/web/src/App.tsx` | Shell routing |
| ~10k | `apps/api/app/api/routes/scheduled_blocks.py` | Blocks + bundle create + capacity |
| ~10k | `apps/web/src/components/AssistPanel.tsx` | Assist UI |
| ~9k | `apps/api/app/scheduler/replan.py` | Update Schedule orchestrator |
| ~9k | `apps/api/app/services/task_helpers.py` | Soft-delete / complete / subtree helpers |

---

## Classification

Legend: **keep** (size OK / coherent) · **extract component** (UI split) · **extract service** (domain out of route/UI) · **leave alone** (pain ≠ payoff yet) · **split module** (file carve, same layer)

| Hotspot | Classify | Why |
|---------|----------|-----|
| `SettingsPanel.tsx` | **extract component** ✓ Cut #5 | Domain sections now in `components/settings/*`; shell remains |
| `App.css` | **leave alone** (or light section files later) | Painful to navigate; splitting CSS without a design-system plan is high-churn / low product value — **Cut #8 held** |
| `TaskDetailPanel.tsx` | **extract component** ✓ Cut #2 | Section bodies extracted; panel owns shell + save flow |
| `CalendarView.tsx` | **extract component** ✓ Cut #4 | Toolbar + block menu in `CalendarToolbar` / `CalendarBlockMenu` |
| `TaskList.tsx` | **extract component** ✓ Cut #1 | Batch bar in `TaskBatchBar.tsx`; forest render stays in list |
| `api.ts` | **keep** / optional **split module** | Client kit; section comments already help; barrel-split only if import friction hurts |
| `microsoft_calendar.py` / `google_calendar.py` | **leave alone** | Dense but correctly layered as services; Tesla territory if touched |
| `models/__init__.py` | **split module** (optional) | Classic monolith; extract per-entity files when next schema wave needs it |
| `schemas/__init__.py` | **split module** (optional) | Same story as models |
| `routes/tasks.py` | **extract service** ✓ Cut #3 | Thin CRUD orchestration; PATCH/batch/labels in `task_patch.py` |
| `task_helpers.py` | **keep** | Soft-delete / complete / subtree; right layer |
| `task_patch.py` | **keep** | PATCH/batch section-project, plan bind, `sync_task_labels` + `add_task_labels` |
| `useTaskBatchActions.ts` | **keep** (new) | Cut #1 hardening — batch mutations out of `TaskList` |
| `CalendarDayColumn.tsx` | **keep** (new) | Cut #4 hardening — day/week grid column; drag state stays in `CalendarView` |
| `OutlineImportPanel.tsx` | **keep** | Large but single pipeline (propose → review → apply) |
| `outline_templates.py` | **keep** | Service-layer correct |
| `placement.py` / `replan.py` | **keep** | Scheduler package already modular |
| `bundle_blocks.py` | **keep** | New Round 2/4 service — good boundary |
| `Sidebar.tsx` / `App.tsx` | **leave alone** | Shell size is fine |
| `AssistPanel.tsx` | **leave alone** | Bounded |

**Layer verdict:** Domain mostly still lives in API services. Cut wave #1–#5 peeled fat React surfaces and `task_patch.py` off routes; **monolith models/schemas** and **App.css** remain (Cuts **#6–#8 held**).

---

## Ordered cut list

Greenlit wave executed **2026-08-27** for Cuts **#1–#5** (structure-only; zero behavior change intent). Cuts **#6–#8** remain **held** — do not start without explicit greenlight.

| # | Cut | Status | Risk | Effort | Evidence / notes |
|---|-----|--------|------|--------|------------------|
| 1 | Extract **TaskList batch bar** (+ due/move/label/style) into `TaskBatchBar.tsx` | **Hardened** 2026-08-27 | **Low** | S | `TaskBatchBar.tsx` + `useTaskBatchActions.ts`; `npx tsc -b` PASS; smoke: multi-select → due/move/label/style/delete/bundle |
| 2 | Extract **TaskDetail** collapsible sections into child components | **Implemented** 2026-08-27 | **Low–Med** | M | `TaskDetailSection.tsx` + domain sections (`Scheduling`, `Recurrence`, `Deps`, `Labels`, `Advanced`, `Promote`, `CreateProject`); tsc PASS; **manual smoke operator-owned** |
| 3 | Peel `_apply_task_patch` / batch section-project rules from `routes/tasks.py` → `task_patch.py` | **Hardened** 2026-08-27 | **Med** | S–M | `add_task_labels` + `sync_task_labels` in `task_patch.py`; batch pytest **9/9** (+ inbox move, missing label 404, patch+labels combo) |
| 4 | Split **CalendarView** toolbar + block menu from grid | **Hardened** 2026-08-27 | **Med** | M | `CalendarToolbar`, `CalendarBlockMenu`, **`CalendarDayColumn`**; tsc PASS; smoke: drag block, resize, due-marker move, bundle gray, release/clear |
| 5 | Split **SettingsPanel** by domain tabs/sections | **Hardened** 2026-08-27 | **Med** | M | `components/settings/*`; scheduling PATCH via `schedulingDraft.ts` documented in shell; smoke: save scheduling defaults + calendar display |
| 6 | Split `schemas/__init__.py` into domain modules | **Held** | **Med–High** | M | Import churn across API; do with a quiet week |
| 7 | Split `models/__init__.py` similarly | **Held** | **High** | M–L | Alembic/relationship imports; pair with schema wave |
| 8 | Carve `App.css` into feature CSS modules / files | **Held** | **High** | L | Visual regression risk; defer unless design-system pass |

**Explicitly out of scope:** mega-rewrite of calendar sync, moving domain into the web client, “clean architecture” folder reshuffles, apps/desktop refactors.

---

## Recommendation

1. Cuts **#1–#5** structure + **#1/#3/#4/#5 hardening** landed; operator manual smoke still owns UI regression on #1, #2, #4, #5.
2. Do **not** book Cuts **#6–#8** as smash work until explicitly greenlit.
3. Next quiet week: consider **Cut #6** (schemas) before **#7** (models); **#8** (CSS) stays last.
4. Keep [09-technical-architecture.md](./09-technical-architecture.md) current when further cuts land (DEF-012 living rule).

---

## Related

- [DEFECTS.md — DEF-011](./DEFECTS.md#def-011--refactor-assessment-modularize--de-mix-layers)  
- [09-technical-architecture.md](./09-technical-architecture.md)  
- [HYGIENE-R4-QUICKSCAN.md](./HYGIENE-R4-QUICKSCAN.md) — dependency ducks for same Round 4 exit  
