# Changelog

## [Unreleased] — Wave 2a (Slice 3 complete)

- Hygiene gate: [docs/HYGIENE-W2-QUICKSCAN.md](docs/HYGIENE-W2-QUICKSCAN.md) (pass)
- **Google Calendar Slice 1 (shipped):** OAuth connect, encrypted tokens, pull primary events, busy overlays — verified live
- **Google Calendar Slice 2 (shipped):** `calendar_subscriptions` (primary + informational), mirror-to-Google toggle (best-effort push of scheduled blocks), per-subscription syncToken, 24×7 calendar viewport (default 6A–10P) — verified live
- **Google Calendar Slice 3 (shipped):** `GET /calendar/conflicts` — block↔busy and block↔block overlap flags; calendar UI conflict styling (no `tasks.status` mutation) — verified live
- cryptography for Fernet token encryption
- Parked for W2b+: Time Map overrides, scoped bundles, settings expansion, fuzzy-scheduling planning session, sidebar→calendar drag-schedule

### Planned next

- **W2b** — SkedPal triad (Time Maps, Plans, Update Schedule)

## [0.2.3] — 2026-08-10 — Wave 1.5 exit

- Formal exit record: [docs/WAVE-1.5-EXIT.md](docs/WAVE-1.5-EXIT.md) (tip d2b47e9)
- Marks W1.5 complete (incl. closeout UI + companion W1.6); next is W2a Google Calendar

## [0.2.2] — 2026-08-10 — Wave 1.5 closeout

- Show completed toggle on Inbox / Today / Upcoming / Project / Label / Epic lists (localStorage)
- Calendar desktop drag: move blocks, resize from bottom edge, drag due markers; phone stays modal-only
- Epic aggregate smart view: click epic in sidebar; GET /tasks?epic_id= joins projects under the epic
- Follow-up: calendar drag pointer listeners attach synchronously (d2b47e9)

### Planned next

- **W2a** — Google Calendar sync + busy map
- **W2b** — SkedPal triad (Time Maps / Plans / Update Schedule)
- Remaining product items → **W3 / W3+** (see [docs/07-wave-roadmap.md](docs/07-wave-roadmap.md))

## [0.2.1] — 2026-08-10 — Wave 1.6 mobile polish

- Narrow shell: hamburger drawer nav + backdrop (replaces stacked 40vh sidebar)
- Task detail opens as full-screen sheet on phone; list hidden while open
- Larger tap targets; always-visible row/nav affordances on coarse/hover-none
- Calendar forced to day mode on narrow viewports
- Top bar reflow: menu + quick-add + sign-out; search on second row

## [0.2.0] — 2026-08-10 — Wave 1.5

- Session cookie login/logout; first-run setup claims bootstrap admin
- Household multi-account (admin-managed); passphrase-friendly secrets
- Demo user `nebula` with seeded fixture data
- Recurrence engine: `every` / `every!`, limited frames, multi-weekday, quick-add tokens, task-detail set/clear, complete rollover
- Time-based reminders: absolute `fire_at`, task-detail CRUD, client poll + ack, in-app toast + optional browser Notification
- Label delete reassign/migrate: optional `reassign_to` on delete; Labels UI multi-select
- Scheduled Postgres backup scripts (`scripts/backup-postgres.ps1` / `.sh`) with retention
- Cloudflare Tunnel Compose profile + [docs/CLOUDFLARE-TUNNEL.md](docs/CLOUDFLARE-TUNNEL.md) (optional Access)
- Hygiene: [docs/HYGIENE-W1.5-QUICKSCAN.md](docs/HYGIENE-W1.5-QUICKSCAN.md)

## [0.1.0] — 2026-08-10 — Wave 1 MVP

Wave 1 (MVP) exited. See [docs/WAVE-1-EXIT.md](docs/WAVE-1-EXIT.md).

### Added

- Local Docker Compose stack (Postgres, FastAPI, Vite/React web)
- Hierarchy: Epic → Project → Section → Task → subtask → nested subtask
- Labels management; Inbox / Today / Upcoming / Project / Label views
- Calendar day/week with due markers and manual scheduled blocks
- Day-of-year and ISO week chrome in calendar titles
- Quick-add parser; global search; client-side undo (Ctrl/Cmd+Z)
- Optimistic UI + keyboard navigation + shortcuts help (?)
- Settings themes: Dark, Solarized Dark, Light, Solarized Light, Black, Forest, Midnight, Amethyst, Garnet (+ hex overrides)
- Schema stubs for W1.5/W2 (recurrence, reminders, focus windows, calendars, soft-target, deadline)

### Known deferred

See Wave 1 exit known-gaps table; several closed in Wave 1.5 (see [docs/WAVE-1.5-EXIT.md](docs/WAVE-1.5-EXIT.md)).
