# ADR-002: Single-User Tenancy

**Status:** Accepted  
**Date:** 2026-08-09  
**Context:** Tenancy model for personal productivity app.

## Decision

The application is **personal single-user**. No workspaces, team sharing, assignees, role-based access control, or multi-tenant isolation logic in MVP through W2.

Every domain table includes `owner_id UUID NOT NULL` referencing `users(id)`.

## Rationale

- Product scope is one operator's productivity system, not a collaboration platform.
- Single-user simplifies auth, conflict resolution, and UI (no sharing dialogs, no permission matrix).
- `owner_id` on all domain tables is **future-proofing hygiene**, not multi-tenancy implementation:
  - Clean data model if optional accounts or desktop multi-profile are added later
  - Consistent query pattern (`WHERE owner_id = :current`)
  - Avoids painful migration adding ownership columns to every table post-launch

## Consequences

- MVP API assumes exactly one active owner (bootstrap user).
- No invite flows, no `@assignee`, no project sharing URLs.
- Explicit non-goals: teams, comments, karma, public sharing ([01-product-vision.md](../01-product-vision.md)).
- W1.5 login adds authentication but not multi-user — still one row, one operator.
- If multi-user is ever reopened, it becomes a major ADR revision with row-level security or account switching — not a incremental patch.

## Related

- [ADR-003-local-first-auth.md](./ADR-003-local-first-auth.md)
- [04-data-schema.md](../04-data-schema.md)
