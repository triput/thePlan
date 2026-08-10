# Functional Specification

This document defines observable product behavior for the application. Implementation details live in [04-data-schema.md](./04-data-schema.md), [05-api-contract.md](./05-api-contract.md), and [sql/001_baseline.sql](./sql/001_baseline.sql).

---

## 1. Information Architecture & Hierarchy

### Entity Model

| Level | Description | Key Attributes |
|-------|-------------|----------------|
| **Epic** | Strategic initiative spanning multiple projects or months | title, description, color, start_date, target_date, archive state, aggregated duration rollups |
| **Project** | Functional domain or goal category; optional epic parent | title, description, color, sort_order, archive state, epic_id (nullable) |
| **Section** | Visual grouping within a project | title, sort_order, project_id |
| **Task** | Actionable work unit at nesting_level 0 | Full task field set (see §3) |
| **Subtask** | Child of a task; nesting_level 1 | Same field set; parent_task_id required |
| **Nested Subtask** | Deepest layer; nesting_level 2 | Same field set; parent must be nesting_level 1 |

### Hierarchy Rules

- Maximum nesting depth: **2** (parent task → subtask → nested subtask). Enforced by `nesting_level CHECK (<= 2)` and application validation of parent chain depth.
- A task may belong to a project directly, to a section within a project, or to neither (Inbox).
- **Inbox** is the catchment for tasks with `project_id IS NULL`.
- Epic → Project is optional (`epic_id` nullable on projects).
- Reorder within a container uses `sort_order` (integer, lower = higher in list).
- Archive is soft (`is_archived`); archived entities are hidden from default views but retained in the database.

### Parent Completion Policy

When a user marks a parent task complete while one or more child tasks remain open:

1. Show a **warning dialog** (warn-and-allow; never silently auto-complete children).
2. Offer two explicit choices:
   - **(a) Complete parent only** — mark the parent complete; children remain open.
   - **(b) Bulk-complete open children** — mark the parent and all descendant tasks complete in one operation (offline catch-up path).
3. Never auto-complete children without the user's explicit choice.

Uncompleting a parent does not automatically uncomplete children.

---

## 2. MVP Screens & Navigation

### List Views

- **Project list** — projects grouped by epic (ungrouped projects shown separately); archive toggle.
- **Section list** — sections within the active project with tasks grouped under each section.
- **Task detail** — inline or panel edit for title, description, priority, due, duration, labels, subtasks.
- **Hierarchy navigation** — sidebar or equivalent: Epics, Projects, Inbox, smart views, Calendar.

### Smart Views (Fixed; MVP)

System-provided named filters backed by `saved_filters` with `is_system = TRUE`. No user-authored query language in MVP.

| View | Predicate (conceptual) |
|------|------------------------|
| **Inbox** | `project_id IS NULL AND is_completed = FALSE` |
| **Today** | Incomplete tasks that belong on today's local calendar: `due_at` falls on today **or** any `scheduled_block` overlaps today. Scheduling onto today (calendar) is enough — due/deadline not required. |
| **Upcoming** | Incomplete tasks with `due_at` in the next N days after today (default 7) **or** a `scheduled_block` overlapping that window, sorted by soonest due/block start |
| **By Project** | Filter to selected project; optional section grouping |
| **By Epic** | All tasks in projects linked to selected epic |
| **By Label** | Tasks with selected label |

Smart view predicates are stored as JSON in `saved_filters.predicate_json` for forward compatibility with W2 query language (fixed views become special cases of the same model).

### Calendar View (MVP — Required)

- **Day** and **Week** layouts required at MVP.
- **Month** layout: include if implementation cost is low; not a blocker for MVP exit.
- **Nice-to-have chrome:** day-of-year and ISO week-of-year in consistent form with `  •  ` separators (day: `…  •  Year YYYY: Day N  •  Week W`; week: `Year YYYY: Week W  •  …  •  Days A–B`).
- Display:
  - Tasks with `due_at` set appear as due markers/events on their due datetime.
  - Manually placed **scheduled_blocks** appear as time blocks on the calendar grid.
- Interactions:
  - Drag a task or block to change `due_at` or block `start_time`/`end_time`.
  - Create a manual block by dragging on empty calendar space (creates `scheduled_blocks` row linked to task).
  - Pin toggle on blocks (`is_pinned`) is stored but auto-respect behavior is W2; MVP stores the flag for manual blocks.
- **No external calendar events** in MVP (no Google/Microsoft overlay until W2).
- Calendar is the only project timeline view in MVP. No Gantt. Board/Kanban deferred to optional W3.

### Quick-Add

Global capture box (keyboard shortcut, e.g. `q` or `Ctrl+K`). Accepts natural-language metadata tokens; returns structured task payload via parse endpoint before create.

### Search

Global full-text search across task titles and descriptions. Results open in a flat list with context (project, due, labels). MVP scope: simple `ILIKE` or Postgres full-text; advanced query syntax is W2.

### Undo

Last destructive mutation (complete, delete, move) is undoable within a session via client-side undo stack backed by inverse API calls. Minimum: undo complete/uncomplete and delete/restore for tasks. Stack depth: at least 1 action; target 10–20 for MVP.

---

## 3. Task Fields

| Field | MVP UI | Schema | Notes |
|-------|--------|--------|-------|
| title | Yes | Required | Max 500 chars |
| description | Yes | Optional | Plain text MVP; markdown rendering W2+ |
| priority | Yes | P1–P4 enum | Default P4 |
| due_at | Yes | TIMESTAMPTZ nullable | User-facing "due date/time" |
| deadline_at | No (W2) | TIMESTAMPTZ nullable | Hard commit; enforced by scheduler in W2 |
| soft_target_at | No (W2) | TIMESTAMPTZ nullable | Plan-bound soft target; surfaced with Plans in W2 |
| estimated_duration_minutes | Yes | Integer, default 30 | Stored as minutes |
| min_block_duration_minutes | Schema only | Integer, default 15 | Scheduler W2 |
| max_block_duration_minutes | Schema only | Integer, default 120 | Scheduler W2 |
| labels | Yes | M2M via task_labels | |
| project / section | Yes | FK nullable | Null project = Inbox |
| parent_task_id | Yes | FK nullable | Defines subtask nesting |
| nesting_level | Derived | 0–2 CHECK | Must match parent chain |
| preferred_time_window_id | No (W2) | FK focus_windows nullable | SkedPal Time Map binding |
| status | Partial | schedule_status enum | MVP uses unscheduled/completed primarily |
| is_completed / completed_at | Yes | Boolean + timestamp | |
| sort_order | Yes | Integer | Reorder within container |

### Completed Task Retention

Completed tasks are retained indefinitely. Default list views hide completed items. A **Show completed** toggle reveals them (dimmed styling). Calendar dims completed due markers.

---

## 4. Labels & Colors

### Labels

- Many-to-many with tasks via `labels` + `task_labels`.
- Label attributes: name (unique per owner), color_hex.
- **Standalone label management (MVP):** dedicated Labels screen (or settings section) to create, rename, recolor, and delete labels **without** opening a task. Creating several labels in one sitting is supported (repeat create / bulk-friendly UI).
- **Prune:** deleting a label detaches it from all tasks (`ON DELETE CASCADE` on `task_labels`) and removes the label row. Confirm when the label is still attached to tasks (show usage count).
- **Backlog (W1.5):** on delete, offer optional **reassign/migrate** — pick one or more surviving labels to apply to those tasks (bulk) before the doomed label is removed, so related work stays tagged without hand-editing each task.
- **Lowercase-only names:** all label names are stored and compared as lowercase. API and UI normalize on write (`Waiting` → `waiting`). Reject or fold duplicates that differ only by case — uniqueness is `(owner_id, name)` after normalization so `Waiting`, `WAITING`, and `waiting` cannot coexist.
- Assign/remove on task detail remains available; quick-add label tokens deferred to W1.5 if needed.

### Colors (Epic & Project & Label)

Canonical swatches: [08-color-palette.md](./08-color-palette.md).

- **Preset palette** — Synesis/Phronesis-derived named hexes (teal, emerald, mint, azure, violet, coral, amber, charcoal, etc.) in client constants; a few extras for breadth.
- **Custom hex** — any `#RRGGBB` (7 chars) always allowed.
- **Defaults:** epic `#6D3FC9`, project `#0A8558`, label `#635F75`.
- Stored as `color_hex VARCHAR(7)` on epics, projects, and labels.
- Priority and due/overdue accents are fixed UI tokens (see palette doc), not user entity colors.

---

## 5. Authentication & Sessions

### MVP: Local-Only

- Single-user local session stub: no remote identity provider, no Cloudflare Access.
- API trusts localhost / LAN binding; optional lightweight session cookie for CSRF hygiene.
- `users` table populated with one row at bootstrap; `password_hash` nullable in MVP.

### W1.5: Login / Remote-Ready

- Password-based session login and/or Cloudflare Access integration.
- Enables optional remote hosting without schema rewrite.

See [ADR-003-local-first-auth.md](./adr/ADR-003-local-first-auth.md).

---

## 6. Dual-Layer Time Model

### Internal Storage

- All durations stored as **integer minutes** (`estimated_duration_minutes`, etc.).
- All timestamps stored as **TIMESTAMPTZ in UTC** (`due_at`, `deadline_at`, block times).
- User timezone from `user_settings.timezone` drives display and "today" boundaries.

### Work Capacity Baselines

Multi-day duration estimates translate to working capacity, not 24-hour elapsed time:

| Unit | Minutes |
|------|---------|
| 1 work day | 480 (8 h) |
| 1 work week | 2,400 (40 h) |
| 1 work month | 9,600 (160 h) |
| 1 work year | 115,200 (1,920 h) |

Configurable via `user_settings.workday_minutes` (default 480) and derived week/month calculations.

### Scale-Aware UI Formatting

The display formatter selects the best unit for the view context:

| Range | Display |
|-------|---------|
| < 60 minutes | `45m` |
| 1–24 hours | `2h 30m` |
| 1–30 days | `3.5 days` |
| 1–12 months | `2.5 months` |
| > 12 months | `1.2 years` |

Rollups at project/epic level use the same formatter on aggregated minute totals.

---

## 7. Quick-Add Parser Rules

Deterministic multi-pass pipeline. Extract metadata in strict precedence; sanitize remainder as title.

### Precedence Order

1. Explicit tag markers (`!!`, `#`, `epic:`)
2. Priority tokens (`p1`–`p4`, `!1`–`!4`)
3. Duration units (numeric + unit suffix)
4. Date/time expressions
5. Title fallback (remaining text)

### Epic & Project Tags

- **Epic:** `(?:!!|epic:)(?:"([^"]+)"|'([^']+)'|(\S+))` — e.g. `!!Organon`, `!!"Q3 Infrastructure"`, `epic:Auth`
- **Project:** `#(?:"([^"]+)"|'([^']+)'|(\S+))` — e.g. `#CoreEngine`, `#"Client App"`
- **Project/Section:** `#Project/Section` resolves both project and section by name.

### Priority

- Pattern: `(?<=\s|^)(?:p|P|!)(1|2|3|4)(?=\s|$)`
- Mapping: p1/P1/!1 → highest; p4 default.

### Duration (Ambiguity Fix)

**Locked rule:** `m` / `min` / `mins` / `minute` / `minutes` = **minutes only**. Months use `mo` / `mon` / `mth` / `month` / `months` only. The token `1.5m` means **1.5 minutes**, not months.

Pattern: `(?<=\s|^)(\d+(?:\.\d+)?)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|wk|wks|week|weeks|mo|mon|mth|month|months|y|yr|yrs|year|years)(?=\s|$)`

| Unit suffix | Multiplier (minutes) |
|-------------|---------------------|
| m, min, … | × 1 |
| h, hr, … | × 60 |
| d, day, … | × 480 |
| w, wk, … | × 2,400 |
| mo, mon, month, … | × 9,600 |
| y, yr, … | × 115,200 |

### Date & Time

- **Relative:** today, tomorrow (tom), yesterday, next monday/tue/… — computed against user's local date boundary.
- **Absolute:** YYYY-MM-DD, MM/DD/YYYY, DD-MMM (15-Aug), Oct 24.
- **Exact time:** `at 3pm`, `at 14:30` — binds due_at timestamp.
- **Fuzzy windows (W2 scheduler):** `@morning` (08:00–12:00), `@afternoon` (12:00–17:00), `@evening` (17:00–21:00) — maps to `preferred_time_window_id` when focus windows exist.

### Example

Input: `Review architecture spec 1.5h p1 next Tue at 9am !!Organon #Dev/Backend @morning`

| Extracted | Value |
|-----------|-------|
| Epic | Organon |
| Project / Section | Dev / Backend |
| Priority | p1 |
| Duration | 90 minutes |
| Due | Next Tuesday 09:00 (user TZ → UTC) |
| Preferred window | morning (stored when W2 windows exist) |
| Title | "Review architecture spec" |

---

## 8. Calendar MVP Semantics

- **Due markers:** tasks with `due_at` render on calendar at due datetime (all-day vs timed based on whether time component is midnight/local day boundary).
- **Manual blocks:** user-created `scheduled_blocks` rows; drag to move/resize.
- **No external events** until W2 Google Calendar integration.
- **No auto-scheduler** in MVP; blocks are user-placed only.
- Dragging a due marker updates `due_at`. Dragging a block updates `start_time`/`end_time`.
- Conflict display: overlapping manual blocks are allowed in MVP (visual overlap only); overbook detection is W2.

---

## 9. Wave 2 — SkedPal Scheduler Behaviors (Spec Level)

These behaviors are **not in MVP** but are locked for W2 design. Schema and API are prepared from day one.

### SkedPal Triad

1. **Time Maps** — `focus_windows` table: named recurring local time ranges (e.g. "Morning Deep Work" Mon–Fri 08:00–11:00). Tasks bind via `preferred_time_window_id`.
2. **Plans** — flexible time frames (e.g. "Thursday morning", "by Friday afternoon") stored as plan entities linked to tasks; `soft_target_at` on tasks holds Plan-bound soft targets.
3. **Update Schedule** — explicit user-triggered replan action; async worker recomputes `scheduled_blocks` without blocking CRUD.

### Bundling vs Blocks

- **Formal time blocks** — discrete `scheduled_blocks` rows on the calendar.
- **Bundled / knockout lists** — tasks grouped for sequential execution within a window without pre-assigning exact block times until Update Schedule runs.
- Mode per task or plan; scheduler converts bundles into blocks during allocation pass.

### Pins, Soft vs Hard

| Constraint | Source | Scheduler treatment |
|------------|--------|---------------------|
| **Hard** | `deadline_at`, `is_pinned = TRUE` blocks, external calendar busy events | Never moved automatically |
| **Soft** | Plan window, `soft_target_at`, preferred time window | Relaxable during fuzzy fit |

**Pinned block (W2 backlog — not MVP exit):** User places (or accepts) a `scheduled_block` at a specific clock time and sets `is_pinned = TRUE`. Update Schedule / fuzzy replan **must not** move or split that block until the user unpins. This is distinct from `due_at` and `deadline_at`: it means “do this work *at this time*” (e.g. prep immediately before a meeting that lives on someone else’s calendar). Operator may choose the time manually from knowledge of external events; own Google busy map (W2 sync) helps when the related event is on a connected calendar, but pin remains the hard lock either way.

### Rule Inheritance

Child tasks inherit scheduling constraints from parent (time window, plan binding) unless explicitly overridden. Reduces per-task configuration.

### Scheduling Pipeline (Async Worker)

1. **Busy map** — external calendar events + pinned blocks → BUSY/FREE timeline.
2. **Dependency resolution** — topological sort of `task_dependencies` DAG.
3. **Priority queue** — UPS scoring (below).
4. **Slice & fit** — split tasks into blocks respecting min/max slice sizes and focus windows.
5. **Conflict handling** — flag `overbooked` status when task cannot fit before deadline; never auto-move pins or higher-priority hard constraints.

### UPS Formula

**Urgency & Priority Score:**

$$\text{UPS} = (W_p \cdot P) + (W_u \cdot U) + (W_d \cdot D) + (W_e \cdot E)$$

| Component | Definition | Default weight |
|-----------|------------|----------------|
| **P** (Priority) | P1=100, P2=75, P3=50, P4=25 | W_p = 0.35 |
| **U** (Urgency) | See below | W_u = 0.40 |
| **D** (Dependency depth) | Normalized downstream blocked count (0–100) | W_d = 0.15 |
| **E** (Epic alignment) | 100 if parent epic has near-term target_date; else 0 | W_e = 0.10 |

**Urgency decay:**

$$\text{Slack} = \frac{\text{DueDate} - \text{CurrentTime} - \text{RemainingDuration}}{\text{RemainingDuration}}$$

$$U = 100 \cdot e^{-k \cdot \max(\text{Slack},\, 0)}$$

When Slack ≤ 0, U = 100. Default **k = 0.5**; configurable via `user_settings.ups_weights` JSONB.

### Buffer

Insert `inter_block_buffer_minutes` (default **5**) between back-to-back auto-scheduled blocks. Configurable in user settings.

### Fuzzy Fit Rules

- Prefer contiguous blocks within a focus window over scattered minimum slices.
- Relax soft window constraints before failing.
- Pinned blocks and external busy events are immovable.

### GCal Conflict (W2)

When a Google Calendar hard event overlaps a pinned block: both treated as BUSY; scheduler never auto-moves pins; surface overbook/flag in UI.

---

## 10. Explicit Non-Goals

| Item | Status |
|------|--------|
| Team workspaces, assignees, comments | Out |
| Karma, streaks, badges | Out |
| Board / Kanban view | W3 (optional) |
| Flutter mobile/desktop | Out (Tauri W3) |
| External calendar sync | W2 (Google); W3 (Microsoft) |
| Auto-scheduler | W2 |
| Recurrence engine | W1.5 (schema in MVP) |
| SLM / AI quick-add assist | W3 |
| Location-based reminders | W3 (candidate) |
| Voice input | W3 (candidate; not before W2) |
| Email-to-task | W3 (candidate; not before W2) |
| Templates | W3 (backlog; low priority) |
| Zapier / IFTTT / automation hubs | Post-W3 backlog |
| Notion / Obsidian deep links or sync | Post-W3 backlog (maybe late W3 if cheap) |
| Attachments | Out |
| Todoist import | W1.5 |
| Saved filter query language | W2 (fixed views MVP) |
| Offline PWA sync | Out for MVP (online-first) |
| Remote auth / Cloudflare Access | W1.5 |

---

## 11. Timezone & Travel

Single `user_settings.timezone` (IANA string, e.g. `America/Los_Angeles`). All timestamps UTC in DB; UI renders in configured zone. User changes timezone in settings when traveling; no automatic geo-detection in MVP.

---

## 12. Backup

Documented `pg_dump` one-liner against Compose Postgres volume. Optional scheduled backup script in W1.5. OAuth tokens and secrets stored in host env / Docker secrets; never committed to git.
