# Feature Catalog

Todoist + SkedPal feature harvest with wave tags. This catalog formalizes parity targets; it is based on the original draft, 2026 product documentation refresh, and locked plan decisions — not a live click-through audit.

**Wave tags:** MVP | W1.5 | W1.6 | W2a | W2b | W3 | W3+ | Out

**Terminology:** Wave tags = delivery waves. **P1–P4** = task priority only (enum, UI, UPS scoring). **W2a** = Google Calendar; **W2b** = Scheduler.

---

## Todoist-Class Features

### Hierarchy & Organization

| Feature | Wave | Notes |
|---------|------|-------|
| Projects | MVP | With sections |
| Sections | MVP | Sort order within project |
| Epics (top-level initiatives) | MVP | Extension beyond Todoist |
| Subtasks (1 level) | MVP | |
| Nested subtasks (2 levels deep) | MVP | Extension beyond Todoist |
| Nested projects | Out | Epic replaces sub-project pattern |
| Inbox (no project) | MVP | `project_id IS NULL` |
| Archive project/epic | MVP | Soft archive |
| Reorder tasks/sections | MVP | sort_order |
| Templates | W3+ / W4 | **Theme F prove-it:** built-in `coursera_specialization` pack + outline ingest ([ADR-011](./adr/ADR-011-templates-outline-ingest.md)). Full template CRUD/catalog remains W4. |
| Project/view sharing | Out | Single-user |

### Task Core

| Feature | Wave | Notes |
|---------|------|-------|
| Title & description | MVP | Plain text description |
| Markdown notes | W3+ | Rendering in detail view |
| Priority P1–P4 | MVP | |
| Due date / datetime | MVP | `due_at` |
| Deadline (separate from due) | W2b UI | `deadline_at` in schema from MVP |
| Duration estimate | MVP | Minutes internally |
| Complete / uncomplete | MVP | Parent warn-and-allow policy |
| Parent bulk-complete children | MVP | Option (b) in completion dialog |
| Task dependencies | W2b | Schema in MVP; enforced by scheduler |
| Recurring due dates (`every`, `every!`) | W1.5 | Same-task rollover; limited frames (`starts_on`/`ends_on`); multi-weekday |
| Quick-add recurrence tokens | W1.5 | `every` / `every!` + from/until frame phrases |
| Intraday multi-occurrence (habits) | W3+ | Multiple times per day; likely NL/`BYHOUR` on existing engine — consider Wave 4 if W3 splits |
| Subtask inheritance | MVP | Nesting rules only; scheduler inheritance W2 |

### Labels & Filters

| Feature | Wave | Notes |
|---------|------|-------|
| Labels (many-to-many) | MVP | |
| Label colors | MVP | Presets in 08-color-palette |
| Standalone label management (create/prune without task) | MVP | Dedicated Labels UI |
| Lowercase-only label names | MVP | Normalize on write; unique per owner |
| Label delete with reassign/migrate | W1.5 | Optional bulk apply other label(s) to affected tasks before prune |
| Epic/project color presets | MVP | Synesis/Phronesis-aligned presets; entity custom hex picker W1.5 |
| Fixed smart views (Inbox, Today, Upcoming) | MVP | System saved_filters |
| Smart view by Project | MVP | |
| Smart view by Epic | W1.5 closeout | **Shipped** — sidebar epic → `?epic_id=` rollup |
| Smart view by Label | MVP | |
| Saved filter query language | W2b | Predicate model from MVP; slip to W3+ if capacity |
| Custom filter favorites | W2b | User-authored saved_filters |

### Views

| Feature | Wave | Notes |
|---------|------|-------|
| List view | MVP | Primary task list |
| Today view | MVP | |
| Upcoming view | MVP | 7-day horizon default |
| Calendar view (day/week) | MVP | Due markers + manual blocks; click/slot create + modal edit |
| Calendar view (month) | W1.5 | Not shipped Wave 1; optional/non-blocker |
| Day-of-year + ISO week numbers in chrome | MVP | Shipped in calendar titles |
| Board / Kanban | W3+ | Optional column view; sections may map to columns |
| Upcoming drag-plan timeline | W1.5 closeout | Calendar drag — **shipped** (desktop) |
| Sidebar → calendar drag-schedule | W2b late / W3 | Drop task from list onto day/time slot to create block |
| Gantt / project timeline | Out | Calendar only in MVP |
| Productivity trends / charts | Out | No gamification |

### Capture & Input

| Feature | Wave | Notes |
|---------|------|-------|
| Quick-add box | MVP | |
| Natural language parser (deterministic) | MVP | Duration, priority, due, epic/project tags |
| Quick-add recurrence tokens | W1.5 | `every` / `every!` + from/until |
| Keyboard shortcuts | MVP | q, j/k navigate, etc. |
| Voice input | W4 | Candidate |
| Email-to-task | W4 | Candidate |

### Search & History

| Feature | Wave | Notes |
|---------|------|-------|
| Global search | MVP | Title + description |
| Undo last action | MVP | Session stack; delete undo recreates (new IDs) |
| Task soft-delete + restore | W2c | `deleted_at` on tasks; true undelete same UUID |
| Activity log / audit trail | W2b | schedule_runs + task history lite |
| Completed task history | W1.5 closeout | Show/hide completed toggle — **shipped** |
| Smart view by Epic | W1.5 closeout | Click epic in sidebar; `?epic_id=` — **shipped** |

### Reminders & Notifications

| Feature | Wave | Notes |
|---------|------|-------|
| Time-based reminders | W1.5 | Absolute `fire_at`; in-app toast + optional browser Notification |
| Location reminders | W4 | Candidate |
| In-app notifications | W1.5 | Toast via client poll + ack |
| Browser Notification API | W1.5 | Optional; channel=`browser` + permission |
| Push (mobile) | Out | No mobile app |

### Integrations & Import

| Feature | Wave | Notes |
|---------|------|-------|
| Todoist CSV/JSON import | W3+ | Deferred from W1.5 (stale upstream); CSV/JSON → hierarchy |
| Outline ingest (curriculum JSON) | W3+ Theme F | Operator paste/upload → review → apply; golden fixture under `testdata/outlines/`; [ADR-011](./adr/ADR-011-templates-outline-ingest.md). No Coursera client. |
| Google Calendar sync | W2a | Pull + optional mirror push; before scheduler |
| Multi-calendar subscriptions | W2a Slice 2 | One primary (busy) + informational overlays; mirror toggle to primary |
| 24×7 calendar viewport | W2a Slice 2 | Default 6A–10P; Settings/chrome toggle for full day |
| Time Map temporary overrides | W2b | Day/week dated windows that auto-expire |
| Scoped bundles | W2b late / W3 | Bundle constrained to epic or project |
| Scheduling settings expansion | W2b | Buffers, default duration, default block vs bundle style |
| Fuzzy scheduling depth | W2b session | Deferral, MBL overrides, soft plans — dedicated plan first |
| Microsoft Calendar sync | W3 | Slice 2 — after account polish |
| iCloud calendar | Out | Unless reopened |
| Zapier / IFTTT / automation hubs | Post-W3 | Backlog candidate after W3; not planned in W1–W3 |
| Notion / Obsidian deep links or sync | Post-W3 (maybe late W3) | Backlog: open/link notes from tasks; full sync unlikely early. Prefer post-W3; reconsider at W3 only if cheap |
| Public API / webhooks | W3 / Post-W3 | REST in MVP; webhooks / hub connectors later (supports Zapier-class flows) |

### Collaboration & Social

| Feature | Wave | Notes |
|---------|------|-------|
| Comments | Out | |
| Assignees | Out | |
| Shared projects | Out | |
| Team workspaces | Out | |
| Karma / streaks | Out | Explicit non-goal |
| AI assist (Todoist-style) | W3+ | SLM local assist; never blocks CRUD |

### Platform

| Feature | Wave | Notes |
|---------|------|-------|
| Web app (responsive) | MVP | Basic viewport; stacked narrow layout only |
| Responsive / phone-friendly polish | W1.6 | Drawer nav, detail sheet, touch targets, narrow calendar — shipped |
| UI themes (Settings) | MVP | Nine presets (Dark, Solarized Dark/Light, Light, Black, Forest, Midnight, Amethyst, Garnet) + hex overrides |
| Desktop (Tauri) | W3 | Slice 3 — after MS Calendar; Desktop ADR first |
| Mobile native | Out | Responsive web only (W1.6 polish) |
| Offline PWA | Out | Online-first MVP |
| Flutter client | Out | Rejected |

*MVP viewport meta + stacked `@media` exist; W1.6 is the intentional phone-daily-driver gate after Tunnel.*

---

## SkedPal-Class Features

### Time Estimation

| Feature | Wave | Notes |
|---------|------|-------|
| Estimated duration | MVP | Integer minutes |
| Min block duration (slice floor) | W2b UI | Schema MVP |
| Max block duration (slice ceiling) | W2b UI | Schema MVP |
| Work capacity baselines (8h/40h/160h) | MVP | Display + parser |
| Scale-aware duration formatting | MVP | UI formatter |

### Time Maps & Windows

| Feature | Wave | Notes |
|---------|------|-------|
| Focus windows / Time Maps | W2b Slice 1 | CRUD UI + task binding + `@morning`/`@afternoon`/`@evening`; seeds on provision — **shipped** |
| Painted Time Maps (green/yellow/red) | W2b late / W3 | Multi-band single map; preferred → overflow → forbidden |
| Preferred time window per task | W2b | FK on tasks |
| Working hours configuration | W2b | Via focus_windows + settings |
| Fuzzy window tokens (@morning, etc.) | W2b | Quick-add binding |

### Plans & Soft Targets

| Feature | Wave | Notes |
|---------|------|-------|
| Plans (flexible time frames) | W2b | CRUD + task bind + Settings UI — **shipped** (Plans B) |
| soft_target_at on tasks | W2b UI | Task detail + list badges; copied on plan bind — **shipped** |
| Soft vs hard constraint semantics | W2b | Soft=plan/window; hard=deadline/pin/busy |
| Rule inheritance from parent | W2b | Window/plan propagation |

### Scheduling Engine

| Feature | Wave | Notes |
|---------|------|-------|
| Auto time-blocking | W2b | Async worker |
| Update Schedule (replan) | W2b | Explicit user action |
| Slice & fit algorithm | W2b | Min/max block splitting |
| UPS priority scoring | W2b | Configurable weights |
| Urgency decay (exponential) | W2b | k=0.5 default |
| Dependency-aware ordering | W2b | Topological sort |
| Inter-block buffer | W2b | Default 5 min, configurable |
| Overbook detection & flag | W2a Slice 3 / W2b | W2a: visual conflict flags via `GET /calendar/conflicts` (no status mutation). W2b: `schedule_status.overbooked` |
| Contiguity optimization | W2b | Prefer back-to-back slices |

### Calendar & Blocks

| Feature | Wave | Notes |
|---------|------|-------|
| Manual scheduled blocks | MVP | Click empty slot or task; modal edit start/end |
| Pin / lock blocks | W2b | `is_pinned`; scheduler never moves until unpin. Use case: fixed clock time (e.g. prep before someone else's meeting) — not due/deadline. MVP stores flag only |
| Drag reschedule blocks / due markers | W1.5 closeout | **Shipped** on desktop; modal on narrow |
| Bundled / knockout task lists | W2b | vs formal blocks |
| External calendar as busy source | W2a | Google; MS W3+ |
| Calendar cutout / busy map | W2a | Step 1 before Update Schedule |
| Status tracker (% done, overbook count) | W2b | Utility, not gamification |

### Priority & Ranking

| Feature | Wave | Notes |
|---------|------|-------|
| P1–P4 explicit priority | MVP | |
| Dynamic UPS ranking | W2b | |
| Relative priority board | Out | P1–P4 sufficient unless reopened |
| Epic alignment boost | W2b | UPS E component |

### Capture & Intelligence

| Feature | Wave | Notes |
|---------|------|-------|
| Outline-first capture | MVP | List hierarchy + quick-add |
| SLM-assisted parsing | W3+ | Ollama; never blocks CRUD |
| SLM schedule hints | W3+ | Advisory only |

---

## Infrastructure & Ops Features

| Feature | Wave | Notes |
|---------|------|-------|
| Local Docker Compose stack | MVP | postgres + api + web |
| Docker Desktop (Windows default) | MVP | ADR-004 |
| Podman-compatible Compose | MVP | Alternate runtime |
| Local-only auth | MVP | ADR-003 |
| Password login | W1.5 | Admin can already set any user’s password |
| Multi-account household login | W1.5 | N personal `users` rows; same URI; `owner_id` isolation — not teams ([ADR-002](./adr/ADR-002-single-user.md)) |
| Admin full profile edit (except username) | W3 | Slice 1 — email, display name, password, disable; username immutable ([ADR-007](./adr/ADR-007-account-self-service.md)) |
| Self-service account settings | W3 | Slice 1 — `PATCH /auth/me` |
| Temp / forced password reset | W3 | Slice 1 — `must_change_password` |
| Cloudflare Tunnel remote access | W1.5 | Compose profile `tunnel`; see [CLOUDFLARE-TUNNEL.md](./CLOUDFLARE-TUNNEL.md) |
| Cloudflare Access | W1.5 | Optional; documented with Tunnel |
| pg_dump backup one-liner | MVP | Documented in root README |
| Scheduled pg_dump backup script | W1.5 | `scripts/backup-postgres.ps1` / `.sh`; prune via `BACKUP_KEEP_DAYS` |
| Hosted Postgres fallback | W4 | Not default |
| WebSocket invalidation | W2b | Optional; REST sufficient MVP |
| Dependency Hygiene wave | Pre-version | Toolchain + deps pass |

---

## MVP Cut Summary

**Ship in Wave 1 (MVP):** Todoist core (hierarchy extension, labels, fixed smart views Inbox/Today/Upcoming/Project/Label, quick-add, search, undo, calendar day/week with click/slot blocks + modal edit, day-of-year/ISO week chrome, nine UI themes, local Compose, local auth, pg_dump one-liner in README).

**Schema-only in Wave 1:** Recurrence, reminders, deadline_at, soft_target_at, scheduler fields, external calendar tables, focus_windows. (Recurrence + reminders engines landed in W1.5.)

**Defer to W1.5 (shipped core + closeout):** Recurrence, reminders, login, household, label reassign, backup script, Tunnel; show-completed, calendar drag, epic aggregate. Calendar month optional/non-blocker.

**Defer to W1.6 (shipped):** Phone-friendly / responsive cleanup.

**Defer to W2a:** Google Calendar sync + busy map / cutout.

**Defer to W2b:** SkedPal triad, auto-scheduler, UPS, pins/deadline UI, dependency enforcement, soft-delete + session restore; filter QL / WebSocket if capacity.

**Defer to W3:** Account polish (Slice 1) → Microsoft Calendar (Slice 2) → Tauri (Slice 3). See [07-wave-roadmap.md](./07-wave-roadmap.md) cut.

**Defer to W3+:** Todoist import, intraday multi-occurrence habits, optional Kanban; **Theme F** templates prove-it + outline ingest ([ADR-011](./adr/ADR-011-templates-outline-ingest.md)).

**Defer to W4 / candidates:** Location reminders, voice, email-to-task, full template catalog/CRUD, hosted Postgres, saved filter query language.

**Parked W2c:** Soft-delete, Time Map overrides, scoped bundles, sidebar drag, compose worker (after W3 or as fallout).

**Post-W3 backlog:** Zapier / IFTTT / automation-hub connectors; Notion / Obsidian deep links; task handoff between household accounts (discussion only).

**Never (unless reopened):** Team workspaces, karma, Flutter, attachments, gamification.
