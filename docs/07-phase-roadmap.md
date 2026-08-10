# Phase Roadmap

Phased delivery from MVP through P3. Each version begins with a **Dependency Hygiene** wave unless explicitly overridden.

---

## Version Structure

```
[Prior version freeze/tag]
        ↓
Dependency Hygiene Wave (toolchain, pub/package majors, container pins, doc pins)
        ↓
Feature waves (MVP → P1.5 → P2 → P3)
```

Dependency Hygiene is a gate: feature work for a new version does not start until hygiene exits or a documented quick-scan pass is recorded.

---

## Phase 1 — MVP (Current Target)

**Goal:** Personal single-user task management with calendar visibility and fast local deployment.

### Deliverables

| Wave | Output |
|------|--------|
| Wave 0 | Repo scaffolding, Compose, ADRs, hygiene pins |
| Wave 1 | Documentation package (`docs/`) |
| Wave 2 | FastAPI + Alembic + CRUD API + quick-add parse |
| Wave 3 | Vite/React SPA — lists, smart views, calendar, quick-add |
| Wave 4 | Local deploy docs, backup one-liner |

### Scope

- Full hierarchy (Epic → Nested Subtask)
- Labels, fixed smart views, quick-add, search, undo
- Calendar day/week (+ month if cheap)
- Manual scheduled_blocks
- Local Docker Compose + Postgres
- Local-only auth (bootstrap user)
- Schema stubs for recurrence, reminders, scheduler, calendars

### Exit Criteria

See [06-mvp-backlog.md](./06-mvp-backlog.md). No calendar sync, no auto-scheduler, no remote auth.

---

## Phase 1.5 — Soon After MVP

**Goal:** Daily-driver enhancements and remote-ready auth without scheduler complexity.

### Features

| Feature | Notes |
|---------|-------|
| Recurrence engine | `every` / `every!` semantics; quick-add tokens |
| Todoist import | CSV/JSON export → hierarchy mapping |
| Time-based reminders | In-app + optional browser Notification API |
| Login / remote-ready auth | Password session and/or Cloudflare Access |
| Backup script | Scheduled pg_dump optional |
| Cloudflare Tunnel | Template for remote access to home host |

### Auth Progression

MVP: local bootstrap user, no login wall.

P1.5: `password_hash` populated; login/logout endpoints; session cookies; optional Cloudflare Access in front of Tunnel.

Schema already has `users` + `password_hash` from baseline — no migration required for basic password auth.

### Not in P1.5

- Auto-scheduler
- Google Calendar sync
- Filter query language
- SLM

---

## Phase 2 — Scheduler + Google Calendar

**Goal:** SkedPal-class automated time-blocking with external calendar awareness.

### SkedPal Triad (Confirmed)

1. **Time Maps** — `focus_windows` UI and task binding
2. **Plans** — flexible time frames; `soft_target_at` surfaced
3. **Update Schedule** — explicit replan action; async worker

### Additional P2 Features

| Feature | Notes |
|---------|-------|
| Auto-scheduler worker | Decoupled from CRUD (ADR-005) |
| UPS scoring + slice/fit | U = 100·e^(-k·max(Slack,0)), k=0.5 |
| Pins, soft vs hard | `deadline_at` enforced; pinned blocks immovable until unpin (fixed clock-time work, e.g. prep before someone else’s meeting — not due/deadline) |
| Bundled vs formal blocks | Knockout lists → blocks on replan |
| Rule inheritance | Parent → child window/plan propagation |
| Overbook UI | schedule_status.overbooked |
| deadline_at UI | Hard commit surfaced |
| Google Calendar sync | Bidirectional; busy map input |
| Task dependency enforcement | Topological ordering in scheduler |
| Saved filter query language | User-authored saved_filters; fixed views as special case |
| WebSocket invalidation | Optional cache push |
| Status tracker | Today's blocks done % + overbook count (utility, not gamification) |

### GCal Conflict Policy

External hard events and pinned blocks are both BUSY. Scheduler never auto-moves pins. Overbook flagged, not silently dropped.

---

## Phase 3 — SLM + Microsoft + Desktop

**Goal:** Intelligence assist and native desktop without rewriting domain logic.

### Features

| Feature | Notes |
|---------|-------|
| Local SLM (Ollama) | Ambiguous quick-add + schedule hints; never blocks CRUD |
| Microsoft Calendar | calendar_provider.microsoft sync |
| Tauri 2 desktop | Wraps web UI + FastAPI sidecar |
| Hosted Postgres fallback | Optional; local Compose remains default |

### Desktop Bundle Strategy

Tauri shell + embedded API process talking to local Postgres (Compose service or documented install). Same REST contract; no second data model.

---

## Infrastructure Timeline

| Capability | Phase |
|------------|-------|
| Docker Desktop + Compose (local) | MVP |
| pg_dump backup docs | MVP |
| Cloudflare Tunnel | P1.5+ (post-MVP remote) |
| Cloudflare Access | P1.5 (optional IdP) |
| Hosted Postgres | P3 fallback |
| Podman alternate runtime | MVP-compatible (ADR-004) |

---

## Explicit Non-Goals (All Phases)

- Team workspaces, sharing, comments, assignees
- Karma, streaks, gamification
- Board / Kanban timeline
- Flutter (rejected — Tauri + shared web UI)
- Mobile native apps (responsive web until desktop)
- Location reminders, attachments
- iCloud calendar (unless reopened)

---

## Dependency Hygiene Wave Checklist

Run before each major version's feature waves:

- [ ] Pin Python, Node, Postgres image versions
- [ ] Audit FastAPI, SQLAlchemy, Alembic, Vite, React majors
- [ ] Review container base image CVEs
- [ ] Update doc pins and ADR references
- [ ] Record quick-scan or full pass in version notes

---

## Documentation Map

| Phase | Primary docs |
|-------|--------------|
| MVP | 01–07, sql/001_baseline.sql, adr/001–005 |
| P1.5 | Update 02, 03, 05, 06, 07; new ADRs as needed |
| P2 | Scheduler spec expansion in 02; calendar sync in 05 |
| P3 | Desktop bundle ADR; SLM assist appendix |

---

## Related Documents

- [01-product-vision.md](./01-product-vision.md)
- [06-mvp-backlog.md](./06-mvp-backlog.md)
- [03-feature-catalog.md](./03-feature-catalog.md)
- [adr/](./adr/)
