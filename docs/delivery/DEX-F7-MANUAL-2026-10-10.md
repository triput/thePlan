# Dex F7 review and local verification

**Filename:** DEX-F7-MANUAL-2026-10-10.md  
**Last modified:** 2026-10-10  
**File version:** 1.2  
**Disposition:** R1–R6 verified closed in the focused Dex retest. F7 remains Open for the acknowledged completion gaps and remaining sign-off. Original findings below are retained as history. No implementation edits, commit, push, or production data changes by Dex.

## Build and environment

Reviewed the local F7 W1–W3 sources against `NEXT-FEATURES-SPEC.md` section 10 and `F7-SAVED-VIEWS.md`. Current HEAD at final inspection: `ed442de`. The working tree contained staged team changes; the tested artifact is the frozen source snapshot, not a claim that all work belongs to that commit.

Snapshot: `C:\Users\trish\.codex\visualizations\2026\10\08\01a11d56-e98c-7c31-995d-8b17c9a41e5a\f7-review`. Its `source-manifest.json` hashes 386 files across API, CLI, and web; comparison with the working tree after testing found no changed source files in that manifest.

Disposable Docker project `dex-f7-review`: PostgreSQL 16 with tmpfs data; API image `dex-f7-review-api:local`; fresh migration through `027_saved_filter_presentation`; frozen frontend served only at `http://localhost:18080`. Synthetic account and tasks only. No daily-driver migrations or household credential changes. Browser checks used Chrome and the Computer Use browser controls.

## Verified checks

| Check | Result and limits |
|---|---|
| API quality suite | **64 passed** in 4.61 s: `python -m pytest tests/test_f7_w1_views.py tests/test_f7_w1_predicate.py tests/test_f7_w1_quality.py -q` inside the isolated API container. |
| CLI suite | **32 passed** in 0.30 s: `python -m pytest tests/test_views_commands.py tests/test_main_commands.py -q` against the frozen CLI copied into the test container. These are mocked API tests. Local Windows Python environments lacked pytest, so the container supplied the runner. |
| Frontend | `npm run build` passed from the frozen web snapshot. Bundle `index-CUN2ytSz.js`; existing >500 kB bundle advisory. |
| Actual CLI/API integration | Separate temporary CLI session, actual `python -m theplan`: login; views list/create/get/query by ID with limit 1 and offset 1; query by Inbox slug; patch name/order; delete the user view. All exited 0. The query returned the completed fixture on its second page. |
| Browser list/board | Sidebar displays API-created user views. Selecting a view honors its persisted Board mode. List/Board switching works within the page. |
| Browser mutation and server readback | Workflow move succeeds server-side; filter edit persists; incomplete-date and rename-only mutations reproduce the defects below. |
| Isolated frontend logic | Executed the real TypeScript predicate adapter through TypeScript transpilation in Node, under Los Angeles and Tokyo TZ; exercised actual TanStack QueryClient invalidation. Findings below. |

These results do not constitute full F7-A–D acceptance. Full browser labels any/all, repair flows, accessibility, large-result continuation, and representative existing-data migration/backfill remain pending. The API suite covers engine behaviors independently of that browser work.

## Findings

### R1 — P2: Saved boards do not refresh after task moves

**Location:** `apps/web/src/components/TaskBoard.tsx:333–339`, `:596–599`, `:632–655`.

Saved-board data uses `["views", viewId, "tasks", "board"]`, while successful moves and revision-conflict recovery invalidate only `["tasks", "board"]` and `["tasks"]`. The accumulator reset does not affect `savedViewBoardQuery.data`.

**Repro:** Open a saved board containing a Ready task; use Move to → In progress. The UI retains the card in Ready. API readback showed `workflow_state=in_progress`, `board_revision=1`. Reload and reopen the view: the card appears in In progress. The real QueryClient also reported `isInvalidated=false` after executing the two existing invalidations against the saved key.

**Fix direction:** Include saved task queries in workflow/task mutation and conflict invalidation, including edits/completion from other task surfaces. Verify two successive moves without reload; verify a predicate that stops matching removes the card.

### R2 — P2: Saved-board column totals and WIP remain zero

**Location:** `apps/web/src/components/TaskBoard.tsx:510–545`.

Cards are grouped from the saved-view response, but totals/WIP use `openServerTotals` from the disabled ordinary-column queries. Saved views are not included in the smart-filter count branch.

**Repro:** After refreshing R1, the In progress column visibly contains the fixture, but its header count and WIP both show **0**. Roots only is off. Screenshot: `f7-review/board-zero-count.png` in the snapshot directory.

**Fix direction:** Derive saved-view counts from the appropriate saved-view data, with truthful partial-page semantics once continuation is implemented. Cover roots-only behavior separately.

### R3 — P2: Incomplete fixed-date filters silently become unbounded

**Location:** `apps/web/src/savedViewPredicate.ts:91–97`; save in `components/SavedViewFilterModal.tsx`.

The adapter emits a fixed due restriction only if both fields parse. Missing bounds omit the whole dimension; Save does not reject the incomplete input.

**Repro:** Edit a saved view, choose Fixed date range, enter From `2026-10-10`, leave To blank, and Update view. Browser reports **View updated**. Server readback contains only `{"v":1,"dimensions":{"completion":"open"}}`; the requested date constraint is absent.

**Fix direction:** Reject incomplete/invalid bounds in the editor and preserve the draft for correction. Do not turn a selected restriction into an unrestricted query.

### R4 — P2: Editing a fixed range changes its absolute bounds

**Location:** `apps/web/src/savedViewPredicate.ts:50–63`, `:160–166`.

Reading truncates UTC ISO strings to dates, while writing interprets dates at browser-local midnight. This loses time-of-day and changes the absolute interval when the editor's timezone differs. Fixed ranges are contractually absolute and must remain fixed.

**Executed repro:** Round-trip the real adapter with fixed bounds `2026-10-10T07:00:00Z` to `2026-10-11T07:00:00Z`, completion any. In Los Angeles the instants survive. In Tokyo the result becomes `2026-10-09T15:00:00.000Z` to `2026-10-10T15:00:00.000Z`, a 16-hour shift. This was a Node TZ reproduction, not a browser timezone emulation. API-created bounds with explicit hours also cannot be preserved by date-only truncation.

**Fix direction:** Preserve original absolute bounds when dates are untouched and define date-only editing in the configured user timezone. Ensure a rename-only edit cannot rewrite due bounds.

### R5 — P2: Completed-only saved lists initially hide their matches

**Location:** `apps/web/src/components/TaskList.tsx:371–375`, `:393–395`.

The saved query returns matching completed tasks, then the ordinary global Show completed preference removes them again.

**Repro:** Create a completed task and a view with `completion: done`; API query total is **1**. With Show completed off, opening that view displays **No tasks here yet**. Checking Show completed reveals the task. A saved `any` predicate is also narrowed by this independent toggle.

**Fix direction:** Let the saved predicate determine completion membership so list, board, API, and CLI agree. Do not require another preference to make a completed-only view useful.

### R6 — P2: Renaming a view with omitted completion changes its results

**Location:** `apps/web/src/savedViewPredicate.ts:30–39`, `:76–77`, `:134–136`.

Omitted completion means no constraint in the API engine, but the edit adapter defaults it to open and always writes that restriction back.

**Browser repro with server readback:** Create a view with `dimensions: {}` and one open plus one completed fixture. The API returns both. Open Edit filters, change only the name, and Update view. Persisted dimensions become `{"completion":"open"}` and total drops from **2 to 1**.

**Fix direction:** Distinguish defaults for a new view from omitted dimensions in an existing view. Preserve omission or normalize it to equivalent `any`, without changing membership.

## Acknowledged completion gaps

- **Pagination:** list requests only 200 items; board requests only 500, with no saved-view continuation. This is unfinished F7-D scope, not a pass or an accepted non-goal.
- **Presentation:** toggle writes local storage rather than PATCHing saved presentation. Also finish the specified sort behavior: task queries ignore `presentation_json.sort`, and the modal writes a new `{mode}` object that drops any saved sort metadata. The sort contract needs supported values and matching query behavior.
- **Sidebar reorder:** still absent from the UI despite being in committed F7 scope.

The due-only system-engine default was accepted as documented. Existing web Today/Upcoming calendar enrichment was not filed as a new regression in this review. Copy polish: “Rolling (server timezone)” should describe the user's configured timezone.

## Resolution (Dex retest passed)

Implementation landed **2026-10-10** (Andi+Jules). Dex verified all six original repros closed on the same date. F7 stays **Open / in-progress** for the known completion gaps and remaining acceptance; human sign-off unchanged.

| ID | Fix direction landed |
|----|----------------------|
| **R1** | Task/board mutation invalidation includes **`views`** task-query prefix so saved boards refresh after moves and related edits. |
| **R2** | Saved-board column totals and WIP derive from **grouped saved-view data**, not disabled ordinary column queries. |
| **R3** | Filter editor **rejects incomplete fixed** date bounds instead of silently omitting the due dimension. |
| **R4** | Fixed due ranges **preserve absolute ISO** on untouched dates; rename-only edits do not rewrite bounds via date-only local truncation. |
| **R5** | Saved-view lists **ignore global Show completed**; membership follows the saved predicate (aligned with API/CLI). |
| **R6** | **Omitted completion** on an existing view is preserved on rename/edit; adapter does not default-write `open` over omission. |

Acknowledged completion gaps (pagination, presentation PATCH + sort contract, sidebar reorder) remain open scope — not closed by this fix batch.

### Focused retest evidence

Frozen snapshot: sibling `f7-retest` directory alongside the original `f7-review`; 387 hashed files, HEAD `ed442de` plus local fixes. Final source comparison found no drift. Disposable project `dex-f7-retest`, API image `dex-f7-retest-api:local`, fresh tmpfs database through migration 027, localhost:18080 only. This verified a rebuilt isolated copy, not the household live deployment.

- **R1:** Browser Ready → In progress → Ready without reload; card and counts updated after each response. API confirmed Ready at board revision 2. A third move to In progress also succeeded.
- **R2:** After full browser reload and reopening the saved board, In progress contained one card, column count was 1, WIP was 1, other open counts were 0; Roots only off. Screenshot `f7-retest/board-counts-fixed.png`.
- **R3:** New draft named `Incomplete range`, Fixed selected, From `2026-10-10`, To empty. Save displayed `Fixed due range requires both From and To dates.` Name and From remained visible; modal stayed open. API confirmed no view was created. Screenshot `f7-retest/date-validation.png`. Date input was verified using the accessible setValue control after the browser automation fill operation did not retain the date reliably.
- **R4:** Browser rename-only edit retained exact server bounds `2026-10-10T07:12:34Z` through `2026-10-11T07:56:12Z`, including minutes and seconds. LA/Tokyo untouched-bound cases passed in the real adapter suite; no claim of browser timezone emulation.
- **R5:** With the global Show completed unchecked in Inbox, opening a `completion: done` saved list immediately showed `Completed match`, without enabling the toggle.
- **R6:** Rename to `Omitted renamed` persisted with `dimensions: {}`; API still returned both open and completed fixtures, total 2, and browser showed both.
- **Adapter tests:** `node --experimental-strip-types --test tests/savedViewPredicate.test.ts` — **6/6 passed**.
- **Build:** `npm run build` passed; bundle `index-B-uaivGS.js`, size advisory only.
- **API:** same three F7 suites as the first pass — **64 passed** in 5.16 s.
- **CLI:** views + main smoke — **32 passed** in 0.31 s.

Scope remains focused: this does not certify every task writer, all accessibility interactions, large-result counts, or the unfinished pagination/presentation/reorder features.

## Next gate

Finish or explicitly disposition the three known completion gaps with Trish, then repeat broader checklist rows as needed. Keep human sign-off open. Both passes' disposable containers and tmpfs databases were removed; snapshots and screenshots remain for review.
