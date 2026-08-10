# MVP Backlog (Wave 1)

User stories with acceptance criteria for Wave 1 (MVP) only. W1.5+ work is tracked in [07-wave-roadmap.md](./07-wave-roadmap.md).

**Exit criteria (summary):** Full hierarchy CRUD, parent completion with warn+bulk, Today/Inbox/Upcoming smart views, calendar day/week, quick-add, search, undo, local Docker Compose deployment, p95 perceived interaction < 100ms on LAN. **No** calendar sync, **no** auto-scheduler, **no** remote auth required.

---

## E1 — Local Infrastructure

### US-1.1: Docker Compose stack

**As a** user, **I want** to start the full stack with one command **so that** I can run the app locally without manual service wiring.

**Acceptance criteria:**

- [ ] `docker compose up` starts PostgreSQL, API, and web services with healthchecks
- [ ] Compose file is OCI-portable (no Docker-only proprietary features)
- [ ] Baseline schema applied on first boot (Alembic or init script)
- [ ] Bootstrap user and system smart views seeded automatically
- [ ] Documented in README with port mappings (e.g. web :5173, api :8000, postgres :5432)

### US-1.2: Local-only auth bootstrap

**As a** user, **I want** the app to work immediately without login **so that** I can start capturing tasks on first launch.

**Acceptance criteria:**

- [ ] Single `users` row created at bootstrap (`local@localhost`)
- [ ] `GET /auth/me` returns bootstrap user without credential prompt
- [ ] All API mutations scoped to bootstrap owner_id
- [ ] No password required in MVP UI

---

## E2 — Hierarchy CRUD

### US-2.1: Epic management

**As a** user, **I want** to create, edit, archive, and color epics **so that** I can group multi-month initiatives.

**Acceptance criteria:**

- [ ] Create epic with title, optional description, color (preset or custom hex), start/target dates
- [ ] List epics in sidebar; archived hidden by default with toggle
- [ ] Edit and soft-archive epic
- [ ] Epic color visible in navigation

### US-2.2: Project management

**As a** user, **I want** to create projects under epics (or standalone) **so that** I organize work by domain.

**Acceptance criteria:**

- [ ] Create project with optional epic_id, title, color, description
- [ ] Reorder projects via sort_order (drag or keyboard)
- [ ] Archive/unarchive project
- [ ] Standalone projects (no epic) supported

### US-2.3: Sections

**As a** user, **I want** sections within projects **so that** I can visually group tasks.

**Acceptance criteria:**

- [ ] CRUD sections within a project
- [ ] Reorder sections
- [ ] Tasks display grouped by section in project view

### US-2.4: Tasks and nesting

**As a** user, **I want** tasks with up to two levels of subtasks **so that** I can break down work deeply.

**Acceptance criteria:**

- [ ] Create task at project, section, or Inbox (null project)
- [ ] Create subtask (nesting_level 1) and nested subtask (nesting_level 2)
- [ ] Reject nesting beyond level 2 with clear error
- [ ] Reorder tasks within container
- [ ] Edit title, description, priority, due_at, duration, labels

### US-2.5: Inbox

**As a** user, **I want** an Inbox for unassigned tasks **so that** I can capture before organizing.

**Acceptance criteria:**

- [ ] Tasks with `project_id IS NULL` appear in Inbox smart view
- [ ] Move task from Inbox to project/section via UI or API
- [ ] Inbox accessible from sidebar

---

## E3 — Task Completion

### US-3.1: Complete and uncomplete

**As a** user, **I want** to mark tasks complete **so that** I track progress.

**Acceptance criteria:**

- [ ] Complete/uncomplete toggles `is_completed` and `completed_at`
- [ ] Completed tasks hidden from default lists; "Show completed" toggle reveals them
- [ ] Completed tasks dimmed on calendar

### US-3.2: Parent completion with open children

**As a** user, **I want** a clear choice when completing a parent with open subtasks **so that** I can finish offline work without losing data.

**Acceptance criteria:**

- [ ] Completing parent with open children shows warning dialog (not silent)
- [ ] Option (a): complete parent only — children remain open
- [ ] Option (b): bulk-complete all open descendants
- [ ] API returns 409 OPEN_CHILDREN when choice required; client retries with flag
- [ ] Uncompleting parent does not auto-uncomplete children

---

## E4 — Labels & Colors

### US-4.1: Labels

**As a** user, **I want** to manage labels on their own and on tasks **so that** I can cross-cut projects and prune stale tags.

**Acceptance criteria:**

- [ ] Standalone Labels management UI: list all labels; create one or several without attaching to a task; rename; recolor; delete
- [ ] Delete confirms when label is in use; shows task usage count; delete removes label and all task attachments
- [ ] Assign/remove labels on task detail
- [ ] Filter tasks by label via smart view
- [ ] Names are **lowercase-only**: input normalized to lowercase on create/rename; API rejects or folds case-only duplicates
- [ ] Unique per owner after lowercase normalization (no `Waiting` + `waiting` pair)

**Deferred (W1.5):** On delete, optionally reassign affected tasks to other label(s) in bulk before removing the pruned label.

### US-4.2: Color presets

**As a** user, **I want** Synesis/Phronesis-aligned color presets plus custom hex **so that** epics, projects, and labels match my suite.

**Acceptance criteria:**

- [ ] Color picker offers the named presets in [08-color-palette.md](./08-color-palette.md) (teal through slate)
- [ ] Custom `#RRGGBB` input accepted and stored
- [ ] Invalid hex rejected with validation message
- [ ] New epics/projects/labels use documented defaults (`#6D3FC9` / `#0A8558` / `#635F75`) unless overridden

---

## E5 — Smart Views

### US-5.1: Today

**As a** user, **I want** a Today view **so that** I see what's due now.

**Acceptance criteria:**

- [ ] Lists incomplete tasks with `due_at` on today's local calendar **or** a `scheduled_block` overlapping today (calendar-planned work counts even without due/deadline)
- [ ] Respects user_settings.timezone for "today" boundary
- [ ] Sorted by due time / block start then priority

### US-5.2: Upcoming

**As a** user, **I want** an Upcoming view **so that** I see the next several days.

**Acceptance criteria:**

- [ ] Lists incomplete tasks with `due_at` within upcoming_horizon_days (default 7) after today **or** a `scheduled_block` in that window
- [ ] Grouped or sorted by date

### US-5.3: By Project / Epic / Label

**As a** user, **I want** to browse tasks by project, epic, or label **so that** I can focus contextually.

**Acceptance criteria:**

- [ ] Project view shows sections and tasks
- [ ] Epic view aggregates tasks across linked projects
- [ ] Label view shows all tasks with selected label

---

## E6 — Calendar View

### US-6.1: Day and week calendar

**As a** user, **I want** day and week calendar layouts **so that** I see time-based commitments.

**Acceptance criteria:**

- [ ] Day view shows hourly grid for selected date
- [ ] Week view shows 7-day grid
- [ ] Month view included if implementation cost is low (optional, not exit blocker)
- [ ] Navigate prev/next day/week
- [ ] **Nice-to-have:** show **day-of-year** number and **ISO week-of-year** (e.g. day 222 · W32) in the calendar chrome — Trish likes these; not an MVP exit blocker

### US-6.2: Due markers on calendar

**As a** user, **I want** tasks with due dates on the calendar **so that** I see deadlines in time context.

**Acceptance criteria:**

- [ ] Tasks with due_at render at due datetime on calendar
- [ ] Timed vs all-day rendering based on time component
- [ ] Task color from project/epic propagated to marker

### US-6.3: Manual scheduled blocks

**As a** user, **I want** to place and drag time blocks **so that** I can plan my day manually.

**Acceptance criteria:**

- [ ] Create scheduled_block by dragging on calendar or from task
- [ ] Drag block to change start/end time
- [ ] Drag due marker to update due_at
- [ ] Delete block
- [ ] is_pinned stored (auto-respect / immovable-until-unpin deferred to W2 — fixed clock-time work vs due/deadline)
- [ ] Overlapping blocks allowed in MVP (visual only)

### US-6.4: No external calendar in MVP

**As a** developer, **I want** calendar to show only app data **so that** MVP scope stays bounded.

**Acceptance criteria:**

- [ ] No Google/Microsoft event overlay
- [ ] No OAuth calendar flows in MVP UI
- [ ] calendar_accounts table exists but unused in UI

---

## E7 — Quick-Add

### US-7.1: Natural language capture

**As a** user, **I want** to type task metadata naturally **so that** capture is fast.

**Acceptance criteria:**

- [ ] Global quick-add shortcut opens capture box
- [ ] Parser extracts: duration, priority, due/date/time, epic tag, project/section tag
- [ ] Duration rule: `m`/`min` = minutes; `mo`/`mon`/`month` = months (1.5m = 1.5 minutes)
- [ ] `POST /quick-add/parse` returns structured draft; client confirms or auto-creates
- [ ] Unresolved project/epic names reported; task still creatable with title

### US-7.2: Work capacity in parser

**As a** user, **I want** day/week/month durations to use work-hour baselines **so that** estimates match how I think about work.

**Acceptance criteria:**

- [ ] 1d = 480 min, 1w = 2400 min, 1mo = 9600 min in parser
- [ ] Stored as integer minutes in DB

---

## E8 — Search & Undo

### US-8.1: Global search

**As a** user, **I want** to search tasks **so that** I find items quickly.

**Acceptance criteria:**

- [x] Search box queries title and description
- [x] Results show project, due, labels
- [x] Click result opens task detail

### US-8.2: Undo

**As a** user, **I want** to undo recent actions **so that** I recover from mistakes.

**Acceptance criteria:**

- [x] Undo complete/uncomplete (minimum)
- [x] Undo delete (soft restore or recreate from cache)
- [x] Keyboard shortcut for undo (e.g. Ctrl+Z)
- [x] Stack depth ≥ 1; target 10–20

**Implementation notes (Wave 1):** Client-side undo stack (max 15). Delete undo recreates the deleted task tree via `POST /tasks` (new IDs; scheduled blocks not restored). Bulk-complete undo uncompletes parent + captured open descendants.

**Forward (W2):** True session undelete via task soft-delete (`deleted_at` on `tasks`; see [04-data-schema.md](./04-data-schema.md) and [07-wave-roadmap.md](./07-wave-roadmap.md)). Delete undo becomes restore API; client stack still handles complete/uncomplete.

---

## E9 — Performance & UX

### US-9.1: Optimistic UI

**As a** user, **I want** instant feedback on actions **so that** the app feels fast.

**Acceptance criteria:**

- [ ] Task complete, create, move apply optimistically before server confirm
- [ ] Rollback on API error with toast
- [ ] p95 perceived interaction < 100ms on LAN for common actions

### US-9.2: Keyboard navigation

**As a** user, **I want** keyboard shortcuts **so that** I work without the mouse.

**Acceptance criteria:**

- [ ] Navigate task list (j/k or arrow keys)
- [ ] Open quick-add (q or Ctrl+K)
- [ ] Complete selected task (keyboard)
- [ ] Document shortcuts in help overlay

---

## E10 — Schema Readiness (Non-UI)

### US-10.1: Deferred fields in schema

**As a** developer, **I want** W2/W1.5 columns present from baseline **so that** later waves avoid painful migrations.

**Acceptance criteria:**

- [ ] `due_at` and `deadline_at` both on tasks; MVP UI shows due_at only
- [ ] `soft_target_at` on tasks (Plans W2)
- [ ] recurrence_rules, reminders, focus_windows, calendar_accounts tables exist
- [ ] schedule_status includes overbooked
- [ ] saved_filters seeded with Inbox/Today/Upcoming

---

## MVP Exit Checklist

| Criterion | Required |
|-----------|----------|
| Epic → Nested Subtask hierarchy | Yes |
| Parent complete warn + bulk children | Yes |
| Inbox, Today, Upcoming | Yes |
| Calendar day + week | Yes |
| Manual scheduled blocks + drag | Yes |
| Quick-add parser | Yes |
| Global search | Yes |
| Undo | Yes |
| Local Docker Compose | Yes |
| p95 feel < 100ms LAN | Yes |
| Calendar sync (GCal/MS) | **No** |
| Auto-scheduler | **No** |
| Remote auth / login | **No** |
| Recurrence engine | **No** (schema yes) |
| Board/Kanban | **No** (optional W3 candidate) |

---

## Out of Scope (Explicit)

- Recurrence UI and engine (W1.5)
- Reminders (W1.5)
- Todoist import (W1.5)
- Login / Cloudflare Tunnel (W1.5+)
- Auto-scheduler, UPS, Update Schedule (W2)
- Google Calendar sync (W2)
- Filter query language (W2)
- SLM assist (W3)
- Tauri desktop (W3)
- Board / Kanban column view (W3 optional)
- Location reminders, voice input, email-to-task, templates (W3 candidates)
- Zapier / IFTTT / automation hubs (Post-W3 backlog)
- Notion / Obsidian deep links or sync (Post-W3 backlog; maybe late W3 if cheap)
