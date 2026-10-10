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
| **Tasks** | `tasks list`, `tasks get`, `tasks create`, `tasks patch`, `tasks complete`, `tasks uncomplete`, `tasks workflow` |
| **Assist** | `assist propose`, `assist apply` |

List/filter flags map to query parameters on `GET /api/v1/tasks`; see README for the full flag list.

### F1 — planning handoff and hierarchy (HTTP)

Uses the same session file as M2. Spec: [NEXT-FEATURES-SPEC.md §4](./NEXT-FEATURES-SPEC.md#4-f1-cli-planning-handoff). Delivery record: [delivery/F1-HANDOFF.md](./delivery/F1-HANDOFF.md).

| Area | Commands |
|------|----------|
| **Handoff** | `handoff propose` (`--file` or `--stdin`), `handoff apply` (`--idempotency-key` or key in JSON), `handoff receipt` (`--id` or `--idempotency-key`) |
| **Epics** | `epics list`, `get`, `create`, `patch` |
| **Projects** | `projects list`, `get`, `create`, `patch` |
| **Sections** | `sections list`, `get`, `create`, `patch` |
| **Dependencies** | `deps list`, `add`, `remove` (path `--task-id` must be blocking or dependent) |

Handoff maps to `POST /api/v1/handoffs/propose|apply` and `GET /api/v1/handoffs/receipts/...`. Dependencies map to `/api/v1/tasks/{id}/dependencies`. `--format text` on handoff commands prints a tree and resolved defaults without changing the JSON contract.

**Outline ingest** (`outline` UI / `POST /api/v1/outlines/*`) is a separate path; re-import is not idempotent. Use **handoff** for agreed-plan bulk create with receipt replay — [OUTLINE-INGEST.md](./OUTLINE-INGEST.md).

### F2 — Kanban workflow (HTTP)

Uses the same session file as M2. Spec: [NEXT-FEATURES-SPEC.md §5](./NEXT-FEATURES-SPEC.md#5-f2-kanban-for-work-in-progress). Delivery record: [delivery/F2-KANBAN.md](./delivery/F2-KANBAN.md).

| Command | Maps to |
|---------|---------|
| `tasks list --workflow ready\|in_progress\|waiting\|done` | `GET /api/v1/tasks?workflow=` (implies board sort unless overridden) |
| `tasks list --board-order` | `GET /api/v1/tasks?board_order=true` |
| `tasks workflow --id UUID --column COL --expected-revision N` | `POST /api/v1/tasks/{id}/workflow` |

Optional flags on **workflow:** `--waiting-note`, `--board-rank`, `--insert-before-id`, `--insert-after-id`, `--bulk-children`, `--force-parent-only` (Done / open-children policy). Read `board_revision` from `tasks get` before each transition; stale revision → exit **5** / `BOARD_REVISION_CONFLICT`.

### F3 — Scheduler explanations (HTTP, read-only)

Uses the same session file as M2. Spec: [NEXT-FEATURES-SPEC.md §6](./NEXT-FEATURES-SPEC.md#6-f3-scheduler-explanations). Delivery record: [delivery/F3-SCHEDULER-EXPLANATIONS.md](./delivery/F3-SCHEDULER-EXPLANATIONS.md). These commands **do not** call `POST /schedule/replan`.

| Command | Maps to |
|---------|---------|
| `schedule explain --task-id UUID` | `GET /api/v1/tasks/{task_id}/schedule-explanation` — JSON success adds `human_summary` (same text as `summary_text`) |
| `schedule runs list` [`--limit`, `--offset`] | `GET /api/v1/schedule/runs` |
| `schedule runs get --id UUID` | `GET /api/v1/schedule/runs/{id}` |
| `schedule runs explanations --id UUID` [`--task-id`, `--limit`, `--offset`] | `GET /api/v1/schedule/runs/{id}/explanations` |

Run Update Schedule via the web UI or API replan before expecting `evaluation_state: evaluated`.

### F4 — Time Map overrides (HTTP)

Uses the same session file as M2. Spec: [NEXT-FEATURES-SPEC.md §7](./NEXT-FEATURES-SPEC.md#7-f4-temporary-time-map-overrides). Delivery record: [delivery/F4-TIME-MAP-OVERRIDES.md](./delivery/F4-TIME-MAP-OVERRIDES.md). F4 **Open** — operator Dex and sign-off pending.

All subcommands require **`--map-id UUID`** (focus window / Time Map id). **Create** and **edit** take a JSON body via **`--file PATH`** or **`--stdin`** (same pattern as `views create`).

| Command | Maps to |
|---------|---------|
| `overrides list --map-id UUID` | `GET /api/v1/focus-windows/{map_id}/overrides` — includes expired rows |
| `overrides get --map-id UUID --id UUID` | `GET …/overrides/{override_id}` |
| `overrides create --map-id UUID` (`--file` or `--stdin`) | `POST …/overrides` — body matches API **TimeMapOverrideCreate** (inclusive local dates, IANA `timezone`, `strict_mode`, replacement `bands`) |
| `overrides edit --map-id UUID --id UUID` (`--file` or `--stdin`) | `PATCH …/overrides/{override_id}` — partial body; at least one field required |
| `overrides delete --map-id UUID --id UUID` | `DELETE …/overrides/{override_id}` |

Overlap on the same map → exit **5** / **`TIME_MAP_OVERRIDE_OVERLAP`**. Midnight-crossing bands and invalid date order → **422** with stable API codes. Override writes do **not** auto-replan; see scheduler stale **`time_map_overrides`** in [F3 delivery](./delivery/F3-SCHEDULER-EXPLANATIONS.md).

### F5 — Coursera templates (HTTP)

Uses the same session file as M2. Spec: [NEXT-FEATURES-SPEC.md §8](./NEXT-FEATURES-SPEC.md#8-f5-coursera-templates). Delivery record: [delivery/F5-COURSERA-TEMPLATES.md](./delivery/F5-COURSERA-TEMPLATES.md).

| Area | Commands |
|------|----------|
| **Templates** | `templates list`, `templates get ID`, `templates propose ID` (`--file` or `--stdin`; optional `--skip-optional`, `--attach-kind epic\|project\|section`, `--attach-id UUID`), `templates apply ID` (`--file` or `--stdin`; `--idempotency-key UUID`), `templates receipt --id UUID` or `--idempotency-key UUID` |

Maps to `/api/v1/templates/*` and `/api/v1/templates/receipts/...`. **Module** templates require attach context (`--attach-kind` + `--attach-id`). Idempotency keys must be retained across retries for uncertain outcomes. Legacy **`outline`** ingest remains separate and non-idempotent — [OUTLINE-INGEST.md](./OUTLINE-INGEST.md).

### F7 — Saved views (HTTP)

Uses the same session file as M2. Spec: [NEXT-FEATURES-SPEC.md §10](./NEXT-FEATURES-SPEC.md#10-f7-saved-views). Delivery record: [delivery/F7-SAVED-VIEWS.md](./delivery/F7-SAVED-VIEWS.md).

| Area | Commands |
|------|----------|
| **Views** | `views list`, `views get --id UUID`, `views create` (`--file` or `--stdin` JSON body), `views patch --id UUID` (`--file` or `--stdin`), `views delete --id UUID`, `views query` (`--id UUID` or `--slug SLUG`; optional `--limit`, `--offset`, `--board-order`) |

CRUD maps to `/api/v1/views`; **query** maps to `/api/v1/views/{id}/tasks` or `/api/v1/views/by-slug/{slug}/tasks`. System views are read-only at the API (CLI surfaces **`SYSTEM_VIEW_READ_ONLY`**). Prefer **query** over ad hoc `tasks list` for saved-view predicates.

## Session revocation (`session_epoch`)

Password changes and host recovery bump per-user `session_epoch` in PostgreSQL (migration `017_session_epoch`). The API stores the epoch in the session cookie at login; requests with a stale epoch are treated as unauthenticated. This satisfies DEF-027’s requirement to invalidate sessions after recovery without email. Details: [09-technical-architecture.md](./09-technical-architecture.md) §7.

## Agent notes

- Prefer JSON default; use `--format text` only for operator debugging.
- Dependency surface is intentionally small: **httpx** for HTTP; stdlib **argparse** (no Typer).
- For DTO shapes beyond CLI wrappers, OpenAPI from the running API and [05-api-contract.md](./05-api-contract.md) remain authoritative.
