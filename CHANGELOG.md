# Changelog

## [Unreleased] — R3 Midnight Workbench UI (shipped 2026-10-11)

- **R3 Slices 0–3 (web):** Capability inventory ([R3-CAPABILITY-INVENTORY](docs/redesign/R3-CAPABILITY-INVENTORY.md)); Workbench tokens + default **Dark** preset; collapsible desktop sidebar rail; list/board shell restyle; shared **support dock** (calendar idle, **Preview schedule changes**, task details); dirty-edit navigation guards; quieter calendar Time Map bands with **Preferred / Acceptable / Excluded** tiers preserved; **Preview changes** vs **Update Schedule** unchanged; Windows **Ctrl** labels in help — [R3-WORKBENCH-2026-10-11](docs/delivery/R3-WORKBENCH-2026-10-11.md), [USER-GUIDE](docs/USER-GUIDE.md)
- **Quality (Renee exit):** web `npm test` **57/57** green (21 suites), `npm run build` green (chunk-size advisory only) — [R3-WORKBENCH-2026-10-11](docs/delivery/R3-WORKBENCH-2026-10-11.md), [DEX-R3-REVIEW-2026-10-11](docs/delivery/DEX-R3-REVIEW-2026-10-11.md)
- **R3 status:** **Closed / shipped 2026-10-11** — Trish manual acceptance matrix **Pass**; Dex **D1–D4 + D2b** focused Pass; tip **`ab88fa2`**. Deferred: negative-duration API validation, post-refresh tidy (non-blockers)

## [Unreleased] — F7 Saved views W1–W3 (2026-10-10)

- **Dex Wave 1 retest (2026-10-10):** F6 **P1 R1** (`epic_id` / epic `target_date`) **verified closed** — **37** API integration tests on isolated PostgreSQL incl. concurrent apply/reparent ([DEX-WAVE1-RETEST](docs/delivery/DEX-WAVE1-RETEST-2026-10-10.md)). F4 Wave 1 **verified closed** — CLI overrides, day overlay, F4-D red/pins/legend/small-run + **W1-R1** volume stale; web **36** + CLI **36** tests green
- **W1-R1 (2026-10-10, verified closed):** Calendar **Schedule stale** banner uses **`GET /api/v1/schedule/runs/{run_id}/stale-summary`** full-run aggregate (not the first **200** explanation rows); **`CalendarView`** + API **`test_schedule_stale_summary.py`** — Dex volume case **202** explanations ([DEX-IMPORT-VOLUME](docs/delivery/DEX-IMPORT-VOLUME-2026-10-10.md)); [05-api-contract.md](docs/05-api-contract.md)
- **F7 W1 API:** Alembic **`027_saved_filter_presentation`** — `saved_filters.presentation_json`; v1 predicate engine (`saved_filter_predicate`, `saved_filter_query`); **`/api/v1/views`** CRUD + **`/{id}/tasks`** and **`/by-slug/{slug}/tasks`**; system Inbox/Today/Upcoming backfilled to v1 — [delivery/F7-SAVED-VIEWS.md](docs/delivery/F7-SAVED-VIEWS.md), [NEXT-FEATURES-SPEC §10](docs/NEXT-FEATURES-SPEC.md#10-f7-saved-views)
- **Quality (W1):** Renee exit — **64** API pytest (`test_f7_w1_views`, `test_f7_w1_predicate`, `test_f7_w1_quality`)
- **F7 W2 CLI:** `theplan views` **list**, **get**, **create**, **patch**, **delete**, **query** (`--id` / `--slug`, pagination, `--board-order`) — [CLI.md](docs/CLI.md); CLI tests green (`test_views_commands.py`)
- **F7 W3 web:** Saved-view filter modal, sidebar user views, TaskList/TaskBoard via saved-view task query, invalid-reference repair banner — `npm run build` green
- **F7 W3 Quality (2026-10-10):** Automated W3 regression suite — web `npm test` **36** green (Renee exit); Trish Done sign-off **2026-10-10** ([MANUAL-CHECKLIST § Sign-off](docs/delivery/MANUAL-CHECKLIST.md#sign-off)); F7 **not Closed/shipped** (deferred alias non-goal)
- **F7 migration coverage (Trish 2026-10-10):** **B-F7-1 closed (disposition)** — accept **fresh disposable migrate** (Dex) + **synthetic pre-027 dry-run** ([F7-MIGRATION-VERIFY.md](docs/delivery/F7-MIGRATION-VERIFY.md)); household dump not required for closeout
- **F5 B-F5-1 Import merge (2026-10-10):** Web **`ImportPanel.tsx`** — one **Import** modal with **Templates** / **Custom outline** tabs; **IM-R1** tab draft retention **verified closed** ([DEX-IMPORT-VOLUME](docs/delivery/DEX-IMPORT-VOLUME-2026-10-10.md)); Trish Done **2026-10-10**; F5 **not Closed** (PARTIAL operator rows) — [F5-COURSERA-TEMPLATES.md](docs/delivery/F5-COURSERA-TEMPLATES.md)
- **F7 W3 completion (2026-10-10):** Saved-view **load-more** (list page **200**, board **500**); List/Board toggle **PATCH**es `presentation_json.mode` (server shallow-merge); view task **sort** allowlist on `GET …/tasks` via `?sort=` or `presentation_json.sort` (`INVALID_SORT` when invalid; `board_order=true` ignores presentation sort); sidebar user-view **reorder** via `sort_order` — **Verified closed** Dex+Trish **2026-10-10** ([DEX-F7-CHECKLIST](docs/delivery/DEX-F7-CHECKLIST-2026-10-10.md)); cursor **`b0c49d8`**; [05-api-contract.md](docs/05-api-contract.md) Smart Views section updated
- **F4 W3 Wave 1 (2026-10-10):** CLI `theplan overrides` list/get/create/edit/delete; calendar **day-mode** override overlay + **F4-D** red/stale/legend incl. volume stale — **Dex verified closed** — [F4-TIME-MAP-OVERRIDES.md](docs/delivery/F4-TIME-MAP-OVERRIDES.md); Trish Done **2026-10-10**; F4 **not Closed** (optional DST)
- **Wave 1 human verification (Trish 2026-10-10):** [MANUAL-CHECKLIST § Sign-off](docs/delivery/MANUAL-CHECKLIST.md#sign-off) Done **10/10/26 OK** for Setup–F7; PARTIAL/operator residue unchanged — features **not Closed** where delivery Notes say so
- **F7 status:** Trish Done **2026-10-10**; **B-F7-1** migration **closed (disposition:** fresh + synthetic); W3 automated suite **36** green; **not** Closed/shipped (non-goal alias)
- **Dex volume retest (2026-10-10):** **W1-R1** + **IM-R1** **verified closed** — [DEX-IMPORT-VOLUME](docs/delivery/DEX-IMPORT-VOLUME-2026-10-10.md); Trish Done sign-off recorded same day (authorized)

## [Unreleased] — F2 Kanban (2026-10-08)

- **F2 Kanban API:** Alembic `021_task_workflow` — `workflow_state` (`ready` \| `in_progress` \| `waiting`), `waiting_note`, `board_rank`, `board_revision`; `POST /api/v1/tasks/{id}/workflow` with revision check; `GET /tasks?workflow=&board_order=` — [delivery/F2-KANBAN.md](docs/delivery/F2-KANBAN.md), [NEXT-FEATURES-SPEC §5](docs/NEXT-FEATURES-SPEC.md#5-f2-kanban-for-work-in-progress)
- **TaskOut board fields:** `workflow_state`, `board_column`, `waiting_note`, `board_rank`, `board_revision` (Done derived from completion)
- **Web F2:** List/Board toggle on supported views; Kanban columns, WIP summary, Move menu, drag between columns with within-column insert hints, Done + open-column pagination, work-board epic/project filters, roots-only filter — build WIP at review follow-up
- **CLI F2:** `tasks workflow` (column transition); `tasks list --workflow`, `--board-order` — [CLI.md](docs/CLI.md)
- **F2 Dex review corrections:** `board_revision` on complete/uncomplete/bulk/recurrence; workflow transition `FOR UPDATE`; fixed `insert_before_id`/`insert_after_id` + rank re-gap; create assigns `next_board_rank`; default task list excludes archived project/epic (including `epic_id`/`ids`; `project_id` scoped to archived detail unchanged)
- **Quality:** Renee follow-up — API **30** green (`test_task_workflow`, `test_task_complete`, `test_recurrence`, `test_complete_task_unit`); CLI **33** at prior exit; F2-D browser/manual **pending**

## [Unreleased] — F1 CLI planning handoff (2026-10-08)

- **F1 Dex review corrections:** Alembic `020_task_source_refs`; task graft `source_refs`; handoff parent/dependency ownership checks; mixed dependency edges; propose embeds resolved defaults on canonical payload; schedule root inheritance (incl. project under existing epic); intent-stable idempotency hash; dependency cycle closure — [delivery/F1-HANDOFF.md](docs/delivery/F1-HANDOFF.md)
- **F1 handoff API:** `POST /api/v1/handoffs/propose|apply`; receipt lookup `/api/v1/handoffs/receipts/{id}`, `/receipts/by-key/{key}`, `/receipts?idempotency_key=` — owner-scoped idempotent apply with atomic graph + receipt ([delivery/F1-HANDOFF.md](docs/delivery/F1-HANDOFF.md), [NEXT-FEATURES-SPEC §4](docs/NEXT-FEATURES-SPEC.md#4-f1-cli-planning-handoff))
- **Alembic `019_handoff_receipts`:** `handoff_receipts`; `source_refs` on epics and projects
- **Task dependencies API:** `GET|POST /api/v1/tasks/{id}/dependencies`, `DELETE …/dependencies/{dependency_id}` — cycle and ownership validation
- **CLI F1:** `handoff propose|apply|receipt`; `epics` / `projects` / `sections` CRUD; `tasks complete|uncomplete`; `deps list|add|remove` — [CLI.md](docs/CLI.md)
- **Quality:** Renee exit — handoffs **19**, adjacent API **39**, CLI **33**; F1-A–E automated; F1-B concurrent HTTP remains a known limitation in delivery doc
- **Docs:** Handoff distinct from non-idempotent outline ingest — [OUTLINE-INGEST.md](docs/OUTLINE-INGEST.md)

## [Unreleased] — W2c + correctness (2026-10-08)

- **Compose replan worker (W2c):** `scheduler` service in `infra/compose/compose.yaml` polls `schedule_runs` and runs replan; API `SCHEDULE_DISPATCH=external` (default); residual `SCHEDULE_DISPATCH=thread` for no-poller setups — [ADR-005](docs/adr/ADR-005-scheduler-decoupling.md), [apps/api/app/scheduler/README.md](apps/api/app/scheduler/README.md)
- **Schedule concurrency:** Alembic `018_one_running_schedule_run` — partial unique index one `running` row per owner; `POST /schedule/replan` returns **409** `SCHEDULE_RUN_IN_PROGRESS`
- **Trash restore:** child restored while parent still trashed → reparent to nearest live ancestor or inbox root; empty trash no longer hard-deletes live restored descendants
- **Task PATCH:** reparent that would create a cycle → **422** `PARENT_CYCLE`
- **Replan horizon wipe:** cancels Google/MS mirrors for removed unpinned blocks and drops local `ExternalCalendarEvent`. Failed remote deletes keep a `pending_deletion` tombstone (Alembic `026`) and are retried on the next sync instead of returning as anonymous busy — [DEF-028](docs/DEFECTS.md#def-028--calendar-mirror-delete-failure-recovery-pending-deletion) closed 2026-10-09
- **Scheduler:** dependency max-UPS ready queue + prerequisite `not_before`; red bands cut green/yellow; decreasing placement slice sizes
- **Pinned prerequisites:** fully pinned / non-candidate blockers still gate dependents via remaining + `not_before` (shared remaining map so placement unlocks later sweeps)
- **Trash purge:** detach live children flushes before parent hard-delete under `autoflush=False` (CASCADE-safe)
- **Reminders:** due poll skips trashed tasks (`deleted_at` set)
- **Quality:** correctness suite **73/73** green (Renee); scheduler worker tests green; P2 pinned-prereq + purge-flush targeted **34/34**

## [Unreleased] — W2c steal (scheduler polish)

- **DEF-014 (shipped 2026-08-18):** `schedule_style` value `manual` (UI: Manual / backlog) plus live inherit on epics/projects; Update Schedule excludes `manual` and `bundle`. Outline import does not stamp imported tasks as manual. Tunnel ops: operator still needs `docker compose --build api web` (not run in this docs pass).

## [Unreleased] — Wave 3+ (SLM)

- **ADR-010 accepted (2026-08-14):** Local SLM Assist — Ollama default, OpenAI-compatible client, review→confirm→apply; CRUD never blocked ([docs/adr/ADR-010-slm-assist.md](docs/adr/ADR-010-slm-assist.md), [docs/SLM-ASSIST.md](docs/SLM-ASSIST.md))
- **W3+ Assist (shipped):** `POST /api/v1/assist/propose`, `POST /api/v1/assist/apply`, `GET /api/v1/assist/status`; Assist panel (Propose → review → Approve); Settings reachability; Compose `ASSIST_*` env; mocked httpx tests
- **Docs:** Desktop packaging / single installer tabled to **V.Later**; tunnel remains daily driver

## [Unreleased] — Wave 3 (cut locked)

- **W3 Slice 3 (shipped):** Tauri 2 desktop shell (`apps/desktop`) — loads `apps/web` production build; spawns FastAPI uvicorn sidecar on `127.0.0.1:18765`; Compose Postgres; kill-on-exit ([docs/DESKTOP.md](docs/DESKTOP.md), [apps/desktop/README.md](apps/desktop/README.md))
- **W3 Slice 3 (shipped):** Fixed sidecar port — busy `18765` fails with log + dialog; `THEPLAN_API_PYTHON` / PATH Python; smoke script `npm run smoke:sidecar`
- **ADR-009 accepted (2026-08-14):** Tauri prove-it desktop — FastAPI sidecar + Compose Postgres; single installer deferred ([docs/adr/ADR-009-tauri-desktop.md](docs/adr/ADR-009-tauri-desktop.md))
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

- **W3** core slices 1–3 complete (Account + MS Calendar + Tauri prove-it); packaging / single installer later
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
