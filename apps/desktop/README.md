# thePlan desktop (Tauri 2)

W3 Slice 3 prove-it shell per [ADR-009](../../docs/adr/ADR-009-tauri-desktop.md). Operator note: [docs/DESKTOP.md](../../docs/DESKTOP.md).

Loads the production build of `apps/web` and spawns FastAPI (`uvicorn`) as a loopback sidecar on **`127.0.0.1:18765`**. Postgres stays the Compose service (not bundled).

## Prerequisites

- Windows + [WebView2](https://developer.microsoft.com/microsoft-edge/webview2/) (Edge runtime)
- Node 20+ / npm, Rust (rustc/cargo), Python 3.11+ with `apps/api` deps
- Docker Compose Postgres up (host port `5432`)

```powershell
docker compose -f infra/compose/compose.yaml up -d postgres
```

## Python for the sidecar

Resolution order:

1. `THEPLAN_API_PYTHON` (if set)
2. `apps/api/.venv` (`Scripts/python.exe` on Windows, `bin/python` elsewhere)
3. `python` / `python3` on PATH (last resort — easy to pick up the wrong env)

```powershell
# Optional override
$env:THEPLAN_API_PYTHON = "F:\Code Repo\ThePlan\apps\api\.venv\Scripts\python.exe"
```

Optional: `THEPLAN_API_DIR` if the API tree is not at `apps/api` relative to the crate.

## Run (dev)

From `apps/desktop`:

```powershell
npm install
npm run tauri:dev
```

That builds `apps/web` with `VITE_API_URL=http://127.0.0.1:18765`, then starts Tauri. On launch the Rust shell:

1. Fails clearly if port **18765** is busy (fixed port — no ephemeral fallback in this slice)
2. Spawns `python -m uvicorn app.main:app --host 127.0.0.1 --port 18765` with cwd `apps/api`
3. Waits up to ~30s for `GET /health`
4. Shows the main window; kills the sidecar process tree on quit

Equivalent: `npm run build:web` then `npm run tauri -- dev`.

## Build

```powershell
npm run tauri:build
```

Runs `beforeBuildCommand` → `npm run build:web`, then packages with NSIS (prove-it; single-installer / embedded Postgres deferred).

## Smoke (no GUI)

```powershell
npm run smoke:sidecar
```

Spawns uvicorn with the same env/port contract, asserts `/health`, tears down. Needs reachable Postgres.

## Sidecar env (set by the shell)

| Variable | Value |
|----------|--------|
| `DATABASE_URL` | `postgresql+psycopg://theplan:theplan@127.0.0.1:5432/theplan` (override via process env) |
| `CORS_ORIGINS` | includes `http://127.0.0.1:18765` and Tauri WebView origins |
| `FRONTEND_ORIGIN` | `http://127.0.0.1:18765` |
| `SESSION_HTTPS_ONLY` | `false` |

## npm packages

Desktop Node deps are **`@tauri-apps/cli` only** (no MSAL, no forked React app). UI comes from `apps/web/dist`.
