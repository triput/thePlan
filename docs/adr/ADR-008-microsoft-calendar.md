# ADR-008: Microsoft Calendar (Graph) Sync

**Status:** Accepted  
**Date:** 2026-08-14  
**Context:** W3 Slice 2. Google Calendar (W2a) shipped OAuth, multi-calendar subscriptions, busy pull, conflict flags, and optional mirror push of `scheduled_blocks`. Schema already has `calendar_provider.microsoft`. Implementation was Google-only. Roadmap locks Microsoft next, then Tauri ([07-wave-roadmap.md](../07-wave-roadmap.md)).

## Decision

### Product parity

Ship **full Google parity** for Microsoft in this slice:

| Capability | Behavior |
|------------|----------|
| OAuth connect / disconnect | Auth code + refresh; Fernet token columns on `calendar_accounts` |
| Multi-calendar subscriptions | Exactly one **primary**; rest **informational**; both pull busy |
| Busy pull | Window default −7d / +21d; incremental via Graph **delta** token in `calendar_subscriptions.sync_cursor` |
| Conflicts / Calendar overlay | Reuse existing provider-agnostic paths (`scheduled_block_id IS NULL`) |
| Mirror push | When `mirror_blocks` and enabled primary — create/patch/delete Graph events; link via `scheduled_block_id` |

### Account types

**Personal (outlook.com / live) and work/school Entra** via tenant **`common`** (configurable `MICROSOFT_TENANT_ID`, default `common`).

### Auth & config

| Item | Lock |
|------|------|
| Flow | Authorization code + refresh; session `microsoft_oauth_state` (parallel to Google) |
| Client | Confidential client (client id + secret) in Compose env |
| Scopes | `Calendars.ReadWrite`, `offline_access`, `User.Read` |
| Env | `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_REDIRECT_URI`, optional `MICROSOFT_TENANT_ID` (default `common`) |
| HTTP | Prefer **httpx** to Graph/token endpoints (already in stack); do not add MSAL unless forced by edge cases |

Routes: `GET /calendar/oauth/microsoft/start`, `GET /calendar/oauth/microsoft/callback`. Post-OAuth redirect `{FRONTEND_ORIGIN}/?mcal=connected|error…`.

### Schema / API softening

- Rename `calendar_accounts.mirror_blocks_to_google` → **`mirror_blocks`** (Alembic). Semantics: push local scheduled blocks to **this account’s** enabled primary calendar (Google or Microsoft).
- API `CalendarAccountOut` / PATCH body use `mirror_blocks` (accept legacy `mirror_blocks_to_google` as alias on write if cheap; prefer single field).
- `GET /calendars?account_id=` dispatches by `account.provider` (remove Google-only gate).
- Sync / mirror call sites dispatch by provider.

### Sync details

- Default / ensure primary subscription uses Graph calendar **id** (GUID), not the Google alias `"primary"`.
- Delta failure or gone token → clear cursor → full window sync (same recovery pattern as Google 410).
- Mirrored push rows excluded from busy overlays (existing `scheduled_block_id` rule).

### Non-goals (Slice 2)

- Tauri, W2c leftovers
- Teams / shared mailboxes / group calendars as first-class
- iCloud
- Live Graph E2E in CI (mock Graph in tests; operator verifies live)
- Renaming Google OAuth path prefixes

## Consequences

- New service module `microsoft_calendar.py` (or equivalent adapter)
- Settings UI: Microsoft Calendar section alongside Google
- Operator doc: short Entra app registration checklist; secrets gitignored
- Extends W2a calendar contract; does not change ADR-005/006 scheduler semantics

## Related

- [05-api-contract.md](../05-api-contract.md) — calendar endpoints
- [04-data-schema.md](../04-data-schema.md) — `calendar_accounts`, subscriptions, events
- [07-wave-roadmap.md](../07-wave-roadmap.md) — W3 Slice 2
- Google reference: `apps/api/app/services/google_calendar.py`
