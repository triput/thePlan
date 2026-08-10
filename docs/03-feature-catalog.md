# Feature Catalog

Todoist + SkedPal feature harvest with wave tags. This catalog formalizes parity targets; it is based on the original draft, 2026 product documentation refresh, and locked plan decisions — not a live click-through audit.

**Wave tags:** MVP | W1.5 | W2 | W3 | Out

**Terminology:** Wave tags (W1.5/W2/W3) = delivery waves. **P1–P4** = task priority only (enum, UI, UPS scoring).

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
| Templates | W3 | Backlog nice-to-have; low priority; maybe later |
| Project/view sharing | Out | Single-user |

### Task Core

| Feature | Wave | Notes |
|---------|------|-------|
| Title & description | MVP | Plain text description |
| Markdown notes | W2 | Rendering in detail view |
| Priority P1–P4 | MVP | |
| Due date / datetime | MVP | `due_at` |
| Deadline (separate from due) | W2 UI | `deadline_at` in schema from MVP |
| Duration estimate | MVP | Minutes internally |
| Complete / uncomplete | MVP | Parent warn-and-allow policy |
| Parent bulk-complete children | MVP | Option (b) in completion dialog |
| Task dependencies | W2 | Schema in MVP; enforced by scheduler W2 |
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
| Label delete with reassign/migrate | W1.5 | On prune: optional bulk replace deleted label with one or more other labels before detach; keep related tasks correctly tagged |
| Epic/project color presets | MVP | Synesis/Phronesis-aligned presets; entity custom hex picker W1.5 |
| Fixed smart views (Inbox, Today, Upcoming) | MVP | System saved_filters |
| Smart view by Project | MVP | |
| Smart view by Epic | W1.5 | Epic aggregate rollup UI deferred; projects/labels shipped |
| Smart view by Label | MVP | |
| Saved filter query language | W2 | Predicate model from MVP |
| Custom filter favorites | W2 | User-authored saved_filters |

### Views

| Feature | Wave | Notes |
|---------|------|-------|
| List view | MVP | Primary task list |
| Today view | MVP | |
| Upcoming view | MVP | 7-day horizon default |
| Calendar view (day/week) | MVP | Due markers + manual blocks; click/slot create + modal edit |
| Calendar view (month) | W1.5 | Not shipped Wave 1; optional/non-blocker |
| Day-of-year + ISO week numbers in chrome | MVP | Shipped in calendar titles |
| Board / Kanban | W3 | Optional column view for project status; not an MVP/W2 timeline. Sections may map to columns |
| Upcoming drag-plan timeline | W1.5 | Calendar drag deferred W1.5 |
| Gantt / project timeline | Out | Calendar only in MVP |
| Productivity trends / charts | Out | No gamification |

### Capture & Input

| Feature | Wave | Notes |
|---------|------|-------|
| Quick-add box | MVP | |
| Natural language parser (deterministic) | MVP | Duration, priority, due, epic/project tags |
| Quick-add recurrence tokens | W1.5 | `every` / `every!` + from/until |
| Keyboard shortcuts | MVP | q, j/k navigate, etc. |
| Voice input | W3 | Priority-3 backlog; no sooner than W2; likely W3 |
| Email-to-task | W3 | Same as voice; not before W2; likely W3 |

### Search & History

| Feature | Wave | Notes |
|---------|------|-------|
| Global search | MVP | Title + description |
| Undo last action | MVP | Session stack; delete undo recreates (new IDs) |
| Task soft-delete + restore | W2 | Optional W1.5; `deleted_at` on tasks; true undelete same UUID |
| Activity log / audit trail | W2 | schedule_runs + task history lite |
| Completed task history | W1.5 | Show/hide toggle deferred |

### Reminders & Notifications

| Feature | Wave | Notes |
|---------|------|-------|
| Time-based reminders | W1.5 | Schema stub MVP |
| Location reminders | W3 | W3 candidate; not W1/W1.5/W2 |
| In-app notifications | W1.5 | |
| Browser Notification API | W1.5 | Optional |
| Push (mobile) | Out | No mobile app |

### Integrations & Import

| Feature | Wave | Notes |
|---------|------|-------|
| Todoist CSV/JSON import | W3 | Deferred from W1.5 (stale upstream); CSV/JSON → hierarchy |
| Google Calendar sync | W2 | Bidirectional |
| Microsoft Calendar sync | W3 | |
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
| AI assist (Todoist-style) | W3 | SLM local assist W3 |

### Platform

| Feature | Wave | Notes |
|---------|------|-------|
| Web app (responsive) | MVP | |
| UI themes (Settings) | MVP | Nine presets (Dark, Solarized Dark/Light, Light, Black, Forest, Midnight, Amethyst, Garnet) + hex overrides |
| Desktop (Tauri) | W3 | |
| Mobile native | Out | Responsive web only |
| Offline PWA | Out | Online-first MVP |
| Flutter client | Out | Rejected |

---

## SkedPal-Class Features

### Time Estimation

| Feature | Wave | Notes |
|---------|------|-------|
| Estimated duration | MVP | Integer minutes |
| Min block duration (slice floor) | W2 UI | Schema MVP |
| Max block duration (slice ceiling) | W2 UI | Schema MVP |
| Work capacity baselines (8h/40h/160h) | MVP | Display + parser |
| Scale-aware duration formatting | MVP | UI formatter |

### Time Maps & Windows

| Feature | Wave | Notes |
|---------|------|-------|
| Focus windows / Time Maps | W2 | `focus_windows` table |
| Preferred time window per task | W2 | FK on tasks |
| Working hours configuration | W2 | Via focus_windows + settings |
| Fuzzy window tokens (@morning, etc.) | W2 | Quick-add binding |

### Plans & Soft Targets

| Feature | Wave | Notes |
|---------|------|-------|
| Plans (flexible time frames) | W2 | First-class entities |
| soft_target_at on tasks | W2 UI | Schema reserved MVP |
| Soft vs hard constraint semantics | W2 | Soft=plan/window; hard=deadline/pin/busy |
| Rule inheritance from parent | W2 | Window/plan propagation |

### Scheduling Engine

| Feature | Wave | Notes |
|---------|------|-------|
| Auto time-blocking | W2 | Async worker |
| Update Schedule (replan) | W2 | Explicit user action |
| Slice & fit algorithm | W2 | Min/max block splitting |
| UPS priority scoring | W2 | Configurable weights |
| Urgency decay (exponential) | W2 | k=0.5 default |
| Dependency-aware ordering | W2 | Topological sort |
| Inter-block buffer | W2 | Default 5 min, configurable |
| Overbook detection & flag | W2 | schedule_status.overbooked |
| Contiguity optimization | W2 | Prefer back-to-back slices |

### Calendar & Blocks

| Feature | Wave | Notes |
|---------|------|-------|
| Manual scheduled blocks | MVP | Click empty slot or task; modal edit start/end |
| Pin / lock blocks | W2 | `is_pinned`; scheduler never moves until unpin. Use case: fixed clock time (e.g. prep before someone else's meeting) — not due/deadline. MVP stores flag only |
| Drag reschedule blocks / due markers | W1.5 | Click/slot + modal edit shipped in Wave 1 |
| Bundled / knockout task lists | W2 | vs formal blocks |
| External calendar as busy source | W2 | Google; MS W3 |
| Calendar cutout / busy map | W2 | Step 1 of pipeline |
| Status tracker (% done, overbook count) | W2 | Utility, not gamification |

### Priority & Ranking

| Feature | Wave | Notes |
|---------|------|-------|
| P1–P4 explicit priority | MVP | |
| Dynamic UPS ranking | W2 | |
| Relative priority board | Out | P1–P4 sufficient unless reopened |
| Epic alignment boost | W2 | UPS E component |

### Capture & Intelligence

| Feature | Wave | Notes |
|---------|------|-------|
| Outline-first capture | MVP | List hierarchy + quick-add |
| SLM-assisted parsing | W3 | Ollama; never blocks CRUD |
| SLM schedule hints | W3 | Advisory only |

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
| Admin full profile edit (except username) | W3 | Email, display name, password, disable; username immutable |
| Self-service account settings | W3 | User manages own password, email, display name |
| Temp / forced password reset | W3 | Admin sets temp password; must change on next login |
| Cloudflare Tunnel remote access | W1.5+ | Post-MVP hosting |
| Cloudflare Access | W1.5 | Optional IdP |
| pg_dump backup one-liner | MVP | Documented in root README |
| Scheduled pg_dump backup script | W1.5 | Optional cron/task scheduler |
| Hosted Postgres fallback | W3 | Not default |
| WebSocket invalidation | W2 | Optional; REST sufficient MVP |
| Dependency Hygiene wave | Pre-version | Toolchain + deps pass |

---

## MVP Cut Summary

**Ship in Wave 1 (MVP):** Todoist core (hierarchy extension, labels, fixed smart views Inbox/Today/Upcoming/Project/Label, quick-add, search, undo, calendar day/week with click/slot blocks + modal edit, day-of-year/ISO week chrome, nine UI themes, local Compose, local auth, pg_dump one-liner in README).

**Schema-only in Wave 1:** Recurrence, reminders, deadline_at, soft_target_at, scheduler fields, external calendar tables, focus_windows.

**Defer to W1.5:** Epic aggregate smart view, show-completed toggle, calendar drag, recurrence engine, reminders, login, multi-account household login; label delete reassign/migrate (bulk apply other labels on prune); scheduled pg_dump script; calendar month view (optional).

**Defer to W2:** Full SkedPal triad, auto-scheduler, GCal, filter query language, dependency enforcement, pinned-block auto-respect, task soft-delete + session restore.

**Defer to W3:** SLM, Microsoft calendar, Tauri desktop, optional Kanban, location reminders, voice input, email-to-task, templates; Todoist import; admin full profile edit (except username); self-service password/email/display name; temp/forced password reset; intraday multi-occurrence habits (likely NL/`BYHOUR` on existing recurrence). W3 is crowding — consider a Wave 4 split before planning starts.

**Post-W3 backlog:** Zapier / IFTTT / automation-hub connectors (and related inbound/outbound webhooks as needed); Notion / Obsidian deep links or light sync (possible late W3 if cheap, otherwise post-W3); task handoff between household accounts (discussion item only). Not in W1–W2 scope.

**Never (unless reopened):** Team workspaces, karma, Flutter, attachments, gamification.
