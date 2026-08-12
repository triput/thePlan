# Wave Roadmap

Delivery waves from MVP through W3. Each version begins with a **Dependency Hygiene** wave unless explicitly overridden.

---

## Version Structure

```
[Prior version freeze/tag]
        ↓
Dependency Hygiene Wave (toolchain, pub/package majors, container pins, doc pins)
        ↓
Feature waves (MVP → W1.5 → W1.6 → W2a GCal → W2b Scheduler → W3+)
```

**Post-1.5 build order (locked):** Google Calendar (W2a) → Scheduler (W2b). Everything else stays W3 or W3+.

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

## Wave 1.5 — Soon After MVP (Complete — exited 2026-08-10)

**Goal:** Daily-driver enhancements and remote-ready auth without scheduler complexity.

**Status:** **Exited 2026-08-10.** Exit record: [WAVE-1.5-EXIT.md](./WAVE-1.5-EXIT.md) — tip `d2b47e9`. Companion **W1.6** mobile polish shipped. **Next:** [Wave 2a Google Calendar](#wave-2--google-calendar--then-scheduler).

### Shipped

| Feature | Notes |
|---------|-------|
| Recurrence engine | `every` / `every!`; limited `starts_on`/`ends_on` frames; quick-add + task detail |
| Time-based reminders | Absolute `fire_at`; in-app toast + optional browser Notification API |
| Login / remote-ready auth | Password session; optional Cloudflare Access in front of Tunnel |
| Backup script | `scripts/backup-postgres.ps1` / `.sh`; 14-day retention |
| Cloudflare Tunnel | Compose profile `tunnel` + [CLOUDFLARE-TUNNEL.md](./CLOUDFLARE-TUNNEL.md) |
| Label delete reassign/migrate | Optional `reassign_to` on delete; Labels UI multi-select |
| Multi-account login (household) | Multiple `users` rows; `owner_id` isolation — not teams ([ADR-002](./adr/ADR-002-single-user.md)) |
| Admin account + user management | First claimed account is admin; list/create/disable; set passwords |
| Demo seed account `nebula` | Non-admin fixture user; passphrase in gitignored `.secrets-backup/` |
| Show-completed toggle | List header; localStorage; hide completed by default |
| Calendar drag move/resize | Desktop day/week; due-dot drag; narrow modal-only |
| Epic aggregate smart view | Click epic in sidebar; `GET /tasks?epic_id=` |
| ~~Todoist import~~ | **Parked at W3** (stale upstream; not needed for daily driver) |
| Task soft-delete + restore | **Parked at W2b** (or later) |

**Auth notes (W1.5):** Password **or passphrase** (spaces allowed; min ~12 / max ~128). Login by **username or email**. First registration **claims** bootstrap user. Hygiene: [HYGIENE-W1.5-QUICKSCAN.md](./HYGIENE-W1.5-QUICKSCAN.md) (exited 2026-08-10).

### Auth Progression

MVP: local bootstrap user, no login wall.

W1.5: `password_hash` populated; register + login/logout; session cookies; optional Cloudflare Access. **Multi-account single-tenant-of-one** ([ADR-003](./adr/ADR-003-local-first-auth.md)).

### Not in W1.5

- Auto-scheduler / Google Calendar (→ **W2**)
- Filter query language (→ **W2b** capacity / W3+)
- SLM, MS Calendar, Tauri, account self-service, habits, import (→ **W3+**)
- Phone-first responsive polish (→ **W1.6**, shipped)

---

## Wave 1.6 — Mobile / responsive cleanup (Shipped 2026-08-10)

**Goal:** Make daily-driver flows comfortable on a phone browser (especially via Cloudflare Tunnel): navigate, capture, complete, peek calendar, edit a task — without desktop-width assumptions.

**Why now:** Tunnel made remote phone use real.

**Hygiene:** Quick-scan only — exited with W1.6 ship 2026-08-10.

### Shipped

| Item | Notes |
|------|-------|
| Collapsible / drawer nav | Hamburger + off-canvas sidebar; backdrop dismiss |
| Task detail sheet | Full-screen overlay on narrow; list hidden while open |
| Touch targets | ~44px on complete, rows, icon buttons, primary controls |
| Quick-add + modals | Full-width search row; modals near full-bleed |
| Calendar on narrow | Day mode forced; week toggle hidden |
| Auth / settings / labels | Forms stack to single column where needed |

### Out of scope for 1.6

- Native apps / Tauri mobile / Flutter
- Offline-first PWA or mobile push
- Visual redesign
- W2 scheduler / GCal UI

---

## Wave 2 — Google Calendar, then Scheduler (**in progress**)

**Goal:** External busy awareness first, then SkedPal-class automated time-blocking that consumes it.

**Status:** **W2b Plans B complete (2026-08-11)** — named Plans CRUD + task bind; Plans A thin UI shipped earlier. **Fuzzy algorithm session complete (2026-08-12)** — [ADR-006](./adr/ADR-006-fuzzy-scheduling.md); **Update Schedule** worker is the next implementable slice; then painted Time Maps. Hygiene: [HYGIENE-W2-QUICKSCAN.md](./HYGIENE-W2-QUICKSCAN.md) (pass).

**Order (locked):** **2a Google Calendar → 2b Scheduler.** Do not start the auto-scheduler worker until GCal busy sync is usable.

### Phase 2a — Google Calendar

| Feature | Notes |
|---------|-------|
| Google Calendar sync | OAuth via `calendar_accounts`; pull + optional mirror push |
| Busy map / cutout | External hard events as BUSY input |
| Conflict policy (partial) | External hard events and pinned blocks are BUSY; overbook flagged when detected |
| Calendar UI wiring | Surfaces synced busy alongside manual blocks |

No full Update Schedule / UPS pipeline in 2a.

#### Vocabulary (W2a / W2b)

- **Time-blocked** — fixed start/end calendar appointments (deep work). Formal `scheduled_blocks` today.
- **Bundled** — knockout lists in gaps between hard events / time blocks (W2b).
- **Primary Google calendar** — source of truth for available / busy time.
- **Mirror toggle** — push local time blocks to primary Google calendar, or keep local-only.
- **Informational calendars** — see-only overlays; not capacity unless opted in later.

#### W2a slice plan

1. **Slice 1 (prove-it) — complete:** Google OAuth connect → pull events → store `external_calendar_events` → render read-only busy on Calendar day/week; Settings connect/disconnect/sync. Verified live 2026-08-11.
2. **Slice 2 — complete:** Multi-calendar subscriptions (`primary` + `informational`); best-effort mirror push of `scheduled_blocks` when `mirror_blocks_to_google`; per-subscription Google `syncToken`; 24×7 viewport toggle (default 6A–10P). Verified live 2026-08-11.
3. **Slice 3 (capacity) — complete:** Overbook/conflict flags when external busy overlaps pins/blocks (`GET /calendar/conflicts`); calendar UI styling. Does not set `tasks.status` (W2b scheduler). Verified live 2026-08-11.

**Operator note (Slice 2):** Reconnect Google after deploy so `calendar.calendarlist.readonly` is granted. Run Alembic `005_calendar_subscriptions`.

---

### Phase 2b — Scheduler (SkedPal triad)

#### W2b slice plan

1. **Slice 1 — complete:** `focus_windows` CRUD + Settings UI; default Morning/Afternoon/Evening seeds; `preferred_time_window_id` on tasks; quick-add `@morning|@afternoon|@evening`. Verified live 2026-08-11. v1 = one contiguous hard/soft band per named map.
2. **Settings expansion — complete:** `GET/PATCH /settings` + Scheduling defaults UI; `default_estimated_duration_minutes`, `default_min_block_duration_minutes`, `default_schedule_style` (`standalone`), `auto_defer_enabled`; task create + quick-add inherit default duration when omitted. Verified live 2026-08-11. Polish: timezone dropdown → [DEF-002](./DEFECTS.md).
3. **Plans A (thin) — complete:** `deadline_at` + `soft_target_at` surfaced in task detail + list badges; API `TaskUpdate` wired.
4. **Plans B — complete:** `plans` table + CRUD; `tasks.plan_id`; bind copies plan `soft_target_at`; Settings Plans UI; task detail Plan picker; list plan-badge. Out of scope this slice: scheduler worker, rule inheritance, quick-add plan tokens, sidebar plans.
5. **Update Schedule** — **next implementable** — explicit replan action; async worker ([ADR-005](./adr/ADR-005-scheduler-decoupling.md) + [ADR-006](./adr/ADR-006-fuzzy-scheduling.md))

| Feature | Notes |
|---------|-------|
| Auto-scheduler worker | Decoupled from CRUD |
| UPS scoring + slice/fit | U = 100·e^(-k·max(Slack,0)), k=0.5 |
| Pins, soft vs hard | `deadline_at` enforced; pinned blocks immovable until unpin |
| Bundled vs formal blocks | Knockout lists → blocks on replan (**post–v1**; v1 excludes bundle auto-placement per [ADR-006](./adr/ADR-006-fuzzy-scheduling.md)) |
| Scoped bundles | Bundle constrained to one epic or project — late W2b / early W3 |
| Settings expansion | W2b — **shipped** | API + Scheduling defaults UI; timezone still free-text ([DEF-002](./DEFECTS.md)) |
| **Painted Time Maps (SkedPal-class)** | Late W2b / early W3 — one named map with **multiple painted bands** (e.g. morning + evening study on the same map); preference tiers **green → yellow → never red** (scheduler fills preferred first, overflow to yellow only, hard ban on red). Not two duplicate maps for the same intent. Color UI on the week grid. |
| Temporary Time Map overrides | Day/week dated windows that auto-expire (vacation/conference) |
| Rule inheritance | Parent → child window/plan propagation |
| Overbook UI | schedule_status.overbooked |
| deadline_at UI | **shipped** (Plans A) — hard commit surfaced in task detail + list |
| soft_target_at UI | **shipped** (Plans A/B) — task detail + list; copied on plan bind |
| Plans CRUD + task bind | **shipped** (Plans B) — Settings Plans section; task picker; list badge |
| Task dependency enforcement | Topological ordering in scheduler |
| Saved filter query language | User-authored saved_filters — ship if capacity; else W3+ |
| WebSocket invalidation | Optional; else keep REST invalidation |
| Status tracker | Today's blocks done % + overbook count |
| Task soft-delete + session restore | Target by end of W2b |
| Sidebar → calendar drag | Drag a task from list/sidebar onto a day/time slot to create a `scheduled_block` (desktop first; phone keeps tap/slot). Parked UX — not a W2a exit. Late W2b polish or early W3. |

**Fuzzy scheduling** — **exited 2026-08-12** ([ADR-006](./adr/ADR-006-fuzzy-scheduling.md)): replan contract, candidate set, slack/urgency, relaxation ladder, slice/fit, overbook locked for v1 Update Schedule worker.

**Schema fence (locked 2026-08-11 — before Update Schedule worker):**

| Decision | Lock |
|----------|------|
| Default schedule style for new tasks | **Standalone** — Time Block / Bundle are opt-in only |
| Min block length (MBL) | **Use user/default** unless task overrides (override UI later) |
| Auto-defer | **On by default** — missed plan windows may slide; surface a one-time / Settings warning, not a nag modal per task |
| Time Map preference tiers | **In principle** — green preferred → yellow overflow OK → red forbidden; v1 maps stay one band until Painted Time Maps |
| Pins + external busy | **Immovable BUSY** — confirmed (ADR-005 + GCal conflict policy) |

Settings expansion is **shipped**; fuzzy algorithm session **exited 2026-08-12** ([ADR-006](./adr/ADR-006-fuzzy-scheduling.md)). Update Schedule worker is unblocked.

### GCal Conflict Policy (2a + 2b)

External hard events and pinned blocks are both BUSY. Scheduler never auto-moves pins. Overbook flagged, not silently dropped.

---

## Wave 3 / W3+ — Everything else

**Goal:** Intelligence assist, desktop shell, secondary calendars, and deferred product polish — **after** GCal + scheduler.

### Features

| Feature | Notes |
|---------|-------|
| Local SLM (Ollama) | Ambiguous quick-add + schedule hints; never blocks CRUD |
| Microsoft Calendar | calendar_provider.microsoft sync |
| Tauri 2 desktop | Wraps web UI + FastAPI sidecar |
| Board / Kanban view | Optional; sections→columns likely |
| Hosted Postgres fallback | Optional; local Compose remains default |
| Location reminders | Candidate |
| Voice input | Candidate |
| Email-to-task | Candidate |
| Templates | Nice-to-have |
| Todoist import | CSV/JSON → hierarchy |
| Temp / forced password reset | Admin sets temp password; change on next login |
| Admin full profile edit | Any field except username |
| Self-service account settings | Own password, email, display name |
| Intraday / multi-occurrence habits | NL / `BYHOUR` on existing recurrence |

### Wave size note

W3 is large. Before W3 planning starts in earnest, **split a Wave 4** if needed (e.g. account/profile + import + habits vs. SLM / Tauri / MS Calendar). Flag only until W2b exits.

### Desktop Bundle Strategy

Tauri shell + embedded API process talking to local Postgres. Same REST contract; no second data model.

---

## Infrastructure Timeline

| Capability | Wave |
|------------|------|
| Docker Desktop + Compose (local) | MVP |
| pg_dump backup one-liner (root README) | MVP |
| Scheduled pg_dump backup script | W1.5 |
| Cloudflare Tunnel | W1.5 |
| Cloudflare Access | W1.5 (optional IdP in front of Tunnel) |
| Responsive / phone-friendly web | W1.6 (shipped) |
| Google Calendar sync | W2a |
| Auto-scheduler / Update Schedule | W2b |
| Hosted Postgres | W3+ fallback |
| Podman alternate runtime | MVP-compatible (ADR-004) |

---

## Explicit Non-Goals (W1–W3)

- Team workspaces, shared projects, comments, assignees
- Karma, streaks, gamification
- Flutter (rejected — Tauri + shared web UI)
- Mobile native apps (responsive web until desktop; **W1.6** is the responsive polish gate)
- Attachments
- iCloud calendar (unless reopened)
- Row-level task soft-delete / true session undelete (MVP hard delete + client recreate; target **W2b**)

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
- [x] W1.6 entry: quick-scan only (reuse W1.5 pins unless drift found) — exited with W1.6 ship 2026-08-10
- [x] W2 entry: quick-scan — [HYGIENE-W2-QUICKSCAN.md](./HYGIENE-W2-QUICKSCAN.md) (2026-08-10)

---

## Documentation Map

| Wave | Primary docs |
|------|--------------|
| MVP | 01–07, sql/001_baseline.sql, adr/001–005 |
| W1.5 | Auth, recurrence, reminders, ops; closeout — [WAVE-1.5-EXIT.md](./WAVE-1.5-EXIT.md) |
| W1.6 | Responsive shell (shipped) |
| W2a | Google Calendar sync + busy map in 05 |
| W2b | Scheduler triad expansion in 02; soft-delete |
| W3+ | Desktop ADR; SLM; MS Calendar; account UX |

---

## Related Documents

- [01-product-vision.md](./01-product-vision.md)
- [06-mvp-backlog.md](./06-mvp-backlog.md)
- [03-feature-catalog.md](./03-feature-catalog.md)
- [adr/](./adr/)
