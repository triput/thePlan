# Desktop (Tauri) — operator note

**ADR:** [ADR-009 — Tauri Desktop Shell (Prove-it)](./adr/ADR-009-tauri-desktop.md) (Accepted).  
**App tree:** [apps/desktop/README.md](../apps/desktop/README.md).

## What this is

Windows Tauri 2 window shipping the **`apps/web`** production build, plus a **FastAPI uvicorn sidecar** on `127.0.0.1:18765`. Same REST contract as Compose. **Postgres remains Compose** on the host — not embedded in this slice. Single-installer / bundled DB is a later packaging wave.

## Operator steps

1. Start Postgres: `docker compose -f infra/compose/compose.yaml up -d postgres`
2. Ensure `apps/api/.venv` exists with project deps (sidecar prefers it over PATH `python`); optionally set `THEPLAN_API_PYTHON`
3. `cd apps/desktop && npm install && npm run tauri:dev` (or `npm run tauri:build`)
4. WebView2 required on Windows

If port **18765** is taken, the app refuses to start (fixed port). Free the port and retry.

## Out of scope here

Entra / Microsoft live connect setup, auto-updater, code signing polish, mobile Tauri.
