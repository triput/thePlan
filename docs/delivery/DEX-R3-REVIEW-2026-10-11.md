<!--
==============================================================================
  File: docs/delivery/DEX-R3-REVIEW-2026-10-11.md
  Description: Independent Wave 1 review, browser reproductions, and open gates.
  Component: Docs/Delivery
  Version: 1.1
  Created: 2026-10-11
  Last Update: 2026-10-11
==============================================================================
-->

# Dex R3 Wave 1 review

**HOLD full manual acceptance.** Four defects were reproduced on the prior tip; Jim landed code fixes for R3-D1–D4 (**Fixed (code), awaiting Dex retest**). Original review: `301e8a9`, `13eea80`, and `7ba37e4` against `0b74800`. **Retest tip:** 4b51af7 (parent commits soon).

## Verified environment and checks

- Independently ran `npm test` (prior pass): **50/50 pass**, 20 suites. Post-fix automated regression (Renee): **54/54 pass** (+4 behavioral tests in `supportDockState.test.ts` and `taskDetailDraft.test.ts`).
- Independently ran `npm run build`: **pass**, existing large-chunk warning.
- Browser used current working-tree Vite UI at `127.0.0.1:5174` with a separate API container on port 8001 and disposable database `dex_r3_review_20261011`. Existing Compose API image supplied the unchanged backend. Live household data and the deployed web service were not modified.
- Created two manual-scheduling fixture tasks. Actual browser paths exercised: Calendar support task selection, close, collapse, preview create, dirty Cancel, normal Save, successful Save and switch, and rejected Save and switch.
- Tested responsive transition to 683 × 384 CSS pixels. This exercises the narrow breakpoint; it is not a claim of having tested actual browser zoom at 200%.
- Application code was inspected alongside DOM state. This is a focused defect pass, not completion of the entire manual matrix.

## R3-D1 P1 Narrow calendar is covered by an undismissable support panel

**Status:** **Fixed (code), awaiting Dex retest.**

**Fix (Jim):** Narrow viewports honor the dock collapse preference instead of forcing support open; calendar-idle support on narrow gets an accessible **Close** control that collapses/hides the panel so the calendar is reachable again. Task and preview modes retain close paths as before.

**Repro (original):** Open Calendar, then use a viewport at or below 768 px wide. Reproduced at 683 × 384.

**Actual (original):** Calendar support is fixed across the entire viewport. It has neither Close nor Collapse. The calendar and app navigation are covered. Closing a task or preview returns to this same idle support surface.

**Cause (original):** `SupportDock.tsx:57` forces `dockCollapsed` false for narrow screens; the idle support renders with `task-detail-sheet`, whose responsive CSS makes it full-screen. At `SupportDock.tsx:137`, the collapse control is desktop-only, and the close control exists only for preview mode.

**Required:** Make narrow idle support opt-in/dismissible. Closing must return to the calendar; all narrow panel modes need an accessible exit. Test initial Calendar entry, close task, close preview, and resizing while collapsed.

## R3-D2 P2 Collapse does not collapse an open task

**Status:** **Fixed (code), awaiting Dex retest.**

**Fix (Jim):** Collapsing the dock runs the dirty guard, then sets collapse preference **and clears `selectedTaskId`**, so the resolver no longer keeps task mode visible over a “collapsed” chrome state.

**Repro (original):** Calendar → open a task from the support list → Collapse.

**Actual (original):** Task details remain visible. Confirmed with a clean task. A dirty task follows the prompt but reaches the same faulty transition.

**Cause (original):** `App.tsx:180` sets only the collapse preference. `resolveSupportDockMode` prioritizes `selectedTaskId` over collapse, so the task continues to occupy the dock.

**Required:** Define and implement the task-to-collapsed transition consistently. Guard dirty edits, then close or deliberately retain the selected task in a hidden state. Re-expansion and return-to-preview must remain coherent.

## R3-D3 P2 Starting preview from a collapsed dock leaves the result hidden

**Status:** **Fixed (code), awaiting Dex retest.**

**Fix (Jim):** Explicit preview requests call **`revealSupportDock()`** before starting calculation so a collapsed dock expands and the preview surface can render when results arrive.

**Repro (original):** Collapse Calendar support with no task selected → toolbar Preview changes → wait for calculation.

**Actual (original):** Calculation completes but no preview appears. Only the generic Support tab remains. Manually opening Support reveals the ready preview and Apply action.

**Cause (original):** `App.tsx:192–200` starts the preview without expanding support. The resolver hides preview whenever the collapse preference is true.

**Required:** Explicit preview requests reveal the preview surface. Keep collapsing an already-open preview a separate, reversible action. Test both initial start and regeneration paths.

## R3-D4 P2 Failed Save and switch destroys the unsaved draft

**Status:** **Fixed (code), awaiting Dex retest.**

**Fix (Jim):** Form re-init uses **`shouldResetTaskDetailDraft`** (task **identity** change only), so optimistic cache rollback after a failed save no longer overwrites the in-progress draft; client-side title validation and **`describeApiError`** supply readable errors on the imperative save path.

**Repro (original):** Open a task → change Title to a value longer than 500 characters → select Work → Save and switch. The server rejects the update. This is a deterministic validation failure, with no network fault injection.

**Actual (original):** The prompt stays open, but Title resets to its previously saved value. The attempted draft is lost; the underlying error displays as `[object Object]`.

**Cause (original):** `TaskDetailPanel.tsx:449–455` rolls back the optimistic task cache. The effect ending at line 357 copies every changed `task` object back into the form, overwriting the independent user draft. The new imperative save path exposes this behavior through the dirty-navigation guard.

**Required:** Roll back cached persisted state without overwriting the draft on failure. Initialize on task identity change or an explicit successful-save/discard boundary. Validate consistently on the imperative path and show a readable error. Test server rejection and transport failure with multiple changed fields, then successful retry.

**Scope note:** Optimistic rollback and the `[task]` reset predate this wave. This is an existing defect exposed in the new dirty-save path and an unmet explicit R3 acceptance requirement, not a claim that R3 introduced the underlying reset logic.

## Passing focused browser observations

*(Recorded on pre-fix tip; re-verify after Jim’s fixes.)*

- Dirty navigation presents the expected prompt.
- Cancel retains the edited title and current task.
- Normal Save persists a valid title and closes details.
- Save and switch persists valid changes and leaves the task panel.
- A preview calculation on the manual-task fixture settles and displays the manual-exclusion reason when the dock is expanded. No Apply was exercised in this pass.
- Support legend exposes Preferred, Acceptable, Excluded, and Neutral. This verifies copy presence only, not the full overlay behavior matrix.

## Remaining acceptance work

Keep the delivery checklist **Open**. **Retest R3-D1–D4 first** on the post-fix tip, then complete: populated 1440/1366 layouts; actual 125%/200% browser zoom; keyboard focus and modal containment; busy/overlapping/short blocks; Time Map tiers, override, timezone and clipping behavior; preview stale/expiry/conflict/apply/retry; board recurrence/child/revision/ordering behavior; saved-view sorting/counts/pagination; and full draft recovery.

The delivered idle support is a combined summary rather than R3's tabbed Unscheduled/Preview/Key panel, and task details retain the older field layout and deadline copy. Treat visual fidelity as a separate explicit review item. Token alignment and these focused passing flows do not establish that the complete R3 interaction design is implemented.

## Jim handoff

**Jim (fixes landed):** R3-D1–D4 addressed in working tree; +4 web unit tests green (**54/54** total).

**Dex (next):** Ready for **focused retest of R3-D1–D4** at **4b51af7**. Keep the wave **Open**. **HOLD** full manual acceptance until those four paths pass in browser and the remaining matrix rows are exercised. No push, rebuild of the live stack, or production acceptance was performed by Dex on the original pass.
