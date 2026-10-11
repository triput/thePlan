# Manual checklist (Trish)

**R3 Midnight Workbench (2026-10-11):** **Closed / shipped** — Trish manual acceptance matrix **2026-10-11**; Dex **D1–D4 + D2b** focused Pass; web **57** tests (Renee). Matrix: [R3-WORKBENCH-2026-10-11.md](./R3-WORKBENCH-2026-10-11.md). F1–F7 sign-off Notes unchanged (PARTIAL residue **not Closed** where stated).

**Latest Dex gate, 2026-10-10:** **W1-R1 verified closed** — volume stale via **`GET …/stale-summary`** + Calendar (**202** explanations, stale only after offset 200). **IM-R1 verified closed** — Import tab draft/review/receipt/idempotency survive tab navigation ([DEX-IMPORT-VOLUME-2026-10-10.md](./DEX-IMPORT-VOLUME-2026-10-10.md)). F6 R1 verified closed (**37** API integration tests incl. concurrent reparent). F4 Wave 1 **verified closed** — CLI overrides, day overlay, F4-D incl. volume stale ([DEX-WAVE1-RETEST-2026-10-10.md](./DEX-WAVE1-RETEST-2026-10-10.md)). Web **36** + CLI **36** green. **Trish Done sign-off recorded 2026-10-10** (Setup–F7) — see [§ Sign-off](#sign-off); PARTIAL / operator residue rows still **not Closed** per Notes.

**Filename:** MANUAL-CHECKLIST.md

**Last modified:** 2026-10-11 (Page — R3 Closed/shipped Trish manual matrix)

**File version:** 4.5

**Dex coverage, 2026-10-09:** Checked boxes below mean the stated local check has Dex evidence; Trish may independently rerun them. Checked boxes are not a substitute for the [§ Sign-off](#sign-off) Done column (Trish **10/10/26 OK** for Setup–F7). **F1–F3: 31 pass, 5 partial, 1 user-only; prior lifecycle failure retested successfully.** Original pass uses frozen `cc87349`; reused `0199edf` browser evidence is labeled. CLI/API checks are identified separately from browser checks. See [original Dex evidence](./DEX-MANUAL-2026-10-09.md) and [F4 verification / three web P2s](./DEX-F4-MANUAL-2026-10-09.md). **F4 W3 web slice (2026-10-09):** Settings/week overlay Dex-verified; residual P2s **Verified closed**. **Wave 1 (2026-10-10):** CLI `theplan overrides` CRUD, day-mode override overlay, F4-D red/stale/legend incl. **W1-R1** volume stale — **Dex verified closed**; Trish Done **10/10/26 OK**; **F4 not Closed** (optional DST); no push. **F5:** all seven findings verified closed by Dex; **B-F5-1** Import merge **Dex verified closed** (**IM-R1**) — [`ImportPanel.tsx`](../../apps/web/src/components/ImportPanel.tsx); see [F5 evidence](./DEX-F5-MANUAL-2026-10-09.md) and [DEX-IMPORT-VOLUME](./DEX-IMPORT-VOLUME-2026-10-10.md). F5 remains Open for PARTIAL operator rows — **not Closed**; no push. Optional F4 DST browser spot-check remains open.

Standalone operator checklist for browser / CLI verification of F1–F5 delivery waves.
Canonical copy — tick boxes here. Feature delivery docs link here instead of duplicating lists.

**As of 2026-10-10:** prior **2026-10-09** paragraph unchanged for F3–F5 except F4/F7 Wave 1 notes below. **F6** Trish Done **10/10/26 OK** — Dex **three P2s Verified closed**; archive P1 closed; **P1 R1** (`epic_id` / epic `target_date`) **Verified closed** on [Wave 1 retest](./DEX-WAVE1-RETEST-2026-10-10.md) (**37** API integration tests incl. concurrent reparent); **not Closed** (F6-B–D). **F4:** Wave 1 CLI + day overlay + F4-D **Dex verified closed 2026-10-10** (incl. **W1-R1** volume stale); prior week Settings/overlay Dex evidence retained. **F7:** W1 API Quality **64** pytest green; **W2** CLI `theplan views` implemented (CLI tests green); **W3** web implemented (`npm run build` green); **W3 automated suite** web `npm test` **36** green (Renee **2026-10-10**). Dex **2026-10-10** R1–R6 + M1/M2 **verified closed** ([DEX-F7-CHECKLIST](./DEX-F7-CHECKLIST-2026-10-10.md)); cursor **`b0c49d8`**. **B-F7-1 dispositioned** Trish **2026-10-10** (fresh migrate + synthetic pre-027 — [F7-MIGRATION-VERIFY](./F7-MIGRATION-VERIFY.md)). F7 Trish Done **10/10/26 OK** — **not Closed** (deferred alias non-goal).
F1–F3: automated suites green; Trish Done **10/10/26 OK** — PARTIAL/limitation rows documented; features **not Closed** where Notes say so.

---

## Setup

- [ ] Compose API (and web) up; household DB reachable
  Dex 2026-10-09 — **PARTIAL:** Disposable local Compose passed; household DB intentionally not exercised.

- [x] `cd apps/api` → `alembic upgrade head` → at least **`023_schedule_outcome_provenance`** (implies F1 `020` + F2 `021` + F3 `022`/`023`)
  Dex 2026-10-09 — **PASS:** Local stack migrated to 023_schedule_outcome_provenance; alembic current confirmed head.

- [x] **F4 rows:** same migrate → head includes **`024_time_map_overrides`**
  Dex 2026-10-09 — **PASS:** Isolated current-working-tree stack migrated to 024_time_map_overrides; alembic current confirms head.

- [ ] **F6 rows:** same migrate → head includes **`025_schedule_previews`** (`schedule_previews` + `user_settings.scheduling_revision`)
  Dex 2026-10-09 — **Disposable fresh only:** F6 evidence migrated an isolated stack to **025**; household daily-driver path **not** verified on this row.

- [x] **F7 rows:** same migrate → head includes **`027_saved_filter_presentation`** (`saved_filters.presentation_json`)
  Dex 2026-10-10 — **PASS (fresh disposable):** [DEX-F7 checklist](./DEX-F7-CHECKLIST-2026-10-10.md) confirmed **027** on isolated upgrade. Trish **2026-10-10** — **B-F7-1 closed (disposition):** fresh + synthetic pre-027 dry-run ([F7-MIGRATION-VERIFY](./F7-MIGRATION-VERIFY.md)); household dump not required.

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

Delivery: [F4-TIME-MAP-OVERRIDES.md](./F4-TIME-MAP-OVERRIDES.md) · **W1** Quality green · **W2** Quality green (**2026-10-09**, Renee) · **W3** Settings + week overlay Dex-verified (Trish/Dex **2026-10-09**); Wave 1 **CLI + day overlay + F4-D** **Dex verified closed** (**2026-10-10**) · **F4 not Closed**

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

### Wave 1 remainder (2026-10-10 — Dex verified closed)

| Item                                                       | Status                                                                                                         |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| CLI `theplan overrides` list/get/create/edit/delete        | **Dex verified closed 2026-10-10** — operator rows checked below                                             |
| Calendar **day-mode** override overlay                     | **Dex verified closed 2026-10-10**                                                                             |
| **F4-D** red precedence, stale schedule indicators, legend | **Dex verified closed 2026-10-10** — red/pins/legend, small-run + **W1-R1** volume stale                       |

### Prior deferred items (resolved or optional)

| Item                                                              | Wave                                                                   |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Override-only edit → stale explanation / schedule indicator       | F4 **W2** — **landed** (manual rows above; Renee pytest **22** green)  |
| DST transition placement matrix                                   | F4 **W2** — **landed** (pytest; optional operator spot-check **open**) |
| Epic/project inherit + task on map B unaffected by map A override | F4 **W2** — **landed** (pytest; manual row above)                      |

### Operator verify — Wave 1 (unchecked = no Dex evidence yet)

- [x] **`theplan overrides list|get|create|edit|delete --map-id …`** round-trip against a real Time Map (Dex real CLI CRUD passed 2026-10-10)
  Page **2026-10-10** — **LOCAL Quality:** `test_overrides_commands.py` green; Dex operator CRUD passed; see DEX-WAVE1-RETEST-2026-10-10.md.

- [x] **Calendar day view:** Time Map overlay shows **Override** badge and effective override bands on days inside an active override range (week view Dex-verified **2026-10-09**)
  Page **2026-10-10** — **Dex PASS 2026-10-10:** active-date bands/badge and next-day base-map fallback verified.

- [x] **F4-D UI:** red band precedence, stale schedule indicator, and legend copy after override-only edits (no auto-replan)
  Page **2026-10-10** — **Dex PASS 2026-10-10:** red overlap, pins/busy legend, small-run stale badge, and **W1-R1** volume stale via **`GET /api/v1/schedule/runs/{run_id}/stale-summary`** + calendar aggregate — **Verified closed** ([DEX-WAVE1-RETEST](./DEX-WAVE1-RETEST-2026-10-10.md), [DEX-IMPORT-VOLUME](./DEX-IMPORT-VOLUME-2026-10-10.md)). Trish Done **10/10/26 OK** — F4 **not Closed** (optional DST).

---

## F5 — Coursera templates

Delivery: [F5-COURSERA-TEMPLATES.md](./F5-COURSERA-TEMPLATES.md) · **W1** Quality green (**14** pytest, Renee) · **W2** CLI landed (local) · **W3** + **B-F5-1** **Dex verified closed** (**IM-R1**; **`ImportPanel`** — Templates / Custom outline tabs) · **F5-B** Quality green (**7** + W1 **14** = **21** API pytest; CLI list/get; IBM apply **417** tasks — Renee) · PARTIAL operator rows remain · **F5 not Closed**

**Dex 2026-10-09:** All seven findings and both residual paths are **verified closed**. Prior rebuilt-image verification: zero API mounts, 62 API tests, web build and live HTTP/CLI checks passed. Final focused browser retest preserved invalid JSON in Raw mode and ignored a delayed obsolete proposal; fresh proposal/apply created one task with one optional skipped. Final web build passed. F5 Trish Done **10/10/26 OK**; remains Open for PARTIAL operator rows below — **not Closed**. See [full evidence](./DEX-F5-MANUAL-2026-10-09.md).

### W1 API + legacy outline (operator / CLI)

- [x] `GET /api/v1/templates` lists **`coursera_specialization`**, **`coursera_course`**, **`coursera_module`**; `GET …/{id}` returns version **1**, `example_outline`, and scaffold flag where applicable
  Dex 2026-10-09 — **PASS:** Three IDs, v1 examples/scaffold flags verified on rebuilt image **without** testdata mount. **P1 Verified closed** — examples packaged under `apps/api/app/data/outlines`.

- [x] **`coursera_specialization`:** propose + apply tiny outline → epic / project / section / task tree; **`skip_optional`** reduces task count; second apply with **same** idempotency key → `replayed: true`; **new** key → second epic instance
  Dex 2026-10-09 — **PASS (HTTP):** Tiny specialization tree, optional exclusion, same-key replay, and new-key second instance verified. **P2 Verified closed** — idempotency key retained pre-apply for retry (Dex retest).

- [x] **`coursera_course`:** standalone `{ "course": … }` → project-only root; graft under existing epic → project under that epic; certificate-shaped JSON rejected with readable error
  Dex 2026-10-09 — **PASS (HTTP):** Standalone project, existing-epic graft, and certificate-shape rejection verified.

- [x] **`coursera_module`:** requires **`attach_under`** project or section; project attach creates section + tasks; section attach adds tasks only; missing attach → **422** `TEMPLATE_ATTACH_REQUIRED`
  Dex 2026-10-09 — **PASS (HTTP/CLI):** Required parent validation, project and section grafts verified. **P2 Verified closed** — module picker targets standalone projects (Dex retest).

- [x] Template receipt: `GET /api/v1/templates/receipts/by-key/{key}` returns apply result; same key under **`/handoffs/receipts/by-key`** → **404**
  Dex 2026-10-09 — **PASS (HTTP):** Matching template receipt; same key under handoff receipts returns 404.

- [x] Legacy **`POST /api/v1/outlines/propose`** with IBM RAG fixture still succeeds; **`POST /api/v1/templates/coursera_specialization/propose`** on same file matches legacy **summary** counts (outline path still **non-idempotent** on apply)
  Dex 2026-10-09 — **PASS (HTTP + pytest):** IBM proposal summaries match; template apply created 417 tasks. Legacy outline regressions pass.

### W2 CLI

- [x] `theplan templates list` and `get coursera_specialization` (text + JSON output)
  Dex 2026-10-09 — **PASS (actual CLI):** Catalog and specialization detail in text and JSON verified against isolated API.

- [x] `theplan templates propose coursera_module --file … --attach-kind project --attach-id …` then `apply … --idempotency-key …`; `templates receipt --idempotency-key …` matches apply JSON; replay on repeat apply
  Dex 2026-10-09 — **PASS (actual CLI):** Module project graft, apply, by-key receipt equality, and repeat replay verified.

### W3 web (Import shell — B-F5-1)

- [x] **Import** modal: **Templates** tab (Coursera catalog) and **Custom outline** tab in one shell; example JSON download; modest form for common fields; raw JSON still works; blank scaffold visibly distinct from imported syllabus
  Dex 2026-10-09 — **PARTIAL (browser, pre-merge):** Separate pickers; Raw↔Quick sync, invalid-draft preservation, and scaffold classification pass. **Page 2026-10-10:** **B-F5-1 Dex verified closed** — unified [`ImportPanel`](../../apps/web/src/components/ImportPanel.tsx); **IM-R1** tab draft/review/receipt retention ([DEX-IMPORT-VOLUME](./DEX-IMPORT-VOLUME-2026-10-10.md)). Download-event capture timed out; upload not exercised.

- [x] Propose/apply uses **`/templates/*`** (not `/outlines/apply`); optional-item toggle in review; source refs / warnings surfaced before apply
  Dex 2026-10-09 — **PARTIAL:** Templates API route confirmed; browser apply/receipt/replay pass. Both settled-input and in-flight stale-preview paths verified closed. Full source-reference/warning presentation remains open.

### F5-B spot-checks (expand as UX lands)

- [x] Task labels from outline `task_type` (+ optional) visible after apply; durations match supplied `duration_minutes` (defaults disclosed on propose, not invented catalog durations)
  Dex 2026-10-09 — **PARTIAL (HTTP/pytest/browser):** Supplied 17-minute duration retained; labels covered by API tests. Browser review verified explicit 17m and settings-derived 30m. Post-apply label visibility remains API-tested, not browser signed off.

- [x] Duplicate Coursera URL on propose warns; apply still creates a **new** instance (no merge)
  Dex 2026-10-09 — **PASS (HTTP):** Duplicate source URL warns; fresh-key apply creates another instance without merge.

---

## F6 — Replan preview

Delivery: [F6-REPLAN-PREVIEW.md](./F6-REPLAN-PREVIEW.md) · **W1–W2** Quality green (**24** pytest: **9** + **15**, Renee **2026-10-09**) · **W3 conditional go** — **Preview changes** modal (Andi), CLI preview create/get/apply (Tesla, local) · **F6-B–D** not fully accepted · manual rows below **open** · **F6 not Closed**, **not pushed**

**Dex 2026-10-09:** Frozen F6 over `094663f`; disposable migration **025** (fresh only), 47 API tests, 37 CLI tests, web build, and focused live/browser checks — see [Dex evidence](./DEX-F6-MANUAL-2026-10-09.md). **Dex retest:** **three P2s Verified closed** (moved **diff_counts**, planning lead / available-now apply, overlapping receipt replay); archive P1 closed. **Wave 1 retest 2026-10-10:** P1 R1 — project **`epic_id`** reparent/detach + epic **`target_date`** lock+bump — **Verified closed** ([DEX-WAVE1-RETEST](./DEX-WAVE1-RETEST-2026-10-10.md), **37** API integration tests incl. `test_reparent_during_apply_waits_for_owner_lock`). Daily-driver untouched. Known project-delete orphan behavior remains separately disclosed.

### W1 preview (API — no live schedule writes)

- [x] **`POST /api/v1/schedule/previews`** → **202** `running`; poll **`GET …/{id}`** until **`ready`** (or **`failed`** with `error_message`). Live **`scheduled_blocks`** / task schedule fields unchanged vs snapshot before apply
  Dex 2026-10-09 — PASS (HTTP): 202/running to ready; exact live block list and task response unchanged.

- [x] **`ready`** preview shows **`proposal`** (`before_blocks`, `proposed_blocks`, `outcomes`), **`diff_counts`**, **`expires_at`** ≈ **`evaluated_at` + 15m**, **`input_fingerprint`**, **`scheduling_revision`**
  Dex 2026-10-09 — **Verified closed (Dex retest):** Proposal fields, 15-minute TTL, and moved **diff_counts** match before/after lists.

- [x] Edit task **duration** (or scheduling-relevant field) after **`ready`** → next **`GET`** shows **`stale`**; **`proposal`** still returned for inspection; no auto-replan
  Dex 2026-10-09 — PASS (HTTP): Duration change gives stale GET with proposal retained and no automatic replan.

- [x] Force **`expires_at`** in the past (or wait past TTL) → **`GET`** promotes **`expired`**; domain schedule still unchanged
  Dex 2026-10-09 — AUTOMATED PASS: Forced expiry path passed pytest; separate operator expiry check not performed.

- [x] Start **`POST /schedule/replan`** while a preview is **`running`** or **`ready`** — preview admission still succeeds (preview is not blocked by migration **018** one-running-replan)
  Dex 2026-10-09 — AUTOMATED PASS: Preview admission/replan independence passed pytest; separate live admission check not performed.

### W2 apply (API)

- [x] **`POST /api/v1/schedule/previews/{id}/apply`** on **`ready`** preview → **200** receipt (`schedule_run_id`, counts); calendar blocks match **`proposed_blocks`**; second apply → same receipt (idempotent)
  Dex 2026-10-09 — **Verified closed (Dex retest):** Future-dated apply, available-now apply with **planning lead**, sequential receipt replay, and overlapping duplicate idempotent replay.

- [x] Change scheduling inputs after **`ready`**, then apply → **409** **`PREVIEW_STALE`** with **`stale_categories`**; live schedule unchanged
  Dex 2026-10-09 — PARTIAL: Committed duration edit rejects with named category and no writes; browser offers fresh preview. Archive race **Verified closed** (Dex). Epic reparent / **`target_date`** serialization — **Verified closed** Wave 1 retest **2026-10-10** ([DEX-WAVE1-RETEST](./DEX-WAVE1-RETEST-2026-10-10.md)).

- [x] Apply on **`expired`** or non-**`ready`** preview → **409** **`PREVIEW_EXPIRED`** or **`PREVIEW_NOT_APPLICABLE`** as appropriate
  Dex 2026-10-09 — AUTOMATED PASS: Expiry/non-ready rejection covered by pytest; live available-now proposal returns PREVIEW_PAST_BLOCKS.

- [x] While direct replan is **`running`**, apply → **409** **`SCHEDULE_RUN_IN_PROGRESS`**
  Dex 2026-10-09 — AUTOMATED PASS: Running replan conflict covered by pytest; separate live concurrency gate not exercised.

- [x] Second authenticated owner: foreign preview **GET** / apply → **404** (no leak)
  Dex 2026-10-09 — AUTOMATED PASS: Foreign/missing owner behavior covered by pytest; second authenticated live owner not exercised.

### Deferred (do not block W1/W2 API sign-off here)

| Item                                                      | Wave                                                                             |
| --------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Web **Preview changes** modal (before/after, diff counts) | **W3 landed (Andi, local)** — operator verify + any apply-in-web polish **open** |
| CLI `theplan schedule preview` create / get / apply       | **W3 landed (Tesla, local)** — operator verify **open**                          |
| Selective per-block apply; multi-scenario compare         | Out of scope (spec design default)                                               |
| Unsaved hypothetical Time Map edits in preview            | Later extension                                                                  |

---

## F7 — Saved views

**Checklist execution 2026-10-10:** **23 rows verified** (11 HTTP, 5 CLI, 7 browser). [Full evidence](DEX-F7-CHECKLIST-2026-10-10.md) — M1/M2 **Verified closed** Dex+Trish same day. Checkmarks are Dex evidence; Trish sign-off **10/10/26 OK** in [§ Sign-off](#sign-off).

**Focused fix retest, 2026-10-10:** R1–R6 verified closed by Dex in a rebuilt disposable instance: successive board moves, counts after reload, incomplete-date rejection with retained draft, exact absolute-bound preservation, completed-only membership, and rename with omitted completion. Adapter **6**, API **64**, CLI/main smoke **32**, build green. [Retest details](DEX-F7-MANUAL-2026-10-10.md#focused-retest-evidence). **W3 completion gaps** (load-more, presentation PATCH/sort, sidebar reorder) **Verified closed** Dex+Trish **2026-10-10**; cursor **`b0c49d8`**. **W3 automated suite:** web `npm test` **36** green (Renee **2026-10-10**). **B-F7-1 closed (disposition)** Trish **2026-10-10**; Trish Wave 1 verification **10/10/26 OK** — feature **not Closed** (non-goal alias).

**Dex local pass 2026-10-10:** [Detailed report](DEX-F7-MANUAL-2026-10-10.md). API **64/64**, CLI + main smoke **32/32**, frontend build green. Actual CLI list/create/get/query/patch/delete exercised against the disposable API. Browser verified saved sidebar selection, persisted Board mode, load-more, mode PATCH, saved sort (M1), and sidebar reorder (M2). **R1–R6** and **M1/M2 verified closed**. No daily-driver changes.

Delivery: [F7-SAVED-VIEWS.md](./F7-SAVED-VIEWS.md) · **W1** Quality green (**64** API pytest; Renee **2026-10-10**) · **W2** CLI **implemented** (tests green) · **W3** web **implemented** (build green; **npm test** **36** green; M1/M2 verified closed) · **F7 not Closed**

### W1 API (operator / HTTP)

- [x] `alembic upgrade head` → **`027_saved_filter_presentation`**; bootstrap user has system views **`inbox`**, **`today`**, **`upcoming`** with **`predicate_json.v === 1`**

- [x] **`GET /api/v1/views`** — system rows first (`is_system`), user views by `sort_order`; each row includes `id`, `slug`, `presentation_json`

- [x] **`POST /api/v1/views`** — create user view with mixed dimensions + `presentation_json`; **`GET /api/v1/views/{id}`** round-trip; **`PATCH`** rename / predicate / `sort_order`; **`DELETE`** → **204** and tasks remain

- [x] **`PATCH` / `DELETE`** on system **`inbox`** → **403** **`SYSTEM_VIEW_READ_ONLY`**; foreign view id → **404**

- [x] **`GET /api/v1/views/by-slug/inbox/tasks`** and **`GET …/{inbox_id}/tasks`** — same `total`; pagination fields present; inbox task has `project_id` null and open

- [x] **`GET …/views/{id}/tasks?sort=-due_at`** — allowlisted sort applied; bad sort (e.g. `?sort=foo`) → **422** **`INVALID_SORT`**; with **`board_order=true`**, presentation/`sort` ignored (board rank order)

- [x] **`PATCH /api/v1/views/{id}`** with partial **`presentation_json`** (e.g. `{ "mode": "board" }`) — shallow-merge keeps other keys; invalid `mode` → **422** **`INVALID_PRESENTATION`**

- [x] Invalid / legacy predicate on create → **422** **`INVALID_PREDICATE`**; **`inbox` + `project_ids`** together → **422**

- [x] Predicate referencing deleted project or label → **`items: []`**, **`invalid_references`** populated (not full task list)

- [x] Change **`user_settings.timezone`**, re-query **`today`** / **`upcoming`** slug tasks — rolling boundaries follow settings TZ (not browser local)

- [x] Labels filter: create view with **`labels.match: all`** vs **`any`** — result sets differ as expected for multi-label tasks

### W2 CLI

- [x] `theplan views list` — system + user rows; JSON includes `id`, `slug`, `presentation_json`, `is_system`

- [x] `theplan views get --id …` round-trip after create

- [x] `theplan views create --stdin` (or `--file`) with v1 `predicate_json` + optional `presentation_json`; `patch --id … --stdin`; `delete --id …` on user view — tasks unchanged

- [x] `theplan views query --id …` and `views query --slug inbox` — `total`, `limit`, `offset` match API; optional `--board-order`

- [x] Patch/delete system **`inbox`** → stable **`SYSTEM_VIEW_READ_ONLY`** (CLI exit **2**)

### W3 web

- [x] Sidebar shows **user saved views** from API; selecting one loads tasks (not ad hoc `GET /tasks` only)

- [x] **Save view** / filter builder creates or updates a user view with mixed dimensions (labels any/all spot-check)

- [x] List/Board toggle on a **saved view** — **PATCHes** `presentation_json.mode`; reload honors server mode (Dex verified 2026-10-10)

- [x] Predicate with deleted project/label → empty list + **repair** affordance (not full task list)

- [x] Saved-view **Load more** when `total` exceeds first page — list **200** / board **500**; appended rows match API offset (Dex verified 2026-10-10)

- [x] Sidebar **user saved views** — **up/down** reorder persists `sort_order` via PATCH; order survives reload. **PASS M2 retest 2026-10-10:** equal-rank Up and Down swap only displayed neighbors; edge buttons and reload verified.

- [x] **Saved task sort in browser:** **PASS M1 retest 2026-10-10.** Title Z–A peer order matches API; children remain beneath their parent with Z–A sibling order; reload verified.

- [x] **Representative existing-data migration:** **B-F7-1 closed (disposition, Trish 2026-10-10):** Dex **fresh** migrate to **027** + Tesla **synthetic pre-027** dry-run ([F7-MIGRATION-VERIFY](./F7-MIGRATION-VERIFY.md)); household dump not required.

### Deferred / non-goals (still open)

| Item                                     | Status                                                                                                                    |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **`GET /tasks?view=`** convenience alias | Not implemented — use `/views/…/tasks`                                                                                    |
| Automated **W3** regression suite        | **Quality green (2026-10-10):** web `npm test` **36** — Renee exit; Trish Done **10/10/26 OK**; F7 **not Closed** (non-goal alias) |

---

## Not on this gate (parked)

Do not block F1–F3 close on these; they live elsewhere:

| Item                                                              | Where                                                               |
| ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| Prerequisite explanations show UUIDs (want titles)                | F3 backlog — final polish pass                                      |
| Overbooked copy mentions deadlines when blocker is a prerequisite | F3 backlog — final polish pass                                      |
| `priority_ups` stale compare                                      | F3 W3                                                               |
| `time_map_overrides` stale compare + snapshot v3 fingerprint      | F4 W2 — **landed**; Renee Quality green; operator manual still open |
| Schedule-run summary web UI                                       | F3 W3 / later                                                       |
| Full F2-D a11y/touch matrix beyond Move-to Space                  | F2 known limitations                                                |
| DEF-028 calendar mirror delete recovery                           | Closed 2026-10-09 — tombstone + sync retry                          |

---

## Sign-off

Trish authorized Page to record Done **2026-10-10** for Setup–F7 (Wave 1 delivery verification). Done = human acceptance of this table; Notes still govern **Closed/shipped** vs PARTIAL residue.

When a section is done, note date + “ok” here:

| Wave  | Done                             | Notes                                                                                                                                                                                                                                                                                                                                                                                        |
| ----- | -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Setup | 10/10/26 OK                      | Disposable Compose PARTIAL (2026-10-09); alembic **023/024** Dex PASS; **027** **B-F7-1 closed** Trish **2026-10-10** (fresh + synthetic); **025** still fresh-disposable only (F6 R1 / household path **Open**)                                                                                                                                                                             |
| F1    | 10/10/26 OK                      | Dex evidence 2026-10-09; automated green — **not Closed** where unchecked rows remain optional rerun                                                                                                                                                                                                                                                                                         |
| F2    | 10/10/26 OK                      | PARTIAL rows (archived picker, Space dropdown, drag peer/Done) documented — **not Closed**                                                                                                                                                                                                                                                                                                   |
| F3    | 10/10/26 OK                      | Automated suites green; operator/manual rows mixed — **not Closed**                                                                                                                                                                                                                                                                                                                          |
| F4    | 10/10/26 OK                      | W1/W2 Quality green; W3 Settings + week Dex-verified **2026-10-09**; Wave 1 CLI + day + F4-D **Dex verified closed 2026-10-10** incl. **W1-R1** volume stale; optional DST browser open — **not Closed**                                                                                                                                                                                    |
| F5    | 10/10/26 OK                      | W1/W3/F5-B Quality green; Dex all seven findings + residuals **Verified closed**; **B-F5-1 Import merge retested: IM-R1 verified closed**; PARTIAL operator rows (download, source-ref presentation, post-apply labels) — **not Closed**, **not pushed**                                                                                                                                     |
| F6    | 10/10/26 OK                      | W1–W2 Quality **24** pytest green; W3 modal + CLI landed; Dex **3 P2s + archive P1 + P1 R1 Verified closed** (Wave 1 retest **2026-10-10**); F6-B–D not fully accepted — **not Closed**, **not pushed**                                                                                                                                                                                      |
| F7    | 10/10/26 OK                      | Dex **2026-10-10:** 23 rows; R1–R6 + M1/M2 + W3 completion **Verified closed** (`b0c49d8`). **W3 automated suite** **36** green (Renee). **B-F7-1 closed (disposition)** Trish **2026-10-10** (fresh + synthetic). Trish Wave 1 verification complete — **not Closed/shipped** (deferred `GET /tasks?view=` non-goal) — [DEX-F7-CHECKLIST](./DEX-F7-CHECKLIST-2026-10-10.md). |
