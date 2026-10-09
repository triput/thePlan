# theplan CLI

Agent-friendly command-line interface for thePlan. Defaults to **JSON on stdout**; errors use `{"ok":false,"code":"...","message":"..."}` with stable exit codes.

## Install

From the repo root (or `apps/cli`):

```bash
pip install -e "apps/cli"
```

Host-local commands (`auth reset-password`) also need the API package importable and its dependencies:

```bash
pip install -e "apps/api"
export PYTHONPATH="apps/api"   # Windows: set PYTHONPATH=apps\api
export DATABASE_URL="postgresql+psycopg://theplan:theplan@127.0.0.1:5432/theplan"
```

`DATABASE_URL` is read by `app.config.Settings` in `apps/api` (same as the API server).

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `THEPLAN_API_URL` | `http://127.0.0.1:8000` | API base URL (no `/api/v1` suffix) |
| `THEPLAN_SESSION_FILE` | `~/.config/theplan/session` (or `%LOCALAPPDATA%\theplan\session` on Windows) | Saved session cookies after `auth login` |

## Run

```bash
theplan version
theplan --format text version
python -m theplan version
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Usage / validation |
| 2 | Auth |
| 3 | Not found |
| 4 | API or service unavailable |
| 5 | Conflict |

## M1 commands

### `theplan version`

```bash
theplan version
```

Example output:

```json
{
  "ok": true,
  "version": "0.1.0",
  "name": "theplan-cli"
}
```

### `theplan auth reset-password`

Host-local recovery: opens a DB session via `app.db.SessionLocal` and calls `app.services.auth_users.reset_password_for_recovery`.

Exactly one password mode is required:

- `--generate` — service generates a temporary password (returned as `temporary_password` in JSON)
- `--password X` — set explicit password (never logged)
- `--password-stdin` — read from a **pipe/redirect** (not a bare TTY). On a terminal without a pipe it fails fast; use `--interactive` for a hidden prompt, or `--password`.

```bash
theplan auth reset-password --user trish --generate
theplan auth reset-password --user local@localhost --password-stdin <<'EOF'
MyLongSecurePassphrase!!
EOF
```

PowerShell (pipe until EOF — do not type after the command and wait):

```powershell
"MyLongSecurePassphrase!!" | theplan auth reset-password --user trish --password-stdin
theplan --interactive auth reset-password --user trish --password-stdin   # hidden prompt
```

Example success (`--generate`):

```json
{
  "ok": true,
  "user_id": "00000000-0000-0000-0000-000000000001",
  "username": "trish",
  "email": "trish@example.com",
  "must_change_password": true,
  "temporary_password": "xY9_kL2mN4pQ7rS8tUv"
}
```

## M2 HTTP commands

All M2 commands use `THEPLAN_API_URL` and, when authenticated, cookies from `THEPLAN_SESSION_FILE`.

### Auth

```bash
theplan auth login --identifier trish --password 'correct horse battery staple'
theplan auth login --identifier trish --password-stdin <<'EOF'
correct horse battery staple
EOF
theplan auth me
theplan auth logout
```

### Status

```bash
theplan status
```

Calls `GET /health`, then `GET /api/v1/auth/me` and `GET /api/v1/assist/status` (assist failures are reported inside JSON, not a failed exit).

### Tasks

```bash
theplan tasks list --incomplete --limit 20
theplan tasks list --project-id 00000000-0000-0000-0000-000000000010 --completed
theplan tasks get --id 00000000-0000-0000-0000-000000000020
theplan tasks create --title "Write CLI docs" --priority p2 --due-at 2026-10-09T17:00:00Z
theplan tasks patch --id 00000000-0000-0000-0000-000000000020 --title "Write CLI docs (done)"
theplan tasks complete --id 00000000-0000-0000-0000-000000000020
theplan tasks uncomplete --id 00000000-0000-0000-0000-000000000020
```

List query flags map to `GET /api/v1/tasks` parameters (`project_id`, `inbox`, `is_completed` via `--completed` / `--incomplete`, `limit`, `offset`, `trashed`, `epic_id`, `section_id`, `parent_task_id`, `label_id`, `due_from`, `due_to`, repeated `--id`).

### Handoff (F1)

```bash
theplan handoff propose --file graph.json
theplan handoff apply --file graph.json --idempotency-key 00000000-0000-0000-0000-000000000030
theplan handoff receipt --idempotency-key 00000000-0000-0000-0000-000000000030
theplan --format text handoff propose --stdin   # tree + defaults summary
```

### Epics, projects, sections

```bash
theplan epics list --limit 20
theplan epics create --title "Q4 roadmap"
theplan projects list --epic-id 00000000-0000-0000-0000-000000000010
theplan sections list --project-id 00000000-0000-0000-0000-000000000011
theplan sections create --project-id 00000000-0000-0000-0000-000000000011 --title Backlog
```

### Task dependencies

```bash
theplan deps list --task-id 00000000-0000-0000-0000-000000000020
theplan deps add --task-id 00000000-0000-0000-0000-000000000021 \
  --blocking-task-id 00000000-0000-0000-0000-000000000020 \
  --dependent-task-id 00000000-0000-0000-0000-000000000021
theplan deps remove --task-id 00000000-0000-0000-0000-000000000021 \
  --dependency-id 00000000-0000-0000-0000-000000000040
```

### Assist

```bash
theplan assist propose --text "remind me to call dentist tomorrow at 9am"
theplan assist apply --file proposal.json
theplan assist apply --stdin <<'EOF'
{"actions": [{"type": "create_task", "title": "Call dentist"}]}
EOF
```

## Agent notes

- Default output is JSON; pass `--format text` for human-readable lines.
- No interactive prompts unless `--interactive` (reserved for future flows).
- Passwords are never written to logs or success JSON except `temporary_password` when `--generate` is used.
- CLI dependency: **httpx** (cookie jar persisted to the session file). Typer was skipped to keep deps minimal (stdlib `argparse`).

## PYTHONPATH / imports

When `PYTHONPATH` includes `apps/api`, the CLI may import:

- `app.db` — SQLAlchemy session factory
- `app.services.auth_users.reset_password_for_recovery` — host-local recovery

Do not commit secrets; use environment variables only.
