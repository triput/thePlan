# Defects log

**Filename:** DEFECTS.md

**Last modified:** 2026-10-12

**File version:** 1.2

Open product defects that are not wave exit blockers. Priority here is **product severity** (P1–P4), not task priority enum.

---

## DEF-001 — Subtasks added out of sequence appear at list bottom

| Field | Value |
|-------|--------|
| **Severity** | **P2** (mental tax / hierarchy trust; not data loss) |
| **Status** | Closed — shipped 2026-08-27 |
| **Found** | 2026-08-10 |
| **Surface** | Project / Inbox task lists (`TaskList`) |
| **Wave** | Afternoon smash 2026-08-27 |

### Symptom

Parenting is correct in the data model (`parent_task_id` / `nesting_level`), but the **visual list order** follows global create order (`sort_order`, then `created_at`), not tree order under the parent.

Repro:

1. Create task A with subtasks A1, A2.
2. Create task B with several children (and optionally a nested child).
3. Return to A (or A2) and use **+** to add another child / grandchild.
4. New row is indented correctly but renders at the **bottom** of the list (after B’s branch), not under A.

Screenshot evidence: out-of-order children named like “Spec 2 b.1” / “Spec 2 b.2” appear under later top-level tasks while still indented as if under Spec 2 b.

### Root cause (likely)

`GET /tasks` and the list UI treat the project as a **flat** sequence ordered by `Task.sort_order, Task.created_at`. New tasks often share default `sort_order` (0), so **`created_at` wins** → entry order. Indent uses `nesting_level` only; there is no DFS / “parent then children” layout pass in `TaskList`.

Reorder controls can assign distinct `sort_order` values, which is why in-order entry *looks* fine until you insert under an earlier parent.

### Fix (shipped)

Client forest DFS in `taskForest.ts` / `TaskList`: parent then children by sibling `sort_order` then `id`. Optional API sibling `sort_order` on create still deferred.
---

## DEF-002 — Timezone setting is free-text, not a picker

| Field | Value |
|-------|--------|
| **Severity** | **P4** (UX polish; IANA text works) |
| **Status** | Closed — shipped 2026-08-27 |
| **Found** | 2026-08-11 |
| **Surface** | Settings → Scheduling defaults → Timezone |
| **Wave** | Round 2 smash 2026-08-27 |

### Symptom

Timezone is a free-text field. Easy to typo; no discoverability of valid IANA zones.

### Expected

Dropdown (searchable preferred) of common/valid IANA timezones; still store the same string on `user_settings.timezone`.

### Fix (shipped)

Searchable `TimezonePicker` combobox (`Intl.supportedValuesOf('timeZone')` + fallback list); still PATCHes `user_settings.timezone`.

### Notes

Bundle with other small Settings/UI fixes when convenient. Not a Settings expansion exit blocker.

---

## DEF-003 — Mobile task detail: content below deadline clipped, no scroll

| Field | Value |
|-------|--------|
| **Severity** | **P2** (detail unusable on phone for long tasks) |
| **Status** | Closed — shipped 2026-08-27 |
| **Found** | 2026-08-14 |
| **Surface** | Task detail sheet / panel on narrow (mobile) viewport |
| **Wave** | Afternoon smash 2026-08-27 |

### Symptom

On mobile web, opening a task’s detail view shows content through **deadline**, but nothing below is reachable — cannot scroll the detail body.

### Expected

Detail sheet scrolls so fields below deadline (notes, Time Map, Plan, reminders, etc.) are reachable.

### Fix (shipped)

Mobile `.task-detail-panel` / sheet: `100dvh` flex column, `min-height: 0` + `overflow-y: auto` on `.detail-form-body`; sticky Save footer preserved (DEF-016).
---

## DEF-004 — Inbox up/down reorder arrows do nothing

| Field | Value |
|-------|--------|
| **Severity** | **P3** (controls present but inert; workarounds exist) |
| **Status** | Closed — shipped 2026-08-27 |
| **Found** | 2026-08-14 |
| **Surface** | Inbox task list reorder arrows |
| **Wave** | Round 2 smash 2026-08-27 |

### Symptom

Up/down move arrows in the **Inbox** view do not change task order (no visible reorder; likely no successful `sort_order` swap).

### Expected

Arrows swap sibling/`sort_order` with adjacent visible rows (same behavior as other list views that reorder correctly), or arrows are hidden if Inbox intentionally has no reorder.

### Fix (shipped)

Equal sibling `sort_order` values (common Inbox default `0`) made swaps no-ops. `buildReorderSwap` now renumbers the sibling group `0..n-1` after a move when adjacent values are equal; display order ties broken by id.

---

## DEF-006 — NL due times: 24-hour clock and broader datetime forms

| Field | Value |
|-------|--------|
| **Severity** | **P3** (required eventually; not blocking daily driver) |
| **Status** | Closed — Assist honesty cut 2026-08-14; **Round 3 verified 2026-08-27** (no reopen) |
| **Found** | 2026-08-14 |
| **Surface** | Quick-add + Assist enrich (`apps/api/app/services/quick_add.py`; Assist uses same parser) |
| **Wave** | Assist honesty cut (DEF-006 + DEF-007 + review UI) |

### Symptom / gap

Relative phrases like `tonight` / `tomorrow` and `at 9PM` work after recent Assist work. **24-hour and alternate datetime entry** are incomplete or unproven as a product surface:

- Prefer explicit support for `at 21:00`, `at 21:00`, bare `21:00`, and unambiguous 24h without requiring `am`/`pm`.
- Broader forms operators actually type (locale-ish dates, `9pm` without `at`, `2100`, ISO local, etc.) should be inventoried and covered deliberately — not “whatever the SLM invents.”

### Current behavior (partial)

`TIME_AT_PATTERN` is `at <hour>[:mm][am|pm]?`. Hour without meridiem can already be 0–23 in `_parse_at_time`, so **`at 21:00` may work**, but coverage is thin and undocumented; Assist still depends on this shared parser for reliable due enrichment.

### Expected

Documented, tested NL due/time grammar for quick-add **and** Assist enrich: 12h and 24h, common separators, and a short allowlist of date forms — same rules both paths.

### Notes

Non-urgent but **required** before treating Assist time understanding as “done.” Prefer extending the deterministic parser over hoping the SLM formats ISO correctly.

---

## DEF-007 — NL duration (and Assist defaulting to 30m)

| Field | Value |
|-------|--------|
| **Severity** | **P3** (required eventually; wrong estimates train bad habits) |
| **Status** | Closed — Assist honesty cut 2026-08-14; **Round 3 verified 2026-08-27** (no reopen) |
| **Found** | 2026-08-14 |
| **Surface** | Quick-add duration tokens + Assist propose/enrich/apply |
| **Wave** | Assist honesty cut (pair with DEF-006) |

### Symptom

Operator asked Assist roughly: schedule/do something **at 8PM**, **duration 60 minutes**. Result used the **default 30 minutes** (and in this case landed at **9** instead of 8 — treat time skew as related until reproduced).

### Current behavior (partial)

- Compact quick-add tokens like `60m` / `1h` already parse into `estimated_duration_minutes`.
- Prose such as **“duration 60 minutes”** / **“for an hour”** is **not** covered by `DURATION_PATTERN`.
- Assist enrich only fills duration when the deterministic parser finds it; otherwise apply uses user settings default (often 30).
- Assist prove-it still creates **tasks** (`due_at` + estimate), not calendar `scheduled_blocks`. “Schedule at 8PM” is interpreted as due/time cues, not a pinned block — call that out if product wants block creation later (out of ADR-010 prove-it).

### Expected

- Deterministic NL understands common duration phrasings (and keeps compact `60m`/`1h`).
- Assist propose/review/apply preserve that duration so Approve does not silently fall back to 30.
- Document whether “schedule at …” means **due** vs **scheduled_block** once duration work lands.

### Notes

Non-urgent but **required**. Prefer parser + enrich (same path as DEF-006) over prompt-only.

---

## DEF-005 — Mobile layout: word-tower / crushed flex columns (Inbox + Settings)


| Field | Value |
|-------|--------|
| **Severity** | **P2** (Inbox + Settings unreadable on phone) |
| **Status** | Fixed 2026-08-14 |
| **Found** | 2026-08-14 |
| **Surface** | Narrow viewport — task rows, Settings Google Calendar / subscriptions |
| **Wave** | Hotfix (not W3 derail) |

### Symptom

On mobile Chrome, task titles and Settings calendar copy wrapped one word per line; subscription “Primary” controls overlapped checkboxes.

### Root cause

W1.6 touch-target rule applied `min-width/min-height: 2.75rem` to **all** `.icon-btn`, so reorder/subtask buttons stole horizontal space from `.task-title`. Calendar account rows used `flex: 1; min-width: 0` beside Sync/Disconnect, so the info column shrunk instead of wrapping.

### Fix

Scope large touch targets to chrome (header/nav); keep smaller targets on task-row icons; stack calendar account rows and wrap subscription Primary under the label on narrow viewports.

---

## DEF-008 — Resizable task detail (right) panel

| Field | Value |
|-------|--------|
| **Severity** | **P3** (useful polish; fixed ~340px is workable) |
| **Status** | Closed — shipped 2026-08-27 |
| **Found** | 2026-08-14 |
| **Surface** | Task detail panel (`.task-detail-panel` / sheet) — desktop/wide layout |
| **Wave** | Round 2 smash 2026-08-27 |

### Symptom / ask

Operator wants to **drag the left edge** of the right-hand task detail sidebar to widen/narrow it when needed (long descriptions, dense forms). Fixed width (~340px in `App.css`) is fine as default but not adjustable.

### Expected

- Grab handle / edge drag on the panel’s inner (left) border.
- Persist preferred width (e.g. `localStorage`) with sensible min/max clamps.
- Narrow/mobile sheet behavior unchanged (full-bleed / overlay stays as today).

### Fix (shipped)

Left-edge resize handle; width in `localStorage` (`theplan.taskDetail.width`) + CSS var `--task-detail-width`; clamps; mobile sheet ignores resize.

### Notes

Not urgent. Drag-resize only — no need for dual-panel fancy layouts in this item.

---

## DEF-009 — Outline import into existing hierarchy (partial / lower-level)

| Field | Value |
|-------|--------|
| **Severity** | **P3** (prove-it full-tree import covers first land; grafting is the next real pain) |
| **Status** | **Closed** — shipped 2026-08-27 (Theme F polish) |
| **Found** | 2026-08-14 |
| **Surface** | Outline ingest (`/outlines/propose|apply`, Outline UI) — Theme F follow-on |
| **Wave** | Theme F polish / bug bash (after ADR-011 prove-it) |

### Symptom / ask

Current outline import always proposes a **full** certificate → epic → courses → modules → tasks tree. Operator wants **lower-level imports**, e.g. a single course (or module) landing as a **project under an existing epic**, without creating a duplicate specialization epic.

### Expected (when built)

- Propose/apply can target an existing parent: at least **epic** (import course(s) as projects + nested sections/tasks); ideally also **project** (modules → sections) and maybe **section** (tasks only).
- UI: pick target epic/project (or paste outline that is a course/module subtree) before Propose.
- Same review → confirm → apply; still no Coursera client; dedupe remains separate ([ADR-011](./adr/ADR-011-templates-outline-ingest.md) non-goal until booked).

### Fix / current behavior

- `POST /outlines/propose` accepts `attach_under: { kind, id }` (`epic` | `project` | `section`). Apply reuses existing parent ids on actions (`epic_id`, `project_id`, `section_id`) instead of always minting a new epic tree.
- Fragment shapes: `course` / `courses` → projects + sections + tasks under an **epic**; `modules` → sections + tasks under a **project**; task list → tasks under a **section**. Full `certificate` import still creates a new epic when `attach_under` is omitted.
- Outline UI: **Attach under** picker (new epic vs existing epic/project/section) + template selector; after graft apply, navigates to the target epic when applicable.
- Tests: `tests/test_outlines.py` (graft propose/apply under epic, project, section).

---

## DEF-010 — Blank / generic outline template (non-Coursera bulk adds)

| Field | Value |
|-------|--------|
| **Severity** | **P3** (Coursera fixture proves the path; blank template is operator courtesy) |
| **Status** | **Closed** — shipped 2026-08-27 (Theme F polish) |
| **Found** | 2026-08-14 |
| **Surface** | Theme F outline ingest — docs + fixture under `testdata/outlines/`; pack id in API |
| **Wave** | Theme F polish (before or with full W4 template catalog) |

### Symptom / ask

Prove-it ships `coursera_specialization` + one golden JSON. Operator wants a **clear, fillable template** (and docs) for other bulk hierarchy adds that are not Coursera — so Theme F is not “half the job” ending at one specialization.

### Expected (when built)

- Blank outline JSON (and short fill guide) matching the v1 contract: root → children → modules/sections → tasks with `task_type` / `duration_minutes` / `optional` / order.
- Either document that `coursera_specialization` already accepts any JSON in that shape, or add a neutral pack alias (e.g. `hierarchy_v1`) that shares the same mapper.
- Point to it from [OUTLINE-INGEST.md](./OUTLINE-INGEST.md) and `testdata/outlines/README.md`.

### Fix / current behavior

- [`blank_hierarchy_v1.json`](../testdata/outlines/blank_hierarchy_v1.json) — fillable v1 contract (certificate → courses → modules → tasks); fill guide in [`testdata/outlines/README.md`](../testdata/outlines/README.md).
- Template pack **`hierarchy_v1`** — neutral alias sharing the same mapper/validator as `coursera_specialization` (Coursera-specific label cleanup only on the Coursera pack id).
- Outline UI template selector lists **Generic hierarchy (v1)** and **Coursera specialization**; either pack accepts the same JSON shape.
- Operator docs: [OUTLINE-INGEST.md](./OUTLINE-INGEST.md); tests include `test_propose_hierarchy_v1_alias`.

---

## DEF-011 — Refactor assessment (modularize / de-mix layers)

| Field | Value |
|-------|--------|
| **Severity** | **P3** (gut-check hygiene; not a known break) |
| **Status** | Closed — assessment shipped 2026-08-27; **greenlit Cut wave:** #1–#8 **implemented** (#6–#8 **2026-10-08**); operator UI smoke on cuts #1–#5, #8 ([REFACTOR-ASSESSMENT.md](./REFACTOR-ASSESSMENT.md)) |
| **Found** | 2026-08-14 |
| **Surface** | Cross-cutting — API services vs routes vs web components (esp. large files) |
| **Wave** | Round 4 docs — after smash rounds; paired with [HYGIENE-R4-QUICKSCAN.md](./HYGIENE-R4-QUICKSCAN.md) |

### Symptom / ask

Operator gut: some files may house **too many vectors** (UI + orchestration + domain rules), and **business logic may be showing up where it doesn’t belong**. Want a deliberate **refactor assessment** — not a blind rewrite — to see if modularization or layer cleanup is warranted.

### Current behavior (assessment + Cut wave #1–#5)

Durable inventory + classification + ordered cut list: **[REFACTOR-ASSESSMENT.md](./REFACTOR-ASSESSMENT.md)**. Hotspots sized (SettingsPanel / App.css / TaskDetail / Calendar / TaskList tops). Verdict: fat React surfaces + monolith models/schemas; domain mostly still in API services.

**Greenlit structure-only wave (2026-08-27):**

| Cut | Landed | Evidence |
|-----|--------|----------|
| #1 TaskList batch bar → `TaskBatchBar.tsx` | Yes | `npx tsc -b` PASS |
| #2 TaskDetail sections → child components | Yes | tsc PASS |
| #3 PATCH/batch rules → `task_patch.py` | Yes | pytest **41/41 PASS** |
| #4 Calendar toolbar + block menu extract | Yes | tsc PASS |
| #5 SettingsPanel → `components/settings/*` | Yes | tsc PASS |

UI cuts (#1, #2, #4, #5): **manual smoke still operator-owned** — not claimed Closed on visual regression.

**Also landed (2026-10-08):** Cuts **#6** (schemas), **#7** (models domain modules + barrel), **#8** (`styles/*` + App.css barrel). Full API pytest **273/273** after #7; `npm run build` after #8.

### Expected (when run)

1. Inventory hotspots (oversized modules, mixed concerns: e.g. fat `TaskList` / `App.css` / route handlers doing domain work). **Done.**
2. Classify: keep / extract service / extract component / leave alone. **Done.**
3. Propose a short ordered cut list (if any) with risk notes — **no drive-by mega-refactor**. **Done.**
4. Operator greenlight before mutating refactor wave. **Done for #1–#8** (operator smoke on #1–#5 and **#8** checked **2026-10-08** — [REFACTOR-ASSESSMENT.md](./REFACTOR-ASSESSMENT.md)).

### Notes

Triggered by intuition after rapid Theme F / Assist growth, not by a concrete defect. Assessment first; code moves only after explicit greenlight. Separate from feature DEF-008–010. Pair with [DEF-012](./DEFECTS.md#def-012--living-technical-architecture--diagrams-catch-up) / [09-technical-architecture.md](./09-technical-architecture.md) when mapping hotspots.

---

## DEF-012 — Living technical architecture + diagrams (catch-up)

| Field | Value |
|-------|--------|
| **Severity** | **P3** (docs debt; product works without it) |
| **Status** | Closed — Round 4 catch-up 2026-08-27 (living doc; update on topology change) |
| **Found** | 2026-08-14 |
| **Surface** | [09-technical-architecture.md](./09-technical-architecture.md) (+ index in [README.md](./README.md)) |
| **Wave** | Round 4 docs hygiene |

### Symptom / ask

Wave 1 doc package + ADRs existed, but organic growth (W2/W3/Assist/Theme F) left no single **current** system map. Operator wants a hangable architecture page with **diagrams**, knowing it will keep growing.

### Current behavior (Round 4)

[09-technical-architecture.md](./09-technical-architecture.md) updated for smash surfaces: bundles (ADR-012), soft-delete/trash + purge-older, batch edit, promote/demote, outline graft; Mermaid quick map §9b; links to [REFACTOR-ASSESSMENT.md](./REFACTOR-ASSESSMENT.md) + hygiene.

### Expected

- Keep [09-technical-architecture.md](./09-technical-architecture.md) current: runtime topology, layering rules, major pipelines, pointers into code/docs.
- Add diagrams as needed (auth, calendar sync, Update Schedule, …).
- Optionally sync stale lines in functional spec / API contract / feature catalog in the same passes—not a big-bang rewrite.

### Notes

Initial draft shipped with Mermaid: topology, layers, hierarchy, capture pipelines. Not a substitute for ADRs or the functional spec. Reopen when topology/pipelines drift again.

---

## DEF-013 — File headers across api/web hotspots

| Field | Value |
|-------|--------|
| **Severity** | **P3** (convention / readability; product works without it) |
| **Status** | Closed — Round 4 opportunistic pass 2026-08-27; convention remains for future touches |
| **Found** | 2026-08-14 |
| **Surface** | Source modules under `apps/api`, `apps/web` — see [dev/FILE-HEADERS.md](./dev/FILE-HEADERS.md) |
| **Wave** | Round 4 hygiene chore |

### Symptom / ask

Operator wants proper module/file headers (short info blocks) as a house quirk. Not huge yet, but the convention should be real — not vaporware.

### Current behavior

Convention in [dev/FILE-HEADERS.md](./dev/FILE-HEADERS.md). Starter set + Round 4 headers on remaining quiet hotspots (`Sidebar`, settings route already had purpose lines; Wave A files kept existing/ADR headers). Not a mass rewrite of every file.

### Expected

- Follow [dev/FILE-HEADERS.md](./dev/FILE-HEADERS.md): Python module docstrings (purpose + ADR/layer when useful); TS/TSX `/** ... */` on non-trivial entry surfaces.
- Apply across remaining api/web **hotspots** (routes, services, scheduler, fat components) — not mass-rewriting every re-export or generated file.
- Keep headers short (2–6 lines); no corporate novel.

### Notes

Starter set applied with the convention doc (`busy_map`, `deps`, outline/Assist services, `OutlineImportPanel`). Opportunistic thereafter.

---

## DEF-014 — Exclude unplanned / backlog tasks from Update Schedule

| Field | Value |
|-------|--------|
| **Severity** | **P2** (daily annoyance when outline/import dumps hundreds of tasks into replan) |
| **Status** | Closed — shipped 2026-08-18 |
| **Found** | 2026-08-17 |
| **Surface** | Scheduler (`candidates.py` / `style.py`); epic/project schedule-style pickers; task detail **Manual / backlog**; Settings `default_schedule_style` |
| **Wave** | W2c steal — `manual` + live inherit shipped; bulk edit still [DEF-015](./DEFECTS.md#def-015--bulk-edit-on-task-lists-subtree--selection) |

### Symptom / ask

Operator wants tasks that are **not ready to plan** to stay off the calendar when running **Update Schedule** — e.g. imported course modules sitting in a backlog until she picks what to work on. A **`backlog` label** is one idea; open to better designs.

### Current behavior (shipped 2026-08-18)

- New `schedule_style` value **`manual`** (Alembic `013_schedule_style_manual`). UI label is **Manual / backlog** — **not** a magic `backlog` label.
- `load_candidates` excludes effective **`manual` and `bundle`** ([`candidates.py`](../apps/api/app/scheduler/candidates.py), [ADR-006](./adr/ADR-006-fuzzy-scheduling.md)). Manual/pinned blocks remain OK. Bundle is still a distinct style and still stays off auto-placement.
- Live resolution at schedule time, **not** stamp-on-create: `task.schedule_style` → else `project.schedule_style` → else `epic.schedule_style` → else `user_settings.default_schedule_style`. Inbox (no project) is **task override or user default only**.
- Task override always wins. Saving Inherit keeps the task column **null** (does not copy the parent value).
- Outline import does **not** default every imported task to `manual`.
- UI: schedule-style picker on epic/project create + edit; task detail empty = inherit; hint `from project {title}` / `from epic {title}`. Settings default enum includes `manual`.

Tunnel ops (not run in this docs pass): operator still needs `docker compose --build api web` for the live stack.

### Design options (kept)

| Approach | Pros | Cons |
|----------|------|------|
| **A. Rename/clarify `bundle` → `manual` / `backlog` in UI** (+ maybe alias enum later) | Zero schema change; behavior exists today | “Bundle” v2 semantics (scoped bundles) may collide ([W2c scoped bundles](./07-wave-roadmap.md#wave-2c--scheduler-polish--catch-all)) |
| **B. New `schedule_style` value** (e.g. `manual`, `backlog`) | Explicit, queryable, testable | Migration + ADR-006 amend |
| **C. Reserved **`backlog`** label** filtered in `load_candidates` | Visible in lists; no enum | Magic string; label delete/rename breaks rule unless system-reserved |
| **D. User setting: labels or tag that exclude from replan** | Flexible | Settings UI + config surface |
| **E. Default new tasks to excluded** (global or per-project) | Import-friendly | Easy to forget to “promote” tasks into schedulable pool |

**Shipped:** **B** — enum value `manual` plus 018-style live inherit on epics/projects. Not C (no magic `backlog` label). Bundle stays its own style.

### Design (what landed)

**Live resolution at schedule time**, not stamp-on-create:

`task.schedule_style` → else `project.schedule_style` → else `epic.schedule_style` → else `user_settings.default_schedule_style`.

- Task override always wins (one module that *is* ready to plan).
- Set Coursera epic (or a course project) to **Manual / backlog** → Update Schedule skips that tree without 147 clicks.
- Inbox has no project/epic parent; inherit is task or user default only.
- Outline ingest does not stamp `manual` onto every imported row.

**Not a substitute for:** [DEF-015](./DEFECTS.md#def-015--bulk-edit-on-task-lists-subtree--selection) (labels/due/recurrence/multi-select) or [DEF-017](./DEFECTS.md#def-017--cross-project--epic-scheduling-fairness-day-domination) (mix vs cap). This is **whether** a domain is even a candidate.

### Expected (met)

- Clear per-task (and parent) way to mark **exclude from Update Schedule**: **Manual / backlog**.
- Bind style on epic or project; replan skips inheriting descendants without per-task edits.
- Explicit task style overrides parent. Clearing the project/epic style unbinds inheritors; explicit task values stay put.
- Today / Upcoming views unchanged — exclusion is **auto-placement**, not hiding tasks.
- Quality GREEN 2026-08-18: targeted pytest `tests/test_schedule_replan.py tests/test_scheduler_style.py tests/test_schedule_style_inherit.py` — `25 passed`.

### Notes

Related: outline ingest (Theme F) made this P2. Not the same as **pinned blocks** (hard time lock) or **due/deadline** (constraints when schedulable).

**Message to future Trish (2026-08-18):** Set the Coursera **epic** (or project) to **Manual / backlog** **once**. You did **not** rage-click 147 modules. You had the good sense to stop at the thought experiment and yell at the agent instead. If you’re reading this after actually rage-clicking anyway — hi, yes, we knew. Ship DEF-014 before you do it again. :D

---

## DEF-015 — Bulk edit on task lists (subtree / selection)

| Field | Value |
|-------|--------|
| **Severity** | **P2** (high leverage for project/epic housekeeping) |
| **Status** | Closed — Phase 1–3 thin shipped 2026-08-27 (Round 4: due + move/project) |
| **Found** | 2026-08-17 |
| **Surface** | Task list UI, `PATCH /tasks/batch`, labels, recurrence, scheduler fields |
| **Wave** | Afternoon smash + Round 3–4 2026-08-27 |

### Symptom / ask

Bulk operations on a list context, e.g.:

- **Select all** in current scope (epic, project, or parent’s subtasks) — “make everything go away or move” without shift-clicking dozens of micro-modules.
- Schedule **all subtasks under a parent** on the same day (due, soft target, or manual blocks).
- Apply a **label** to everything under a project (or epic subtree).
- Set **recurrence** on a group of tasks.
- Likely also: bulk **schedule style / backlog** (DEF-014), priority, section move, delete, archive.

### Current behavior (Phase 1+2 shipped)

**Phase 1 — multi-select + batch bar**

- Multi-select checkboxes + **Select all** (visible rows) in `TaskList`; batch bar: schedule style, apply label, delete (confirm).
- `PATCH /tasks/batch` with `{ task_ids, patch?, add_label_ids? }`.
- Batch delete uses soft-delete ([DEF-024](./DEFECTS.md#def-024--trash-can-soft-delete-with-retention)).

**Phase 2 — loaded subtree selection (client-side)**

- **⊞** button on rows with loaded descendants — selects the row plus all **visible/loaded** subtasks via `collectLoadedSubtreeIds` (`taskForest.ts`).
- **Alt+click** the row select checkbox — same subtree add (when descendants are loaded).
- Scope is the in-memory task list only (not server-side “whole epic” fetch); expand/collapse or list filters affect what ⊞ / Alt+click includes.

**Phase 3 thin (Round 4):** batch **due date** (+ clear due) and **move to project** / Inbox in `TaskList` batch bar; API tests for `due_at` + project move (orphan `section_id` cleared). **Skipped:** bulk archive (tasks have no archive), bulk recurrence (not on `TaskUpdate`). Still deferred: schedule-same-day blocks, bulk recurrence UI.

**Item 5 leftovers (2026-10-08):** batch **priority** (P1–P4) in `TaskBatchBar` → `PATCH /tasks/batch` `{ priority }`; pytest `test_batch_patch_priority`. Still deferred: bulk recurrence UI, schedule-same-day blocks.

---

## DEF-016 — Task detail Save affordance (scroll fatigue)

| Field | Value |
|-------|--------|
| **Severity** | **P3** (paper cut; worse during heavy editing sessions) |
| **Status** | Closed — shipped 2026-08-17 |
| **Found** | 2026-08-17 |
| **Surface** | `TaskDetailPanel.tsx`, `.task-detail-panel` layout in `App.css` |
| **Wave** | Bug bash / polish; can ship independently of DEF-008 (resize) |

### Symptom / ask

Save / Cancel live at the **bottom** of a long form inside a scrollable right panel (`max-height` + `overflow-y: auto`). Editing title + dates + labels means scrolling to commit — annoying at volume.

### Design options (pick one or combine)

| Approach | Effort | Notes |
|----------|--------|-------|
| **Sticky footer** inside panel — Save/Cancel pinned to bottom of viewport while form scrolls | Low | CSS + maybe split scroll container |
| **Header actions** — Save next to × close; Cancel optional | Low | Always visible; matches mobile sheet patterns |
| **Unsaved indicator + keyboard** — dot on header, Ctrl+S submits | Low | Still need visible button for discoverability |
| **Auto-save debounced** | Medium | Bigger behavior change; recurrence/destructive fields need care |
| **Collapsible sections** — fold recurrence/deps/advanced | Medium | Reduces scroll but doesn’t fix root affordance |

**Recommendation:** **Sticky footer + Save in header** (duplicate submit is fine). Unsaved dot if dirty state is already tracked.

### Expected (when built)

- Save reachable without scrolling for typical edit flows.
- Delete stays separated (destructive row) — don’t sticky the delete button next to Save.
- No regression on mobile sheet / narrow widths.

### Notes

Orthogonal to **DEF-008** (wider panel). If panel grows, scroll pain lessens but header/sticky save still wins.

---

## DEF-017 — Cross-project / epic scheduling fairness (day domination)

| Field | Value |
|-------|--------|
| **Severity** | **P2** (visible with one large epic — e.g. Coursera import — even when other work exists) |
| **Status** | Closed — shipped 2026-08-19 |
| **Found** | 2026-08-17 |
| **Surface** | Scheduler ordering + placement (`ups.py`, `dependencies.py`, `placement.py`, `replan.py`); optional project/epic settings |
| **Wave** | W2c polish or W3+ scheduling UX; **DEF-014 shipped** (manual inherit) — fairness still open |

### Symptom / ask

One **epic or project** (e.g. Coursera certificate tree) can **consume an entire workday** on Update Schedule even when other tasks share the same priority. Adjacency or volume in one project should **not** let its P2s beat equally-ranked P2s elsewhere. Time maps help bound *when* work happens; they do **not** solve *mix* across domains.

### Root cause (current v1 behavior)

1. **UPS ties at same priority** — `PRIORITY_SCORES` is per task; two P2s both get 75. With no due/soft/deadline, **urgency U = 0** for all. Epic alignment **E** is binary per epic (`target_date` within 30 days → +10 for *every* task in that epic). Dependency **D** favors blockers in dense subgraphs (e.g. sequential modules).
2. **Order then greedy exhaust** — `order_candidates` → topo + UPS tie-break; then `replan` loops candidates and **`place_task` fills as much horizon as possible for each task before the next** ([`replan.py`](../apps/api/app/scheduler/replan.py), [`placement.py`](../apps/api/app/scheduler/placement.py)). First high-enough task wins the day; no round-robin, no per-project cap.
3. **No project/epic dimension in UPS** — project identity affects only **E** (via epic `target_date`), not fairness or daily budget.
4. **Outline import** — many sibling tasks, default **P4** unless changed; `sort_order` follows curriculum order; module/task chains can inflate **D** locally. (Operator may promote to P2 — same mechanics apply.)

Time maps constrain **tier/window**; they do not **interleave** across projects.

### Design options (pick in ADR / implementation)

| Approach | What it does | Pros | Cons |
|----------|--------------|------|------|
| **A. Round-robin slice placement** | Among tasks within ε UPS (or same priority band), place **one block** then rotate to next task | No schema change; fixes “first task eats day” | Need tier/band rules; long single tasks still chunky |
| **B. Daily minutes cap per project/epic** | Setting: max auto-scheduled minutes per project (or epic) per local day; overflow deferred | Explicit operator control | Caps need UI + edge cases (P1 override?) |
| **C. Diversity penalty in score** | New UPS term (or post-score): reduce task score if its project/epic already has ≥ N minutes scheduled **today** | Smooth, global | Tunable weights; harder to explain |
| **D. Project / epic scheduling weight** | Nullable `scheduling_weight` or priority on `projects` / `epics` | Matches mental model (“Coursera is P3 *effort*”) | More config surface |
| **E. Scoped pools (W2c)** | “Only schedule tasks from epic X this run” / inverse “exclude epic X” | Operator control per replan | Doesn’t auto-mix; manual |
| **F. Refine epic alignment E** | Cap, decay, or per-project share of E — stop blanket +10 for all tasks in hot epic | Targets Coursera-with-target-date case | Doesn’t help equal-priority different epics with no target |

**Recommendation:** Ship **A + B** as v1 fairness pair — round-robin among same-priority band fixes the greedy bug; optional daily cap gives operator a knob. Document in **ADR-006 addendum** or new **ADR-012 scheduling fairness**. [DEF-014](./DEFECTS.md#def-014--exclude-unplanned--backlog-tasks-from-update-schedule) (`manual` inherit) is the short-term lever for unplanned import bulk — **shipped 2026-08-18**.

### Expected (when built)

- Update Schedule produces a **mixed day** when multiple projects have schedulable same-priority work (unless operator caps or excludes).
- Settings (or project fields) for at least one fairness control — cap and/or weight.
- Tests: two projects, equal P2, no dates → neither monopolizes first day; P1 still wins when configured.
- Replan stats optionally report minutes per project/epic for debugging.

### Notes

Related: [DEF-014](./DEFECTS.md#def-014--exclude-unplanned--backlog-tasks-from-update-schedule) (**shipped** — set epic/project to Manual / backlog so the tree stays off replan), [DEF-018](./DEFECTS.md#def-018--project--epic-time-map-binding-no-click-wall) (bind a whole project to a window — cap *when*, not mix), W2c **scoped bundles** (opt-in grouping — different problem). Not the same as **dependency ordering** within one course — that stays; fairness is **across** projects at equal priority.

---

## DEF-018 — Project / epic Time Map binding (no click-wall)

| Field | Value |
|-------|--------|
| **Severity** | **P2** (other schedulers already taught this lesson; outline import makes it real here) |
| **Status** | Closed — shipped 2026-08-17 |
| **Found** | 2026-08-17 |
| **Surface** | `projects` / `epics` schema, edit forms, scheduler `effective` window resolution (`windows.py` / `placement.py`) |
| **Wave** | W2c steal — Time Map live inherit shipped; plan inherit still parked |

### Symptom / ask

Operator wants to **bind a Time Map to a project or epic once** (e.g. Coursera → 2h evening window, `strict_mode`) and have **all current and future tasks** in that tree honor it. Per-task `preferred_time_window_id` plus no bulk edit is a click-wall. Scope creep is accepted; a wall of one-project blocks is worse.

Seen this failure mode in other “scheduler” products: one domain dumps into the day because constraints only live on tasks.

### Current behavior (shipped 2026-08-17)

- `preferred_time_window_id` on **epics** and **projects** (Alembic `012_hierarchy_time_maps`; FK `focus_windows.id` ON DELETE SET NULL) plus the existing task column.
- Live resolution at schedule time, **not** stamp-on-create: `task.preferred_time_window_id` → else `project.preferred_time_window_id` → else `epic.preferred_time_window_id` → else unbound (full workday).
- Task override always wins. Saving an empty task Time Map keeps the task column **null** (does not copy the parent id).
- Clearing the project/epic map unbinds inheritors; explicit task windows stay put.
- UI: Time Map picker on epic/project edit (and create). Task detail empty = inherit; hint `from project {title}` / `from epic {title}`.

Plan-bind inheritance did **not** ship. [DEF-014](./DEFECTS.md#def-014--exclude-unplanned--backlog-tasks-from-update-schedule) / [DEF-015](./DEFECTS.md#def-015--bulk-edit-on-task-lists-subtree--selection) / [DEF-017](./DEFECTS.md#def-017--cross-project--epic-scheduling-fairness-day-domination) are not this slice.

### Design (what landed)

**Live resolution at schedule time**, not stamp-on-create:

`task.preferred_time_window_id` → else `project.preferred_time_window_id` → else `epic.preferred_time_window_id` → else unbound (full workday / default map).

- Task override always wins (one module that *is* all-day).
- Set Coursera epic (or a course project) to map **Learning 19:00–21:00 strict** → Update Schedule cages that tree without 147 clicks.
- Same inheritance chain for **plan bind** stayed parked (spec listed both; Time Map was the P2).
- UI: Time Map picker on project + epic edit (same control as task detail). Inherited vs override on the task (muted `from project {title}` / `from epic {title}`).

**Not a substitute for:** [DEF-015](./DEFECTS.md#def-015--bulk-edit-on-task-lists-subtree--selection) (still needed for labels/due/recurrence) or [DEF-017](./DEFECTS.md#def-017--cross-project--epic-scheduling-fairness-day-domination) (mix vs cap). This is **when** a domain is allowed to land.

### Expected (met)

- Bind map on epic or project; replan places descendant tasks in that window without per-task edits.
- Explicit task window overrides parent.
- Clearing the project/epic map unbinds descendants that were inheriting (does not wipe explicit task windows).

### Notes

Operator: “DARE me to not have something added to do that.” Added. Pair with a 2h strict map for learning; greedy fill still owns *that* slot ([DEF-017](./DEFECTS.md#def-017--cross-project--epic-scheduling-fairness-day-domination)) — inheritance stops the click-wall, not the mixer.

**Message to future Trish (2026-08-17):** You did **not** rage-click 147 Coursera modules. You had the good sense to stop at the thought experiment and yell at the agent instead. If you’re reading this after actually rage-clicking anyway — hi, yes, we knew. Ship DEF-018 before you do it again. :D

---

## DEF-019 — Calendar bundles for micro-task coursework (aggregate block, keep task rows)

| Field | Value |
|-------|--------|
| **Severity** | **P2** (Coursera-style 2m/7m/10m tasks clutter the calendar; operator wants one “study for an hour” block) |
| **Status** | Closed — thin + Round 4 follow-on (partial gray + shrink) 2026-08-27 ([ADR-012](./adr/ADR-012-calendar-bundles.md)) |
| **Found** | 2026-08-25 |
| **Surface** | `schedule_style.bundle`, `scheduled_blocks`, calendar UI, Update Schedule / manual bundle creation |
| **Wave** | Round 2 smash + Round 4 follow-on 2026-08-27 |

### Symptom / ask

Coursework often decomposes into **many short tasks** (2m, 7m, 10m, …). Operator wants to **block calendar time once** — e.g. “work on this course for an hour” — without **each micro-task** appearing as its own calendar row. Tasks must **stay individual in lists** (complete, reorder, dependencies, labels).

When tasks in the bundle are **completed** or **moved/rescheduled** out of the bundle scope, the aggregate calendar block should **gray out and become removable** (or auto-shrink / dissolve when empty).

### Current behavior (thin shipped)

- Alembic `016_scheduled_block_bundle_meta` — nullable JSONB `bundle_meta` on `scheduled_blocks`.
- `POST /scheduled-blocks/bundle` — selection or parent subtree → one block; duration sum of estimates (or explicit range).
- Task list multi-select **Block as bundle**; calendar grays when `bundle_inactive` (all members complete); delete removes block only.
- DEF-020 release-remainder applies to aggregate rows.

**Round 4 follow-on:** `bundle_inactive` when **any** live member is completed; shrink `end_time` to remaining incomplete estimates (15m floor) on complete. ADR-012 addendum.

**Deferred:** auto scoped bundle replan, auto-dissolve / expand-on-uncomplete, `bundle_blocks` join table.

**Item 5 leftovers (2026-10-08):** batch bar **bundle start** `datetime-local` (default next 15m snap) + optional **Pin** before **Block as bundle**; passes `start_time` / `is_pinned` to `POST /scheduled-blocks/bundle` (duration still API sum of estimates). Still deferred: auto replan, dissolve, join table.

---

## DEF-020 — Calendar capacity release (early complete + bulk clear)

| Field | Value |
|-------|--------|
| **Severity** | **P2** (finished early or emergency replan — calendar should give time back) |
| **Status** | Closed — shipped 2026-08-27 |
| **Found** | 2026-08-25 |
| **Surface** | Calendar UI, `scheduled_blocks`, optional replan hook |
| **Wave** | Afternoon smash 2026-08-27 |

### Symptom / ask

Two related junctures:

**a. Early finish — release remainder**

Completed tasks **gray out** on the calendar (good). When work finishes **faster than the block**, operator wants the **unused tail removed** so Update Schedule (or manual placement) can use the rest of the slot — not leave a gray tomb occupying capacity.

**b. Emergency clear**

Sometimes **many blocks** must come off the calendar at once because urgent work arrived — faster than unpin/delete one-by-one.

### Current behavior (shipped)

- **Release remainder:** `POST /scheduled-blocks/{id}/release-remainder` with optional `{ "at": ISO }` truncates `end_time` to `at` (default now). Deletes the block when the leftover would be &lt; 1 minute. Calendar block menu exposes the action.
- **Clear unpinned:** `POST /scheduled-blocks/clear-unpinned` with `{ start, end }` deletes unpinned blocks overlapping the range (pinned untouched). Calendar toolbar confirm action for visible range.
- `GET /tasks?ids=` supports bulk hydrate for calendar labels after clear/release.

### Quality

Targeted pytest `tests/test_scheduled_blocks.py` — **12 passed** (2026-08-27, Windows venv + local Postgres).

### Notes

Pair with [DEF-019](./DEFECTS.md#def-019--calendar-bundles-for-micro-task-coursework-aggregate-block-keep-task-rows) when bundle blocks exist — release semantics must apply to aggregate blocks too. Distinct from wiping horizon inside Update Schedule (that already wipes unpinned in horizon on replan).

---

## DEF-021 — Browse archived epics/projects and reactivate

| Field | Value |
|-------|--------|
| **Severity** | **P2** (archive works; find-and-restore does not) |
| **Status** | Closed — shipped 2026-08-27 |
| **Found** | 2026-08-25 |
| **Surface** | Sidebar, epic/project lists, `GET /epics?archived=`, `POST …/unarchive` |
| **Wave** | Afternoon smash 2026-08-27 |

### Symptom / ask

Operator can **archive** epics and projects, but there is **no UI to view archived items** or **reactivate** them once hidden. “Where did that go?” and “bring it back” are both blocked.

### Current behavior (shipped)

- Sidebar **Archived** nav → `ArchivedView` lists `GET …?archived=true` epics + projects.
- **Unarchive** calls existing `POST …/unarchive`; invalidates sidebar caches.
---

## DEF-023 — Promote / demote hierarchy (task ↔ project ↔ epic)

| Field | Value |
|-------|--------|
| **Severity** | **P2** (wrong initial scope — fix without recreate) |
| **Status** | Closed — thin shipped 2026-08-27 |
| **Found** | 2026-08-25 |
| **Surface** | Tasks, projects, epics — detail drawer + API |
| **Wave** | Round 2 smash 2026-08-27 |

### Symptom / ask

Operator sometimes picks the **wrong container level**:

- **Promote** project → epic; task → project (new project under epic or standalone).
- **Demote** epic → project (children become projects? or epic folds into a project — pick semantics).

Should preserve tasks, labels, and history where possible — not export/reimport.

### Current behavior

- Fixed hierarchy: epic → project → task → subtask.
- Move task between projects exists; no promote/demote entity operations.

### Thin ship (2026-08-27)

Locked semantics — **no schema / Alembic**. Transactional create + FK rewire (+ delete epic on demote). Confirm dialogs on UI actions.

| Direction | Semantics |
|-----------|-----------|
| **Project → epic** | New epic cloned from project title/description/color/time map/schedule style. **Same project UUID** becomes the (only) child of that epic (`epic_id` rewired). Tasks/sections stay put. Prior parent epic (if any) simply loses the project. UI: Edit project → Promote to epic. |
| **Epic → project** | New **standalone** project shell cloned from epic meta; former child projects get `epic_id = NULL` (orphans); epic row deleted. Tasks stay on orphaned projects — the shell starts empty. Optional body `target_epic_id` places the shell under another epic. UI: Edit epic → Demote to project. |
| **Task → project** | New project from task title/description; epic = body `epic_id` else current project's epic else standalone. Task becomes root; descendants move with nesting renorm (default). `include_descendants=false` with live kids → 400. UI: Task detail → Promote to project. |

**API**

- `POST /api/v1/projects/{id}/promote-to-epic` → `{ epic, project }`
- `POST /api/v1/epics/{id}/demote-to-project` → `{ project, orphaned_project_ids }`
- `POST /api/v1/tasks/{id}/promote-to-project` → `{ project, task }`

**Deferred:** Undo; demote target-epic picker in UI.

### Expected (when fully built)

- Detail drawer actions: **Promote to…** / **Demote to…** with confirm + preview of side effects.
- API: structured move with validation (no cycles, orphan rules).
- Undo or explicit confirm — destructive-ish.

### Notes

Distinct from drag reparent ([DEF-001](./DEFECTS.md#def-001--subtasks-added-out-of-sequence-appear-at-list-bottom)). Pair with [DEF-015](./DEFECTS.md#def-015--bulk-edit-on-task-lists-subtree--selection) Select all for “demote whole subtree” flows.

---

## DEF-024 — Trash can (soft delete with retention)

| Field | Value |
|-------|--------|
| **Severity** | **P2** (accidental delete — operator has *never* done this, obviously) |
| **Status** | Closed — shipped 2026-08-27 (soft-delete, restore, empty trash, purge-older-than; no cron) |
| **Found** | 2026-08-25 |
| **Surface** | Tasks, schema `deleted_at`, Trash UI, `DELETE /tasks/trash` |
| **Wave** | Afternoon smash + Round 3–4 2026-08-27 |

### Symptom / ask

**Hard delete** is immediate and scary. Operator wants a **trash** holding deleted items for a **retention period** (e.g. 30 days) with **restore** — same UUID, children if applicable.

### Current behavior (shipped)

- Alembic `015_task_deleted_at`; `DELETE /tasks/{id}` soft-sets subtree `deleted_at`; lists exclude trashed; `GET /tasks?trashed=true`; `POST /tasks/{id}/restore` (same delete wave).
- Sidebar **Trash** view + per-row **Restore**.
- **`DELETE /api/v1/tasks/trash`** — hard-purge all trashed tasks for the user (`empty_trash_for_user`); unpinned blocks for those tasks removed; pinned blocks left.
- **Round 4:** `DELETE /tasks/trash?older_than_days=N` selective purge; Trash UI **Purge older than…** modal (default 30). Still **no** background cron / Settings retention job.
- Trash UI **Empty trash** button + confirm dialog.
- **Correctness (2026-10-08):** restore child while parent still trashed → reparent to nearest live ancestor or inbox; empty trash does not hard-delete live descendants of a purged parent. Reparent cycles rejected with **422** `PARENT_CYCLE` on task PATCH.
---

## DEF-025 — Inline create parent / child / labels in detail drawer

| Field | Value |
|-------|--------|
| **Severity** | **P2** (context switch fatigue — leave drawer to create related entities) |
| **Status** | Closed — shipped 2026-08-27 (labels + parent/child create) |
| **Found** | 2026-08-25 |
| **Surface** | `TaskDetailPanel`, project/epic edit forms, labels picker |
| **Wave** | Round 2 smash 2026-08-27 |

### Symptom / ask

While editing a task or project in the detail drawer:

- **Create new parent** (e.g. new project under epic, re-parent on the fly).
- **Create new child** (subtask or nested project) without closing the drawer.
- **Create new label** inline in the label picker instead of navigating to Labels view first.

### Current behavior (shipped)

- Labels section: filter + **Create “foo”** via `createLabel`; new label selected on the task.
- **+ New project** modal from Dependencies → selects the new project on the open task.
- Inline **Add subtask** form (respects nesting limit).

---

## DEF-026 — Collapsible sections in task/project detail drawer

| Field | Value |
|-------|--------|
| **Severity** | **P3** (scroll fatigue; drawer keeps growing) |
| **Status** | Closed — shipped 2026-08-27 |
| **Found** | 2026-08-25 |
| **Surface** | `TaskDetailPanel`, project/epic edit panels, `App.css` |
| **Wave** | Afternoon smash 2026-08-27 |

### Symptom / ask

Detail drawer is **long** (recurrence, deps, scheduling, labels, Time Map, …). Operator wants **collapsible sections** — collapsed by default, expand when needed — similar to Settings accordion pattern.

### Current behavior (shipped)

- Collapsible sections: Scheduling, Recurrence, Dependencies, Labels, Advanced — collapsed by default; expand state in `localStorage` (`theplan.taskDetail.sections`).
- Title / description / priority / dates / delete stay always visible; sticky Save unchanged.

---

## DEF-027 — Locked-out account recovery / forgotten password

| Field | Value |
|-------|--------|
| **Severity** | **P2** (operator can lose access to the product; data remains intact) |
| **Status** | Closed — shipped 2026-10-08 (Quality green: session_epoch 28 + CLI 22) |
| **Found** | 2026-09-18 |
| **Surface** | Sign-in, auth service, operator tooling, session management, agent CLI |
| **Wave** | Account recovery + agent CLI (DEF-027) |

### Symptom / ask

An authenticated user can change their own password, and an administrator can assign a
temporary password to another household user. Neither path helps when the sole operator
has forgotten the password and cannot sign in.

The product needs a recovery path that fits its local-first deployment model. Recovery
must not assume outbound email is configured or available.

### Current behavior (pre-fix)

- `PATCH /auth/me` changes the current user's password after sign-in.
- An administrator can set another user's password and force `must_change_password`.
- There was no supported recovery flow for a locked-out sole operator.

### Fix shipped (2026-10-08)

1. **`users.session_epoch`** — Alembic `017_session_epoch`; integer bumped on password change and host recovery; session cookie stores epoch at login; `get_current_user` and the password-change gate reject stale epochs ([`apps/api/app/api/deps.py`](../apps/api/app/api/deps.py), [`auth_users.bump_session_epoch`](../apps/api/app/services/auth_users.py)).
2. **Host-local recovery** — `theplan auth reset-password` calls `reset_password_for_recovery` (sets hash, `must_change_password`, bumps epoch). Operator docs: [CLI.md](./CLI.md), [apps/cli/README.md](../apps/cli/README.md).
3. **Agent CLI M2** — `auth login|logout|me`, `status`, `tasks list|get|create|patch`, `assist propose|apply` (JSON-default HTTP client).
4. **Automated tests** — [`apps/api/tests/test_session_epoch.py`](../apps/api/tests/test_session_epoch.py); [`apps/cli/tests/`](../apps/cli/tests/) (exit codes, recovery stdin CRLF, API status mapping).

**Quality:** Renee green 2026-10-08 — auth/session_epoch **28/28**, CLI **22/22**.

### Recommended first cut (original spec — largely met)

Provide an operator-controlled host command or script that:

1. Selects a local account by username or email.
2. Generates or accepts a temporary secret without writing it to application logs.
3. Sets `must_change_password = true`.
4. Revokes existing sessions for that account.
5. Leaves the user at the existing blocking change-password gate after sign-in.

An expiring one-time recovery link can be considered later. Email-based recovery should
remain optional and must not become a dependency for a local installation.

### Security boundaries

- Do not expose account existence through a public unauthenticated response.
- Rate-limit any network-accessible recovery request surface.
- Do not log passwords, temporary secrets, or recovery tokens.
- Recovery authority belongs to the host operator or an authenticated administrator.
- Record the recovery event without recording the secret.

### Expected

- A sole operator can recover a local account without editing PostgreSQL by hand.
- The temporary credential is immediately replaced through the existing forced-change flow.
- Existing sessions are invalidated after recovery.
- The path works without an email provider and has automated auth tests.

---

## DEF-028 — Calendar mirror delete failure recovery (pending deletion)

| Field | Value |
|-------|--------|
| **Severity** | **P3** (busy-map pollution after a failed remote delete; success path is fine) |
| **Status** | Closed — fixed 2026-10-09 |
| **Found** | 2026-10-08 (code review residual after horizon mirror wipe) |
| **Surface** | `wipe_unpinned_blocks_in_horizon` ([`horizon.py`](../apps/api/app/scheduler/horizon.py)); Google/MS `delete_mirrored_block`; sync pull → `busy_map` |
| **Wave** | W2c / calendar sync polish |

### Symptom / ask

Horizon wipe cancels Google/Microsoft mirrors and drops the local `ExternalCalendarEvent` so successful deletes no longer linger as external busy. If the provider **rejects** the delete, the implementation still removes the local row (so wipe cannot poison busy with a detached mirror). The **remote** event remains. A later calendar sync can re-import it with `scheduled_block_id` unset, and `busy_map` treats it as someone else's appointment.

Changelog already notes the residual ([CHANGELOG.md](../CHANGELOG.md) Unreleased).

### Recommended direction

Keep a **pending-deletion** (or tombstone) record that retains provider / calendar / external event identity after local unlink, so retries can call delete again without losing the handle. Do not leave orphaned remote events as anonymous busy after a failed cancel.

### Expected

- Failed provider deletes are retried (or surface operator-visible debt) without losing external event identity.
- A later sync does not permanently reintroduce wiped mirror slots as external busy without an explicit retry/fail path.

### Resolution (2026-10-09)

Alembic `026_pending_deletion` adds `external_calendar_events.pending_deletion`. Horizon wipe and scheduled-block delete, when the provider delete fails, keep the row, clear `scheduled_block_id`, and set the flag. Busy map, conflicts, and `GET /calendar/events` ignore those tombstones. The next Google or Microsoft sync retries the delete (404/410 count as gone) and will not reimport that external id as busy. A failed retry leaves the tombstone and logs it. A real event in the same pull still imports.

Not this fix: task soft-delete still hard-deletes unpinned blocks. A mirror on one of those blocks can become anonymous busy via `ON DELETE SET NULL` because that writer never calls the provider. Separate from the failed-delete path.

---

## DEF-029 — Course import removes supplied lab title prefixes

| Field | Value |
|-------|-------|
| **Severity** | **P3** (source title fidelity; lab classification retained) |
| **Status** | Closed — shipped 2026-10-09 (preserve task-type prefixes; optional marker still stripped) |
| **Found** | 2026-10-09 (Julie, reported through Trish) |
| **Surface** | Coursera template import; shared outline title normalization |
| **Fixed** | 2026-10-09 — `_clean_task_title` no longer strips `Lab:` / `Video:` / etc.; proposal titles match Apply. Existing imported rows are not rewritten. |

### Observed behavior

Julie reports that importing Trish's course removed the `Lab:` prefix from all **27 lab titles**. The tasks still carry the lab tag. Dex has not inspected the imported records or independently rerun this specific course import.

### Source evidence

`_clean_task_title` in `apps/api/app/services/outline_templates.py` explicitly removes matching task-type prefixes, case-insensitively. Course outline actions use this helper; the module handoff conversion uses it too. This is deliberate normalization in the implementation, rather than evidence of random title truncation. Whether that normalization should remain is the product behavior under review.

### Expected direction

Preserve supplied task titles by default, or make prefix removal an explicit import choice. Retain the task-type label independently. The proposal should show the exact title that Apply will create, so title transformations can be reviewed before import.

### Verification for a fix

- Import a lab whose supplied title starts with `Lab:` and compare source, proposal, and persisted title.
- Cover other task-type prefixes handled by the shared helper, including mixed case and optional items.
- Confirm labels remain intact and ordinary titles are not changed.
- Existing imported titles are not automatically rewritten without a separate user request.

### Workaround

Julie can restore the prefixes with task edits if Trish wants them. This report does not authorize a bulk rename or reimport.

---

## DEF-030 — CLI task patch omits the accepted title argument

| Field | Value |
|-------|-------|
| **Severity** | **P2** (requested task rename cannot be applied through the CLI) |
| **Status** | Closed — shipped 2026-10-09 (`title` added to patch field_map) |
| **Found** | 2026-10-09 (Julie, reported through Trish; Dex local verification) |
| **Surface** | `apps/cli/theplan/commands/tasks.py`, `_optional_task_fields` |
| **Fixed** | 2026-10-09 — patch payload includes `title`; CLI unit tests cover title-only and title+description. Redeploy/reinstall CLI where Julie runs before retrying lab renames. |

### Observed behavior

The task patch parser accepts `--title`, but the payload field map omits it. A title-only patch raises `INVALID_USAGE` with "Provide at least one field to patch" before making an API call. A patch supplying a title plus another supported field sends only that other field, silently omitting the requested title change.

Julie reports that the 27 imported lab titles remain unchanged. Dex verified the command handlers with `api_json` replaced by an in-process capture function; no live records were read or changed.

### Scope and proposed fix

Add `("title", "title")` to the task helper's `field_map`. The existing loop already trims title strings and skips this mapping for create, whose title is handled separately.

Epic, project, and section patch handlers in the current local tree already include that mapping. Intercepted calls from all three contained the supplied title. This does not verify the CLI version installed on supernova.

### Verification for a fix

- A title-only task patch sends the trimmed title to the API.
- A task patch with title and description sends both fields.
- Task create retains its existing title handling; an empty patch still fails.
- Confirm the corrected CLI is installed where Julie will run it before retrying the lab renames.

---

## DEF-031 — List → calendar drag does not make sense in current shell

| Field | Value |
|-------|--------|
| **Severity** | **P3** (misleading affordance / incomplete W2c UX; not data loss) |
| **Status** | Open |
| **Found** | 2026-10-12 (Trish) |
| **Surface** | TaskList ⠿ handle, `CalendarView` drop, `App.tsx` shell layout |
| **Wave** | Backlog — post-R3 tidy / calendar UX; not urgent |

### Symptom

On a project/list screen, task rows show a ⠿ handle with tooltip **“Drag to calendar to schedule.”** The handle starts an HTML5 drag (`application/x-theplan-task-calendar-drag`). The only drop targets are Calendar day-slot columns (`CalendarDayColumn` → `CalendarView.handleTaskDrop`), which create a scheduled block. The sidebar **Calendar** nav link is not a drop target.

The app shell shows **List OR Calendar** as mutually exclusive main panes (`App.tsx`). While the operator is on the list, the calendar grid is not mounted — the gesture cannot complete from that screen. Desktop-only (`!isNarrow`). [USER-GUIDE](./USER-GUIDE.md) and cal-hint copy also assume list and calendar are visible together.

### Expected

The affordance is honest and usable: the operator can schedule from the list without a dead-end drag, or the UI does not promise a drop target that is unreachable from the current view.

Design options (pick one coherent path; do not prescribe here): split or list+calendar layout; park drag until Calendar is open with a reachable source; change tooltip and offer **Schedule…** that opens Calendar or a modal; or another operator-valid flow.

### Notes

Trish confirmed context 2026-10-12. Cross-ref: [USER-GUIDE — Drag and drop](./USER-GUIDE.md#drag-and-drop).
