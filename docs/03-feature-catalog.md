# Feature Catalog

Todoist + SkedPal feature harvest with phase tags. This catalog formalizes parity targets; it is based on the original draft, 2026 product documentation refresh, and locked plan decisions — not a live click-through audit.

**Phase tags:** MVP | P1.5 | P2 | P3 | Out

---

## Todoist-Class Features

### Hierarchy & Organization

| Feature | Phase | Notes |
|---------|-------|-------|
| Projects | MVP | With sections |
| Sections | MVP | Sort order within project |
| Epics (top-level initiatives) | MVP | Extension beyond Todoist |
| Subtasks (1 level) | MVP | |
| Nested subtasks (2 levels deep) | MVP | Extension beyond Todoist |
| Nested projects | Out | Epic replaces sub-project pattern |
| Inbox (no project) | MVP | `project_id IS NULL` |
| Archive project/epic | MVP | Soft archive |
| Reorder tasks/sections | MVP | sort_order |
| Templates | Out | Low priority |
| Project/view sharing | Out | Single-user |

### Task Core

| Feature | Phase | Notes |
|---------|-------|-------|
| Title & description | MVP | Plain text description |
| Markdown notes | P2 | Rendering in detail view |
| Priority P1–P4 | MVP | |
| Due date / datetime | MVP | `due_at` |
| Deadline (separate from due) | P2 UI | `deadline_at` in schema from MVP |
| Duration estimate | MVP | Minutes internally |
| Complete / uncomplete | MVP | Parent warn-and-allow policy |
| Parent bulk-complete children | MVP | Option (b) in completion dialog |
| Task dependencies | P2 | Schema in MVP; enforced by scheduler P2 |
| Recurring due dates (`every`, `every!`) | P1.5 | Schema stub MVP |
| Subtask inheritance | MVP | Nesting rules only; scheduler inheritance P2 |

### Labels & Filters

| Feature | Phase | Notes |
|---------|-------|-------|
| Labels (many-to-many) | MVP | |
| Label colors | MVP | |
| Fixed smart views (Inbox, Today, Upcoming) | MVP | System saved_filters |
| Smart view by Project | MVP | |
| Smart view by Epic | MVP | |
| Smart view by Label | MVP | |
| Saved filter query language | P2 | Predicate model from MVP |
| Custom filter favorites | P2 | User-authored saved_filters |

### Views

| Feature | Phase | Notes |
|---------|-------|-------|
| List view | MVP | Primary task list |
| Today view | MVP | |
| Upcoming view | MVP | 7-day horizon default |
| Calendar view (day/week) | MVP | Due markers + manual blocks |
| Calendar view (month) | MVP | If cheap; not exit blocker |
| Board / Kanban | Out | Explicit non-goal |
| Upcoming drag-plan timeline | MVP | Via calendar view |
| Gantt / project timeline | Out | Calendar only in MVP |
| Productivity trends / charts | Out | No gamification |

### Capture & Input

| Feature | Phase | Notes |
|---------|-------|-------|
| Quick-add box | MVP | |
| Natural language parser (deterministic) | MVP | Duration, priority, due, epic/project tags |
| Quick-add recurrence tokens | P1.5 | |
| Keyboard shortcuts | MVP | q, j/k navigate, etc. |
| Voice input | Out | |
| Email-to-task | Out | |

### Search & History

| Feature | Phase | Notes |
|---------|-------|-------|
| Global search | MVP | Title + description |
| Undo last action | MVP | Session stack |
| Activity log / audit trail | P2 | schedule_runs + task history lite |
| Completed task history | MVP | Show/hide toggle |

### Reminders & Notifications

| Feature | Phase | Notes |
|---------|-------|-------|
| Time-based reminders | P1.5 | Schema stub MVP |
| Location reminders | Out | |
| In-app notifications | P1.5 | |
| Browser Notification API | P1.5 | Optional |
| Push (mobile) | Out | No mobile app |

### Integrations & Import

| Feature | Phase | Notes |
|---------|-------|-------|
| Todoist CSV/JSON import | P1.5 | Soon after MVP |
| Google Calendar sync | P2 | Bidirectional |
| Microsoft Calendar sync | P3 | |
| iCloud calendar | Out | Unless reopened |
| Zapier / IFTTT | Out | |
| Public API / webhooks | P3 | REST exists; webhooks later |

### Collaboration & Social

| Feature | Phase | Notes |
|---------|-------|-------|
| Comments | Out | |
| Assignees | Out | |
| Shared projects | Out | |
| Team workspaces | Out | |
| Karma / streaks | Out | Explicit non-goal |
| AI assist (Todoist-style) | Out / P3 | SLM local assist P3 |

### Platform

| Feature | Phase | Notes |
|---------|-------|-------|
| Web app (responsive) | MVP | |
| Desktop (Tauri) | P3 | |
| Mobile native | Out | Responsive web only |
| Offline PWA | Out | Online-first MVP |
| Flutter client | Out | Rejected |

---

## SkedPal-Class Features

### Time Estimation

| Feature | Phase | Notes |
|---------|-------|-------|
| Estimated duration | MVP | Integer minutes |
| Min block duration (slice floor) | P2 UI | Schema MVP |
| Max block duration (slice ceiling) | P2 UI | Schema MVP |
| Work capacity baselines (8h/40h/160h) | MVP | Display + parser |
| Scale-aware duration formatting | MVP | UI formatter |

### Time Maps & Windows

| Feature | Phase | Notes |
|---------|-------|-------|
| Focus windows / Time Maps | P2 | `focus_windows` table |
| Preferred time window per task | P2 | FK on tasks |
| Working hours configuration | P2 | Via focus_windows + settings |
| Fuzzy window tokens (@morning, etc.) | P2 | Quick-add binding |

### Plans & Soft Targets

| Feature | Phase | Notes |
|---------|-------|-------|
| Plans (flexible time frames) | P2 | First-class entities |
| soft_target_at on tasks | P2 UI | Schema reserved MVP |
| Soft vs hard constraint semantics | P2 | Soft=plan/window; hard=deadline/pin/busy |
| Rule inheritance from parent | P2 | Window/plan propagation |

### Scheduling Engine

| Feature | Phase | Notes |
|---------|-------|-------|
| Auto time-blocking | P2 | Async worker |
| Update Schedule (replan) | P2 | Explicit user action |
| Slice & fit algorithm | P2 | Min/max block splitting |
| UPS priority scoring | P2 | Configurable weights |
| Urgency decay (exponential) | P2 | k=0.5 default |
| Dependency-aware ordering | P2 | Topological sort |
| Inter-block buffer | P2 | Default 5 min, configurable |
| Overbook detection & flag | P2 | schedule_status.overbooked |
| Contiguity optimization | P2 | Prefer back-to-back slices |

### Calendar & Blocks

| Feature | Phase | Notes |
|---------|-------|-------|
| Manual scheduled blocks | MVP | User-placed |
| Pin / lock blocks | P2 | is_pinned; MVP stores flag |
| Drag reschedule blocks | MVP | |
| Bundled / knockout task lists | P2 | vs formal blocks |
| External calendar as busy source | P2 | Google; MS P3 |
| Calendar cutout / busy map | P2 | Phase 1 of pipeline |
| Status tracker (% done, overbook count) | P2 | Utility, not gamification |

### Priority & Ranking

| Feature | Phase | Notes |
|---------|-------|-------|
| P1–P4 explicit priority | MVP | |
| Dynamic UPS ranking | P2 | |
| Relative priority board | Out | P1–P4 sufficient unless reopened |
| Epic alignment boost | P2 | UPS E component |

### Capture & Intelligence

| Feature | Phase | Notes |
|---------|-------|-------|
| Outline-first capture | MVP | List hierarchy + quick-add |
| SLM-assisted parsing | P3 | Ollama; never blocks CRUD |
| SLM schedule hints | P3 | Advisory only |

---

## Infrastructure & Ops Features

| Feature | Phase | Notes |
|---------|-------|-------|
| Local Docker Compose stack | MVP | postgres + api + web |
| Docker Desktop (Windows default) | MVP | ADR-004 |
| Podman-compatible Compose | MVP | Alternate runtime |
| Local-only auth | MVP | ADR-003 |
| Password login | P1.5 | |
| Cloudflare Tunnel remote access | P1.5+ | Post-MVP hosting |
| Cloudflare Access | P1.5 | Optional IdP |
| pg_dump backup script | P1.5 | Documented in MVP |
| Hosted Postgres fallback | P3 | Not default |
| WebSocket invalidation | P2 | Optional; REST sufficient MVP |
| Dependency Hygiene wave | Pre-version | Toolchain + deps pass |

---

## MVP Cut Summary

**Ship in Phase 1:** Todoist core (hierarchy extension, labels, fixed smart views, quick-add, search, undo, calendar day/week, manual blocks, local Compose, local auth).

**Schema-only in Phase 1:** Recurrence, reminders, deadline_at, soft_target_at, scheduler fields, external calendar tables, focus_windows.

**Defer to P1.5:** Recurrence engine, import, reminders, login.

**Defer to P2:** Full SkedPal triad, auto-scheduler, GCal, filter query language, dependency enforcement.

**Defer to P3:** SLM, Microsoft calendar, Tauri desktop.

**Never (unless reopened):** Teams, karma, board, Flutter, location reminders, attachments, gamification.
