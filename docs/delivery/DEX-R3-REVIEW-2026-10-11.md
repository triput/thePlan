<!--
==============================================================================
  File: docs/delivery/DEX-R3-REVIEW-2026-10-11.md
  Description: Independent Wave 1 review, browser reproductions, and open gates.
  Component: Docs/Delivery
  Version: 1.5
  Created: 2026-10-11
  Last Update: 2026-10-11
==============================================================================
-->

# Dex R3 Wave 1 review

**Wave disposition:** **Closed / shipped — Trish 2026-10-11.** Trish ran the full manual acceptance matrix (morning) and authorized ship. All reported dock/draft defects (**D1–D4 + D2b**) **Pass / Closed**; broad matrix no longer **Open** or **HOLD**. Negative-duration API validation and post-refresh tidy remain deferred non-blockers. Detail: [R3-WORKBENCH-2026-10-11.md](./R3-WORKBENCH-2026-10-11.md).

## D2b focused closure, 2026-10-11

**R3-D2b: Pass / Closed by Dex.** Retested code `43f5797`, docs HEAD `db20a21`, using a fresh disposable database `dex_r3_d2b_review`, isolated API on 8001, and working-tree Vite on 5174. Independently ran **57/57 web tests (21 suites)** and production build: pass, existing large-chunk warning only.

Browser checks all began with Calendar Support already collapsed and task entry through top-bar Search:

- Clean Collapse removes task details and exposes Support.
- Dirty Collapse now displays the guard. Cancel retains the edited description and task.
- Discard collapses; reopening through Search confirms the discarded description is absent.
- Save and collapse removes task details and exposes Support. An independent API read confirms `D2b saved via guarded collapse` persisted.
- Opening Support with no selected task still reveals normal calendar support.

Evidence: `docs/redesign/screenshots/r3-d2b-dirty-guard-pass.png`. No new defect found in this focused pass. D1/D3/D4 retain their previous focused Pass results; all reported R3 dock/draft defects are now closed. **Trish closed the broad manual matrix 2026-10-11** (ship authorization). The separate negative-duration validation follow-up and post-refresh tidy/refactor remain deferred non-blockers. No product code changes, commit, or push by Dex. Disposable API/database and Vite cleaned up after testing.

The dated sections below retain earlier review history; this closure supersedes their D2b pending status.

## Dex focused retest, 2026-10-11

**Historical (pre-ship):** Wave was **Open / HOLD** at this retest. Independently tested code tip `4b51af7`, documentation HEAD `6f80e43`. **54/54 web tests pass (20 suites); production build passes**, with the existing large-chunk warning. Browser used the isolated Vite/API/database setup described below. No product code changed or push performed on the retest pass. **Superseded:** Trish **Closed / shipped 2026-10-11** after full manual matrix.

| Item | Retest result |
| --- | --- |
| R3-D1 | **Pass, focused paths.** At 683 x 384 CSS pixels, idle support has a working Close and exposes the Support tab. Task-close and preview-close return to dismissible idle support. This is responsive testing, not actual browser zoom acceptance. |
| R3-D2 | **Pass** (ordinary path on `4b51af7`). Residual **R3-D2b Pass / Closed** on `43f5797` — see closure section above. |
| R3-D3 | **Pass.** Toolbar Preview changes from collapsed support reveals the calculation surface. Collapse followed by another toolbar preview also reveals it; ready results are visible. No proposal was applied. |
| R3-D4 | **Pass, exercised recovery paths.** A 501-character title is rejected with readable client validation and retained draft. A failed API update and an offline API preserve title, description, and duration in Save and switch. Successful retry navigates to Work; independent API read confirms all three values persisted. |

### R3-D2b P2 Collapse after opening a Search result does not collapse or guard

**Status:** **Pass / Closed by Dex** (2026-10-11) on `43f5797` — see **D2b focused closure** above.

**Fix (Jim):** `nextSupportDockToggleAction` — if a task is selected, Collapse always runs the guarded collapse/clear-selection path even when `supportCollapsed` preference is already true (Search-while-collapsed). Expand only when collapsed with no selected task. Unit coverage in `supportDockState.test.ts`.

**Repro (Dex retest residual on `4b51af7`):**

1. On Calendar, collapse support so the Support tab is visible.
2. Search for a task in the top bar and open the result.
3. Click **Collapse** in the task panel.
4. The task remains visible. With an edited description, the same click also skips the dirty prompt. Reproduced with both clean and dirty tasks.

**Cause:** `toggleSupportCollapsed` branched only on the saved `supportCollapsed` preference. Search can display a selected task while that preference remains true, so Collapse called `revealSupportDock()` instead of the guarded collapse path.

Evidence screenshot: `docs/redesign/screenshots/r3-d2-retest-residual.png` (task remains open after Collapse, dirty description, no dialog).

### Additional observation and limits

The negative-duration failure fixture (`-1` minute through Save and switch) reaches the database check constraint and produces an unhandled API error. The browser shows `Failed to fetch` in this cross-origin test setup; draft recovery works. The current TaskUpdate schema has no nonnegative constraint. This is a separate API/input-validation follow-up, not evidence that structured API validation messages have been browser-verified. The original overlong-title path is now intercepted client-side.

Disposable container/database removed after testing; temporary Vite stopped and viewport override reset. The sections below preserve the original review and pre-retest handoff history; this retest section supersedes their pending statuses for the explicitly exercised paths.

**Historical:** **HOLD full manual acceptance** at this retest. Four defects were reproduced on the prior tip; Jim landed code fixes for R3-D1–D4 (**Fixed (code), awaiting Dex retest**). Original review: `301e8a9`, `13eea80`, and `7ba37e4` against `0b74800`. **Retest tip:** `4b51af7` (docs stamp `d910f60`). **Broad matrix closed Trish 2026-10-11.**

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

**Closed 2026-10-11 (Trish):** Delivery checklist in [R3-WORKBENCH-2026-10-11.md](./R3-WORKBENCH-2026-10-11.md) — full manual matrix **Pass** after Dex D1–D4/D2b retest. Wave **Closed / shipped**.

The delivered idle support is a combined summary rather than R3's tabbed Unscheduled/Preview/Key panel, and task details retain the older field layout and deadline copy. Visual fidelity vs mockups remains a **future explicit review** item, not a ship blocker for this wave. Negative-duration API validation and post-refresh tidy stay **deferred**.

## Jim handoff

**Jim / Dex:** All reported R3 dock/draft defects (**D1–D4 + D2b**) focused-Pass / Closed. **Trish Closed / shipped 2026-10-11** — broad manual matrix complete; negative-duration API follow-up + post-refresh tidy deferred non-blockers.
