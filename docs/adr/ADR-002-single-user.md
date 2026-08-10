# ADR-002: Single-User Tenancy

**Status:** Accepted  
**Date:** 2026-08-09  
**Context:** Tenancy model for personal productivity app.

## Decision

The application is **personal single-user per session** — one operator's data at a time. No workspaces, team sharing, assignees, role-based access control, or collaborative multi-tenant logic in MVP through W3.

Every domain table includes `owner_id UUID NOT NULL` referencing `users(id)`.

**Amendment (2026-08-10): Multi-account single-tenant-of-one.** One deployment may host **multiple personal accounts** (e.g. household members) at the same URI. Each account is a separate `users` row; login selects the active account; all domain queries filter `owner_id`. This is **not** teams: no shared projects, assignees, comments, or cross-owner visibility. Isolation is wiring create-user + login + consistent `owner_id` scoping — not workspace RBAC.

## Rationale

- Product scope is one operator's productivity system, not a collaboration platform.
- Single-user simplifies auth, conflict resolution, and UI (no sharing dialogs, no permission matrix).
- `owner_id` on all domain tables is **future-proofing hygiene**, not multi-tenancy implementation:
  - Clean data model for household multi-account on one deployment (W1.5+)
  - Consistent query pattern (`WHERE owner_id = :current`)
  - Avoids painful migration adding ownership columns to every table post-launch

## Consequences

- MVP API assumes exactly one active owner (bootstrap user).
- No invite flows, no `@assignee`, no project sharing URLs.
- Explicit non-goals: teams, comments, karma, public sharing ([01-product-vision.md](../01-product-vision.md)).
- W1.5 adds register/create-account + login for **N personal accounts** on one deployment; each session is one operator, data isolated by `owner_id`.
- Post-W3 may reconsider lightweight task handoff between personal accounts — not team workspaces ([07-wave-roadmap.md](../07-wave-roadmap.md) Post-W3 backlog).

## Related

- [ADR-003-local-first-auth.md](./ADR-003-local-first-auth.md)
- [04-data-schema.md](../04-data-schema.md)
