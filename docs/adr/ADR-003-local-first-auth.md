# ADR-003: Local-First Authentication

**Status:** Accepted  
**Date:** 2026-08-09  
**Context:** Auth model for MVP and path to remote hosting.

## Decision

| Wave | Auth behavior |
|-------|---------------|
| **MVP** | Local-only. Bootstrap `users` row at first run. No login wall, no remote IdP. Optional session cookie for CSRF hygiene. `password_hash` nullable. |
| **W1.5** | Real login story: password session and/or Cloudflare Access in front of Tunnel. Populate `password_hash`. Enable remote hosting without schema rewrite. |

`users` table exists from baseline DDL with `email`, `password_hash`, `display_name`.

## Rationale

- **Ship fast locally:** Operator runs Compose on LAN; authentication friction blocks daily use for a personal tool.
- **Reserve remote path:** Home server + Cloudflare Tunnel (W1.5+) requires auth before exposure to internet. Schema and API paths designed now (`/auth/login`, `/auth/me`) avoid rewrite later.
- **Single-user still:** Login identifies the one operator; not multi-tenant account provisioning.

## MVP Implementation

1. Bootstrap migration seeds one user (`local@localhost`).
2. `GET /auth/me` returns bootstrap user unconditionally on LAN bind.
3. API middleware attaches `owner_id` from session or bootstrap default.
4. No password UI in MVP.

## Wave 1.5 Implementation

1. Set `password_hash` via setup script or first-run wizard.
2. `POST /auth/login` / `POST /auth/logout` with session cookies.
3. Optional: Cloudflare Access as reverse-proxy IdP; `password_hash` remains nullable if Access-only.
4. OAuth tokens for **calendar** providers stored separately in `calendar_accounts` (W2), not user login.

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
- [07-wave-roadmap.md](../07-wave-roadmap.md)
