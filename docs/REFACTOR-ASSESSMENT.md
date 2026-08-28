# Refactor assessment (DEF-011)

**Date:** 2026-08-27 (Round 4)  
**Mode:** Assessment only — **no mega-refactor code moves**  
**Status:** Shipped for operator review; mutating extracts need **Trish greenlight**  
**Pairs with:** [09-technical-architecture.md](./09-technical-architecture.md), [DEF-011](./DEFECTS.md#def-011--refactor-assessment-modularize--de-mix-layers), [DEF-012](./DEFECTS.md#def-012--living-technical-architecture--diagrams-catch-up)

Operator gut after Theme F / Assist / smash rounds: some modules hold too many vectors (UI + orchestration + domain), and business rules may be leaking into the wrong layer. This doc inventories real hotspots, classifies them, and proposes an **ordered cut list**. It is not a rewrite ticket.

---

## Size inventory (approx bytes, 2026-08-27)

Measured under `apps/web/src` and `apps/api/app` (excluding `__pycache__` / `node_modules`).

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
| `SettingsPanel.tsx` | **extract component** | Multiple settings domains (timezone, calendars, Assist, schedule defaults) share one scroll monster |
| `App.css` | **leave alone** (or light section files later) | Painful to navigate; splitting CSS without a design-system plan is high-churn / low product value |
| `TaskDetailPanel.tsx` | **extract component** | Promote / labels / recurrence / deps / inline create can be section components |
| `CalendarView.tsx` | **extract component** | Block chrome vs day/week grid vs toolbar capacity actions |
| `TaskList.tsx` | **extract component** (+ maybe tiny hooks) | Batch bar + forest render + complete/bundle actions — UI orchestration, not stolen domain |
| `api.ts` | **keep** / optional **split module** | Client kit; section comments already help; barrel-split only if import friction hurts |
| `microsoft_calendar.py` / `google_calendar.py` | **leave alone** | Dense but correctly layered as services; Tesla territory if touched |
| `models/__init__.py` | **split module** (optional) | Classic monolith; extract per-entity files when next schema wave needs it |
| `schemas/__init__.py` | **split module** (optional) | Same story as models |
| `routes/tasks.py` | **extract service** (incremental) | Patch/batch/section-project rules + complete/shrink hooks belong in helpers/services already growing |
| `OutlineImportPanel.tsx` | **keep** | Large but single pipeline (propose → review → apply) |
| `outline_templates.py` | **keep** | Service-layer correct |
| `placement.py` / `replan.py` | **keep** | Scheduler package already modular |
| `task_helpers.py` | **keep** | Right layer; grow carefully |
| `bundle_blocks.py` | **keep** | New Round 2/4 service — good boundary |
| `Sidebar.tsx` / `App.tsx` | **leave alone** | Shell size is fine |
| `AssistPanel.tsx` | **leave alone** | Bounded |

**Layer verdict:** Domain mostly still lives in API services. Worst smell is **fat React surfaces** (Settings / TaskDetail / TaskList / Calendar) and **monolith models/schemas**, not “scheduler math in the browser.” Routes `tasks.py` is the main backend candidate for peeling helpers when batch/trash/complete keep growing.

---

## Ordered cut list (for Trish greenlight)

Do **not** start these until explicitly approved. Prefer one cut per wave.

| # | Cut | Risk | Effort | Notes |
|---|-----|------|--------|-------|
| 1 | Extract **TaskList batch bar** (+ due/move/label/style) into `TaskBatchBar.tsx` | **Low** | S | Pure presentational + callbacks; Round 4 just grew this bar |
| 2 | Extract **TaskDetail** collapsible sections into child components | **Low–Med** | M | Watch mutation/cache invalidation ownership |
| 3 | Peel `_apply_task_patch` / batch section-project rules from `routes/tasks.py` → `task_helpers` or `task_patch.py` | **Med** | S–M | Tests already cover batch move/due; keep pytest green |
| 4 | Split **CalendarView** toolbar + block menu from grid | **Med** | M | Easy to break drag/release/bundle gray |
| 5 | Split **SettingsPanel** by domain tabs/sections | **Med** | M | Highest byte win; careful with settings PATCH shape |
| 6 | Split `schemas/__init__.py` into domain modules | **Med–High** | M | Import churn across API; do with a quiet week |
| 7 | Split `models/__init__.py` similarly | **High** | M–L | Alembic/relationship imports; pair with schema wave |
| 8 | Carve `App.css` into feature CSS modules / files | **High** | L | Visual regression risk; defer unless design-system pass |

**Explicitly out of scope until greenlight:** mega-rewrite of calendar sync, moving domain into the web client, “clean architecture” folder reshuffles, apps/desktop refactors.

**5-minute safe extracts (optional, still ask):** Cut #1 only — batch bar file extract with zero behavior change. Not done in Round 4 (assessment-first).

---

## Recommendation

1. Accept this assessment as the DEF-011 exit for **docs**.
2. Next feature pile: prefer **Cut #1 or #3** if a wave already touches TaskList / tasks routes.
3. Do **not** book Cuts #6–#8 as smash work.
4. Keep [09-technical-architecture.md](./09-technical-architecture.md) updated when cuts land (DEF-012 living rule).

---

## Related

- [DEFECTS.md — DEF-011](./DEFECTS.md#def-011--refactor-assessment-modularize--de-mix-layers)  
- [09-technical-architecture.md](./09-technical-architecture.md)  
- [HYGIENE-R4-QUICKSCAN.md](./HYGIENE-R4-QUICKSCAN.md) — dependency ducks for same Round 4 exit  
