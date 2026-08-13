# Wave 1 (MVP) Exit

**Status:** Exited **2026-08-10**  
**Evidence tip:** `ff5724e` (E10 close); E1–E9 in `main` history  
**Next target:** [Wave 1.5](./07-wave-roadmap.md#wave-15--soon-after-mvp) → **exited** — see [WAVE-1.5-EXIT.md](./WAVE-1.5-EXIT.md)

## Delivered (E1–E10)

| Epic | Outcome |
|------|---------|
| E1 Infrastructure | Compose + Postgres + Alembic; bootstrap user; local auth |
| E2 Hierarchy CRUD | Epic → nested subtask; Inbox; reorder; move |
| E3 Completion | Complete/uncomplete; parent OPEN_CHILDREN warn + bulk |
| E4 Labels & colors | Labels management; presets; lowercase uniqueness |
| E5 Smart views | Inbox, Today, Upcoming, Project, Label (+ scheduled blocks in Today/Upcoming) |
| E6 Calendar | Day/week; due markers; manual scheduled blocks; day-of-year / ISO week chrome |
| E7 Quick-add | Parser + create; work-capacity duration rules |
| E8 Search & undo | Global search; client undo stack (Ctrl/Cmd+Z) |
| E9 Perf & UX | Optimistic mutations; keyboard nav; help overlay |
| E10 Schema readiness | Deferred columns + stub tables; smart-view seeds; index parity |

Also shipped in Wave 1 polish: **nine UI themes** (Settings) with hex overrides; top-bar search/quick-add alignment.

## Exit criteria (met)

- Hierarchy CRUD through nested subtasks  
- Parent complete warn + bulk children  
- Inbox / Today / Upcoming  
- Calendar day + week + manual blocks  
- Quick-add, search, undo  
- Local Docker Compose  
- Qualitative LAN feel &lt; 100ms for common actions (no automated p95 harness)

## Explicitly out of Wave 1

Calendar sync, auto-scheduler, remote auth / login wall, recurrence UI, board/Kanban.

## Known gaps → Wave 1.5 (or later)

| Gap | Notes |
|-----|-------|
| Epic aggregate smart view | **Closed in W1.5** — sidebar epic rollup |
| Show completed toggle | **Closed in W1.5** |
| Archived epic/project sidebar toggle | Archive exists; browse archived deferred |
| Section-grouped project task layout | Sections exist; visual grouping polish deferred |
| Entity custom `#RRGGBB` picker UI | Presets shipped; custom hex on entities deferred (chrome themes already support hex) |
| Calendar drag resize/move | **Closed in W1.5** (desktop; modal on narrow) |
| Calendar month view | Optional; not exit blocker |
| Timezone / upcoming horizon settings UI | Schema defaults; browser-local day boundaries in MVP |
| Soft-delete / true undelete | Recreate-from-cache undo in MVP; soft-delete target **W2c** |

## How to run

See root [README.md](../README.md) — Compose web **:8080**, API **:8000**, local Vite **:5173**.
