# Wave Roadmap

Delivery waves from MVP through W3. Each version begins with a **Dependency Hygiene** wave unless explicitly overridden.

---

## Version Structure

```
[Prior version freeze/tag]
        ↓
Dependency Hygiene Wave (toolchain, pub/package majors, container pins, doc pins)
        ↓
Feature waves (MVP → W1.5 → W2 → W3)
```

Dependency Hygiene is a gate: feature work for a new version does not start until hygiene exits or a documented quick-scan pass is recorded.

---

## Wave 1 — MVP (Complete — exited 2026-08-10)

**Goal:** Personal single-user task management with calendar visibility and fast local deployment.

### Deliverables

| Wave | Output |
|------|--------|
| Wave 0 | Repo scaffolding, Compose, ADRs, hygiene pins |
| Wave 1 | Documentation package (`docs/`) |
| Wave 2 | FastAPI + Alembic + CRUD API + quick-add parse |
| Wave 3 | Vite/React SPA — lists, smart views, calendar, quick-add |
| Wave 4 | Local deploy docs, backup one-liner |

*Implementation sub-waves (Wave 0–4 above) are delivery phases inside MVP — not the same as roadmap Wave 1.5 / W2 / W3.*

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

**Exit record:** [WAVE-1-EXIT.md](./WAVE-1-EXIT.md) — exited **2026-08-10**; evidence tip commit `ff5724e`.

---

## Wave 1.5 — Soon After MVP (Current Target)

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
| Label delete reassign/migrate | On prune: optionally bulk-apply other label(s) to affected tasks before removing the deleted label |
| Multi-account login (household) | Multiple `users` rows on one deployment; login selects account; domain queries filter `owner_id` — not teams/workspaces ([ADR-002](./adr/ADR-002-single-user.md) amendment) |
| Admin account + user management | First claimed account is admin; admin can list/create/disable household users (not team RBAC) |
| Demo seed account `nebula` | Non-admin test user with rich fixture data; passphrase stored only in gitignored `.secrets-backup/` |
| Task soft-delete + restore | **Optional if cheap during auth work** — else defer to W2; see [04-data-schema.md](./04-data-schema.md) |

**Auth notes (W1.5):** Password **or passphrase** (spaces allowed; min ~12 / max ~128; no complexity theater). Login by **username or email**. First registration **claims** the bootstrap user in place (preserves existing data UUID). Subsequent household accounts require an authenticated session (or admin create). Hygiene gate: [HYGIENE-W1.5-QUICKSCAN.md](./HYGIENE-W1.5-QUICKSCAN.md) (exited 2026-08-10).

### Auth Progression

MVP: local bootstrap user, no login wall.

W1.5: `password_hash` populated; register/create-account + login/logout endpoints; session cookies; optional Cloudflare Access in front of Tunnel. **Multi-account single-tenant-of-one:** e.g. operator, spouse, housemate each get their own `users` row and isolated data at the same URI — no team workspaces, sharing, or assignees ([ADR-003](./adr/ADR-003-local-first-auth.md)).

Schema already has `users` + `password_hash` from baseline — no migration required for basic password auth.

### Not in W1.5

- Auto-scheduler
- Google Calendar sync
- Filter query language
- SLM

---

## Wave 2 — Scheduler + Google Calendar

**Goal:** SkedPal-class automated time-blocking with external calendar awareness.

### SkedPal Triad (Confirmed)

1. **Time Maps** — `focus_windows` UI and task binding
2. **Plans** — flexible time frames; `soft_target_at` surfaced
3. **Update Schedule** — explicit replan action; async worker

### Additional W2 Features

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
| Task soft-delete + session restore | Add nullable `deleted_at` on `tasks` (or `is_deleted`); optional same on `scheduled_blocks`; DELETE → soft; list queries filter `deleted_at IS NULL`; undo/restore clears flag and preserves UUID + children. Alternative: `deleted_tasks` staging table. Target **by end of W2** (may land W1.5 if cheap). MVP delete undo recreates via POST (new IDs) — not true undelete |

### GCal Conflict Policy

External hard events and pinned blocks are both BUSY. Scheduler never auto-moves pins. Overbook flagged, not silently dropped.

---

## Wave 3 — SLM + Microsoft + Desktop

**Goal:** Intelligence assist and native desktop without rewriting domain logic.

### Features

| Feature | Notes |
|---------|-------|
| Local SLM (Ollama) | Ambiguous quick-add + schedule hints; never blocks CRUD |
| Microsoft Calendar | calendar_provider.microsoft sync |
| Tauri 2 desktop | Wraps web UI + FastAPI sidecar |
| Board / Kanban view | Optional column view for “what’s going on”; sections→columns is a likely mapping. Not a substitute for calendar scheduling |
| Hosted Postgres fallback | Optional; local Compose remains default |
| Location reminders | W3 candidate; not W1/W1.5/W2 |
| Voice input | Priority-3 backlog; no sooner than W2; likely W3 |
| Email-to-task | Same as voice; not before W2; likely W3 |
| Templates | Backlog nice-to-have; low priority; maybe later |

### Desktop Bundle Strategy

Tauri shell + embedded API process talking to local Postgres (Compose service or documented install). Same REST contract; no second data model.

---

## Infrastructure Timeline

| Capability | Wave |
|------------|------|
| Docker Desktop + Compose (local) | MVP |
| pg_dump backup one-liner (root README) | MVP |
| Scheduled pg_dump backup script | W1.5 |
| Cloudflare Tunnel | W1.5+ (post-MVP remote) |
| Cloudflare Access | W1.5 (optional IdP) |
| Hosted Postgres | W3 fallback |
| Podman alternate runtime | MVP-compatible (ADR-004) |

---

## Explicit Non-Goals (W1–W3)

- Team workspaces, shared projects, comments, assignees
- Karma, streaks, gamification
- Flutter (rejected — Tauri + shared web UI)
- Mobile native apps (responsive web until desktop)
- Attachments
- iCloud calendar (unless reopened)
- Row-level task soft-delete / true session undelete (MVP ships hard delete + client recreate; **not** a permanent non-goal — target W2, optional W1.5)

**Not excluded:** Multiple personal accounts on one deployment (household login) — each operator's data isolated by `owner_id`; see W1.5 auth progression. Lightweight task handoff between personal accounts is a **Post-W3 discussion item**, not W1–W3 scope.

Board / Kanban is **not** a permanent non-goal — see Wave 3 optional candidate.

---

## Post-W3 Backlog

Not scheduled in W1–W3; park here for later reconsideration:

| Item | Notes |
|------|-------|
| Zapier / IFTTT / automation hubs | External trigger/action connectors; likely needs stable public API + webhooks first |
| Webhooks (inbound/outbound) | Enabler for hub integrations; may land with or just before Zapier-class work |
| Notion / Obsidian link or light sync | Deep-link from tasks to notes, or optional bidirectional sync later. Possible late W3 if trivial; prefer post-W3 |
| Task handoff between household accounts | **Discussion item only — no design now.** Optional future: send/assign a task copy or handoff between personal accounts on the same deployment. Not team workspaces or shared projects; revisit after W3 |

---

## Dependency Hygiene Wave Checklist

Run before each major version's feature waves:

- [x] Pin Python, Node, Postgres image versions — [W1.5 quick scan](./HYGIENE-W1.5-QUICKSCAN.md) (2026-08-10)
- [x] Audit FastAPI, SQLAlchemy, Alembic, Vite, React majors — spot check in same note
- [ ] Review container base image CVEs — deferred to next **full** hygiene wave
- [x] Update doc pins and ADR references — Wave 1 exit + this scan
- [x] Record quick-scan or full pass in version notes — `docs/HYGIENE-W1.5-QUICKSCAN.md`

---

## Documentation Map

| Wave | Primary docs |
|------|--------------|
| MVP | 01–07, sql/001_baseline.sql, adr/001–005 |
| W1.5 | Update 02, 03, 05, 06, 07; new ADRs as needed |
| W2 | Scheduler spec expansion in 02; calendar sync in 05 |
| W3 | Desktop bundle ADR; SLM assist appendix |

---

## Related Documents

- [01-product-vision.md](./01-product-vision.md)
- [06-mvp-backlog.md](./06-mvp-backlog.md)
- [03-feature-catalog.md](./03-feature-catalog.md)
- [adr/](./adr/)
