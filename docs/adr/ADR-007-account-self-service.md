# ADR-007: Account Self-Service & Forced Password Change

**Status:** Accepted  
**Date:** 2026-08-12  
**Context:** W3 Slice 1. W1.5 shipped household login and admin `PATCH /auth/users/{id}` (display name, disable, set password). Non-admins cannot edit their own profile. Admin cannot edit email. Admin-set passwords never force a change on next login. Roadmap cut locks account polish before Microsoft Calendar and Tauri ([07-wave-roadmap.md](../07-wave-roadmap.md)).

## Decision

### Self-service

| Who | May change |
|-----|------------|
| Any authenticated user | Own **password**, **email**, **display_name** via `PATCH /auth/me` |
| Admin (existing + extended) | Any user’s **email**, **display_name**, **password**, **is_disabled** via `PATCH /auth/users/{id}` (cannot disable self — already locked) |
| Nobody | **username** — immutable after create/register |

Email uniqueness: changing email to one already used by another user → `422 EMAIL_TAKEN` (same as register/create).

Password rules unchanged: 12–128 characters, spaces allowed, no complexity rules ([ADR-003](./ADR-003-local-first-auth.md)).

No email verification, magic links, or IdP in W3. Local household model remains.

### Forced / temp password reset

Add `users.must_change_password BOOLEAN NOT NULL DEFAULT false`.

| Event | Effect |
|-------|--------|
| Admin sets `password` on `PATCH /auth/users/{id}` | Set `must_change_password = true` on that user (always when password field is present in the patch) |
| User successfully changes own password via `PATCH /auth/me` | Clear `must_change_password = false` |
| Admin clears flag explicitly | Optional: `must_change_password: false` on admin PATCH without requiring a password body — for recovery only |
| Login | Still succeeds with the temp password (session created). Not a separate login realm. |

**Client gate:** After login / on app load, if `GET /auth/me` returns `must_change_password: true`, show a **blocking** change-password sheet. Domain UI (tasks, calendar, settings except Account) stays inaccessible until the user submits a new password via `PATCH /auth/me` and the flag clears.

**API gate (light):** Mutating domain endpoints may return `403 PASSWORD_CHANGE_REQUIRED` when the flag is set. Read endpoints used by the change-password flow (`GET /auth/me`, `PATCH /auth/me`) remain allowed. Prefer client gate as primary UX; API gate as belt-and-suspenders for non-browser clients.

Self-service password change when the flag is already false does not set the flag.

### Admin “require change on next login”

When admin sets a password in Household UI, the API always sets the flag (see above). Optional UI checkbox is unnecessary for v1 — setting a password **is** the temp-reset signal. Document that behavior in Household copy.

### Out of scope (Slice 1)

- Account deletion / username rename
- Cloudflare Access / OAuth changes
- Task handoff between household accounts (post-W3)
- Email verification

## Consequences

- Alembic migration adds `must_change_password`
- `UserOut` / admin user DTOs include the flag
- Settings gains an **Account** section for all users; Household gains email edit
- Extends [ADR-003](./ADR-003-local-first-auth.md); does not replace it

## Related

- [ADR-003-local-first-auth.md](./ADR-003-local-first-auth.md) — household login baseline
- [ADR-002-single-user.md](./ADR-002-single-user.md) — personal accounts, not teams
- [05-api-contract.md](../05-api-contract.md) — auth endpoints
- [04-data-schema.md](../04-data-schema.md) — `users` table
- [07-wave-roadmap.md](../07-wave-roadmap.md) — W3 Slice 1
