# Defects log

Open product defects that are not wave exit blockers. Priority here is **product severity** (P1–P4), not task priority enum.

---

## DEF-001 — Subtasks added out of sequence appear at list bottom

| Field | Value |
|-------|--------|
| **Severity** | **P2** (mental tax / hierarchy trust; not data loss) |
| **Status** | Open |
| **Found** | 2026-08-10 |
| **Surface** | Project / Inbox task lists (`TaskList`) |
| **Wave** | Deferred to **bug bash** (not W2a); fix when convenient |

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

### Expected

List shows a depth-first tree: each parent’s children (by sibling `sort_order`) immediately under that parent, regardless of when those children were created.

### Fix direction

1. **Client (sufficient for display):** Before render, order `tasks` as a forest DFS keyed by `parent_task_id`, siblings by `sort_order` then `created_at`/`id`.
2. **Optional API:** On create under a parent, assign `sort_order` among siblings (e.g. max sibling + gap) so flat sort stays coherent for exports/other clients.

### Out of scope for this defect

- Drag-and-drop reparent
- Section-grouped project layout polish
- Soft-delete

---

## DEF-002 — Timezone setting is free-text, not a picker

| Field | Value |
|-------|--------|
| **Severity** | **P4** (UX polish; IANA text works) |
| **Status** | Open |
| **Found** | 2026-08-11 |
| **Surface** | Settings → Scheduling defaults → Timezone |
| **Wave** | Bug bash / polish bundle — non-urgent |

### Symptom

Timezone is a free-text field. Easy to typo; no discoverability of valid IANA zones.

### Expected

Dropdown (searchable preferred) of common/valid IANA timezones; still store the same string on `user_settings.timezone`.

### Notes

Bundle with other small Settings/UI fixes when convenient. Not a Settings expansion exit blocker.

---

## DEF-003 — Mobile task detail: content below deadline clipped, no scroll

| Field | Value |
|-------|--------|
| **Severity** | **P2** (detail unusable on phone for long tasks) |
| **Status** | Open |
| **Found** | 2026-08-14 |
| **Surface** | Task detail sheet / panel on narrow (mobile) viewport |
| **Wave** | Bug bash / cleanup — do **not** derail W3 |

### Symptom

On mobile web, opening a task’s detail view shows content through **deadline**, but nothing below is reachable — cannot scroll the detail body.

### Expected

Detail sheet scrolls so fields below deadline (notes, Time Map, Plan, reminders, etc.) are reachable.

### Notes

Likely overflow / flex / `100dvh` sheet layout; check W1.6 detail-sheet CSS vs nested scroll containers.

---

## DEF-004 — Inbox up/down reorder arrows do nothing

| Field | Value |
|-------|--------|
| **Severity** | **P3** (controls present but inert; workarounds exist) |
| **Status** | Open |
| **Found** | 2026-08-14 |
| **Surface** | Inbox task list reorder arrows |
| **Wave** | Bug bash / cleanup — do **not** derail W3 |

### Symptom

Up/down move arrows in the **Inbox** view do not change task order (no visible reorder; likely no successful `sort_order` swap).

### Expected

Arrows swap sibling/`sort_order` with adjacent visible rows (same behavior as other list views that reorder correctly), or arrows are hidden if Inbox intentionally has no reorder.

---

## DEF-006 — NL due times: 24-hour clock and broader datetime forms

| Field | Value |
|-------|--------|
| **Severity** | **P3** (required eventually; not blocking daily driver) |
| **Status** | Closed — Assist honesty cut 2026-08-14 |
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
| **Status** | Closed — Assist honesty cut 2026-08-14 |
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
| **Status** | Open — backlog |
| **Found** | 2026-08-14 |
| **Surface** | Task detail panel (`.task-detail-panel` / sheet) — desktop/wide layout |
| **Wave** | Bug bash / UX polish (not wave-blocking) |

### Symptom / ask

Operator wants to **drag the left edge** of the right-hand task detail sidebar to widen/narrow it when needed (long descriptions, dense forms). Fixed width (~340px in `App.css`) is fine as default but not adjustable.

### Expected

- Grab handle / edge drag on the panel’s inner (left) border.
- Persist preferred width (e.g. `localStorage`) with sensible min/max clamps.
- Narrow/mobile sheet behavior unchanged (full-bleed / overlay stays as today).

### Notes

Not urgent. Drag-resize only — no need for dual-panel fancy layouts in this item.

---

## DEF-009 — Outline import into existing hierarchy (partial / lower-level)

| Field | Value |
|-------|--------|
| **Severity** | **P3** (prove-it full-tree import covers first land; grafting is the next real pain) |
| **Status** | Open — backlog |
| **Found** | 2026-08-14 |
| **Surface** | Outline ingest (`/outlines/propose|apply`, Outline UI) — Theme F follow-on |
| **Wave** | Theme F polish / bug bash (after ADR-011 prove-it) |

### Symptom / ask

Current outline import always proposes a **full** certificate → epic → courses → modules → tasks tree. Operator wants **lower-level imports**, e.g. a single course (or module) landing as a **project under an existing epic**, without creating a duplicate specialization epic.

### Expected (when built)

- Propose/apply can target an existing parent: at least **epic** (import course(s) as projects + nested sections/tasks); ideally also **project** (modules → sections) and maybe **section** (tasks only).
- UI: pick target epic/project (or paste outline that is a course/module subtree) before Propose.
- Same review → confirm → apply; still no Coursera client; dedupe remains separate ([ADR-011](./adr/ADR-011-templates-outline-ingest.md) non-goal until booked).

### Notes

Severity sits between P2 and P3 on purpose: not blocking daily driver while the full-tree path works, but it will feel like P2 the first time a second course needs to join an epic already in thePlan. Acceptable outline shapes: full certificate JSON with “attach under epic X”, or a course-/module-scoped JSON fragment.

---

## DEF-010 — Blank / generic outline template (non-Coursera bulk adds)

| Field | Value |
|-------|--------|
| **Severity** | **P3** (Coursera fixture proves the path; blank template is operator courtesy) |
| **Status** | Open — backlog |
| **Found** | 2026-08-14 |
| **Surface** | Theme F outline ingest — docs + fixture under `testdata/outlines/`; pack id in API |
| **Wave** | Theme F polish (before or with full W4 template catalog) |

### Symptom / ask

Prove-it ships `coursera_specialization` + one golden JSON. Operator wants a **clear, fillable template** (and docs) for other bulk hierarchy adds that are not Coursera — so Theme F is not “half the job” ending at one specialization.

### Expected (when built)

- Blank outline JSON (and short fill guide) matching the v1 contract: root → children → modules/sections → tasks with `task_type` / `duration_minutes` / `optional` / order.
- Either document that `coursera_specialization` already accepts any JSON in that shape, or add a neutral pack alias (e.g. `hierarchy_v1`) that shares the same mapper.
- Point to it from [OUTLINE-INGEST.md](./OUTLINE-INGEST.md) and `testdata/outlines/README.md`.

### Notes

Does **not** require W4 template CRUD. First-class user-authored template catalog remains W4 ([ADR-011](./adr/ADR-011-templates-outline-ingest.md)).

---

## DEF-011 — Refactor assessment (modularize / de-mix layers)

| Field | Value |
|-------|--------|
| **Severity** | **P3** (gut-check hygiene; not a known break) |
| **Status** | Open — backlog |
| **Found** | 2026-08-14 |
| **Surface** | Cross-cutting — API services vs routes vs web components (esp. large files) |
| **Wave** | After Theme F prove-it settled; pair with or after a Dependency Hygiene-style pause when booking the next feature pile |

### Symptom / ask

Operator gut: some files may house **too many vectors** (UI + orchestration + domain rules), and **business logic may be showing up where it doesn’t belong**. Want a deliberate **refactor assessment** — not a blind rewrite — to see if modularization or layer cleanup is warranted.

### Expected (when run)

1. Inventory hotspots (oversized modules, mixed concerns: e.g. fat `TaskList` / `App.css` / route handlers doing domain work).
2. Classify: keep / extract service / extract component / leave alone.
3. Propose a short ordered cut list (if any) with risk notes — **no drive-by mega-refactor**.
4. Operator reviews before any mutating refactor wave.

### Notes

Triggered by intuition after rapid Theme F / Assist growth, not by a concrete defect. Assessment first; code moves only after explicit greenlight. Separate from feature DEF-008–010. Pair with [DEF-012](./DEFECTS.md#def-012--living-technical-architecture--diagrams-catch-up) / [09-technical-architecture.md](./09-technical-architecture.md) when mapping hotspots.

---

## DEF-012 — Living technical architecture + diagrams (catch-up)

| Field | Value |
|-------|--------|
| **Severity** | **P3** (docs debt; product works without it) |
| **Status** | Open — living doc; **initial catch-up drafted 2026-08-14** |
| **Found** | 2026-08-14 |
| **Surface** | [09-technical-architecture.md](./09-technical-architecture.md) (+ index in [README.md](./README.md)) |
| **Wave** | Docs hygiene; update when topology/pipelines/layering change |

### Symptom / ask

Wave 1 doc package + ADRs existed, but organic growth (W2/W3/Assist/Theme F) left no single **current** system map. Operator wants a hangable architecture page with **diagrams**, knowing it will keep growing.

### Expected

- Keep [09-technical-architecture.md](./09-technical-architecture.md) current: runtime topology, layering rules, major pipelines, pointers into code/docs.
- Add diagrams as needed (auth, calendar sync, Update Schedule, …).
- Optionally sync stale lines in functional spec / API contract / feature catalog in the same passes—not a big-bang rewrite.

### Notes

Initial draft shipped with Mermaid: topology, layers, hierarchy, capture pipelines. Not a substitute for ADRs or the functional spec.

---

## DEF-013 — File headers across api/web hotspots

| Field | Value |
|-------|--------|
| **Severity** | **P3** (convention / readability; product works without it) |
| **Status** | Open — backlog; **initial convention shipped 2026-08-14** |
| **Found** | 2026-08-14 |
| **Surface** | Source modules under `apps/api`, `apps/web` — see [dev/FILE-HEADERS.md](./dev/FILE-HEADERS.md) |
| **Wave** | Docs / hygiene chore; sprinkle while touching files or as a short pass |

### Symptom / ask

Operator wants proper module/file headers (short info blocks) as a house quirk. Not huge yet, but the convention should be real — not vaporware.

### Expected

- Follow [dev/FILE-HEADERS.md](./dev/FILE-HEADERS.md): Python module docstrings (purpose + ADR/layer when useful); TS/TSX `/** ... */` on non-trivial entry surfaces.
- Apply across remaining api/web **hotspots** (routes, services, scheduler, fat components) — not mass-rewriting every re-export or generated file.
- Keep headers short (2–6 lines); no corporate novel.

### Notes

Starter set applied with the convention doc (`busy_map`, `deps`, outline/Assist services, `OutlineImportPanel`). Rest is opportunistic or a dedicated P3 pass.

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
| **Status** | Open — backlog |
| **Found** | 2026-08-17 |
| **Surface** | Task list UI, `PATCH /tasks`, labels, recurrence, scheduler fields |
| **Wave** | W3+ productivity UX (after DEF-014 if shared batch API) |

### Symptom / ask

Bulk operations on a list context, e.g.:

- Schedule **all subtasks under a parent** on the same day (due, soft target, or manual blocks).
- Apply a **label** to everything under a project (or epic subtree).
- Set **recurrence** on a group of tasks.
- Likely also: bulk **schedule style / backlog** (DEF-014), priority, section move.

### Current behavior

- Only **bulk complete** exists (`bulk_children` on complete API + dialog in `TaskList`).
- No multi-select row model; no batch PATCH endpoint.

### Expected (when built)

**Phase 1 — selection + batch PATCH**

- Multi-select in list (checkbox mode or shift-click); “Select all under …” for parent row / section header / project scope.
- Batch actions bar: labels, due date, schedule style, priority, delete (with confirm).
- API: `POST /tasks/batch` or `PATCH` with `{ task_ids, patch }` — single transaction, partial failure reporting optional.

**Phase 2 — subtree semantics**

- “This task and all descendants” without manual select-all.
- “All tasks in project X matching filter” defers to saved filters / W2c query language unless a minimal project scope is enough for v1.

**Phase 3 — schedule same day**

- Clarify product: set **due_at** / **soft_target_at** vs create **manual `scheduled_blocks`** vs run mini-replan for subset — probably separate actions in the batch bar.

### Notes

Keep Assist / outline paths propose→confirm; bulk edit is **operator-driven** on existing rows. Consider undo stack parity (`bulk_complete` pattern in `undoStack.tsx`).

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

