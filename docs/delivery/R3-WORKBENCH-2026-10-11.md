# R3 Midnight Workbench — delivery note (Slices 0–3)

**Dex retest 2026-10-11:** **HOLD full manual acceptance.** D1/D3/D4 **Pass**; D2 ordinary collapse **Pass**; residual **R3-D2b** (Search-while-collapsed Collapse) **Fixed (code), awaiting Dex retest**. See [DEX-R3-REVIEW-2026-10-11.md](DEX-R3-REVIEW-2026-10-11.md). Wave **Open / not Closed / not shipped**.

<!--
==============================================================================
  File: docs/delivery/R3-WORKBENCH-2026-10-11.md
  Description: R3 Workbench UI wave delivery — Slices 0–3 scope, deferred items, open manual gate.
  Component: Docs/Delivery
  Version: 1.1
  Created: 2026-10-11
  Last Update: 2026-10-11
==============================================================================
-->

**Status:** **Implemented (Slices 0–3)** in working tree · **Not Closed / not shipped** — Slice 4 verification and manual acceptance remain open; phase gates apply (Renee Quality exit before Page marks Closed).

**Authority**

| Doc | Role |
| --- | --- |
| [R3_DEX_REVIEW_AND_JIM_HANDOFF.md](../redesign/R3_DEX_REVIEW_AND_JIM_HANDOFF.md) | Design direction, corrections, acceptance themes, slice order |
| [R3-CAPABILITY-INVENTORY.md](../redesign/R3-CAPABILITY-INVENTORY.md) | Slice 0 capability truth + **Deferred** boundary |

**Theme naming (operator note):** R3 art is “Midnight Workbench,” but **Settings → Theme** presets keep historical ids. **`Dark`** (default) matches R3 `r3.css` cool-dark chrome (`#0B1020` / `#10172E`, accent `#7EA6FF`, IBM Plex Sans). The preset labeled **`Midnight`** remains the **light navy** palette — not the R3 dark look. Do not rename presets in docs without an explicit product decision.

---

## What landed (by slice)

### Slice 0 — Inventory

- [R3-CAPABILITY-INVENTORY.md](../redesign/R3-CAPABILITY-INVENTORY.md): production UI capability map, handoff corrections, explicit deferred list, slice mapping.

### Slice 1 — Foundations and work surfaces

- **Workbench tokens** — shared type scale, spacing, radii, sidebar rail width, Time Map semantic colors in [`apps/web/src/index.css`](../../apps/web/src/index.css); default theme preset **`dark`** aligned to R3 cool-dark tokens in [`theme.ts`](../../apps/web/src/theme.ts).
- **Collapsible navigation (desktop)** — sidebar **`⟨` / `⟩`** control collapses to icon rail; preference in [`navPrefs.ts`](../../apps/web/src/navPrefs.ts) (`theplan.nav.collapsed`). Narrow viewports keep **☰** drawer behavior unchanged.
- **List and board restyle** — existing query keys, sorting, filters, pagination, and mutations unchanged; presentation uses Workbench shell styles ([`shell-sidebar.css`](../../apps/web/src/styles/shell-sidebar.css), list/board CSS).

### Slice 2 — Shared support panel and task details

- **Support dock** — right-hand panel on Calendar and when a task is open elsewhere ([`SupportDock.tsx`](../../apps/web/src/components/SupportDock.tsx), [`support-dock.css`](../../apps/web/src/styles/support-dock.css)).
- **Calendar idle** — **Calendar support** panel: schedule hint, **Preview changes** entry, unscheduled-in-horizon sample links, **Map & blocks** legend ([`CalendarSupportIdle.tsx`](../../apps/web/src/components/CalendarSupportIdle.tsx)).
- **Task details in dock** — selecting a task replaces dock content with **Task details**; **Collapse** returns to calendar support when on Calendar (desktop).
- **Schedule preview in dock** — **Preview schedule changes** uses shared [`SchedulePreviewPanelContent.tsx`](../../apps/web/src/components/SchedulePreviewPanelContent.tsx) (`layout="dock"`); legacy modal shell retained but unused in app shell.
- **Dirty-edit guards** — unsaved task draft prompts on switch task, close, change view, collapse dock, and calendar preview handoff ([`supportDockState.ts`](../../apps/web/src/supportDockState.ts), [`UnsavedTaskChangesDialog`](../../apps/web/src/components/UnsavedTaskChangesDialog.tsx), [`taskDetailDraft.ts`](../../apps/web/src/taskDetailDraft.ts)).
- **Dock collapse** — desktop **Collapse** / collapsed **Support** expand tab; collapse preference [`supportDockPrefs.ts`](../../apps/web/src/supportDockPrefs.ts).

### Slice 3 — Calendar and preview integration

- **Quieter calendar chrome** — band overlays and block styling in [`calendar.css`](../../apps/web/src/styles/calendar.css) / [`CalendarDayColumn.tsx`](../../apps/web/src/components/CalendarDayColumn.tsx).
- **Three Time Map tiers preserved** — **Preferred** (green), **Acceptable** (yellow), **Excluded** (red), plus **Neutral** overlay and non-color legend copy in calendar support; overrides, timezone, day/week, and clipping behavior unchanged.
- **Toolbar contract unchanged** — **Preview changes** (calculate → stored proposal) vs **Update Schedule** (collect → calculate → apply) remain distinct ([`CalendarToolbar.tsx`](../../apps/web/src/components/CalendarToolbar.tsx)).
- **Windows-aware shortcuts** — help overlay uses **Ctrl** on Windows for **Ctrl+K** and **Ctrl+Z** ([`HelpOverlay.tsx`](../../apps/web/src/components/HelpOverlay.tsx)).

---

## Non-goals / deferred (this wave)

From inventory and handoff — **do not treat as shipped** in Slices 0–3:

| Item | Notes |
| --- | --- |
| Unified command palette | Separate Quick Add, Search, shortcuts only |
| Epic swimlanes, daily workload charts, activity history | Handoff out of redesign |
| Per-change undo UI | Global **Ctrl+Z** stack only |
| Selective apply (subset of preview) | **Apply whole proposal** only |
| “Done, last 7 days” default | Board/saved views use API pagination + completion predicate |
| Coursera / external-busy reinterpretation | External busy stays gray occupancy |
| Hard-coded mockup counts | API/pagination truth |
| Slice 4 integrated verification | Browser matrix, focused regression, Dex/manual sign-off |
| Overlap cascade layout (if not meeting reachability) | Keep prior overlap behavior until validated |
| Extra confirmation on **Update Schedule** | First slice keeps existing direct replan unless Trish opts in |

Full table: [R3-CAPABILITY-INVENTORY § Explicit DEFERRED](../redesign/R3-CAPABILITY-INVENTORY.md#explicit-deferred-list-r3-pictured-or-handoff--not-this-wave).

---

## Quality evidence

**Automated (Renee, 2026-10-11):** cwd `apps/web`. Green after Jim’s D1–D4 fixes (+4 tests vs pre-fix **50/50**).

| Check | Command | Result |
| --- | --- | --- |
| Web unit tests | `cd apps/web && npm test` | Exit 0. **57** tests / **21** suites after R3-D2b (+3). |
| Web production build | `cd apps/web && npm run build` | Exit 0. `tsc -b && vite build` (Vite 8.2.1). Existing JS chunk >500 kB warning only — not a failure. |
| New regression modules | `supportDockState.test.ts`, `taskDetailDraft.test.ts`, calendar height/compact in `calendarUtils.test.ts` | Present and green; dock collapse/preview resolver and draft-reset/save-validation coverage expanded for D1–D4. |

**Not run:** browser Dex retest of D1–D4; full manual UI acceptance rows below; `apps/api` pytest; `npm run lint`.

Wave remains **Open / HOLD full manual acceptance / not Closed / not shipped** until Dex retest of D1–D4, remaining checklist rows, and Trish sign-off.

---

## Open Dex / manual checklist (R3 acceptance)

Adapted from handoff [§ Acceptance evidence for Renee and Dex](../redesign/R3_DEX_REVIEW_AND_JIM_HANDOFF.md#acceptance-evidence-for-renee-and-dex). **All rows Open** — not Closed, not shipped.

### Layout and responsive

- [ ] **Open** — At **1440×900** and **1366×768**, expanded/collapsed navigation and support panel usable with real long titles.
- [ ] **Open** — At **125%** and **200%** browser zoom, every action and all content reachable via scroll or intentional responsive layout (125% export crop alone is not a failure).

### Keyboard and focus

- [ ] **Open** — Focus visible and sensible through flyout, calendar item, details, dirty-edit prompt, return, and collapse.
- [ ] **Open** — Non-drag move actions work; typing in fields does not trigger global mutations.

### Calendar grid

- [ ] **Open** — Three-way overlaps, short adjacent blocks, multiple placements for one task, and mixed external/pinned/movable/proposed blocks remain distinguishable and selectable.
- [ ] **Open** — Green/yellow/red bands, overrides, settings timezone, clipping, and selected-map scope behave as before (quieter paint only).

### Preview and replan

- [ ] **Open** — Preview create causes no live placement changes; apply uses the displayed valid proposal.
- [ ] **Open** — Stale/expired/running-conflict cases fail honestly; retry cannot duplicate work; edits invalidate relevant explanations and previews.

### Tasks, board, saved views

- [ ] **Open** — Board moves, within-column ordering, Waiting notes, completion/uncompletion, recurrence, child policy, and stale revision recovery unchanged; repeated moves do not blank accumulated pages.
- [ ] **Open** — Saved views preserve filters, sort, presentation, completion membership, pagination, and sidebar ordering; counts do not claim completeness while pages remain.

### Dirty edits and panel safety

- [ ] **Open** — Task draft survives failed save and cancelled navigation; unschedule preserves the task; delete remains distinct.
- [ ] **Open** — Collapsing or switching panels does not discard a draft or apply a preview.

### Data honesty

- [ ] **Open** — No pictured placeholder became a hard-coded production count, reason, grouping, seven-day limit, or unsupported command.

---

## Source index (primary)

| Area | Files |
| --- | --- |
| Shell | [`App.tsx`](../../apps/web/src/App.tsx), [`Sidebar.tsx`](../../apps/web/src/components/Sidebar.tsx), [`navPrefs.ts`](../../apps/web/src/navPrefs.ts) |
| Support dock | [`SupportDock.tsx`](../../apps/web/src/components/SupportDock.tsx), [`supportDockContext.tsx`](../../apps/web/src/supportDockContext.tsx), [`supportDockState.ts`](../../apps/web/src/supportDockState.ts) |
| Calendar | [`CalendarView.tsx`](../../apps/web/src/components/CalendarView.tsx), [`CalendarToolbar.tsx`](../../apps/web/src/components/CalendarToolbar.tsx), [`CalendarDayColumn.tsx`](../../apps/web/src/components/CalendarDayColumn.tsx) |
| Preview UI | [`SchedulePreviewPanelContent.tsx`](../../apps/web/src/components/SchedulePreviewPanelContent.tsx) |
| Tests | [`supportDockState.test.ts`](../../apps/web/tests/supportDockState.test.ts), [`taskDetailDraft.test.ts`](../../apps/web/tests/taskDetailDraft.test.ts) |

**Next:** Slice 4 — run checklist above, record evidence in this doc, link Renee Quality exit; Trish/Dex sign-off before Closed/shipped.
