# ADR-009: Tauri Desktop Shell (Prove-it)

**Status:** Accepted  
**Date:** 2026-08-14  
**Context:** W3 Slice 3. Roadmap: Tauri shell + FastAPI sidecar + local Postgres, same REST contract ([07-wave-roadmap.md](../07-wave-roadmap.md), [ADR-001](./ADR-001-tech-stack.md)). Operator deferred single-installer / bundled Postgres to a later packaging wave; keep the sidecar.

## Decision

### Scope (Slice 3 prove-it)

| In | Out (later packaging wave) |
|----|----------------------------|
| Tauri 2 desktop window on Windows | Bundled/embedded Postgres; zero-Docker single installer |
| Ship production Vite/React build inside the app | Auto-updater, code signing, MSI polish |
| Spawn **FastAPI (uvicorn) as sidecar** child process | SQLite / second data model |
| UI → sidecar over loopback REST (same [05-api-contract.md](../05-api-contract.md)) | Replacing Compose for tunnel/server |
| Postgres via **existing Compose** (`DATABASE_URL`) | Offline-only daily driver without Docker |

“Embedded API + local Postgres” for this slice means: **API process embedded; Postgres remains the Compose service.**

### Sidecar lifecycle

1. On app start: ensure loopback port (prefer fixed `18765` unless busy → ephemeral), spawn uvicorn with `apps/api` and env (`DATABASE_URL` to Compose Postgres on host, `CORS_ORIGINS` / `FRONTEND_ORIGIN` suitable for the WebView origin).
2. Wait for `GET /health` before showing primary UI (or show a short “starting…” state).
3. On app quit: terminate sidecar process tree.

### Auth / CORS

- Session cookies against loopback API; configure CORS and `FRONTEND_ORIGIN` so the Tauri WebView origin (or `http://127.0.0.1:<ui>`) can use credentials.
- No separate desktop auth model.

### Layout

- New app tree under `apps/desktop/` (Tauri 2 + Rust shell).
- Reuse `apps/web` build artifacts; do not fork the React app.
- Domain logic stays exclusively in the API ([ADR-005](./ADR-005-scheduler-decoupling.md)).

### Prerequisites (operator)

- Docker Compose Postgres (and typically full stack for comparison) running.
- Windows WebView2 (Edge runtime) present.
- Python env capable of running `apps/api` for the sidecar (dev: venv; document path).

### Non-goals

- Mobile Tauri / Flutter
- Changing Cloudflare Tunnel workflow
- Entra/Microsoft live connect (parked)
- W2c leftovers

## Consequences

- Desktop ADR locked before scaffold
- Packaging / single installer remains a future wave item on the roadmap
- Compose remains the source of truth for Postgres in Slice 3

## Related

- [ADR-001-tech-stack.md](./ADR-001-tech-stack.md)
- [ADR-004-container-runtime.md](./ADR-004-container-runtime.md)
- [ADR-005-scheduler-decoupling.md](./ADR-005-scheduler-decoupling.md)
- [07-wave-roadmap.md](../07-wave-roadmap.md)
- [05-api-contract.md](../05-api-contract.md)
