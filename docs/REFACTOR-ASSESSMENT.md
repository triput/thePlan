# Refactor assessment (DEF-011)

**Date:** 2026-08-27 (Round 4)  
**Mode:** Assessment + **greenlit cut wave** — structure-only extracts (#1–#5); no mega-rewrite  
**Status:** Cuts **#1–#8 implemented** (#6–#8 **2026-10-08**); **hardening wave** on **#1, #3, #4, #5** 2026-08-27 (Cut #2 skipped)  
**Pairs with:** [09-technical-architecture.md](./09-technical-architecture.md), [DEF-011](./DEFECTS.md#def-011--refactor-assessment-modularize--de-mix-layers), [DEF-012](./DEFECTS.md#def-012--living-technical-architecture--diagrams-catch-up)

Operator gut after Theme F / Assist / smash rounds: some modules hold too many vectors (UI + orchestration + domain), and business rules may be leaking into the wrong layer. This doc inventories real hotspots, classifies them, and proposes an **ordered cut list**. It is not a rewrite ticket.

---

## Size inventory (approx bytes, 2026-08-27)

Measured under `apps/web/src` and `apps/api/app` (excluding `__pycache__` / `node_modules`). **Pre-cut baseline** — parent files shrank after Cut wave #1–#5 (2026-08-27); exact re-measure deferred.

| Bytes | Path | Notes |
|------:|------|-------|
| ~59k | `apps/web/src/components/SettingsPanel.tsx` | Largest UI surface — many settings domains in one file |
| ~53k | `apps/web/src/styles/` + barrel `App.css` | Feature CSS files (**Cut #8** 2026-10-08) |
| ~48k | `apps/web/src/components/TaskDetailPanel.tsx` | Detail form + promote + labels + recurrence + deps |
| ~43k | `apps/web/src/components/CalendarView.tsx` | Grid + block menus + release/clear + bundle gray |
| ~40k | `apps/web/src/components/TaskList.tsx` | Forest, batch bar, DnD-ish reorder, complete, bundles |
| ~35k | `apps/web/src/api.ts` | HTTP client + DTO types (acceptable as a client kit) |
| ~32k | `apps/api/app/services/microsoft_calendar.py` | OAuth + sync + mirror — integration density |
| ~27k | `apps/api/app/models/` (was monolith `__init__.py`) | Domain modules + barrel (**Cut #7** 2026-10-08) |
| ~26k | `apps/api/app/schemas/` (was monolith `__init__.py`) | Domain modules + barrel re-export (**Cut #6** 2026-10-08) |
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
| `App.css` / `styles/*` | **split module** ✓ Cut #8 | Feature files + `@import` barrel; `import "./App.css"` unchanged in `App.tsx` |
| `TaskDetailPanel.tsx` | **extract component** ✓ Cut #2 | Section bodies extracted; panel owns shell + save flow |
| `CalendarView.tsx` | **extract component** ✓ Cut #4 | Toolbar + block menu + **day grid** (`CalendarDayColumn.tsx`); orchestrator keeps drag/replan |
| `TaskList.tsx` | **extract component** ✓ Cut #1 | Batch bar in `TaskBatchBar.tsx`; batch handlers in `useTaskBatchActions` hook |
| `api.ts` | **keep** / optional **split module** | Client kit; section comments already help; barrel-split only if import friction hurts |
| `microsoft_calendar.py` / `google_calendar.py` | **leave alone** | Dense but correctly layered as services; Tesla territory if touched |
| `models/` | **split module** ✓ Cut #7 | `mixins`, `user`, `hierarchy`, `task`, `label`, `calendar`, `schedule`, `enums`; barrel preserves Alembic `import *` |
| `schemas/` | **split module** ✓ Cut #6 | `common`, `auth`, `settings`, `hierarchy`, `tasks`, `labels`, `calendar`, `search`, `assist`, `outlines`; `from app.schemas import …` unchanged |
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

**Layer verdict:** Domain mostly still lives in API services. Cut wave **#1–#8** peeled fat React surfaces, `task_patch.py`, **schemas**, **models**, and **App.css** off monolith files (structure-only; operator smoke on UI cuts).

---

## Ordered cut list

Greenlit wave executed **2026-08-27** for Cuts **#1–#5** (structure-only; zero behavior change intent). **Cut #6** (schemas) and **Cut #7** (models) landed **2026-10-08**. **Cut #8** (App.css) greenlit immediately after #7.

| # | Cut | Status | Risk | Effort | Evidence / notes |
|---|-----|--------|------|--------|------------------|
| 1 | Extract **TaskList batch bar** (+ due/move/label/style) into `TaskBatchBar.tsx` | **Hardened** 2026-08-27 | **Low** | S | `TaskBatchBar.tsx` + `useTaskBatchActions.ts`; `npx tsc -b` PASS; smoke: multi-select → due/move/label/style/delete/bundle |
| 2 | Extract **TaskDetail** collapsible sections into child components | **Implemented** 2026-08-27 | **Low–Med** | M | `TaskDetailSection.tsx` + domain sections (`Scheduling`, `Recurrence`, `Deps`, `Labels`, `Advanced`, `Promote`, `CreateProject`); tsc PASS; **manual smoke operator-owned** |
| 3 | Peel `_apply_task_patch` / batch section-project rules from `routes/tasks.py` → `task_patch.py` | **Hardened** 2026-08-27 | **Med** | S–M | `add_task_labels` + `sync_task_labels` in `task_patch.py`; batch pytest **9/9** (+ inbox move, missing label 404, patch+labels combo) |
| 4 | Split **CalendarView** toolbar + block menu from grid | **Hardened** 2026-08-27 | **Med** | M | `CalendarToolbar`, `CalendarBlockMenu`, **`CalendarDayColumn`**; tsc PASS; smoke: drag block, resize, due-marker move, bundle gray, release/clear |
| 5 | Split **SettingsPanel** by domain tabs/sections | **Hardened** 2026-08-27 | **Med** | M | `components/settings/*`; scheduling PATCH via `schedulingDraft.ts` documented in shell; smoke: save scheduling defaults + calendar display |
| 6 | Split `schemas/__init__.py` into domain modules | **Implemented** 2026-10-08 | **Med–High** | M | Domain modules + explicit barrel; pytest assist/batch/auth/outlines/scheduled_blocks **61/61** |
| 7 | Split `models/__init__.py` into domain modules | **Implemented** 2026-10-08 | **High** | M–L | `user`, `hierarchy`, `task`, `label`, `calendar`, `schedule`, `mixins` + barrel; full pytest **273/273** |
| 8 | Carve `App.css` into feature CSS files | **Implemented** 2026-10-08 | **High** | L | `src/styles/*` (14 files) + barrel; `npm run build` PASS; operator smoke checklist below |

**Explicitly out of scope:** mega-rewrite of calendar sync, moving domain into the web client, “clean architecture” folder reshuffles, apps/desktop refactors.

---

## Recommendation

1. Cuts **#1–#8** structure + **#1/#3/#4/#5 hardening** landed; operator manual smoke owns UI regression on #1, #2, #4, #5, **#8**.
2. No further DEF-011 cuts booked until next assessment pass.
3. Keep [09-technical-architecture.md](./09-technical-architecture.md) current when further cuts land (DEF-012 living rule).

### Cut #8 — operator manual smoke (post-CSS split)

- [ ] Cold load: sidebar nav, epic expand, settings gear opens panel
- [ ] Task list: multi-select → batch due / move / label / style / delete
- [ ] Task detail: open task, collapsible sections, save
- [ ] Calendar: week view, drag block, bundle gray on partial complete, release/clear unpinned
- [ ] Quick-add bar parse + create
- [ ] Auth: login/logout (household admin if applicable)

---

## Related

- [DEFECTS.md — DEF-011](./DEFECTS.md#def-011--refactor-assessment-modularize--de-mix-layers)  
- [09-technical-architecture.md](./09-technical-architecture.md)  
- [HYGIENE-R4-QUICKSCAN.md](./HYGIENE-R4-QUICKSCAN.md) — dependency ducks for same Round 4 exit  
