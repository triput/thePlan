# Dependency Hygiene — Round 4 Quick Scan

**Date:** 2026-08-27  
**Mode:** Quick scan (not a full W3-style upgrade wave)  
**Result:** **Exit / pass** — ducks in a row; **no dependency version mutations** this round  
**Recorded for:** After Round 4 feature freeze (bulk edit P3, bundle shrink, trash purge-older, refactor assessment) before the next feature pile  
**Basis:** [HYGIENE-W3.md](./HYGIENE-W3.md) + live pin audit 2026-08-27

## Toolchain pins

| Layer | Pin / observed | Action |
|-------|----------------|--------|
| API Docker image | `python:3.12-slim` | Keep |
| Local API venv | Python **3.11.9** | Acceptable (`requires-python` ≥3.11); prefer 3.12 when convenient |
| Web Docker build | `node:22-alpine` | Keep |
| Host Node | **v26.7.0** / npm **12.0.2** | Fine for local Vite; Compose uses Node 22 |
| Postgres | `postgres:16-alpine` | Keep |
| Nginx runtime | `nginx:1.27-alpine` | Keep |
| cloudflared | `cloudflare/cloudflared:2026.7.3` | Keep (pinned W3; not `:latest`) |
| pgAdmin (tools profile) | `dpage/pgadmin4:8` | Keep |

## Package majors (spot check)

### API (`apps/api/requirements.txt` / `pyproject.toml`)

| Package | Pinned | Action |
|---------|--------|--------|
| FastAPI | 0.115.6 | Keep |
| Starlette | 0.41.3 | Keep (FastAPI pin) |
| SQLAlchemy | 2.0.51 | Keep |
| Alembic | 1.14.0 | Keep |
| Pydantic | 2.13.4 | Keep |
| httpx | 0.28.1 | Keep |
| cryptography | 44.0.2 | Keep |
| uvicorn | 0.34.0 | Keep |
| psycopg | 3.2.13 | Keep |
| pytest | 9.1.1 | Keep |

### Web (`apps/web/package.json`)

| Package | Range | Action |
|---------|-------|--------|
| React / React DOM | ^19.2.8 | Keep |
| Vite | ^8.2.0 | Keep |
| React Query | ^5.101.4 | Keep |
| TypeScript | ~6.0.2 | Keep |
| oxlint | ^1.75.0 | Keep |

No installs / bumps applied. Confirm with Trish before any non-trivial upgrade wave.

## Alembic head

| Item | Value |
|------|-------|
| Head revision | **`019_handoff_receipts`** (revises `018_one_running_schedule_run`) |
| Prior notable | `018_one_running_schedule_run`; `017_session_epoch`; trash `015_task_deleted_at` |
| Drift vs Round 4 freeze | **F1** added `019` after Round 4 closeout; run `alembic upgrade head` before F1 API/CLI manual checks |

## Native / ops debt

| Item | Status |
|------|--------|
| cloudflared pin | Still good |
| Compose healthchecks | Present |
| Base-image CVE deep scan | **Deferred** (same as W3) |
| Pytest vs live Compose DB bleed | Known ops gap; not a hygiene blocker |
| apps/desktop (Tauri) | Out of Round 4 product scope; no pin audit this pass |

## Docs pins

- Refactor assessment: [REFACTOR-ASSESSMENT.md](./REFACTOR-ASSESSMENT.md) (DEF-011)
- Living arch catch-up: [09-technical-architecture.md](./09-technical-architecture.md) (DEF-012)
- Prior full pass: [HYGIENE-W3.md](./HYGIENE-W3.md)

## Checklist

- [x] Review Python / Node / Postgres / Nginx / cloudflared pins
- [x] Spot-check FastAPI, SQLAlchemy, Alembic, Vite, React majors
- [x] Confirm Alembic head matches shipped schema
- [x] Record quick-scan exit (this file)
- [ ] Optional CVE deep scan — deferred
- [ ] Full upgrade wave — **not booked**; needs Trish greenlight

## Operator note

No recreate required for pins (unchanged from W3). After Round 4 ship:

```powershell
docker compose -f infra/compose/compose.yaml up -d --build api web
```
