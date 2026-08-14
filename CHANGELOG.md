# Changelog

## [Unreleased] — Wave 3 (cut locked)

- **ADR-008 accepted (2026-08-14):** Microsoft Calendar Graph sync — full GCal parity, `mirror_blocks` rename, tenant `common` ([docs/adr/ADR-008-microsoft-calendar.md](docs/adr/ADR-008-microsoft-calendar.md))
- **W3 Slice 2 (shipped):** Microsoft Calendar — Graph OAuth, multi-cal subscriptions, busy pull, mirror push ([docs/MICROSOFT-CALENDAR.md](docs/MICROSOFT-CALENDAR.md))
- **W3 Slice 2 (shipped):** Alembic `011_mirror_blocks` — rename `mirror_blocks_to_google` → `mirror_blocks` (provider-neutral)
- **W3 Slice 2 (shipped):** Settings → Microsoft Calendar section + `?mcal=` OAuth toast
- **W3 Slice 2 (shipped):** Mocked Microsoft Graph unit tests
- **W3 cut locked (2026-08-12):** W3 = Account polish → MS Calendar → Tauri; W3+ = SLM, Todoist import, habits, optional Kanban; W4 = voice/email/location/templates/hosted Postgres/filter QL; W2c parked — [07-wave-roadmap.md](docs/07-wave-roadmap.md)
- **ADR-007 accepted (2026-08-12):** Account self-service + forced password change ([docs/adr/ADR-007-account-self-service.md](docs/adr/ADR-007-account-self-service.md))
- **W3 Slice 1 (shipped):** Alembic `010_must_change_password`; `users.must_change_password` column
- **W3 Slice 1 (shipped):** `PATCH /auth/me` self-service — optional `password`, `email`, `display_name`; clears flag when password is set; `422 EMAIL_TAKEN` on conflict; username immutable
- **W3 Slice 1 (shipped):** Admin `PATCH /auth/users/{id}` — email edit + setting `password` always forces `must_change_password`
- **W3 Slice 1 (shipped):** API password-change gate — mutating domain routes return `403 PASSWORD_CHANGE_REQUIRED` while flag is set (`GET/PATCH /auth/me` exempt)
- **W3 Slice 1 (shipped):** Settings → Account UI (all users); Household email edit + admin temp-password copy; blocking change-password gate in app shell until flag clears

## [Unreleased] — Wave 2b (Schedule refactor A)

- **Fix:** Week Time Map overlay — red bands used element `opacity` over seed greens and read as another green; use tier alpha fills, z-index (green < yellow < red), and a red hatch so forbidden zones stay red
- **UX:** Week **Time Map** dropdown — default **Neutral** (no bands); selecting a map paints only that map’s bands (visual only; does not change scheduling)
- **Docs:** **W2c** slice — scheduler polish & catch-all (Time Map overrides, rule inheritance, scoped bundles, soft-delete, sidebar drag, compose worker); may run before or after core W3 and absorb W3 fallout
- **Dependency Hygiene (W3 entry):** [HYGIENE-W3.md](docs/HYGIENE-W3.md) — pass; pin `cloudflare/cloudflared:2026.7.3` (drop `:latest`); toolchain/majors spot-check keep; no forced package upgrades
- **W2b Painted Time Maps (shipped):** Alembic `009_painted_time_maps`; slim `focus_windows` header + `strict_mode` (replaces `is_hard`); child `time_map_bands` with green/yellow/red tiers; existing windows backfilled as one green band; scheduler placement order green → yellow → neutral (minus red); `strict_mode` kills neutral spill; Settings multi-band editor; week calendar color overlay; tasks still bind via `preferred_time_window_id`
- **W2b Schedule refactor (A):** Alembic `008_schedule_refactor`; shared `busy_intervals` primitives; `user_settings.workday_start_local` (default 08:00); nullable `tasks.schedule_style` (inherit user default); Settings workday-start field; task detail schedule-style picker; per-task bundle override; scheduler README notes future compose worker
- **W2b Update Schedule (thin):** `POST /schedule/replan` (202 `ScheduleRunOut`; stale reclaim 15m; 409 `SCHEDULE_RUN_IN_PROGRESS`); `GET /schedule/runs/{id}`; in-process async worker per [ADR-006](docs/adr/ADR-006-fuzzy-scheduling.md); Calendar **Update Schedule** button with poll
- **Docs:** Guest [Quick Start guide](docs/guides/QUICK-START.md) for live-instance UI (W2b Plans B scope; no ops/setup)
- **W2b Plans B (shipped):** Alembic `007_plans`; `plans` CRUD (`GET/POST/PATCH/DELETE /plans`); `tasks.plan_id` + bind semantics (set copies plan `soft_target_at` when present; unbind leaves soft target; same-request `soft_target_at` wins); Settings Plans section; task detail Plan picker; list plan-badge
- **W2b Plans A (thin):** `deadline_at` + `soft_target_at` in task detail panel and list badges; `TaskUpdate` typed for both fields
- **W2b Settings expansion (shipped):** Alembic `006_settings_expansion`; `GET/PATCH /settings`; Settings → Scheduling defaults UI (timezone, locale, workday/week, buffer, horizon, default duration/MBL, schedule style standalone/block/bundle, auto-defer warning); task create and quick-add inherit default duration when omitted; number-input `step` fix so 480 workday minutes is valid
- **W2b Slice 1 (shipped):** Focus windows CRUD (`/focus-windows`); Settings Time Maps UI; task detail Time Map picker; default Morning/Afternoon/Evening seeds; `preferred_time_window_id` on tasks; quick-add `@morning|@afternoon|@evening` resolution — verified live
- Hygiene gate: [docs/HYGIENE-W2-QUICKSCAN.md](docs/HYGIENE-W2-QUICKSCAN.md) (pass)
- **Google Calendar Slice 1–3 (shipped):** OAuth, multi-cal/mirror/24h, conflict flags
- cryptography for Fernet token encryption
- **ADR-006 accepted (2026-08-12):** Fuzzy scheduling contract for v1 Update Schedule — replan trigger/horizon, candidate set, slack/urgency, relaxation ladder, slice/fit, overbook ([docs/adr/ADR-006-fuzzy-scheduling.md](docs/adr/ADR-006-fuzzy-scheduling.md))
- Parked as **W2c** (scheduler polish & catch-all): Time Map overrides, rule inheritance, scoped bundles, soft-delete, sidebar→calendar drag, dedicated compose worker — may run before or after core W3; after W3 also absorbs W3 fallout
- **Schema fence locked:** standalone default; MBL use default; auto-defer on; green→yellow→never red **in force** for bound Time Maps; pins + GCal busy immovable
- **DEF-002:** Timezone dropdown picker (polish; bundle with other fixes)

### Planned next

- **W3 Slice 3** — Tauri 2 desktop ([07-wave-roadmap.md](docs/07-wave-roadmap.md))
- **W2c** remains parked (after W3 or as fallout bucket)

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
