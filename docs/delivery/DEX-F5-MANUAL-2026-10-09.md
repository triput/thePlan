# Dex F5 review and manual verification

**Filename:** DEX-F5-MANUAL-2026-10-09.md
**Last modified:** 2026-10-09 (Dex — both residuals verified closed)
**File version:** 1.4

## Final residual retest — PASS

2026-10-09: rebuilt web from the prior frozen fixture with current `TemplatesPanel.tsx` (SHA-256 `5adb49573be3b43d213806862cb1bcf64733b7aa8c3e07ffe46030bf6a5e1626`). Web build passes (`index-Br1ZSnfk.js`). Reused the previously verified API image with a fresh disposable database.

- **R1 verified closed:** Pasted the same unfinished JSON draft and clicked Quick fields. Raw stayed selected (`aria-selected=true`), the exact draft remained byte-for-byte intact, and the parse error appeared. Replacing it with valid JSON then allowed Quick fields and populated the correct course title.
- **R2 verified closed:** Delayed a two-task proposal response by five seconds and checked Skip optional while Proposing was displayed. After the obsolete response arrived, no preview or Apply button appeared. A fresh proposal showed one task and one optional skipped. Apply created exactly one project, one section, and one task; receipt `d41c8966-250a-4d16-815c-51fd41c9740c`, key `d7b29c68-ca6d-43e8-be37-4794ebfbbe69`.

Evidence in the existing `f5-retest` scratch directory: `residual-final-evidence.jsonl` and `residuals-closed.png`. This was a focused browser recheck plus web build; the prior 62 API and live CLI passes were not rerun. Test stack removed afterward. No product edits, commits, or pushes. Historical findings below are retained; this section supersedes their awaiting-retest wording. Download/upload and remaining broad manual rows stay open.

## Build and outcome

Frozen uncommitted F5 working tree over `4ae0a8d`, captured approximately 12:53 Pacific. Manifest contains 434 files. Source comparison before documentation edits found no drift. Initial Dex pass: **one P1 and six P2 findings** below.

**Dex final residual retest: all seven findings, including both residual paths, verified closed.** F5 remains Open for the remaining manual checklist and human sign-off. No push by Dex.

| # | Severity | Dex symptom | Fix (working tree) | Retest |
|---|----------|-------------|-------------------|--------|
| 1 | P1 | Template detail 500 — examples loaded from missing `/testdata/outlines` | Package examples under `apps/api/app/data/outlines`; no runtime testdata mount | **PASS** — rebuilt image, no API mounts |
| 2 | P2 | New idempotency key on browser retry after failed/lost apply response | Allocate and retain key **before** apply; bind to payload across retries | **PASS** — committed response replaced with 502; retry replayed |
| 3 | P2 | Raw JSON lost when switching to Quick fields | Raw↔Quick sync preserves current editor JSON; stay on Raw when sync fails | **PASS** (valid JSON, retest); invalid-draft path **PASS — draft preserved in Raw** |
| 4 | P2 | Module picker cannot target standalone course projects | Owner-wide / standalone project selection in module attach UI | **PASS** — browser standalone project graft applied |
| 5 | P2 | Skip optional / attach / edits still apply stale preview graph | Invalidate preview when inputs change; ignore obsolete in-flight propose responses | **PASS** (after-completion, retest); in-flight path **PASS — obsolete response ignored** |
| 6 | P2 | Renamed scaffold banner claims imported syllabus | Improved scaffold detection / provenance | **PASS** — renamed sample remains scaffold |
| 7 | P2 | Review omits settings-default task durations | Duration disclosure in proposal review UI | **PASS** — explicit 17m and settings-derived 30m visible |

Disposable `dex-f5-smoke` Compose stack on localhost:18080, tmpfs database and synthetic QA account. No household data or external integrations. Web production build passed. **54 API tests passed** across F5 W1/B, handoffs, and legacy outlines. **18 CLI tests passed** across template commands and main commands.

The initial container detail request failed due to finding 1. A **test-only** `testdata` mount was added to continue functional testing; it is not a product fix. Tests also needed the repository mounted at `/workspace` because legacy fixture tests assume repository-relative paths. All functional passes below have this packaging caveat.

## Dex retest, 2026-10-09

**Five findings verified closed (unchanged).** **Andi residual fix wave (2026-10-09, working tree, not pushed):** R1 invalid JSON tab stay; R2 propose generation ignores stale in-flight responses — **Fixed (code), awaiting Dex retest.** F5 stays Open. Prior retest: frozen 347 source/config/fixture files over committed base `4ae0a8d`, ~13:32 Pacific; final hash comparison found no source drift. Rebuilt API image `dex-f5-retest-api:local` has image ID `sha256:5d80d033bb187cc1e52e84ad7a7d3dfdb0dc56a1a0ddd00a9f2e8bb299b958bd`. Docker inspect confirmed **zero API container mounts**. All three template detail endpoints pass without `/testdata`.

**62 API tests passed** (the earlier 54-test selection plus eight packaged-example/scaffold tests); frozen web build passed. Live HTTP and actual CLI driver passed again, including all shapes/grafts, optional exclusion, receipts, replay, duplicate-source warning, and IBM apply **417**. Pytest used a separate test runner with repository fixtures mounted; the runtime API serving browser/HTTP checks had no mounts. The earlier 18 CLI unit-test result was not rerun in this retest.

Browser verification:

- Valid custom two-task Raw JSON survives Quick fields and return to Raw with title, modules, tasks, and 17-minute estimate intact.
- Review visibly shows **17m (explicit in outline)** and **30m (from scheduling settings)**.
- Changing Skip optional after a completed proposal removes Apply; re-propose shows one task / one optional skipped.
- Test-only internal proxy allowed the server to commit Apply, then replaced its successful response with HTTP 502. Browser retry used key `3fd3178c-57c8-4f4b-b54d-9ac319c01e40` again and returned **Receipt (replay)**, receipt `8064aa30-244f-4a83-b0cf-1becd82283ce`. No second instance was created by that retry.
- Module picker exposes the browser-created standalone project without selecting an epic. Module apply created one section and one task; receipt `47c5186d-789f-416c-8ac6-67f4bd9d3cdf`.
- Renaming the sample to My statistics course and replacing its URL retains **Blank scaffold** and a placeholder warning.

### Residual R1 [P2]: Invalid JSON still gets overwritten by mode switching — **Verified closed**

Paste an unfinished draft such as `{"course":{"title":"Unsaved unfinished curriculum"` into Raw JSON. Click Quick fields. An error says to fix Raw JSON first, but the UI switches anyway and displays the previous form. Click Raw JSON again: the previous valid outline replaces the unfinished draft. `syncFormFromJson` returns false on parse failure, but its caller ignores that return and always changes modes (`TemplatesPanel.tsx:785–786`). Keep Raw mode and the exact draft when synchronization fails. The original valid-JSON repro is closed on retest.

**Fix (Andi, working tree):** Mode switch respects failed sync — stay on Raw and preserve the invalid draft. **Awaiting Dex retest.**

### Residual R2 [P2]: An in-flight proposal restores a stale preview — **Verified closed**

Use the custom course containing one normal and one optional task. Start Propose with Skip optional unchecked, delay the response five seconds, and check Skip optional while Proposing is displayed. The handler clears the preview, but the old response then unconditionally populates entities and enables Apply. With Skip optional still checked, Apply created both tasks: receipt `7f675b3c-10b9-419a-a7b9-2d63b9c5b352`, key `d83047dd-d127-498d-a573-35152f4c7015`. `proposeMutation.onSuccess` does not check whether the inputs changed since dispatch (`TemplatesPanel.tsx:494–503`). Associate each request with an input generation/snapshot and ignore obsolete responses, or prevent changes while pending. The after-completion input-change repro passes on retest.

**Fix (Andi, working tree):** Propose dispatch tagged with input generation; stale responses ignored. **Awaiting Dex retest.**

Retest artifacts are under `C:\Users\trish\.codex\visualizations\2026\10\08\01a11d56-e98c-7c31-995d-8b17c9a41e5a\f5-retest`: `source-manifest.json`, `api-cli-evidence.json`, `fault_proxy.py`, `fault-evidence.jsonl`, and `stale-proposal-receipt.png`. The proxy was confined to the disposable environment; no product code was edited. The screenshot shows the checked optional exclusion beside the two-task preview; exact applied counts are in the receipt log. Disposable stack removed after the pass. Download/upload remain outside this focused retest; prior unverified status is unchanged. No commits or pushes from Dex. **Andi** residual fixes are local working-tree only — **not pushed**; Dex has not rerun R1/R2 yet.

The sections below preserve the **initial** findings and evidence; the retest table, residual fix notes, and this section supersede their awaiting-retest status.

## Findings for the team

### 1. [P1] Template example JSON is absent from the production image — **Fixed (code), awaiting Dex retest**

Catalog GET returned 200, but `GET /api/v1/templates/coursera_course` returned 500. Container log: `FileNotFoundError: /testdata/outlines/blank_hierarchy_v1.json`. All three detail examples share this file loader. `apps/api/Dockerfile` copies only the `apps/api` build context; production Compose has no testdata mount. Thus the ordinary container deployment cannot provide the examples needed by the Templates form or CLI get.

Package runtime template definitions/examples with the API, or explicitly include them in the image. Do not depend on a repository testdata directory being present at runtime. Source: `apps/api/app/services/builtin_templates.py:35`, API Dockerfile, `infra/compose/compose.yaml`.

**Fix (Andi+Tesla, working tree):** Examples live under `apps/api/app/data/outlines` and ship with the API image context — retest ordinary container detail **without** a `/testdata` mount.

### 2. [P2] Browser retries generate a new key after an unsuccessful response — **Fixed (code), awaiting Dex retest**

Source-confirmed error path: `TemplatesPanel` generates the key inside the mutation at line 450, but stores it only in `onSuccess` at line 463. If the server commits and the response is lost, `onError` leaves the key null; pressing Apply again creates a fresh key and a second instance. This defeats F5-C's uncertain-outcome retry guarantee. Allocate and retain the key before sending, and bind it to the submitted payload across retries. Successful-response replay was browser-tested and passes; a dropped post-commit response was **not** injected during this pass.

**Fix (Andi+Tesla, working tree):** Idempotency key allocated and retained pre-apply for retry — retest lost-response / retry path.

### 3. [P2] Raw JSON is discarded when switching to Quick fields — **Fixed (code), awaiting Dex retest**

Browser repro: select course, paste a custom two-task course into Raw JSON, click Quick fields, then Raw JSON. The editor now contains the original four-task example; the custom title/modules/tasks are gone. Quick fields calls `syncJsonFromForm` rather than parsing the current JSON into form/outline state. This overwrites supplied curriculum without warning. Source: `TemplatesPanel.tsx:397`, `:705`, `:836`.

**Fix (Andi+Tesla, working tree):** Raw↔Quick mode sync preserves edited JSON — retest paste / toggle round-trip.

### 4. [P2] Module picker cannot target a standalone course — **Fixed (code), awaiting Dex retest**

The API successfully created a standalone course and attached a module to its project. In the browser, the module's Target project control is disabled until an epic is chosen, and the project query then filters by that epic. No path exposes standalone projects or their sections. This prevents adding a module to the standalone course that the course template itself creates. Allow owner-wide/standalone project selection; retain optional epic filtering. Source: `TemplatesPanel.tsx:346–355`, `:629`.

**Fix (Andi+Tesla, working tree):** Module attach UI exposes standalone / owner-wide projects — retest course-then-module browser path.

### 5. [P2] Changing proposal inputs leaves the old graph applicable — **Fixed (code), awaiting Dex retest**

Browser repro: propose a course containing one normal and one optional task; check **Skip optional items (preview exclude)**; click Apply. The checkbox remains checked, but both tasks are created. Receipt `e04adff2-cc27-4e8c-a192-b4295d1a3c0a`, key `776096f0-ca16-4335-b226-0168cfcb4f81`, reports two tasks. Input handlers do not clear or invalidate the previous preview. Attach changes and raw/form edits follow the same stale-preview pattern. Require re-proposal after changing proposal inputs, or rebuild the preview before enabling Apply. Source: `TemplatesPanel.tsx:876` and Apply button/handleApply.

**Fix (Andi+Tesla, working tree):** Stale propose preview invalidated when inputs change — retest Skip optional after propose and attach/raw edits.

### 6. [P2] Renaming a scaffold relabels sample content as imported syllabus — **Fixed (code), awaiting Dex retest**

Browser repro: select the built-in course, change only its title to **My statistics course** and replace the placeholder URL with a valid URL, then propose. The banner says **Imported syllabus detected**, although the untouched example modules and tasks (Welcome and overview, Syllabus and setup guide, Practice quiz, Hands-on exercise) remain. `is_blank_scaffold` tests only the root title prefix. This violates the requirement to distinguish scaffolds from supplied curricula; track provenance or detect remaining placeholders without asserting that a renamed scaffold was imported. Source: `builtin_templates.py:109–113` and `TemplatesPanel` scaffold banner.

**Fix (Andi+Tesla, working tree):** Scaffold detection improved — retest renamed-title propose banner.

### 7. [P2] Web review does not disclose defaulted task durations — **Fixed (code), awaiting Dex retest**

The custom browser outline supplied 17 minutes for one task and omitted the optional task's duration. API propose returns `resolved_defaults` with `estimated_duration_minutes: 30` from user settings; the UI stores that field but never renders it. Review rows show only titles and labels, and the proposal has no duration warning. Apply creates the task with 30 minutes without the required preview disclosure. Render explicit and defaulted minutes, identifying settings-derived values. Source: `TemplatesPanel.tsx:429` and `EntityReviewRow`; live API evidence records the defaults.

**Fix (Andi+Tesla, working tree):** Review UI discloses explicit and defaulted durations — retest 17-minute + omitted-duration propose.

## Verified behavior

| Area | Evidence |
|---|---|
| Catalog/detail | Three IDs, v1, examples and scaffold flags via HTTP and real CLI, after test-only fixture mount. |
| Specialization | Tiny graph apply; optional skip reduces count; same key replays; new key creates a second instance. |
| Course | Standalone project root; graft beneath existing epic; certificate-shaped standalone input rejected. |
| Module | Missing parent rejected 422; project graft creates section/tasks; section graft creates tasks only. Actual CLI propose/apply/receipt/replay passes. |
| Receipts | Template key lookup returns matching receipt; handoff key lookup returns 404. Browser second Apply after success shows Receipt (replay), same key and receipt. |
| Content/defaults | Supplied 17-minute task retained; labels and optional flags covered by API suite; missing duration disclosed by API, but not web review. |
| Duplicate source | Proposal warns about existing source URL; fresh key creates a new instance. |
| IBM / legacy | Live template apply creates 417 tasks; template and legacy propose summaries match. Legacy outline regressions pass. |
| Web happy path | Distinct Templates/Outline controls; custom Raw JSON proposal, apply and receipt render; successful replay passes. Input-mode and stale-preview defects above remain. |

Example JSON download was attempted through the browser, but download-event capture timed out and reset the browser-control session. **Not signed off**; no product download defect is claimed. File upload was not exercised. These narrow checks remain for a later pass/operator.

Harness corrections: first API assertion assumed receipt entity order and was changed to select by task title; CLI helper initially assumed a `data` envelope but CLI emits top-level fields. Final driver run passed. The reruns intentionally left duplicate synthetic instances in the disposable database; these are not additional product findings.

## Artifacts and disposition

Scratch: `C:\Users\trish\.codex\visualizations\2026\10\08\01a11d56-e98c-7c31-995d-8b17c9a41e5a\f5-smoke`.

- `source-manifest.json`: frozen source hashes.
- `f5_checks.py`, `api-cli-evidence.json`: live API and actual CLI commands/results, including IBM apply receipt.
- `optional-applied.png`: checked Skip optional control beside two-task preview/receipt evidence.
- `module.json`, `proposal.json`, `ui-outline.json`: synthetic fixture inputs.

Disposable stack removed after testing; source snapshot and evidence retained. Dex made no product code changes, commits, or pushes. **Andi+Tesla** fixes above live in the local working tree only — **not pushed**. Human sign-off table remains untouched until Dex retest and Trish gate.
