# Dependency Hygiene — W1.5 Quick Scan

**Date:** 2026-08-10  
**Mode:** Quick scan (not full CVE audit)  
**Result:** **Exit / pass** — proceed with W1.5 auth feature work  
**Recorded for:** Wave 1.5 login + household accounts (per [07-wave-roadmap.md](./07-wave-roadmap.md) hygiene gate)

## Toolchain pins

| Layer | Pin / observed | Notes |
|-------|----------------|-------|
| API Docker image | `python:3.12-slim` | Matches ADR-001 (3.12+) |
| Local API venv | Python **3.14.5** | Recreated 2026-08-10 (`py -3.14`); host has 3.14 + 3.11, no 3.12 |
| Web Docker build | `node:22-alpine` | Current LTS line for builds |
| Host Node | **v26.4.0** / npm 12 | Fine for local Vite; Compose build uses Node 22 |
| Postgres | `postgres:16-alpine` | Stable; keep |
| Nginx runtime | `nginx:1.27-alpine` | Keep |

## Package majors (spot check)

| Package | Pinned / installed | Action |
|---------|-------------------|--------|
| FastAPI | 0.115.6 | Keep for W1.5 auth wave |
| SQLAlchemy | **2.0.51** | Bumped from 2.0.36 for Python 3.14 typing (PEP 649) |
| Alembic | 1.14.0 | Keep |
| Pydantic | 2.13.4 | Keep |
| psycopg / binary | **3.2.13** | Bumped from 3.2.3 (3.14 wheels) |
| Starlette | 0.41.3 (via FastAPI) | SessionMiddleware available |
| React / Vite | 19.2.x / 8.2.x | Keep |
| React Query | 5.101.x | Keep |

No forced major upgrades in this wave. Auth adds: `pwdlib[argon2]`, `itsdangerous` (if not already transitive), optionally `email-validator`.

## Container / docs

- Compose healthchecks present for postgres, api, web.
- CORS already includes `:8080` and `:5173`.
- Doc pins: Wave 1 exit recorded; W1.5 auth ADRs in place.
- Optional pgAdmin via Compose `--profile tools` (:5050).

## Follow-ups (not blockers)

1. ~~Align local venv to Python 3.12 when easy (Docker already 3.12).~~ Done via **3.14.5** local venv (3.12 not installed on host).
2. ~~Consider Nginx `/api` reverse-proxy before Cloudflare Tunnel (LAN cookie/CORS hygiene).~~ Done in Compose web nginx.
3. Full CVE scan of base images deferred to next full hygiene wave.

## Checklist

- [x] Pin Python, Node, Postgres image versions (reviewed)
- [x] Audit FastAPI, SQLAlchemy, Alembic, Vite, React majors (spot check)
- [x] Review container base image pins (quick; no CVE deep dive)
- [x] Update doc pins / record this quick-scan
- [x] Record quick-scan or full pass in version notes (this file)
- [x] Local API venv on Python 3.14.5 (2026-08-10 follow-up)
