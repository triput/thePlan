# F7 manual checklist execution

**Filename:** DEX-F7-CHECKLIST-2026-10-10.md  
**Last modified:** 2026-10-10  
**File version:** 1.1  
**Result:** 23 checklist rows verified: 11 HTTP, 5 CLI, 7 browser. M1/M2 verified closed in the focused retest below. F7 overall and human sign-off remain open.

## M1/M2 focused retest, 2026-10-10

Current web source/tests copied into the isolated fixture and built as `index-C7CR3qX8.js`. `m1-m2-manifest.json` records hashes; comparison with the working tree found no source drift. The original manifest below describes the earlier test artifact. API fixture reused the prior isolated API image; no production service or household data was changed.

- **M1 PASS:** Saved `-title` API order and browser roots both read Alpha only, Alpha and beta. Added Child A and Child Z beneath Alpha only; browser rendered Alpha only, Child Z, Child A, Alpha and beta. Hierarchy and descending sibling order survived reload/reopening the view.
- **M2 PASS:** Four views at rank 100 displayed alphabetically with first Up and last Down disabled. Repair project Up swapped only the last two; Down reversed it. Server readback confirmed Browser mixed 0, Pagination view 1, Repair label 2, Repair project 3. Reset all ranks to 100, then Browser mixed Down swapped only the first two; reload preserved Pagination view, Browser mixed, Repair label, Repair project and correct edge controls.
- **Independent checks:** `node --experimental-strip-types --test tests/taskForest.test.ts tests/reorder.test.ts tests/savedViewPredicate.test.ts`: 14/14 passed. `npm run build` passed (bundle-size advisory only).
- Screenshot: `f7-manual/m1-m2-retest-pass.png`. Disposable containers/database removed after testing. Nothing committed or pushed.

The findings below preserve the original failure evidence; both are now verified closed. Existing-data migration, a committed W3 browser regression suite, and human final acceptance remain open.

## Tested artifact

Frozen 389-file snapshot at `C:\Users\trish\.codex\visualizations\2026\10\08\01a11d56-e98c-7c31-995d-8b17c9a41e5a\f7-manual`, with `source-manifest.json` hashes. HEAD at inspection was `b52416a` plus local completion-gap changes. Source comparison during the pass found no drift. This included the newer pagination, mode PATCH, sort, and reorder implementation; it was not just the earlier six-fix build.

Disposable Docker project `dex-f7-manual`, tmpfs PostgreSQL, API image `dex-f7-manual-api:local`, frontend `index-Ba5-zhPU.js` at localhost:18080. Synthetic account, labels, projects, and tasks. No household data or credentials modified. Containers and temporary database removed after completion; artifacts retained.

## HTTP/operator evidence — all 11 rows pass

The retained `http_checks.py` uses real HTTP against the isolated running API. It provisions synthetic fixture data, asserts responses, and uses a separate disposable owner for isolation. Direct ORM insertion was used only for the foreign-owner fixture and 505-task volume fixture, not to replace the HTTP operations under test.

- Migration reports `027_saved_filter_presentation (head)`; all three system slugs have v1 predicates. This is a fresh-database upgrade, not a representative existing-household migration.
- List returns system views first, user views by rank, with ID/slug/presentation metadata.
- Mixed project + priority + completion + labels query: any returns two fixtures; all returns one. Create/get/rename/predicate/order round-trip passed. Deleting the view returned 204; tasks remained readable.
- System PATCH/DELETE return 403 `SYSTEM_VIEW_READ_ONLY`; another owner's get/query/patch/delete all return 404.
- Inbox ID and slug pages agree, including totals, limit/offset, null project, and open completion.
- Explicit `sort=-due_at` is descending; bad sort returns 422 `INVALID_SORT`. Board ordering gives identical IDs under conflicting valid sort requests.
- Partial presentation PATCH retains sort and an extra metadata key; invalid mode returns 422 `INVALID_PRESENTATION`.
- Invalid dimension, legacy predicate, and Inbox+project contradiction reject with 422 `INVALID_PREDICATE`.
- Deleted label and deleted empty project each yield empty results plus `invalid_references`.
- Settings timezone changed through HTTP between Los Angeles and Tokyo. Today and Upcoming result identities matched independently computed half-open boundaries around the running server's current date. Twelve due-date boundary fixtures cover instants immediately before/after the two zones' window edges. Each queried window returned four matching fixtures; identities, not just counts, were asserted. Settings restored to LA afterward.
- Label any/all behavior verified independently of the browser.

Additional volume check: 505 tasks returned as pages of 200/200/105, total always 505, 505 distinct IDs.

## Actual CLI evidence — all 5 rows pass

Frozen CLI ran via `python -m theplan` inside the isolated container against its live HTTP API, with a dedicated `/tmp/manual-session` cookie file.

- List metadata and get round-trip verified.
- Create via stdin, patch name/rank via stdin, then delete succeeded; task total unchanged.
- Query by ID and Inbox slug, limit 2/offset 1, with and without board ordering: items and all pagination fields exactly matched HTTP results.
- System PATCH and DELETE both returned exit **2**, top-level `code: SYSTEM_VIEW_READ_ONLY`.

The first check script incorrectly expected a nested `error` key in the failure envelope. Correcting that test expectation and rerunning both protected commands confirmed the existing top-level CLI contract; this was not a product failure.

## Browser evidence — 5 rows pass, reorder fails

Chrome against the frozen local build:

- Sidebar selects API-created views and renders matching fixtures.
- Created `Browser mixed` using project, P1, and alpha/beta labels. Any displayed both fixtures; editing to all displayed only `Alpha and beta`.
- Deleted-label view initially showed an empty list and repair banner. Explicitly removed missing refs, selected alpha, and saved: exactly two alpha-tagged fixtures appeared. Deleted-project view also showed empty results and repair affordance.
- Saved List/Board toggle persisted `mode: board` in server readback; reload and reopening the view selected Board.
- List continuation reached task 399 then task 504, with **505 distinct selectable task rows**, and no Load more button afterward. Board started with 500 cards and one Ready Load more button (501 buttons in that region); continuation produced **505 cards** and removed the button.

The UI tests are manual browser automation evidence, not a committed browser regression suite. The original six P2s remain verified closed by the preceding focused retest.

## M1 — P2: Saved sort is overridden by the rendered list

**Locations:** `apps/web/src/components/TaskList.tsx:461`; additional forest ordering in the render paths. Retain hierarchy where needed, but do not replace the saved ordering of peer tasks.

**Repro:** Edit `Browser mixed` to labels any and Title (Z–A), then save. Server stores `presentation_json.sort: -title`; its task endpoint returns `Alpha only`, then `Alpha and beta`. The browser renders `Alpha and beta`, then `Alpha only`, including after the response settles. Both are root tasks in the same project. `orderTasksForest(items)` restores the ordinary manual ordering after the server has already sorted the saved result.

**Expected:** Visible peer order agrees with the chosen saved sort and API/CLI. Mode persistence itself passes; sort sign-off stays open.

Screenshot: `f7-manual/sort-mismatch.png` in the artifact directory.

## M2 — P2: Sidebar reorder uses a different tie-breaker than display

**Locations:** `apps/web/src/components/Sidebar.tsx:119–124`, `:167–171`; `apps/web/src/reorder.ts` comparison and `buildReorderSwap`/`canReorderUp`.

All new views default to rank 100. Sidebar sorts ties by name, while the reused reorder helper sorts them by ID.

**Repro:** Four default-rank views display Browser mixed, Pagination view, Repair label, Repair project. Browser mixed (first) has an enabled Up arrow, while Pagination view (second) has a disabled Up arrow. Moving Repair project up also moved Pagination view ahead of Browser mixed, because renumbering used ID order rather than the displayed order. Server readback confirmed ranks 0/1/2/3 for Pagination view, Browser mixed, Repair project, Repair label. Restoring equal default ranks and reloading reproduced the incorrect enabled/disabled arrows.

**Expected:** Arrow availability and the neighbor being swapped use exactly the rendered ordering, including equal ranks. Persistence alone is insufficient to sign this row off.

Screenshot: `f7-manual/reorder-tie-mismatch.png`.

## Resolution (pending Dex retest)

| ID | Fix landed |
|----|------------|
| **M1** | `orderTasksForest(..., { peerOrder: "stable" })` on saved TaskList — hierarchy kept; peer order matches API/presentation sort |
| **M2** | Sidebar reorder/`canReorder*` use `compareBySortOrderThenName` (same as display); projects still use id tie-break |

## Checks left open with notes

- **Saved sort in browser:** M1 fixed in code; requires Dex retest.
- **Sidebar reorder:** M2 fixed in code; requires Dex retest.
- **Representative existing-data migration/backfill:** fresh migration and v1 seeds passed; did not migrate a copy of household data. No production migration performed.
- **Automated W3 regression suite:** still not implemented. This manual pass does not substitute for a checked-in suite.
- **Human final acceptance:** reserved for Trish; individual verified rows are checked without closing the wave.
- Optional `/tasks?view=` alias remains an unimplemented non-goal; supported `/views/.../tasks` paths passed.

## Corroborating checks

`npm run build` passed (bundle-size advisory only). API suites `test_f7_w1_views.py`, `test_f7_w1_predicate.py`, `test_f7_w1_quality.py`, and `test_f7_presentation_sort.py`: **71 passed** in 7.25 s. Browser sort failure demonstrates why passing API sort tests alone does not finish web acceptance.
