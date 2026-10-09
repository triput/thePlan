# Dex F4 local verification

**Filename:** DEX-F4-MANUAL-2026-10-09.md
**Last modified:** 2026-10-09 (Trish/Dex — residual P2s closed)
**File version:** 1.5

## Tested build and result

Frozen copy of the uncommitted F4 W1/W2/W3 working tree over `cc87349`, captured approximately 11:55 Pacific on 2026-10-09. This is **not** a committed F4 tip. SHA-256 manifest covers 422 copied files; comparison before documentation edits found no source drift.

Disposable `dex-f4-smoke` Compose project, tmpfs PostgreSQL, synthetic QA users, localhost port 18080. Migration head **024_time_map_overrides** confirmed. Household data and external integrations were not used.

**52 focused API tests passed**, covering `test_f4_w1_scheduler_overrides.py`, `test_time_map_override_api.py`, `test_f4_w2_scheduler.py`, `test_input_fingerprint.py`, and `test_f3_w2_acceptance.py`. Frontend production build passed. These are automated evidence, distinct from the browser checks below.

**Three P2 findings were open in the initial Dex browser pass.** **Andi (2026-10-09, working tree at `F:\Code Repo\ThePlan`, not pushed)** landed fixes for all three; **Dex recheck: empty-band handling and header alignment Pass; original UTC overlay Pass.** Two **residual** rendering P2s (mixed override/settings timezone; out-of-view band clipping) are **Verified closed (Trish/Dex browser retest, ~12:17 Pacific)** on the updated frozen working tree. F4 remains **Open / in-progress** (not Closed). No push. CLI, day overlay, and remaining F4-D work retain their documented deferred status.

## Code fixes (2026-10-09 — Andi; Dex recheck complete)

| P2 | Dex symptom | Fix (working tree) | Retest |
|----|-------------|-------------------|--------|
| 1 — empty strict edit | Edit injected default 09:00–12:00 band; last band not removable | No default band injection on edit; last band removable | PASS: browser edit/save and empty creation; HTTP readback |
| 2 — override badge | Override badge increased header height; slot grids shifted | Fixed week header height so grid origin stays aligned | PASS: seven headers and gutter 64 px; common grid origin |
| 3 — band timezone | Override bands painted at raw UTC wall time vs blocks in display TZ | Wall-clock conversion + settings.timezone band hours + visible clipping | PASS (Trish/Dex): original UTC case; residual mixed-zone + clipping — **Verified closed** |

**Archived lifecycle:** prior Dex reproduction **Verified closed** — unchanged; no retest required for that row unless regressions appear during F4 W3 retest.

## Findings

### Original P2: empty strict overrides cannot survive a web edit — **Verified closed**

**Status (2026-10-09):** Andi removed default-band injection on edit and enabled removing the last band. Dex browser recheck passed for this fix.

1. Create an override through the API with `strict_mode: true`, `bands: []`.
2. Settings -> Time Maps -> Overrides correctly lists **No bands / Strict**.
3. Click Edit. The form inserts a green **09:00–12:00 Monday–Friday** band.
4. Click Update override without changing any fields. The list becomes **1 green / Strict**; HTTP readback confirms the inserted band was persisted.

This changes an all-day closure into available time. The same form cannot create an empty override: the last Remove button is disabled, and the removal handler refuses to remove it. Preserve an empty array when loading an existing override and permit removal of the final band.

Source: `apps/web/src/components/settings/TimeMapOverridesSection.tsx`, `startEdit` lines 131–135, `removeBand` line 227, disabled button line 345. Evidence: `empty-override-edit.png` and `supplement-evidence.json` in the scratch folder below.

### Original P2: Override badge shifts calendar time grids — **Verified closed**

**Status (2026-10-09):** Andi fixed week header height so the override badge does not shift slot-grid origin. Dex browser recheck passed for this fix.

With a Monday–Sunday week and an override on Friday–Sunday, enabling Map A's overlay adds a third line to those day headers. Measured header heights: **45.45 px** on ordinary days versus **63.44 px** on override days. Slot-grid origins: **y=201.01** versus **y=219**. Bands and scheduled blocks consequently shift relative to neighboring columns and the common time gutter. Selecting Neutral removes the extra line.

Use a consistent header/gutter height or position the badge without changing the slot-grid origin. Source: `apps/web/src/components/CalendarDayColumn.tsx` lines 336–342 and `.cal-col-header` / `.cal-col-override-badge` in `apps/web/src/styles/calendar.css`. Evidence: `week-overlay.png` plus browser DOM geometry measurements recorded in this report.

### Original P2: override overlay and blocks use different timezones — **Dex Pass (original case); residuals verified closed**

**Status (2026-10-09):** Andi aligned override band rendering with block wall-clock model. Dex recheck Pass for UTC settings + UTC override in Pacific browser. Residual mixed-zone + clipping — **Verified closed (Trish/Dex)** on local working tree at `F:\Code Repo\ThePlan`.

Set scheduling timezone to **UTC**, use a Pacific-time browser, and replan a task inheriting a strict map with an override **15:00–17:00 UTC**. The API schedules the task at **2026-10-10T15:00:00+00:00**. The calendar block editor correctly displays **08:00–08:30** local, but the green override band paints at **15:00–17:00 local**. The task appears outside its governing band. After changing the override to 16:00–18:00 and replanning, API evidence records 16:00 UTC while the browser block is at 09:00 local.

The new override resolver uses scheduling settings, but `TimeMapBandOverlay` combines its raw band times with a browser-local Date. Normalize the effective band to the calendar's display timezone, including date rollover, or consistently render the entire calendar in the scheduling timezone. The underlying raw-clock overlay renderer predates F4; this finding demonstrates its effect on the newly delivered override overlay. Source: `apps/web/src/components/CalendarView.tsx` lines 268–272; `apps/web/src/components/CalendarDayColumn.tsx` lines 72–75; `apps/web/src/timeMapOverrides.ts`.

## Direct API and browser evidence

| Check | Result / scope |
|---|---|
| Override create, patch, delete | HTTP passed; browser create, update, and delete passed; empty edit/create Pass (Dex recheck). |
| Base map preservation | HTTP readback unchanged after override creation. |
| Overlap and adjacency | Same-map overlap returned 409 with conflict dates; adjacent range and same dates on another map succeeded. |
| UI overlap validation | Readable message names the conflicting date range. |
| UI invalid date order | `End date must be on or after start date`. |
| UI midnight-crossing band | `Band 1 crosses midnight...` with split-band guidance. |
| Invalid timezone | Direct HTTP returned 422 `TIME_MAP_OVERRIDE_TIMEZONE`. Typing an unrecognized name into the picker retained UTC on submission; no invalid timezone persisted. |
| No automatic replan | Run count stayed unchanged after override writes; explicit replan required. |
| Expired overrides | Stored/listed through API; outside-range base behavior also covered by focused pytest. |
| All-day unavailable | API accepts empty strict bands; focused scheduler regression passes. Web edit/save and creation with the final band removed now pass in browser and HTTP readback. |
| Inheritance / cross-map independence | Task inherits project Map A, uses override and records applicable_override. Explicit Map B task is not stale when only A changes and has no applicable_override. Additional inheritance/unbound cases passed in pytest. |
| Snapshot | Live explanation reports v3, algorithm f3-w2, and applicable_override provenance. |
| Override staleness | HTTP create/patch mark time_map_overrides; focused suite also covers delete. Browser tooltip says `Inputs changed since last run: time map overrides changed`. |
| Replan clears stale | Browser Update Schedule completed; settled detail panel removed Stale and displayed new run `2ca9249d-96c1-43ee-a537-ab21f7a5e3c9`; HTTP readback agrees. |
| DST | Focused parametrized regression suite passed. No independent browser DST/time-travel test; optional human spot-check remains open. |
| Week overlay | Range badges and replacement/base selection observed; badge shift verified closed; mixed-zone + clipping P2s **Verified closed (Trish/Dex)**. Day-mode overlay not in scope. |
| Archived lifecycle fix | **Verified closed** (unchanged): archived-project/manual and archived-epic/bundle return excluded_lifecycle_archived in HTTP and show project/epic archived in browser. Focused regression also includes full pins. |

Native date fields needed accessible `setValue`; Playwright fill displayed dates without committing the React form state. The test driver initially used unsupported `include_archived` instead of `archived=true` on the project list; it was corrected before lifecycle assertions. Neither harness issue is classified as a product defect.

## Focused recheck, approximately 12:10 Pacific

Fresh frozen working-tree snapshot: `f4-recheck`, 423 files with SHA-256 manifest, still over `cc87349`. Web production build passed. Direct HTTP smoke was rerun to prepare and verify fixtures. The 52-test count above belongs to the initial pass; this frontend-only recheck did not rerun that suite.

- **Empty edit PASS:** saved No bands / Strict row opens with zero bands and remains empty after unchanged save.
- **Empty create PASS:** new form seeds one green band; Remove deletes the final band; browser creates a strict zero-band override on 2026-10-14. HTTP confirms both existing and newly created rows have `bands: []` and `strict_mode: true`.
- **Header alignment PASS:** all seven headers and gutter measure 64 px, and every column's slots start at y=219.5625, including a mix of override and base days.
- **Original timezone repro PASS:** UTC settings plus UTC override 15:00–17:00 paints 08:00–10:00 in Pacific browser and agrees with the task block.

### Residual P2: use scheduling timezone for override band hours — **Verified closed (Trish/Dex)**

**Dex symptom (2026-10-09 recheck):** Override timezone `America/New_York` with UTC scheduling settings and 15:00–17:00 band hours painted **12:00–14:00 Pacific** instead of aligning with the task at **08:00 Pacific**. Stored override timezone must select date applicability only; band hours use **settings.timezone** (backend contract).

**Andi fix (working tree, not pushed):** Overlay band instants match settings.timezone for wall-clock hours; override IANA TZ used for date match only.

### Residual P2: clip bands to visible hour bounds — **Verified closed (Trish/Dex)**

**Dex symptom (2026-10-09 recheck):** Base band **01:00–03:00 Pacific** (outside 06:00–22:00 view) incorrectly shifted to **06:00–08:00** instead of clipping or hiding.

**Andi fix (working tree, not pushed):** Intersect band interval with visible day bounds before top/height; no shift-into-view.

Prior evidence: `C:\Users\trish\.codex\visualizations\2026\10\08\01a11d56-e98c-7c31-995d-8b17c9a41e5a\f4-recheck` (`mixed-zone-residual.png`, etc.). F4 remains Open. No push.

## Final residual recheck, approximately 12:17 Pacific — **Trish/Dex sign-off**

**Both residual reproductions PASS (Verified closed).** Fresh frozen working tree over `cc87349` at `F:\Code Repo\ThePlan`, 423-file SHA-256 manifest in `f4-residual-recheck`. Production web build passed. Direct HTTP smoke/setup passed; the original 52-test suite was not rerun for this focused frontend pass.

- **Mixed-zone PASS:** UTC scheduling settings, stored override zone America/New_York, 15:00–17:00 band. API places the task at 2026-10-10T15:00:00+00:00. In the Pacific browser the task and band now align at 08:00; the band ends at 10:00. Limited-hour DOM style is `top: 12.5%; height: 12.5%`.
- **06:00–22:00 clipping PASS:** base 08:00–10:00 UTC is 01:00–03:00 Pacific. Base-day columns now contain zero band overlays in limited-hour view. Switching to 24-hour mode restores those bands at `top: 4.16667%; height: 8.33333%`, correctly 01:00–03:00. Switching back removes them.
- Grid origins remain aligned at y=219.5625 across the mixed week. Empty-edit behavior retains the preceding verified pass; it was not re-exercised in this narrow recheck.

Evidence: `C:\Users\trish\.codex\visualizations\2026\10\08\01a11d56-e98c-7c31-995d-8b17c9a41e5a\f4-residual-recheck`: `source-manifest.json`, `api-evidence.json`, `mixed-zone-api.json`, `mixed-zone-clipping-pass.png`.

This closes the reported rendering residuals, not all possible timezone/date-rollover or DST combinations. F4 remains Open for documented remaining scope and human sign-off. No product edits, commits, or pushes. Disposable stack removed after verification.

## Initial-pass reproduction artifacts

Scratch folder: `C:\Users\trish\.codex\visualizations\2026\10\08\01a11d56-e98c-7c31-995d-8b17c9a41e5a\f4-smoke`.

- `source-manifest.json`: frozen source hashes.
- `api_smoke.py`, `api-evidence.json`: direct HTTP smoke and recorded results.
- `supplement.py`, `supplement-evidence.json`: lifecycle closure, empty-band mutation, stale fixture.
- `browser-replan-evidence.json`: fresh explanation after browser replan.
- `empty-override-edit.png`, `week-overlay.png`, `override-stale.png`, `archived-lifecycle-pass.png`: browser evidence.

The source snapshot and evidence remain available; the disposable Compose stack is removed after testing. The node_modules junction points to existing repository dependencies and must not be recursively traversed for cleanup. No product source edits, commits, or pushes were made by Dex during this pass. **Andi** fixes (initial three P2s + two residual P2s above) live in the local working tree only; **Verified closed (Trish/Dex) on the stated reproductions**; not pushed.
