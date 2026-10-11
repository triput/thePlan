# R3 capability inventory (Slice 0)

<!--
==============================================================================
  File: docs/redesign/R3-CAPABILITY-INVENTORY.md
  Description: Production UI capability inventory for R3 Midnight Workbench — prevent control loss in Slice 1+.
  Component: Design/Delivery
  Version: 1.0 (Slice 0)
  Created: 2026-10-11
  Last Update: 2026-10-11
==============================================================================
-->

**Authority:** [R3_DEX_REVIEW_AND_JIM_HANDOFF.md](./R3_DEX_REVIEW_AND_JIM_HANDOFF.md) (corrections, deferred scope, and slice order).

**Purpose:** Record what the **current production web UI** exposes so R3 restyling does not drop actions because they are absent from mockups. This is source-derived inventory (grep/read of `apps/web`), not runtime sign-off.

**Disposition legend**

| Tag | Meaning |
| --- | --- |
| **Keep** | Behavior and user access must survive R3 (may move into rail flyout, overflow, or support panel). |
| **Restyle** | Primary R3 work is tokens, layout, density, and hierarchy; API/query/mutation semantics unchanged. |
| **Deferred** | Shown in R3 art or called out in handoff as **out of this wave** — do not implement unless explicitly scoped later. |

---

## Handoff corrections affecting presentation (must not regress)

These override mockup simplifications; full rationale is in the handoff doc.

1. **Three Time Map tiers** — Keep distinct **green / yellow / red** band semantics (plus neutral/no overlay), non-color cues, map-scoped precedence, overrides, settings timezone rendering, day/week behavior, and out-of-window clipping. R3 may quiet the visual treatment; it must not collapse to “Available vs Excluded” only (`CalendarDayColumn.tsx`, `focusWindows.ts`, `TimeMapOverridesSection.tsx`).
2. **Update Schedule ≠ Preview changes** — **Update Schedule** runs collect → calculate → **apply** (`CalendarView.tsx` → `postScheduleReplan`). **Preview changes** runs calculate → stored proposal → **Apply whole proposal** in modal (`SchedulePreviewModal.tsx`). Do not merge or swap these paths in Slice 1–3 unless Trish explicitly opts into extra Update confirmation.
3. **Unschedule ≠ delete task** — Removing a **scheduled block** (`CalendarBlockMenu` delete / `deleteScheduledBlock`) clears calendar placement; **Delete task** (`TaskDetailPanel`, batch bar) soft-deletes to Trash. Copy and confirmations must stay distinct.
4. **Windows-aware shortcuts** — Help and global handlers use **Ctrl** (not ⌘-only glyphs). Scope shortcuts away from text fields; expose equivalent buttons (`App.tsx`, `HelpOverlay.tsx`, `TaskList.tsx` list navigation).

---

## Explicit DEFERRED list (R3-pictured or handoff — not this wave)

Do **not** build these as part of R3 Midnight Workbench unless a separate scoped decision is recorded:

| Item | Notes |
| --- | --- |
| **Unified command palette** | R3 art suggests search/add/command in one surface; production has separate Quick Add, Search, and shortcuts only. |
| **Epic swimlanes on board** | Handoff: no swimlanes in this redesign. |
| **Daily workload charts** | Handoff: not in this redesign. |
| **Activity history / audit timeline** | Handoff: not in this redesign. |
| **Per-change undo UI** | Production has a **global** undo stack (`undoStack.tsx`, Ctrl+Z); not per-mutation undo chips from mockups. |
| **Selective apply (subset of preview)** | Production is **whole-proposal apply** only (`SchedulePreviewModal.tsx`). |
| **“Done, last 7 days” as default Done column** | Board Done uses paginated API loads, not a fixed 7-day window; saved views use predicate `completion`, not mockup defaults. |
| **Coursera / external-busy reinterpretation** | External busy blocks stay gray calendar occupancy; do not fold coursework into external events (handoff Q&A). |
| **Hard-coded mockup counts** | Column totals, WIP, stale badges, and list lengths must reflect API/pagination (`TaskBoard.tsx`, `TaskList.tsx`). |

---

## 1. Shell and navigation

| Capability | Where | Disposition |
| --- | --- | --- |
| App shell layout (sidebar + main + optional task detail) | `App.tsx`, `App.css`, `main-layout.css` | Restyle |
| Narrow viewport: hamburger, nav backdrop, `nav-open` | `App.tsx` | Keep |
| Top bar: Quick Add, Assist, Import, Search, help (?), user chip, Sign out | `App.tsx` | Restyle (cluster layout may match R3 support area later) |
| Task detail sheet when task selected (loading/error states) | `App.tsx` | Keep |
| Task detail width CSS variable from localStorage | `App.tsx` (`theplan.taskDetail.width`) | Keep |
| OAuth return toasts + open Calendar (`?gcal=`, `?mcal=`) | `App.tsx` | Keep |
| Deep link saved view (`?saved_view=` / `?view=`) | `App.tsx` | Keep |
| Global toasts | `ToastHost.tsx` | Restyle |
| Due reminder polling (in-app toast + browser notification) | `ReminderPoller.tsx` | Keep |
| Undo stack provider | `App.tsx`, `undoStack.tsx` | Keep |

### Sidebar (`Sidebar.tsx`)

| Capability | Where | Disposition |
| --- | --- | --- |
| Brand | `Sidebar.tsx` | Restyle |
| Smart views: Inbox, Work, Today, Upcoming | `Sidebar.tsx` | Keep |
| Saved views list + **New saved view** (+) | `Sidebar.tsx`, `SavedViewFilterModal.tsx` | Keep |
| Saved view **reorder** (up/down) | `Sidebar.tsx`, `reorder.ts` | Keep |
| Calendar nav entry | `Sidebar.tsx` | Keep |
| Labels management entry + **By label** shortcuts | `Sidebar.tsx` | Keep |
| Archived / Trash entries | `Sidebar.tsx` | Keep |
| Epic tree expand/collapse, epic select, edit epic, add project under epic | `Sidebar.tsx`, `EditEpicForm.tsx`, `CreateProjectForm.tsx` | Keep |
| Standalone projects + reorder + edit | `Sidebar.tsx`, `EditProjectForm.tsx` | Keep |
| Project reorder within epic / standalone | `Sidebar.tsx` | Keep |
| Settings footer → Settings modal | `Sidebar.tsx`, `SettingsPanel.tsx` | Keep |
| `requestExpandEpic` event (post-import navigation) | `Sidebar.tsx`, `ImportPanel` callback in `App.tsx` | Keep |

---

## 2. Task list (`TaskList.tsx`)

| Capability | Where | Disposition |
| --- | --- | --- |
| View-scoped task fetch (inbox, work, today, upcoming, project, epic, label, saved) | `TaskList.tsx`, `view.ts` | Keep |
| **List / Board** toggle (where `boardViewSupported`) | `TaskList.tsx`, `taskPresentation.ts` | Restyle |
| Persist list vs board per view key (localStorage) | `taskPresentation.ts` | Keep |
| Saved view: persist presentation mode to server (`patchView`) | `TaskList.tsx` | Keep |
| Saved view: **Edit filters** / repair banner | `TaskList.tsx`, `SavedViewFilterModal.tsx` | Keep |
| **Show completed** toggle (not on saved views filtered to open-only) | `TaskList.tsx` | Keep — not “last 7 days Done” |
| **Overbooked only** filter + count chip | `TaskList.tsx` | Keep |
| Project view: **Add section** (`CreateSectionForm`) | `TaskList.tsx` | Keep |
| Section groups + section reorder | `TaskList.tsx`, `reorder.ts` | Keep |
| Epic view: project/section grouping + “Other” bucket | `TaskList.tsx` | Keep |
| Hierarchy nesting + forest ordering | `taskForest.ts`, `TaskList.tsx` | Keep |
| Task row: select, Alt+click / subtree select, complete checkbox | `TaskList.tsx` | Keep |
| Task row meta: priority, due, plan, soft target, deadline, overbooked, duration, labels | `TaskList.tsx` | Restyle |
| Task **manual reorder** (siblings) | `TaskList.tsx`, `ReorderButtons.tsx` | Keep |
| **Drag handle → calendar** (schedule via drop) | `TaskList.tsx`, `taskCalendarDrag.ts` | Keep |
| Add subtask (+) on row | `TaskList.tsx` | Keep |
| Inline **add task** / **add subtask** forms | `TaskList.tsx` | Keep |
| Multi-select toolbar + **TaskBatchBar** | `TaskList.tsx`, `TaskBatchBar.tsx` | Keep |
| Saved view **Load more** pagination | `TaskList.tsx` | Keep |
| List keyboard: J/K/↑/↓ focus, Enter open, X/Space complete | `TaskList.tsx` | Keep |
| Open children policy on complete (`CompleteDialog`) | `TaskList.tsx` | Keep |
| Switch to **TaskBoard** when presentation is board | `TaskList.tsx` → `TaskBoard.tsx` | Restyle |

---

## 3. Board (`TaskBoard.tsx`)

| Capability | Where | Disposition |
| --- | --- | --- |
| Columns: Ready, In progress, Waiting, **Done** (derived completion column) | `TaskBoard.tsx` | Restyle |
| Column **counts** (roots-only vs server total) | `TaskBoard.tsx` | Keep — real totals, not mock numbers |
| **WIP summary** (In progress + Waiting) | `TaskBoard.tsx` | Keep |
| Work/Inbox/Today/Upcoming: epic + project **filter selects** | `TaskBoard.tsx`, `taskPresentation.ts` | Keep |
| **Roots only** toggle (localStorage) | `TaskBoard.tsx` | Keep |
| Per-column and Done **Load more** / saved-view board pagination | `TaskBoard.tsx` | Keep |
| Drag-and-drop column move + within-column insert hints | `TaskBoard.tsx` | Keep |
| **Move to…** select (non-drag move) | `TaskBoard.tsx` | Keep |
| Waiting move → **note modal** | `TaskBoard.tsx` | Keep |
| Complete with open children dialog | `TaskBoard.tsx`, `CompleteDialog.tsx` | Keep |
| Card badges: due, deadline, plan, overbooked, duration, labels, sched hints | `TaskBoard.tsx` | Restyle |
| Smart Today/Upcoming: scheduled-block membership | `TaskBoard.tsx` | Keep |
| Saved view: `queryViewTasks` with `board_order` | `TaskBoard.tsx` | Keep |
| Undo push on bulk complete from board | `TaskBoard.tsx`, `undoStack.tsx` | Keep |

---

## 4. Calendar and toolbar

### Toolbar (`CalendarToolbar.tsx` via `CalendarView.tsx`)

| Capability | Where | Disposition |
| --- | --- | --- |
| Prev / **Today** / Next | `CalendarToolbar.tsx` | Restyle |
| Title (day or week) | `CalendarToolbar.tsx` | Restyle |
| **Schedule conflict** count banner | `CalendarToolbar.tsx` | Keep |
| **Clear unpinned** (scoped visible day/week + confirm) | `CalendarToolbar.tsx`, `CalendarView.tsx` | Keep |
| **Preview changes** (poll preview, open modal) | `CalendarToolbar.tsx`, `CalendarView.tsx` | Keep |
| **Update Schedule** (direct replan poll) | `CalendarToolbar.tsx`, `CalendarView.tsx` | Keep |
| **6A–10P / 24h** toggle | `CalendarToolbar.tsx`, `calendarUtils.ts` | Keep |
| **Time Map overlay** select (visual only; Neutral + focus windows) | `CalendarToolbar.tsx` | Restyle |
| **Schedule stale** run-level hint badge | `CalendarToolbar.tsx`, `CalendarView.tsx` | Keep |
| **Day / Week** mode (week hidden on narrow) | `CalendarToolbar.tsx` | Keep |

### Grid (`CalendarView.tsx`, `CalendarDayColumn.tsx`)

| Capability | Where | Disposition |
| --- | --- | --- |
| Scheduled blocks (pinned/unpinned, bundle, conflicts) | `CalendarDayColumn.tsx` | Restyle |
| **External busy** events (gray; unchanged by Time Map) | `CalendarDayColumn.tsx` | Keep |
| Due markers + drag due | `CalendarView.tsx`, `CalendarDayColumn.tsx` | Keep |
| Block drag move + resize | `CalendarView.tsx` | Keep |
| Slot click / task drop from list | `CalendarView.tsx` | Keep |
| Time Map band overlay (green/yellow/red tiers) | `CalendarDayColumn.tsx`, `focusWindows.ts` | Restyle — **keep three tiers** |
| Override-active day header badge | `CalendarView.tsx` | Keep |
| Overlay legend (precedence, pins, busy count) | `CalendarView.tsx` | Restyle |
| Narrow: drag disabled; tap-to-edit hint copy | `CalendarView.tsx` | Keep |

### Block editor (`CalendarBlockMenu.tsx`)

| Capability | Where | Disposition |
| --- | --- | --- |
| Create / edit block: task, start/end, **pin** | `CalendarBlockMenu.tsx` | Keep |
| **Delete** block / bundle remove | `CalendarBlockMenu.tsx` | Keep — unschedule placement, not task delete |
| **Release remainder** (completed task / unused slot) | `CalendarBlockMenu.tsx`, `CalendarView.tsx` | Keep |
| Bundle member count + inactive bundle copy | `CalendarBlockMenu.tsx` | Keep |

---

## 5. Task detail (`TaskDetailPanel.tsx` and sections)

| Capability | Where | Disposition |
| --- | --- | --- |
| Panel open/close; header **Save** + close | `TaskDetailPanel.tsx` | Restyle |
| **Resizable width** (pointer + Home/End) + localStorage | `TaskDetailPanel.tsx` | Keep |
| Core fields: title, description, priority, due, soft target, deadline | `TaskDetailPanel.tsx` | Restyle |
| Collapsible sections (localStorage open state) | `TaskDetailPanel.tsx`, `TaskDetailSection.tsx` | Keep |
| **Scheduling**: plan, duration, preferred Time Map, schedule style + inheritance hints | `TaskDetailScheduling.tsx` | Keep |
| **Why this schedule?** explanation panel (stale badge, reason facts, run id) | `TaskDetailScheduling.tsx` | Keep — use API text, not mock strings |
| Overbooked explainer (vs calendar overlap) | `TaskDetailScheduling.tsx` | Keep |
| **Recurrence** edit | `TaskDetailRecurrence.tsx` | Keep |
| **Dependencies**: project, section, parent, add child | `TaskDetailDeps.tsx` | Keep |
| **Labels** | `TaskDetailLabels.tsx` | Keep |
| **Advanced**: reminders, source refs | `TaskDetailAdvanced.tsx`, `SourceRefsReadonly` | Keep |
| **Promote to project** | `TaskDetailPromote.tsx` | Keep |
| **Delete task** (confirm) | `TaskDetailPanel.tsx` | Keep |
| Footer Save / Delete | `TaskDetailPanel.tsx` | Restyle |
| Workflow column changes | *Board only* (`TaskBoard.tsx`) | Keep (not in detail form today) |

*Slice 2 note:* Handoff requires dirty-form prompts when switching tasks/panels; production today closes without a universal guard — implement in Slice 2, do not drop fields while adding guards.

---

## 6. Schedule preview (`SchedulePreviewModal.tsx`)

| Capability | Where | Disposition |
| --- | --- | --- |
| Modal open from calendar Preview | `CalendarView.tsx` | Restyle |
| States: loading, running, failed, ready, stale, expired, applied | `SchedulePreviewModal.tsx` | Keep |
| Summary stats + diff counts (added/removed/moved/unchanged unpinned) | `SchedulePreviewModal.tsx` | Keep |
| Pinned block hint | `SchedulePreviewModal.tsx` | Keep |
| Block change list (truncation message) | `SchedulePreviewModal.tsx` | Keep |
| Affected tasks + reason facts (cap 25 + overflow text) | `SchedulePreviewModal.tsx` | Keep |
| Apply errors: stale categories, refresh CTA | `SchedulePreviewModal.tsx` | Keep |
| **Close**, **Refresh preview**, **Apply whole proposal** | `SchedulePreviewModal.tsx` | Keep |
| Selective apply / per-block checkboxes | — | **Deferred** |

---

## 7. Saved views

| Capability | Where | Disposition |
| --- | --- | --- |
| Create from sidebar (+) | `Sidebar.tsx`, `SavedViewFilterModal.tsx` | Keep |
| Edit from list header / repair banner | `TaskList.tsx`, `SavedViewFilterModal.tsx` | Keep |
| Predicate: inbox, projects, epics, labels (any/all), priorities, workflow, completion, schedule status/style, due (none/rolling/fixed) | `SavedViewFilterModal.tsx`, `savedViewPredicate.ts` | Keep |
| Sort key (manual, created, due, priority, title) | `SavedViewFilterModal.tsx`, `taskPresentation.ts` | Keep |
| Presentation mode at save (list/board from toggle) | `SavedViewFilterModal.tsx` | Keep |
| Invalid reference repair strip | `SavedViewFilterModal.tsx` | Keep |
| Delete saved view | `SavedViewFilterModal.tsx` | Keep |
| Sidebar reorder | `Sidebar.tsx` | Keep |
| “Done last 7 days” default column | — | **Deferred** (use completion predicate + pagination instead) |

---

## 8. Settings — calendar-related and scheduling

| Capability | Where | Disposition |
| --- | --- | --- |
| Settings modal shell | `SettingsPanel.tsx` | Restyle |
| Account / password | `settings/AccountSection.tsx` | Keep |
| Theme preset + custom colors | `settings/ThemeSections.tsx` | Restyle |
| Scheduling defaults (timezone, horizon, workweek, etc.) + save | `settings/SchedulingDefaultsSection.tsx`, `schedulingDraft.ts` | Keep |
| **Calendar display**: Show 24 hours (syncs with calendar via event) | `settings/CalendarDisplaySection.tsx` | Keep |
| **Time Maps** CRUD (bands with green/yellow/red tiers) | `settings/TimeMapsSection.tsx` | Keep |
| **Time Map overrides** (dated replacements, tiers) | `settings/TimeMapOverridesSection.tsx` | Keep |
| Plans | `settings/PlansSection.tsx` | Keep |
| **Google / Microsoft** connect, disconnect, mirror, subscriptions, sync | `settings/CalendarAccountsSections.tsx` | Keep |
| Assist status | `settings/AssistStatusSection.tsx` | Keep |
| Household (admin) | `HouseholdPanel.tsx` | Keep |

---

## 9. Archive, Trash, Labels

| Capability | Where | Disposition |
| --- | --- | --- |
| **Archived** epics/projects list + unarchive | `ArchivedView.tsx` | Keep |
| Archive epic/project from edit forms | `EditEpicForm.tsx`, `EditProjectForm.tsx` | Keep |
| **Trash**: list trashed tasks, restore, empty trash, purge older than N days | `TrashView.tsx` | Keep |
| **Labels** view: create single/batch, edit, colors, usage counts | `LabelsManagement.tsx`, `EditLabelForm.tsx` | Keep |
| Label nav shortcuts in sidebar | `Sidebar.tsx` | Keep |

---

## 10. Import, Assist, Search, Quick Add

| Capability | Where | Disposition |
| --- | --- | --- |
| **Quick Add** with parse preview chips + create | `QuickAdd.tsx`, `App.tsx` | Restyle |
| **Search** tasks (debounced, keyboard nav in results) | `SearchBox.tsx` | Restyle |
| **Assist**: propose actions, review edit, apply | `AssistPanel.tsx` | Keep |
| **Import** modal: Templates vs Custom outline tabs | `ImportPanel.tsx`, `TemplatesPanel.tsx`, `OutlineImportPanel.tsx` | Keep |
| Import deep link `?import=` and `theplan:open-import` event | `ImportPanel.tsx` | Keep |
| Post-import: expand epic + select epic view | `App.tsx`, `Sidebar.tsx` | Keep |
| Unified command palette | — | **Deferred** |

---

## 11. Keyboard shortcuts and help

| Shortcut | Action | Where | Disposition |
| --- | --- | --- | --- |
| `?` | Toggle help overlay | `App.tsx`, `HelpOverlay.tsx` | Keep |
| `Q` or **Ctrl+K** | Focus Quick Add | `App.tsx`, `HelpOverlay.tsx` | Keep — Windows labels |
| `/` | Focus search | `App.tsx`, `HelpOverlay.tsx` | Keep |
| **Ctrl+Z** | Global undo (stack) | `App.tsx`, `undoStack.tsx` | Keep — not per-change undo UI |
| `J` / `K` or ↑ / ↓ | Navigate tasks in list | `TaskList.tsx`, `HelpOverlay.tsx` | Keep |
| `Enter` | Open focused task | `TaskList.tsx` | Keep |
| `X` or `Space` | Complete/uncomplete focused task | `TaskList.tsx` | Keep |
| `Esc` | Close nav drawer / modals (contextual) | `App.tsx`, `HelpOverlay.tsx` | Keep |
| Shortcuts suppressed in inputs and when modal open | `App.tsx`, `TaskList.tsx` | Keep |

Help button (?) in top bar | `App.tsx` | Restyle |

---

## 12. Batch actions (`TaskBatchBar.tsx`)

When one or more tasks are selected in list view:

| Action | Disposition |
| --- | --- |
| Set schedule style (manual / standalone) | Keep |
| Set priority | Keep |
| Apply label | Keep |
| Set due / clear due | Keep |
| Move to project (inbox) | Keep |
| Block as bundle (start time + optional pin) | Keep |
| Delete selected | Keep |
| Clear selection | Keep |

---

## Slice mapping (reminder)

| Slice | Inventory focus |
| --- | --- |
| **0 (this doc)** | Capability truth + deferred boundary |
| **1** | Shell/nav, list, board — restyle without losing rows in sections 1–3, 11–12 |
| **2** | Task detail + support panel state, dirty navigation |
| **3** | Calendar tiers, toolbar, preview integration |
| **4** | Verification against handoff acceptance list |

---

## Source index (primary files)

- Shell: `apps/web/src/App.tsx`, `apps/web/src/components/Sidebar.tsx`
- Tasks: `apps/web/src/components/TaskList.tsx`, `apps/web/src/components/TaskBoard.tsx`, `apps/web/src/components/TaskBatchBar.tsx`
- Calendar: `apps/web/src/components/CalendarView.tsx`, `CalendarToolbar.tsx`, `CalendarDayColumn.tsx`, `CalendarBlockMenu.tsx`
- Preview: `apps/web/src/components/SchedulePreviewModal.tsx`
- Detail: `apps/web/src/components/TaskDetailPanel.tsx` (+ `TaskDetail*.tsx` sections)
- Saved views: `apps/web/src/components/SavedViewFilterModal.tsx`, `apps/web/src/savedViewPredicate.ts`, `apps/web/src/taskPresentation.ts`
- Settings: `apps/web/src/components/SettingsPanel.tsx`, `apps/web/src/components/settings/*`
- Utilities: `apps/web/src/view.ts`, `apps/web/src/focusWindows.ts`, `apps/web/src/undoStack.tsx`, `apps/web/src/components/HelpOverlay.tsx`
