# thePlan agent CLI

Machine-oriented command-line interface for operators and automation agents. Defaults to **JSON on stdout**; failures use a stable envelope and exit codes so scripts can branch without parsing prose.

**Command reference and examples:** [apps/cli/README.md](../apps/cli/README.md) (source of truth for flags and sample output).

## Install

From the repository root:

```bash
pip install -e "apps/cli"
```

**Host-local recovery** (`theplan auth reset-password`) also requires the API package on `PYTHONPATH` and a working database URL (same as the API server):

```bash
pip install -e "apps/api"
export PYTHONPATH="apps/api"   # Windows: set PYTHONPATH=apps\api
export DATABASE_URL="postgresql+psycopg://theplan:theplan@127.0.0.1:5432/theplan"
```

HTTP commands (M2) only need the CLI install plus a reachable API; they do not import `apps/api` at runtime unless you use reset-password.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | (from `app.config.Settings`) | PostgreSQL URL for **host-local** `auth reset-password` only |
| `THEPLAN_API_URL` | `http://127.0.0.1:8000` | API base URL — **no** `/api/v1` suffix |
| `THEPLAN_SESSION_FILE` | `~/.config/theplan/session` (Linux/macOS) or `%LOCALAPPDATA%\theplan\session` (Windows) | Persisted session cookies after `auth login` |

Do not commit secrets; use environment variables only.

## Output contract

Global flags (all commands):

- `--format json` (default) — single JSON object on stdout per invocation
- `--format text` — human-readable key/value or stderr error line
- `--interactive` — reserved; enables interactive prompts when future flows need them (agents should omit it)

**Success:**

```json
{
  "ok": true,
  "...": "command-specific fields"
}
```

**Failure:**

```json
{
  "ok": false,
  "code": "STABLE_CODE",
  "message": "Human-readable detail"
}
```

Passwords are never logged or included in success JSON except `temporary_password` when reset-password uses `--generate`.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Usage / validation |
| 2 | Auth (HTTP 401/403 or auth-related CLI failure) |
| 3 | Not found (HTTP 404) |
| 4 | API or service unavailable (5xx and other unreachable cases) |
| 5 | Conflict (HTTP 409) |

HTTP status mapping for M2 calls is implemented in the CLI client; see [apps/cli/README.md](../apps/cli/README.md).

## Milestones

### M1 — version and host-local recovery

| Command | Scope |
|---------|--------|
| `theplan version` | CLI identity (`version`, `name`) |
| `theplan auth reset-password` | **Host-local:** DB session via `app.db`, `reset_password_for_recovery` — selects user by username or email, sets password, `must_change_password`, **increments `session_epoch`** to revoke existing sessions |

Password mode (exactly one): `--generate`, `--password`, or `--password-stdin`. `--password-stdin` requires a pipe/redirect (or global `--interactive` for a hidden prompt); a bare TTY fails fast instead of hanging. Examples in [apps/cli/README.md](../apps/cli/README.md).

### M2 — HTTP via API (session file)

Uses `THEPLAN_API_URL` and cookies from `THEPLAN_SESSION_FILE` when authenticated.

| Area | Commands |
|------|----------|
| **Auth** | `auth login`, `auth me`, `auth logout` |
| **Status** | `status` — `GET /health`, then `/api/v1/auth/me` and `/api/v1/assist/status` (assist errors stay inside JSON; exit 0 if health/me succeed) |
| **Tasks** | `tasks list`, `tasks get`, `tasks create`, `tasks patch` |
| **Assist** | `assist propose`, `assist apply` |

List/filter flags map to query parameters on `GET /api/v1/tasks`; see README for the full flag list.

## Session revocation (`session_epoch`)

Password changes and host recovery bump per-user `session_epoch` in PostgreSQL (migration `017_session_epoch`). The API stores the epoch in the session cookie at login; requests with a stale epoch are treated as unauthenticated. This satisfies DEF-027’s requirement to invalidate sessions after recovery without email. Details: [09-technical-architecture.md](./09-technical-architecture.md) §7.

## Agent notes

- Prefer JSON default; use `--format text` only for operator debugging.
- Dependency surface is intentionally small: **httpx** for HTTP; stdlib **argparse** (no Typer).
- For DTO shapes beyond CLI wrappers, OpenAPI from the running API and [05-api-contract.md](./05-api-contract.md) remain authoritative.
