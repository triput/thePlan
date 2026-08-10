# Changelog

## [0.2.0] — 2026-08-10 — Wave 1.5 auth (in progress)

- Session cookie login/logout; first-run setup claims bootstrap admin
- Household multi-account (admin-managed); passphrase-friendly secrets
- Demo user `nebula` with seeded fixture data
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
- Optimistic UI + keyboard navigation + shortcuts help (`?`)
- Settings themes: Dark, Solarized Dark, Light, Solarized Light, Black, Forest, Midnight, Amethyst, Garnet (+ hex overrides)
- Schema stubs for W1.5/W2 (recurrence, reminders, focus windows, calendars, soft-target, deadline)

### Known deferred

See Wave 1 exit known-gaps table (epic aggregate view, show-completed, calendar drag, household login → W1.5, etc.).
