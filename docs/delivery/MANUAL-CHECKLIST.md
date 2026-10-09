# Manual checklist (Trish)

**Filename:** MANUAL-CHECKLIST.md

**Last modified:** 2026-10-09 (Dex — F5 residuals verified closed; remaining manual rows open)

**File version:** 2.4

**Dex coverage, 2026-10-09:** Checked boxes below mean the stated local check has Dex evidence; Trish may independently rerun them. They do not complete the human sign-off table. **F1–F3: 31 pass, 5 partial, 1 user-only; prior lifecycle failure retested successfully.** Original pass uses frozen `cc87349`; reused `0199edf` browser evidence is labeled. CLI/API checks are identified separately from browser checks. See [original Dex evidence](./DEX-MANUAL-2026-10-09.md) and [F4 verification / three web P2s](./DEX-F4-MANUAL-2026-10-09.md). **F4 W3 web slice: empty-band edit/create, header alignment, and original UTC overlay Pass; residual P2s (mixed override TZ → settings.timezone band hours; 06–22 visible clipping) Verified closed (Trish/Dex, local working tree). F4 remains Open (CLI, day overlay, F4-D, sign-off table); no push.** **F5:** all seven findings, including both residuals, verified closed by Dex; see [F5 evidence](./DEX-F5-MANUAL-2026-10-09.md). F5 remains Open for remaining manual coverage and human sign-off; no push. F4 evidence below distinguishes direct browser/HTTP checks from focused automated corroboration; the optional browser DST check remains open.

Standalone operator checklist for browser / CLI verification of F1–F5 delivery waves.
Canonical copy — tick boxes here. Feature delivery docs link here instead of duplicating lists.

**As of 2026-10-09:** tip on `cursor` `main` includes F3-W2 through `93dbbcb` (plus Move-to Space `0c36ee2`); **F4-W1** spine with API pytest **17** green; **F4-W2** fingerprint **v3** + stale **`time_map_overrides`** — Renee pytest **22** green (**2026-10-09**), Dex local W2 evidence recorded below; **F4-W3** Settings + week overlay Dex-verified (Trish/Dex) — **not pushed**. F4 remains **Open / in-progress** (not Closed). **F5-W1** template API pytest **14** green (Renee, **2026-10-09**); **F5-W2** CLI landed (local); **F5-W3** + **F5-B** Quality green; Dex verified all seven findings and both residual paths closed — **not pushed**. F5 **Open / in-progress** (not Closed).
F1–F3: automated suites green; human gate still open for those waves where sections below are unchecked.

---

## Setup

- [ ] Compose API (and web) up; household DB reachable

  Dex 2026-10-09 — **PARTIAL:** Disposable local Compose passed; household DB intentionally not exercised.

- [x] `cd apps/api` → `alembic upgrade head` → at least **`023_schedule_outcome_provenance`** (implies F1 `020` + F2 `021` + F3 `022`/`023`)

  Dex 2026-10-09 — **PASS:** Local stack migrated to 023_schedule_outcome_provenance; alembic current confirmed head.

- [x] **F4 rows:** same migrate → head includes **`024_time_map_overrides`**

  Dex 2026-10-09 — **PASS:** Isolated current-working-tree stack migrated to 024_time_map_overrides; alembic current confirms head.

- [ ] Web: signed in as yourself

  Dex 2026-10-09 — **USER:** Signed in as disposable QA account; Trish account check remains yours.

- [x] CLI: `theplan auth login` against the same API (for CLI rows below)

  Dex 2026-10-09 — **PASS:** Actual CLI auth login against the same isolated API, separate session file.


---

## F1 — Planning handoff

Delivery: [F1-HANDOFF.md](./F1-HANDOFF.md)

- [x] `theplan handoff propose --file …` then `--format text` — tree matches JSON entities; propose JSON `payload` shows embedded duration/priority defaults

  Dex 2026-10-09 — **PASS:** CLI JSON embedded 30-minute/P4 defaults; text tree matched both graft tasks.

- [x] Apply with a fresh UUID key; `theplan handoff receipt --idempotency-key …` matches apply JSON; second apply shows `replayed: true`

  Dex 2026-10-09 — **PASS:** Fresh-key apply, receipt JSON equality, repeated apply replayed=true with same receipt.

- [x] Epic, project, or **task** detail in web shows **source refs** after a handoff / task-only graft that included `source_refs`

  Dex 2026-10-09 — **PASS:** Browser task-only graft: Advanced showed dex-checklist / QA-F1 link.

- [x] Graft tasks under an existing section: host project `schedule_style` unchanged; new tasks respect handoff `schedule_policy`

  Dex 2026-10-09 — **PASS:** CLI readback: standalone host unchanged, grafted tasks manual.

- [x] `theplan deps list|add|remove` round-trip against two real task IDs

  Dex 2026-10-09 — **PASS:** Actual CLI add/list/remove round-trip on synthetic owned tasks.

- [x] `theplan epics|projects|sections` list/get/create/patch against owned entities

  Dex 2026-10-09 — **PASS:** Actual CLI create/get/list/patch for all three entity types.

- [x] Outline re-import still **duplicates** (handoff idempotency does **not** apply to outline)

  Dex 2026-10-09 — **PASS:** Browser approved identical outline twice; two same-title epics appeared.


---

## F2 — Kanban

Delivery: [F2-KANBAN.md](./F2-KANBAN.md)

- [x] Project view: toggle **Board**; columns Ready / In progress / Waiting / Done; WIP summary matches In progress + Waiting totals

  Dex 2026-10-09 — **PASS:** Browser columns and WIP verified in current and earlier smoke.

- [ ] **Work** board: epic / project filters narrow cards; archived containers not offered in project picker; All / All = owner-wide (inbox + projects, no date filter)

  Dex 2026-10-09 — **PARTIAL:** Epic/project narrowing and owner-wide inclusion pass. Archived project itself omitted, but active child project under archived epic remains in picker; see evidence note.

- [x] **Move to…** menu moves a card; CLI `theplan tasks get --id …` shows matching `workflow_state`, `board_column`, `board_revision`

  Dex 2026-10-09 — **PASS:** Browser move plus CLI get: waiting / waiting, revision 2, matching Drag verification note.

- [ ] **Keyboard:** focus **Move to…** select → **Space** opens the dropdown (does **not** open task details) — fix `0c36ee2`; browser retest

  Dex 2026-10-09 — **PARTIAL:** Space/Enter no longer open task detail; ArrowDown/Enter moved card. Native dropdown opening itself remains a human check.

- [ ] Drag within a column (insert before/after peer); drag to another column (Waiting prompts for note, then applies saved insert hints); drop on **Done** runs completion policy when parent has open children

  Dex 2026-10-09 — **PARTIAL:** Drag into empty Waiting opens note prompt and saves correctly. Peer insertion/within-column reorder and parent Done drag inconclusive via browser control; menu parent policy passed earlier.

- [x] **Load more** on an open column and on **Done** when totals exceed page size

  Dex 2026-10-09 — **PASS:** Earlier 0199edf browser smoke loaded 52 Ready / 32 Done, including both continuation pages; move reset repopulated first pages.

- [x] Complete recurring task on board → toast “next occurrence”; card lands in **Ready**, not Done

  Dex 2026-10-09 — **PASS:** Current browser: next-occurrence toast observed, due advances, card stays Ready.

- [x] Move completed task to In progress → uncomplete + workflow in one step; list view shows same state

  Dex 2026-10-09 — **PASS:** Current browser: completed conflict fixture moved to In progress; List exposes unchecked Mark complete control.

- [x] **Roots only** toggle hides subtasks; column headers may still show API totals (known quirk)

  Dex 2026-10-09 — **PASS:** Earlier 0199edf browser smoke hid/restored child using Roots only.

- [x] Today / Upcoming board: scheduled-but-not-due tasks still appear when blocks overlap the smart range

  Dex 2026-10-09 — **PASS:** Current browser shows today/tomorrow scheduled tasks with null due dates in corresponding smart boards after explicit All/All reset.

- [x] Stale board: complete in one session → workflow with stale revision in another → **409** `BOARD_REVISION_CONFLICT`

  Dex 2026-10-09 — **PASS:** Separate HTTP session completed task; stale revision returned 409 BOARD_REVISION_CONFLICT (0 vs 1); stale browser move refreshed card into Done.

- [ ] Default list/board hides tasks in archived project or epic; opening archived **project** detail still lists its tasks

  Dex 2026-10-09 — **PARTIAL:** Default API and board exclusion passed; explicit archived project query returns task. Archived browser view has Restore only, so opening archived project detail unverified.

- [x] `theplan tasks workflow --id … --column waiting --expected-revision N --waiting-note "…"` then list with `--workflow waiting --board-order`

  Dex 2026-10-09 — **PASS:** Actual CLI workflow waiting with expected revision/note, followed by workflow-filtered board-order list.


---

## F3 — Scheduler explanations

Delivery: [F3-SCHEDULER-EXPLANATIONS.md](./F3-SCHEDULER-EXPLANATIONS.md)

### Core (W1)

- [x] **Update Schedule** on a mix of auto + manual/bundle tasks → run completes; manual/bundle show exclusion explanations

  Dex 2026-10-09 — **PASS:** Current browser Update Schedule completed; CLI and browser style exclusion copy verified; earlier mixed-run smoke also passed.

- [x] Task with pinned blocks covering full estimate → “covered by pins”; replan does not add unpinned blocks for that task

  Dex 2026-10-09 — **PASS:** Browser/CLI covered-by-pins copy; direct block API confirms one pinned block and no added unpinned blocks.

- [x] Dependent with unfinished blocker → **blocked** prerequisite; after blocker completes + replan → dependent can show **placed**

  Dex 2026-10-09 — **PASS:** Earlier 0199edf browser: blocked manual prerequisite, then blocker completion + replan changed dependent to Placed 30 minutes.

- [x] Partial fit in horizon → **horizon exhausted**; past deadline with zero placement → **no suitable slot** / **deadline limit** as appropriate

  Dex 2026-10-09 — **PASS:** Current browser/CLI: 1320 of 3000 placed, 1680 horizon-exhausted; earlier past-deadline browser case named deadline/remaining minutes.

- [x] Task never replanned → **Why this schedule?** never-evaluated copy (no fabricated story)

  Dex 2026-10-09 — **PASS:** Earlier 0199edf browser: new task before replan showed No scheduling evaluation recorded.

- [x] Change estimate or deadline after a run → stale badge + named categories on next panel load (no auto-replan)

  Dex 2026-10-09 — **PASS:** Current browser edit 30 -> 45 retained old result/run, showed Stale with tooltip duration changed. Earlier browser replan cleared Stale; lifecycle tooltip also verified.

- [x] `theplan schedule explain --task-id …` JSON includes `human_summary` matching `summary_text`

  Dex 2026-10-09 — **PASS:** Actual CLI explain: human_summary equals summary_text across placed/excluded/blocked/unplaced fixtures.

- [x] `theplan schedule runs list` / `get --id …` / `explanations --id …` match API pagination and owner scope

  Dex 2026-10-09 — **PASS:** Actual CLI list/get and explanation pages (limit 2, offsets 0/2) matched direct API responses; owner boundary tested separately.

- [x] Second user cannot read another owner’s run or explanation (**404**)

  Dex 2026-10-09 — **PASS:** Second authenticated test owner received 404 for foreign run, run explanations, and task explanation.


### W2 spot-checks

- [x] Completed / trashed / archived (project or epic) → lifecycle exclusion copy; manual/bundle on **archived** project → lifecycle wins over style exclusion

  Dex 2026-10-09 — **PASS, retested:** Current frozen working tree: archived-project/manual and archived-epic/bundle now return excluded_lifecycle_archived and show the correct lifecycle copy in browser. Full-pin precedence regression also passes in the focused suite. Completed/trash retain prior pass evidence. See [F4 evidence](./DEX-F4-MANUAL-2026-10-09.md).

- [x] Dependency cycle → **`blocked_dependency_cycle`** (only cycle members; downstream is prerequisite-blocked)

  Dex 2026-10-09 — **PASS:** Current CLI/API: A/B cycle facts name only A/B; downstream fact is blocked_prerequisite.

- [x] Deadline binding → **`unplaced_deadline_limit`** when applicable

  Dex 2026-10-09 — **PASS:** Current browser/CLI: deadline-binding fixture emits unplaced_deadline_limit.

- [x] Placed task after replan: explanation has **`algorithm_version`: `f3-w2`** and **`placement_facts`**

  Dex 2026-10-09 — **PASS:** Current CLI/API placed explanation: algorithm_version=f3-w2 and nonempty placement_facts.


---

## F4 — Temporary Time Map overrides

Delivery: [F4-TIME-MAP-OVERRIDES.md](./F4-TIME-MAP-OVERRIDES.md) · **W1** Quality green · **W2** Quality green (**2026-10-09**, Renee) · **W3** Settings + week overlay Dex-verified (Trish/Dex); CLI / day overlay / F4-D deferred · **F4 not Closed**

### W1 spine (API + scheduler — manual spot-checks)

- [x] Create override on a Time Map (HTTP or future CLI): inclusive dates, stored timezone, replacement bands; **base map bands unchanged** on `GET /focus-windows/{id}`

  Dex 2026-10-09 — PASS (HTTP): Inclusive range/timezone/bands round-trip; base bands unchanged. Browser nonempty create also passed.

- [x] Second overlapping date range on the **same** map → **409** `TIME_MAP_OVERRIDE_OVERLAP`; adjacent ranges and same dates on **another** map succeed

  Dex 2026-10-09 — PASS (HTTP/browser): Same-map overlap 409; adjacent and other-map dates succeed. Browser message names the conflicting range.

- [x] **Update Schedule** with a task bound to that map: placement on an override day uses override bands; day before/after uses base map; **Why this schedule?** shows **`applicable_override`** in `placement_facts` when applicable

  Dex 2026-10-09 — PASS (HTTP + focused pytest): Inherited Map A task placed in override band with applicable_override; before/after base behavior covered by focused scheduler regressions. Browser Update Schedule completed; raw placement facts verified through API.

- [x] Override write (create/patch/delete) does **not** auto-replan; expired override still appears in list; scheduling after expiry uses base map again

  Dex 2026-10-09 — PASS (HTTP + focused pytest): Writes do not start runs; expired row listed. After-expiry base placement covered by focused regression.

- [x] Empty bands + `strict_mode: true` → treated as all-day unavailable for that override range (API contract)

  Dex 2026-10-09 — PASS (API/scheduler only): Empty strict accepted and scheduler regression passes. Web edit/save and empty creation now pass in browser plus HTTP readback — see W3 row below.

### W2 fingerprint + placement (local build — Quality green 2026-10-09)

- [x] After replan, placed task explanation shows snapshot **`v`: 3** and **`algorithm_version`: `f3-w2`** (legacy v2 rows may show **`provenance`** stale until replan)

  Dex 2026-10-09 — PASS (HTTP): Current persisted explanation has input_snapshot.v=3 and algorithm_version=f3-w2.

- [x] Override-only change (create, patch bands/dates, or delete) on the task's **effective** map → **Why this schedule?** shows **Stale** with **`time_map_overrides`** (no auto-replan); replan clears override stale when inputs match

  Dex 2026-10-09 — PASS (HTTP/browser + focused pytest): Create/patch staleness and browser named tooltip verified; browser replan clears Stale. Delete stale is covered by focused regression.

- [x] Task on map **B** unchanged when override exists only on map **A** (inherit epic/project map or task bind — cross-map independence)

  Dex 2026-10-09 — PASS (HTTP + focused pytest): Inherited Map A task uses override; B task has no applicable override and is not stale after A-only change. Unbound/epic/project variants pass in focused suite.

- [ ] Override spanning a **DST** transition: placement respects stored local dates/timezone (pytest matrix in `test_f4_w2_scheduler.py`; optional browser spot-check)

  Dex 2026-10-09 — AUTOMATED PASS; optional browser spot-check remains open. Focused DST parameter matrix passed in the 52-test run.

### W3 web UI (Settings + week calendar — local build)

- [x] **Settings → Time Maps:** expand a map → **Overrides** — create inclusive date range, IANA timezone, replacement bands (incl. strict / empty bands); row appears in list with status; **Edit** patches; **Delete** removes; base map bands on the same map unchanged

  Dex 2026-10-09 — PASS, rechecked: Empty strict edit/save preserves zero bands. New form seeds green; removing the final band and creating a strict override succeeds. HTTP confirms both rows remain empty. Earlier nonempty CRUD/base preservation evidence retained. See [F4 evidence](./DEX-F4-MANUAL-2026-10-09.md).

- [x] **Validation UX:** second overlapping range on the **same** map → UI toast/message for **409** `TIME_MAP_OVERRIDE_OVERLAP`; band that crosses midnight (client or API) → **422** / `TIME_MAP_OVERRIDE_BAND_CROSSES_MIDNIGHT` copy with band index when provided; invalid date order / timezone surfaced readably

  Dex 2026-10-09 — PASS: Browser overlap, reversed-date, and midnight-band messages verified. Invalid IANA name rejected by HTTP 422; browser picker retains last valid UTC rather than submitting unrecognized text.

- [x] **Calendar (week view):** choose Time Map overlay control → days inside an active override show **Override** badge and paint **effective override bands** (not base-only bands for those days); days outside override range still show base map bands; **day view** overlay **not** in scope yet (defer)

  Dex 2026-10-09 — **PASS, Verified closed (Trish/Dex):** UTC settings + America/New_York override 15:00–17:00 paints 08:00–10:00 Pacific alongside its 08:00 task (band hours = settings.timezone). Base 01:00–03:00 Pacific bands clip/hide in 06–22 view and reappear correctly in 24-hour view. Header alignment retains its prior pass. Day view overlay still deferred. See [final residual evidence](./DEX-F4-MANUAL-2026-10-09.md).

### Deferred to later F4 waves (do not block W1 / W3 UI slice sign-off here)

| Item | Wave |
|------|------|
| Override-only edit → stale explanation / schedule indicator | F4 **W2** — **landed** (manual rows above; Renee pytest **22** green) |
| DST transition placement matrix | F4 **W2** — **landed** (pytest; optional operator spot-check) |
| Epic/project inherit + task on map B unaffected by map A override | F4 **W2** — **landed** (pytest; manual row above) |
| CLI override list/create/edit/delete | F4 **W3** (deferred) |
| Calendar **day-mode** override overlay | F4 **W3** (deferred) |
| Red precedence, pins/busy copy, full F4-D UX | F4 **W3** |

---

## F5 — Coursera templates

Delivery: [F5-COURSERA-TEMPLATES.md](./F5-COURSERA-TEMPLATES.md) · **W1** Quality green (**14** pytest, Renee) · **W2** CLI landed (local) · **W3** Quality green (**TemplatesPanel**, web build — Andi) · **F5-B** Quality green (**7** + W1 **14** = **21** API pytest; CLI list/get; IBM apply **417** tasks — Renee) · **Outline merge deferred** · **F5 not Closed**

**Dex 2026-10-09:** All seven findings and both residual paths are **verified closed**. Prior rebuilt-image verification: zero API mounts, 62 API tests, web build and live HTTP/CLI checks passed. Final focused browser retest preserved invalid JSON in Raw mode and ignored a delayed obsolete proposal; fresh proposal/apply created one task with one optional skipped. Final web build passed. F5 remains Open for unchecked coverage below and human sign-off. See [full evidence](./DEX-F5-MANUAL-2026-10-09.md).

### W1 API + legacy outline (operator / CLI)

- [x] `GET /api/v1/templates` lists **`coursera_specialization`**, **`coursera_course`**, **`coursera_module`**; `GET …/{id}` returns version **1**, `example_outline`, and scaffold flag where applicable

  Dex 2026-10-09 — **PASS with packaging caveat (HTTP/CLI):** Three IDs, v1 examples/scaffold flags verified after test-only mount. **P1 Fixed (code):** examples packaged under `apps/api/app/data/outlines` — **awaiting Dex retest** without testdata mount.

- [x] **`coursera_specialization`:** propose + apply tiny outline → epic / project / section / task tree; **`skip_optional`** reduces task count; second apply with **same** idempotency key → `replayed: true`; **new** key → second epic instance

  Dex 2026-10-09 — **PASS (HTTP):** Tiny specialization tree, optional exclusion, same-key replay, and new-key second instance verified. **P2 Fixed (code):** idempotency key retained pre-apply for retry — **awaiting Dex retest**.

- [x] **`coursera_course`:** standalone `{ "course": … }` → project-only root; graft under existing epic → project under that epic; certificate-shaped JSON rejected with readable error

  Dex 2026-10-09 — **PASS (HTTP):** Standalone project, existing-epic graft, and certificate-shape rejection verified.

- [x] **`coursera_module`:** requires **`attach_under`** project or section; project attach creates section + tasks; section attach adds tasks only; missing attach → **422** `TEMPLATE_ATTACH_REQUIRED`

  Dex 2026-10-09 — **PASS (HTTP/CLI):** Required parent validation, project and section grafts verified. **P2 Fixed (code):** module picker can target standalone projects — **awaiting Dex retest**.

- [x] Template receipt: `GET /api/v1/templates/receipts/by-key/{key}` returns apply result; same key under **`/handoffs/receipts/by-key`** → **404**

  Dex 2026-10-09 — **PASS (HTTP):** Matching template receipt; same key under handoff receipts returns 404.

- [x] Legacy **`POST /api/v1/outlines/propose`** with IBM RAG fixture still succeeds; **`POST /api/v1/templates/coursera_specialization/propose`** on same file matches legacy **summary** counts (outline path still **non-idempotent** on apply)

  Dex 2026-10-09 — **PASS (HTTP + pytest):** IBM proposal summaries match; template apply created 417 tasks. Legacy outline regressions pass.

### W2 CLI

- [x] `theplan templates list` and `get coursera_specialization` (text + JSON output)

  Dex 2026-10-09 — **PASS (actual CLI):** Catalog and specialization detail in text and JSON verified against isolated API.

- [x] `theplan templates propose coursera_module --file … --attach-kind project --attach-id …` then `apply … --idempotency-key …`; `templates receipt --idempotency-key …` matches apply JSON; replay on repeat apply

  Dex 2026-10-09 — **PASS (actual CLI):** Module project graft, apply, by-key receipt equality, and repeat replay verified.

### W3 web (when landed)

- [ ] Template picker distinct from **Outline** panel; example JSON download; modest form for common fields; raw JSON still works; blank scaffold visibly distinct from imported syllabus

  Dex 2026-10-09 — **PARTIAL (browser):** Distinct picker, Raw↔Quick sync, invalid-draft preservation, and scaffold classification pass. Download-event capture timed out; upload not exercised.

- [ ] Propose/apply uses **`/templates/*`** (not `/outlines/apply`); optional-item toggle in review; source refs / warnings surfaced before apply

  Dex 2026-10-09 — **PARTIAL:** Templates API route confirmed; browser apply/receipt/replay pass. Both settled-input and in-flight stale-preview paths verified closed. Full source-reference/warning presentation remains open.

### F5-B spot-checks (expand as UX lands)

- [ ] Task labels from outline `task_type` (+ optional) visible after apply; durations match supplied `duration_minutes` (defaults disclosed on propose, not invented catalog durations)

  Dex 2026-10-09 — **PARTIAL (HTTP/pytest/browser):** Supplied 17-minute duration retained; labels covered by API tests. Browser review verified explicit 17m and settings-derived 30m. Post-apply label visibility remains API-tested, not browser signed off.

- [x] Duplicate Coursera URL on propose warns; apply still creates a **new** instance (no merge)

  Dex 2026-10-09 — **PASS (HTTP):** Duplicate source URL warns; fresh-key apply creates another instance without merge.

---

## Not on this gate (parked)

Do not block F1–F3 close on these; they live elsewhere:

| Item | Where |
|------|--------|
| Prerequisite explanations show UUIDs (want titles) | F3 backlog — final polish pass |
| Overbooked copy mentions deadlines when blocker is a prerequisite | F3 backlog — final polish pass |
| `priority_ups` stale compare | F3 W3 |
| `time_map_overrides` stale compare + snapshot v3 fingerprint | F4 W2 — **landed**; Renee Quality green; operator manual still open |
| Schedule-run summary web UI | F3 W3 / later |
| Full F2-D a11y/touch matrix beyond Move-to Space | F2 known limitations |
| DEF-028 calendar mirror delete recovery | Deferred |

---

## Sign-off

When a section is done, note date + “ok” here (optional):

| Wave | Done | Notes |
|------|------|-------|
| Setup | | |
| F1 | | |
| F2 | | |
| F3 | | |
| F4 | | W1/W2 Quality green; W3 Settings + week overlay Dex-verified (residual P2s closed); CLI/day/F4-D deferred — **not Closed** |
| F5 | | W1/W3/F5-B Quality green; Dex all findings/residuals verified closed; remaining manual rows open — **not Closed**, **not pushed** |
