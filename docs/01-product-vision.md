# Product Vision

**Working name:** Phronesis Light (conversational only; official name TBD)

## What We Are Building

A personal, single-user, web-first productivity application that combines structured task management (Todoist-class hierarchy and capture) with automated time-blocking (SkedPal-class scheduling) in a later wave. The application prioritizes execution speed, deep hierarchical organization, and utility over engagement mechanics.

## Core Principles

### Speed First

Interaction latency must feel instant. Target sub-100ms perceived response on a local LAN deployment through optimistic client rendering, client-side caching, and a CRUD API that never blocks on background scheduling work.

### Utility Over Gamification

No karma scores, streak badges, leaderboards, or other engagement loops. Focus on clean tracking, focus windows, calendar visibility, and reliable completion workflows.

### Expanded Hierarchy

Extend standard task tools with a top-level **Epic** layer and one additional subtask nesting level beyond Todoist's current depth:

**Epic → Project → Section → Task → Subtask → Nested Subtask**

Epics span multi-month initiatives; projects organize functional domains; sections group work within a project; tasks support two levels of subtask nesting (`nesting_level` 0–2).

### Dynamic Scheduling (Later)

Wave 2 introduces SkedPal-inspired fuzzy time-blocking: slice tasks into calendar blocks, respect dependencies and focus windows, pin manual placements, and surface overbooking. MVP ships manual due dates and manually placed blocks only.

### Local-First Infrastructure

Primary deployment is **Docker Compose + PostgreSQL** on local hardware. Remote access via Cloudflare Tunnel is planned post-MVP, not required for Wave 1 exit. Hosted Postgres is a fallback option, not the default architecture.

## Target User

One operator (personal productivity). No teams, workspaces, sharing, or role-based access control. Schema retains `owner_id` on domain tables for future hygiene (desktop multi-profile, optional accounts) without implementing multi-tenancy in MVP.

## Technology Direction

| Layer | Choice |
|-------|--------|
| Backend | Python 3.12+ / FastAPI / SQLAlchemy 2 / Alembic |
| Web client | TypeScript / Vite / React |
| Database | PostgreSQL (local Compose) |
| Desktop (later) | Tauri 2 wrapping the web UI + API sidecar |
| Containers | Docker Desktop + Compose on Windows; OCI-portable |

Flutter is explicitly rejected. Domain logic lives in the API; web and desktop are thin clients of the same contract.

## MVP Scope Summary

**In:** Full hierarchy CRUD, labels, Synesis/Phronesis-aligned color presets ([08-color-palette.md](./08-color-palette.md)), fixed smart views (Inbox, Today, Upcoming, by Project/Epic/Label), calendar view (day/week), quick-add parser, search, undo, local Compose stack, local-only auth.

**Out of MVP:** Auto-scheduler, external calendar sync, recurrence engine, login/remote auth, board/Kanban (optional W3 candidate), teams, gamification, SLM assist, desktop client, voice input, email-to-task, location reminders, templates (all W3 backlog candidates — not before W2 where applicable).

## Explicit Non-Goals (All Waves Unless Reopened)

- Team workspaces, assignees, comments, public sharing
- Karma, streaks, productivity gamification
- Board / Kanban as a project view (not MVP; optional W3 candidate)
- Flutter or separate mobile-native clients (responsive web until Tauri)
- AI/SLM in the critical path before Wave 3

## Success Criteria (MVP)

A single user can manage the full Epic→Nested Subtask hierarchy, complete tasks with parent/child policies, work from Today/Inbox/Upcoming and calendar day/week views, capture tasks via quick-add, search and undo changes, and run the stack locally with p95 interaction feel under 100ms on LAN — without calendar sync, auto-scheduling, or remote authentication.
