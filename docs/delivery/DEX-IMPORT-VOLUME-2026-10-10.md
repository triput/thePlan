# Dex stale-volume retest and Import merge review

<!--
==============================================================================
  File: docs/delivery/DEX-IMPORT-VOLUME-2026-10-10.md
  Description: Volume stale-summary closure and merged Import browser evidence.
  Component: Docs/Delivery
  Version: 1.1
  Created: 2026-10-10
  Last Update: 2026-10-10
==============================================================================
-->

**Result:** W1-R1 verified closed. **IM-R1 verified closed** in the focused browser retest below; Import happy paths pass. Trish Done sign-off **2026-10-10**; PARTIAL operator rows unchanged.

## IM-R1 focused retest: PASS, 2026-10-10

Refreshed the complete web source snapshot for the coordinated Import changes; `import-retest-manifest.json` records this revision. Final hash comparison found no drift. Bundle `index-BHOhdHRj.js`. An initial partial two-file refresh lacked the matching OutlineImportPanel prop update and did not build; the complete source snapshot built successfully. This was fixture setup, not a product defect.

- Program title `KEEP THIS DRAFT` survived Templates > Custom outline > Templates.
- Propose produced 1 epic / 2 projects / 3 sections / 5 tasks. Edited proposed task title to `Video: Reviewed title`; both the preview and edit survived another tab round trip.
- Apply succeeded. After switching tabs again, receipt `e83c890c-321d-4a46-a29d-82883e3906a1` and key `aa9d0fb9-fe72-4257-865e-364fc15579ae` remained visible. The imported task also showed the edited title and video label.
- Changing the dropdown to Coursera course loaded that example and cleared the prior review. Returning via the dropdown to specialization loaded its original example, as intended.
- Web unit suite 36/36 passed; production build passed (bundle-size advisory only). Screenshot `import-preserved-pass.png` in the artifact directory. Disposable stack removed; no commits or pushes.

Original failure details below are retained as history. No residual IM-R1 defect found; other PARTIAL manual rows unchanged; Trish Done **2026-10-10**.

## Tested artifact

Frozen working tree over `b0c49d8`, scratch `C:\Users\trish\.codex\visualizations\2026\10\08\01a11d56-e98c-7c31-995d-8b17c9a41e5a\wave1-final`. Hashes in `source-manifest.json`; final comparison found no drift. Bundle `index-C0QPnQ79.js`; isolated API and tmpfs PostgreSQL in `dex-wave1`, browser localhost:18080. Household data untouched.

## W1-R1: verified closed

Created 201 unchanged synthetic tasks with IDs preceding one affected task, then performed a real HTTP replan: 202 explanations. Before the override change, stale summary reported zero. After override-only creation:

- First 200 explanations: none stale.
- Second page: affected task stale with `time_map_overrides`.
- New aggregate: exactly `stale_task_count: 1`, `categories: [time_map_overrides]`, `total_explanations: 202`.
- Browser Calendar displayed Schedule stale with `1 task may be out of date (time map overrides changed)`. No Update Schedule was invoked after the override edit.

Evidence: `volume-retest.json`, `volume-stale-pass.png`. Independently reran the three new stale-summary API tests: **3 passed**. Web unit suite **36 passed**; build passed (bundle-size advisory only).

## Import merge operator checks

- One Import button opens the shell with Templates and Custom outline tabs.
- Templates propose/apply succeeded: synthetic Dex merge fixture, 1 epic / 2 projects / 3 sections / 5 tasks; receipt and idempotency key visible.
- Custom outline propose/approve succeeded: Dex custom fixture, 1 epic / 1 project / 1 section / 1 task. Modal closed and navigated to the new epic.
- Browser readback retained `Video:`, `Reading:`, and `Lab:` prefixes and displayed the expected labels. Template review showed scaffold warning and explicit task durations.
- Custom outline's draft survived a tab round trip, including an invalid JSON draft.
- Upload/download and every attachment target were not re-exercised in this merge-focused pass; their existing PARTIAL dispositions remain.

## IM-R1 [P2]: tab navigation resets Templates draft and review state

**Location:** `apps/web/src/components/TemplatesPanel.tsx:375–390`, triggered by `ImportPanel.tsx` passing `active={open && mode === "templates"}`.

**Repro:** Open Import > Templates, change Program title to `KEEP THIS DRAFT`, switch to Custom outline, then return to Templates. Program title becomes `Your program or learning path title`. Repeated successfully. Initial reproduction used `Dex merge fixture` with the same loss.

The effect depends on `panelOpen` and reloads the example whenever the tab becomes active. It resets JSON, form values, proposal entities, summary, idempotency key, and receipt. Navigating to another tab should not silently discard operator work. Initialize only when needed or after an explicit template/reset action, preserving each tab's state across navigation.

Evidence: `import-draft-before.png` and `import-draft-reset.png`. Happy-path apply success does not close this finding.

## Cleanup and disposition

Disposable containers and database removed; artifacts retained. No code changes, commits, pushes, or human acceptance marks by Dex. W1-R1 and IM-R1 are verified closed. F4/F5 overall status remains subject to the existing human acceptance process.
