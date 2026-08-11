# Changelog

## [0.2.1] — 2026-08-10 — Wave 1.6 mobile polish

- Narrow shell: hamburger drawer nav + backdrop (replaces stacked 40vh sidebar)
- Task detail opens as full-screen sheet on phone; list hidden while open
- Larger tap targets; always-visible row/nav affordances on coarse/hover-none
- Calendar forced to day mode on narrow viewports
- Top bar reflow: menu + quick-add + sign-out; search on second row

## [0.2.0] — 2026-08-10 — Wave 1.5 (in progress)

- Session cookie login/logout; first-run setup claims bootstrap admin
- Household multi-account (admin-managed); passphrase-friendly secrets
- Demo user `nebula` with seeded fixture data
- Recurrence engine: `every` / `every!`, limited frames, multi-weekday, quick-add tokens, task-detail set/clear, complete rollover
- Time-based reminders: absolute `fire_at`, task-detail CRUD, client poll + ack, in-app toast + optional browser Notification
- Label delete reassign/migrate: optional `reassign_to` on delete; Labels UI multi-select
- Scheduled Postgres backup scripts (`scripts/backup-postgres.ps1` / `.sh`) with retention
- Cloudflare Tunnel Compose profile + [docs/CLOUDFLARE-TUNNEL.md](docs/CLOUDFLARE-TUNNEL.md) (optional Access)
- Hygiene: [docs/HYGIENE-W1.5-QUICKSCAN.md](docs/HYGIENE-W1.5-QUICKSCAN.md)

### Planned next

- **W1.5 closeout** — show-completed toggle, calendar drag, epic aggregate view
- **W2a** — Google Calendar sync + busy map
- **W2b** — SkedPal triad (Time Maps / Plans / Update Schedule)
- Remaining product items → **W3 / W3+** (see [07-wave-roadmap.md](docs/07-wave-roadmap.md))

## [0.1.0] — 2026-08-10 — Wave 1 MVP

Wave 1 (MVP) exited. See [docs/WAVE-1-EXIT.md](docs/WAVE-1-EXIT.md).

### Added

- Local Docker Compose stack (Postgres, FastAPI, Vite/React web)
- Hierarchy: Epic → Project → Section → Task → subtask → nested subtask
- Labels management; Inbox / Today / Upcoming / Project / Label views
- Calendar day/week with due markers and manual scheduled blocks
- Day-of-year and ISO week chrome in calendar titles
- Quick-add parser; global search; client-side undo (Ctrl/Cmd+Z)
- Optimistic UI + keyboard navigation + shortcuts help (`?`)
- Settings themes: Dark, Solarized Dark, Light, Solarized Light, Black, Forest, Midnight, Amethyst, Garnet (+ hex overrides)
- Schema stubs for W1.5/W2 (recurrence, reminders, focus windows, calendars, soft-target, deadline)

### Known deferred

See Wave 1 exit known-gaps table (epic aggregate view, show-completed, calendar drag, household login → W1.5, etc.).
