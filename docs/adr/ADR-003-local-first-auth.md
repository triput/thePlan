# ADR-003: Local-First Authentication

**Status:** Accepted  
**Date:** 2026-08-09  
**Context:** Auth model for MVP and path to remote hosting.

## Decision

| Wave | Auth behavior |
|-------|---------------|
| **MVP** | Local-only. Bootstrap `users` row at first run. No login wall, no remote IdP. Optional session cookie for CSRF hygiene. `password_hash` nullable. |
| **W1.5** | Real login story: register/create-account + password session and/or Cloudflare Access in front of Tunnel. Populate `password_hash`. **Multiple personal accounts** on one deployment (household login); session selects one `users` row; domain queries filter `owner_id`. Enable remote hosting without schema rewrite. |

`users` table exists from baseline DDL with `email`, `password_hash`, `display_name`.

## Rationale

- **Ship fast locally:** Operator runs Compose on LAN; authentication friction blocks daily use for a personal tool.
- **Reserve remote path:** Home server + Cloudflare Tunnel (W1.5+) requires auth before exposure to internet. Schema and API paths designed now (`/auth/login`, `/auth/me`) avoid rewrite later.
- **Household accounts, not teams:** W1.5 supports N personal `users` rows on one URI — each operator's data isolated by `owner_id`. No workspaces, sharing, or assignees ([ADR-002](./ADR-002-single-user.md)).

## MVP Implementation

1. Bootstrap migration seeds one user (`local@localhost`).
2. `GET /auth/me` returns bootstrap user unconditionally on LAN bind.
3. API middleware attaches `owner_id` from session or bootstrap default.
4. No password UI in MVP.

## Wave 1.5 Implementation (shipped)

1. `POST /auth/register` claims bootstrap user UUID when no `password_hash` exists yet; sets `is_admin=true`.
2. `POST /auth/login` / `POST /auth/logout` with signed session cookies; session binds `owner_id`.
3. Admin `POST /auth/users` for additional household accounts; public registration closed after setup.
4. Optional demo user `nebula` seeded when `SEED_DEMO_USER=true`; passphrase in gitignored `.secrets-backup/`.
5. All domain handlers scope queries to session `owner_id`; ownership checks on cross-entity FKs (project epic, task project/section/parent).

## Security Notes

- MVP binds API to localhost/LAN; document that LAN exposure without W1.5 auth is dev-only.
- Secrets (OAuth tokens, session keys) in host env or Docker secrets; never git.
- Follow operator backup rules: `.secrets-backup/` before sanitizing for push.

## Consequences

- MVP exit criteria do **not** require login.
- W1.5 adds auth stories to [06-mvp-backlog.md](../06-mvp-backlog.md) successor and [05-api-contract.md](../05-api-contract.md) auth section.
- Cloudflare Tunnel template deferred to W1.5 docs, not MVP Wave 4 blocker.

## Related

- [ADR-002-single-user.md](./ADR-002-single-user.md)
- [ADR-007-account-self-service.md](./ADR-007-account-self-service.md) — W3 self-service + forced password change
- [07-wave-roadmap.md](../07-wave-roadmap.md)
