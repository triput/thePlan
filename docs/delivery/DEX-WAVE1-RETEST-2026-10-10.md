# Dex Wave 1 verification

**Latest Dex retest, 2026-10-10:** **W1-R1 verified closed** — 202-explanation run with the only stale task after row 200 correctly reports one stale task via **`GET /api/v1/schedule/runs/{run_id}/stale-summary`** and in browser Calendar. F6 **P1 R1** verified closed (**37** API integration tests incl. concurrent reparent). F4 Wave 1 **verified closed** — CLI overrides CRUD, day overlay, F4-D red/pins/legend/small-run and **volume** stale badge. Web **36** + CLI **36** tests green. Import volume retest (**IM-R1**) — [DEX-IMPORT-VOLUME-2026-10-10.md](./DEX-IMPORT-VOLUME-2026-10-10.md). Trish Done sign-off **2026-10-10** ([MANUAL-CHECKLIST § Sign-off](./MANUAL-CHECKLIST.md#sign-off)); features with PARTIAL residue **not Closed**.

<!--
==============================================================================
  File: docs/delivery/DEX-WAVE1-RETEST-2026-10-10.md
  Description: Independent F4 operator checks, F6 R1 regression verification, and F7 suite corroboration.
  Component: Docs/Delivery
  Version: 1.2
  Created: 2026-10-10
  Last Update: 2026-10-10 (Page — W1-R1 volume stale-summary verified closed)
==============================================================================
-->

## Result

F6 R1 verified closed by independent execution of the regression suite on isolated PostgreSQL, including the real two-session apply/reparent race. F4 override CLI CRUD and day overlay pass. F4-D **verified closed**: red overlap, pins/busy legend, small-run **Schedule stale** badge, and **W1-R1** volume stale badge (204+ explanations, stale only after offset 200) pass after **`stale-summary`** + calendar aggregate. Trish Done sign-off recorded **2026-10-10** (Setup–F7).

## Artifact and checks

Frozen source over `b0c49d8` plus local Wave 1 work at `C:\Users\trish\.codex\visualizations\2026\10\08\01a11d56-e98c-7c31-995d-8b17c9a41e5a\wave1-retest`. Source hashes in `source-manifest.json`; frontend bundle `index-H-_fauGT.js`. Disposable Docker project `dex-wave1`, API `dex-wave1-api:local`, tmpfs PostgreSQL, localhost:18080. The final drift check found concurrent changes only in App.tsx, quick-add.css, OutlineImportPanel.tsx, and TemplatesPanel.tsx; those later edits are not covered by this pass.

- Web `npm test`: **36 passed**. These are Node unit/helper regression tests, not a browser end-to-end suite. `npm run build` passed with the normal bundle-size advisory.
- API `test_f6_w2_preview_apply.py` + `test_f6_lock_writers.py`: **37 passed**. Includes reparent-to-manual stale rejection, project detach stale rejection, epic target_date revision bump, and `test_reparent_during_apply_waits_for_owner_lock`. The latter pauses Apply at its fingerprint boundary, confirms the concurrent real route cannot commit, then releases Apply and verifies the writer completes. This is automated integration evidence, not a separately authored concurrency driver in this pass.
- CLI `test_overrides_commands.py` + `test_main_commands.py`: **36 passed**.
- Actual CLI against the running API: create, list, get, edit to `bands: []`, delete, and empty-list readback all passed. Recreated an override for browser testing.

## F4 browser evidence

Synthetic map: green 08:00–18:00, yellow 10:00–16:00, red 11:00–14:00, settings and override timezone America/Los_Angeles. Red had sort_order -1 to exercise tier precedence independently of supplied sort order.

- Day view displays the Override badge and correct bands on the active date. Moving to the next date clears the badge and returns to the base map.
- Overlapping red renders with visible hatching. Pinned and external-busy blocks remain visible above the bands. Legend states visual-only/no replan, red precedence, one pinned block, and one external busy event.
- After a completed replan, changing only the override shows `Schedule stale` with `time map overrides changed`. The earlier live task block stays where it was, now within the expanded red interval; the override did not silently replan it.
- Pinned and external-busy rows were synthetic ORM fixtures; no provider credentials or provider synchronization was used. Map/task/override changes were HTTP or actual CLI operations.
- Screenshot: `day-overlay-stale-pass.png` in the artifact directory.

## W1-R1 [P2]: Stale indicator ignores explanations after the first 200

**Dex finding (2026-10-10):** **Verified closed** — volume retest on **`wave1-final`** artifact ([DEX-IMPORT-VOLUME-2026-10-10.md](./DEX-IMPORT-VOLUME-2026-10-10.md) § W1-R1).

**Location (historical):** `apps/web/src/components/CalendarView.tsx` — calendar called `fetchScheduleRunExplanations(..., { limit: 200 })` once and derived the warning only from that page.

**Reproduction (historical):** Add 201 unchanged manual tasks with IDs preceding the affected task, then run Update Schedule. The completed run has 204 explanations. Edit only the affected map override. API page 0 (limit 200) has zero stale rows; page 1 has the affected task with `time_map_overrides`. Reload and open Calendar: no Schedule stale badge, although that task's old block is still present and its explanation is stale.

**Expected:** Scan all pages or obtain a server-side stale aggregate before indicating no stale tasks. Any count must cover the whole run, or clearly state incompleteness. This affects ordinary owners with more than 200 evaluated tasks, not just saved-view pagination.

Evidence (original fail): `stale-volume-evidence.json` and `stale-page-two-missing.png`. Volume pass: `volume-retest.json`, `volume-stale-pass.png`.

### Resolution (product — **Verified closed**)

| Item | Status |
|------|--------|
| **API** | **`GET /api/v1/schedule/runs/{run_id}/stale-summary`** — owner-scoped full-run aggregate (`stale_task_count`, sorted union `categories`, `total_explanations`); same read-time stale compare as explanation rows; batches internally (not capped at list `limit` 200). Documented in [05-api-contract.md](../05-api-contract.md) § Schedule. |
| **Web** | **`CalendarView`** uses **`fetchScheduleRunStaleSummary`** for the **Schedule stale** banner instead of the first explanations page. |
| **Quality** | API **`test_schedule_stale_summary.py`** — stale on page two only, empty run, foreign run **404**. |
| **Dex** | **Verified closed 2026-10-10** — 202-explanation run; stale only on page 2; aggregate `stale_task_count: 1`; browser banner shows **Schedule stale** with `time map overrides changed`. |

## Limits and cleanup

No new household migration evidence was produced. Preserve Trish's migration disposition separately. F5 merge work and later template changes were not assessed in the original pass; **IM-R1** and Import merge happy paths verified separately ([DEX-IMPORT-VOLUME-2026-10-10.md](./DEX-IMPORT-VOLUME-2026-10-10.md)). Optional DST browser coverage and final human acceptance remain separate.

Disposable containers and database removed after the pass. Source snapshots/screenshots retained. Dex pass: no product code edits, commits, pushes, daily-driver migrations, or provider calls. Post-pass W1-R1 fix verified on volume retest **2026-10-10**.
