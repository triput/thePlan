# Dex F6 review and manual verification

**Latest Dex gate, 2026-10-10:** F6 **P1 R1** verified closed (**37** API integration tests incl. concurrent reparent). F4 Wave 1 **verified closed** incl. **W1-R1** volume stale. Web **36** + CLI **36** green. [Evidence](DEX-WAVE1-RETEST-2026-10-10.md). Trish Done sign-off **2026-10-10**; F6 **not Closed** (F6-B–D).

**Filename:** DEX-F6-MANUAL-2026-10-09.md
**Last modified:** 2026-10-10 (Page — P1 R1 + W1-R1 Dex verified closed)
**File version:** 1.3

## Tesla fix wave — 2026-10-09 (working tree, not pushed)

**P1 residual R1 — Verified closed (Wave 1 retest 2026-10-10)** — **37** API integration tests incl. concurrent reparent ([DEX-WAVE1-RETEST](./DEX-WAVE1-RETEST-2026-10-10.md)). Renee/Tesla: **4** focused pytest green on lock-writer selection. **Three initial P2s + archive P1: Verified closed** (Dex retest).

- **`PROJECT_SCHEDULING_FIELDS`** now includes **`epic_id`** (reparent and detach, including `null`).
- **`EPIC_SCHEDULING_FIELDS`** now includes **`target_date`** (UPS epic alignment).
- Shared predicate aligned in `scheduling_revision.py`; project/epic patch routes take the common owner lock + revision path before mutating those fields.

**Disposition:** Prior Dex retest closed **three P2s** and the original archive interleaving P1. **P1 R1 verified closed** on Wave 1 retest **2026-10-10**. Trish Done **2026-10-10**; **not Closed** (F6-B–D). No commits or pushes from Tesla in this wave.

## Dex fix retest

**Three P2s verified closed. Original archive race closed.** At retest time, project epic reassignment still bypassed lock/revision (P1 residual R1 — **superseded by Tesla fix wave above**). Frozen working tree over `094663f`, 364 files captured around 16:27 Pacific; final hash comparison found no source drift. Rebuilt disposable image/web, migration 025. **42 tests passed** across `test_f6_w1_preview.py`, `test_f6_w2_preview_apply.py`, and `test_f6_lock_writers.py`. This is the combined selection actually run; it is not a claim that the two preview files alone contain 42 tests. Web build passed with the existing bundle-size advisory.

- Original archive interleaving: a real second-session archive remained blocked while Apply held the owner lock, then completed after Apply committed. Reversing the order (archive first) yielded PREVIEW_STALE with lifecycle category.
- Available-now: first block was about **135 seconds** in the future; immediate Apply succeeded, receipt `cf47df04-1cd6-40e3-8931-2213b1a03f49`. Planning boundary is fixed during calculation, not shifted at apply. Operator reviews longer than that lead can still legitimately require a fresh preview; the 15-minute TTL is not a guarantee that no proposed start will pass sooner.
- Overlapping preloaded sessions: both returned identical receipt `66162ba9-5a3f-4155-b06b-5bd0958b1938` after the first committed.
- Browser diff: **Moved 1** agrees with the moved task row (16:50 → 16:55 Pacific). **Removed 1** correctly identifies the now-manual task from the residual fixture.

### Residual R1 [P1] Project epic reassignment still bypasses serialization — **Fixed (code), awaiting Dex retest (Tesla)**

**Dex retest symptom (historical):** `PROJECT_EPIC_SCHEDULING_FIELDS` included preferred map, style, and archive but omitted `epic_id`. `update_project` did not lock or bump for an epic-only patch, changing inherited style, map, lifecycle, and priority inputs. Epic **`target_date`** (UPS) was also absent from the epic scheduling field set (source observation at retest time).

Repro: create a project and task with inherited (`null`) schedule style under standalone defaults. Calculate a ready preview. Immediately after Apply reads its fingerprint, session B calls the real project-update route to attach the project to a **Manual** epic. B committed without blocking and revision stayed **14 → 14**. Apply still succeeded and created a block for that now-manual task.

Receipt `1189ef24-24ca-4343-8985-30b5c0d8caeb`; preview `1826f9da-6891-4b87-94bb-ffb8747bbc28`; readback one block for the affected task. The first test-driver attempt used the unsupported literal `inherit` and received 422 before project creation; the corrected reproduction uses the API's `null` inheritance representation.

**Fix (Tesla, working tree):** Project **`epic_id`** reparent/detach and epic **`target_date`** on lock+bump path; **4** focused pytest green. **Awaiting Dex retest** — repeat `reparent_repro.py` interleaving on disposable stack.

**Known project-delete ORM behavior:** retained as disclosed, outside this fix's scope. No cascade redesign or claim of cascade deletion.

Artifacts: `f6-retest/source-manifest.json`, `retest.py`, `reparent_repro.py`, and `moved-counts-fixed.png` beneath the existing visualization scratch root. Test stack removed after the pass. No product edits, commits, pushes, or daily-driver migration by Dex. F6 remains Open.

## Outcome (initial Dex pass)

**One P1 and three P2s from the initial pass; F6 remains Open.** Reviewed frozen uncommitted F6 over `094663f`, captured about 15:27 Pacific. 362 source/config/fixture hashes; final comparison found no source drift. No product code edits, commits, or pushes by Dex. **Current disposition:** three P2s **Verified closed** (Dex retest); archive P1 closed; P1 R1 **Fixed (code), awaiting Dex retest** (Tesla).

## Jules fix wave — 2026-10-09 (working tree, not pushed)

**Fixes retested: three P2s closed; archive P1 closed; P1 residual R1 fixed in code (Tesla), awaiting Dex retest.** No commits or pushes from Jules/Tesla in these waves.

| # | Severity | Dex symptom | Fix (working tree) | Retest |
|---|----------|-------------|-------------------|--------|
| 1 | P1 | Concurrent project archive after apply validation → stale proposal commits | Scheduling-relevant writers (incl. project archive) take common owner lock + revision path before mutating scheduling state | **PASS** — archive **Verified closed** (Dex); reparent **`epic_id`** / epic **`target_date`** **Fixed (code), awaiting Dex retest** (Tesla) |
| 2 | P2 | Available-now preview → immediate **PREVIEW_PAST_BLOCKS** on apply | Preview calculate uses **planning lead**: wall UTC **ceiled to the next whole minute**, then **+ 90s** (`preview_collection_time` / `PREVIEW_PLANNING_LEAD_SECONDS`); apply still rejects past blocks, no slide | **Verified closed** (Dex) |
| 3 | P2 | **MOVED** in list but summary **Moved 0** | **diff_counts** / `summarize_diff` pairs moved blocks consistently with display | **Verified closed** (Dex) |
| 4 | P2 | Overlapping duplicate apply → **PREVIEW_STALE** instead of receipt | Refresh locked preview row before status/receipt check on apply retry | **Verified closed** (Dex) |

Initial findings and evidence below are retained; this table supersedes their open disposition. Dex must rerun disposable stack for Tesla R1 fix before closing P1.

Disposable `dex-f6-smoke` stack, localhost:18080, synthetic QA account, tmpfs database. Rebuilt image migrated to **025_schedule_previews (head)**. Daily-driver and household data untouched. Web build passed (bundle-size advisory only).

**47 API tests passed**: F6 W1/W2 + Microsoft calendar (33), task soft delete (14). **37 CLI tests passed**: schedule-preview commands, API client status, main commands. An initial invocation named nonexistent `test_task_trash.py` and collected no tests; corrected selection used `test_task_soft_delete.py`.

## Findings

### 1. [P1] All scheduling writers must participate in apply serialization — archive **Verified closed**; reparent **`epic_id`** / epic **`target_date`** **Fixed (code), awaiting Dex retest**

The acknowledged writer-lock gap permits a stale proposal to commit. Deterministic two-session repro used the real `archive_project` route in session B immediately after session A read the live fingerprint while holding the owner lock. B committed successfully; A then applied its old proposal and created a block for the now-archived project's task.

Evidence: preview `73761d89-c0e7-44bf-9fa8-101935fd3f96`; successful receipt `09535a47-14b3-484d-8da1-ff0bd128c61e`; readback `archived=true`, task block count **1**. The test inserted a synchronization hook at the fingerprint boundary, not a production code edit. It demonstrates a real permitted transaction interleaving.

`projects.py:138–145` archives without taking the scheduling lock or revision bump. Other scheduling-relevant project/epic and map writes need the same audit. Acquire the common lock **before reading/mutating** scheduling state and hold through commit; simply bumping after a separately committed mutation does not satisfy the atomic validation contract. Apply validation boundary: `schedule_preview_apply.py:78` and `:142`.

**Fix (Jules, working tree):** Scheduling writers participate in apply serialization (project archive and related audit). **Verified closed (Dex retest)** — archive interleaving repro passes. Epic reparent residual: **Tesla fix wave** above.

### 2. [P2] A preview calculated during available time is already too old to apply — **Verified closed** (Dex retest)

With UTC, seven workdays, workday 00:00–24:00, and a standalone 60-minute task, preview returned ready with first block starting exactly at collection: `2026-10-09T22:28:20.244260+00:00`. An immediate apply returned **409 PREVIEW_PAST_BLOCKS**. This is the normal available-now case; repeatedly refreshing will produce another block already in the past by apply time.

Keep the past-block rejection, but provide an explicit future planning boundary/lead time at calculation so the operator can review and apply the immutable proposal. Do not silently slide it during apply. Sources: `scheduler/preview.py:46–55`, `schedule_preview_apply.py:98`.

**Fix (Jules, working tree):** Preview **planning lead** at calculate — UTC wall time **ceiled to the next whole minute**, then **+ 90 seconds** (`preview_planning.py`); snapshot `collected_at` drives placement; apply unchanged (**PREVIEW_PAST_BLOCKS** only). **Verified closed (Dex retest)** — available-now create → immediate apply.

### 3. [P2] Summary move counts contradict the before/after list — **Verified closed** (Dex retest)

Browser repro: existing task block at 16:28 Pacific; changed work window moved proposed block to 17:29. Block changes correctly says **MOVED**, but summary shows **Added 1 / Removed 1 / Moved 0**. `summarize_diff` counts all nonidentical after rows as added, so `len(after) - unchanged - added` is zero for unique blocks. Match moved pairs consistently with the display; keep unchanged interval identity normalization.

Source: `services/schedule_previews.py:74–77`. Screenshot `diff-counts.png` records the contradictory display. Browser apply of this future proposal succeeded.

**Fix (Jules, working tree):** Moved pairing in **diff_counts** / summarize path aligned with MOVED display. **Verified closed (Dex retest)** — browser summary agrees with MOVED row.

### 4. [P2] Overlapping duplicate apply can return PREVIEW_STALE instead of the original receipt — **Verified closed** (Dex retest)

Two sessions loaded the same ready preview, matching the route's pre-lock `_get_owned_preview` lookup. Session A applied and committed. Session B then acquired the preview row lock, but SQLAlchemy reused its already-loaded ready object; the query does not refresh populated attributes. B returned **409 PREVIEW_STALE / provenance**, rather than recognizing applied status and returning A's receipt.

Evidence: preview `280b2dd1-be99-4e28-969d-10b2f58f2b89`, first receipt `a10c336c-f7bd-49b9-83df-5d3e9b2a27ac`. Sequential fresh-request retry passes; this is specifically overlapping requests with a preloaded row. Refresh/populate the locked row before checking status and stored receipt. Source: `schedule_preview_apply.py:108–116`.

**Fix (Jules, working tree):** Locked-row refresh before apply status/receipt check. **Verified closed (Dex retest)** — overlapping sessions replay same receipt.

## Verified behavior and limits

- HTTP create returns 202/running, polling reaches ready. Preview leaves exact task response and live block list unchanged.
- Proposal before/after/outcomes, fingerprint, revision, and exact 900-second ready TTL present. Diff **shape** passes; moved semantics fail as above.
- Title-only edit keeps preview ready. Duration edit makes GET stale, retaining proposal; apply returns PREVIEW_STALE with duration category and no block changes.
- Future-dated apply creates blocks matching proposed task/start/end identities. Sequential duplicate apply returns the identical receipt.
- Actual CLI auth/create/get/apply/replay succeeds; stale apply exits **5** with structured error and fresh-preview guidance.
- Browser Calendar Preview changes opens, shows before/after task title, and applies a future proposal successfully. A later duration edit produces named stale feedback, disables Apply, and offers Generate fresh preview.
- Expiry, foreign-owner boundary, replan conflict/admission, failure rollback, pins, and direct/preview parity passed the existing automated selection. They were not all separately exercised through browser/manual sessions; checklist distinguishes those limits.
- Provider calls were not made against real accounts. Provider failure behavior is covered by the automated mocked selection.

## Artifacts and disposition

Scratch: `C:\Users\trish\.codex\visualizations\2026\10\08\01a11d56-e98c-7c31-995d-8b17c9a41e5a\f6-smoke`.

`source-manifest.json`, `initial-evidence.json` (available-now rejection), `manual_checks.py`, `manual-evidence.json` (HTTP and real CLI results), `concurrency_repros.py`, `retry_repro.py`, corresponding fixture IDs, and `diff-counts.png` retained. Concurrency scripts require fresh ready preview IDs to repeat after successful apply; they operate only on the disposable fixture.

Disposable stack removed after testing. Trish Done sign-off recorded **2026-10-10**; no migration on daily-driver. Dex: no commits or pushes. **Jules + Tesla fix waves:** local working tree only — **not pushed**. Dex retest closed three P2s, archive P1, and **P1 R1 (`epic_id` / `target_date`) Verified closed (Wave 1 retest 2026-10-10).** F6 **not Closed** (F6-B–D).
