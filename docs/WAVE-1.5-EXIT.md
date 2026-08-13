# Wave 1.5 Exit

**Status:** Exited **2026-08-10**  
**Evidence tip:** `d2b47e9` (calendar drag fix); closeout ship `09de617`; companion **Wave 1.6** mobile polish `95ad007`  
**Hygiene:** [HYGIENE-W1.5-QUICKSCAN.md](./HYGIENE-W1.5-QUICKSCAN.md) (quick-scan pass 2026-08-10)  
**Next target:** [Wave 2a — Google Calendar](./07-wave-roadmap.md#wave-2--google-calendar--then-scheduler) (**started**)

## Scope

Daily-driver enhancements and remote-ready auth **without** scheduler / calendar-sync complexity. Wave **1.6** (phone-friendly shell) shipped as a sibling polish wave after Tunnel made remote phone use real; treated as complete with this exit.

## Delivered

| Area | Outcome |
|------|---------|
| Auth / household | Session login/logout; first-run claims bootstrap admin; multi-account `owner_id` isolation; admin user management; passphrase-friendly secrets |
| Recurrence | `every` / `every!`; limited date frames; quick-add + task detail; complete rollover |
| Reminders | Absolute `fire_at`; poll/ack; in-app toast + optional browser Notification |
| Labels | Delete with optional `reassign_to` migrate |
| Ops | Scheduled `pg_dump` scripts (14-day retention); Cloudflare Tunnel Compose profile + docs |
| Demo | Seed account `nebula` (credentials in gitignored `.secrets-backup/`) |
| Closeout UI | Show-completed toggle (localStorage); calendar desktop drag move/resize + due-dot drag; epic aggregate (`GET /tasks?epic_id=`) |
| Wave 1.6 | Drawer nav, full-screen task sheet, touch targets, day-only calendar on narrow |

## Exit criteria (met)

- Login wall + household multi-account on one deployment  
- Recurrence and time-based reminders usable from task detail / quick-add  
- Remote access path documented (Tunnel; Access optional)  
- Backup script for local Postgres  
- Closeout list UI: show completed, calendar drag (desktop), epic rollup  
- Phone-usable shell via W1.6  

## Explicitly out of Wave 1.5

| Item | Parked at |
|------|-----------|
| Google Calendar sync / busy map | **W2a** |
| Auto-scheduler / SkedPal triad / UPS | **W2b** |
| Soft-delete + true undelete | **W2c** |
| Saved filter query language | **W3+** (unless capacity steals into W2c) |
| Todoist import | **W3** |
| Account self-service / admin full profile edit / temp password reset | **W3+** |
| Intraday multi-occurrence habits (`BYHOUR`) | **W3+** |
| SLM, Microsoft Calendar, Tauri, Kanban | **W3+** |
| Calendar month view | Optional non-blocker (still open) |

## Known gaps carried forward

| Gap | Notes |
|-----|-------|
| Archived epic/project sidebar browse | Archive API exists; browse UI still light |
| Section-grouped project task layout | Sections exist; visual grouping polish deferred |
| Entity custom `#RRGGBB` picker | Presets shipped; free hex on entities deferred |
| Timezone / upcoming horizon settings UI | Schema defaults; browser-local day boundaries |
| Calendar drag on narrow viewports | Intentional — modal edit only when ≤768px |
| Pytest against live Compose + `SESSION_HTTPS_ONLY` | Cookie Secure breaks TestClient auth; separate from product exit |

## Wave 1 gaps closed here

From [WAVE-1-EXIT.md](./WAVE-1-EXIT.md): epic aggregate, show-completed, calendar drag, household login / remote-ready auth — **shipped in 1.5 / closeout**.

## How to run

See root [README.md](../README.md) and [USER-GUIDE.md](./USER-GUIDE.md). Compose web **:8080**; Tunnel optional per [CLOUDFLARE-TUNNEL.md](./CLOUDFLARE-TUNNEL.md).
