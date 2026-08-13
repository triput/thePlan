# Dependency Hygiene — W3 Entry (Full Pass)

**Date:** 2026-08-12  
**Mode:** Full hygiene wave (not a quick scan)  
**Result:** **Exit / pass** — W3 feature work may proceed after this gate  
**Recorded for:** Post–W2b Painted Time Maps; before Wave 3 feature waves (per [07-wave-roadmap.md](./07-wave-roadmap.md))  
**Basis:** [HYGIENE-W2-QUICKSCAN.md](./HYGIENE-W2-QUICKSCAN.md) + live pin audit

## Toolchain pins

| Layer | Pin / observed | Action |
|-------|----------------|--------|
| API Docker image | `python:3.12-slim` | Keep |
| Local API venv | Python **3.11.9** | Acceptable (`requires-python` ≥3.11); prefer 3.12 when convenient |
| Web Docker build | `node:22-alpine` | Keep |
| Host Node | **v26.7.0** | Fine for local Vite; Compose uses Node 22 |
| Postgres | `postgres:16-alpine` | Keep |
| Nginx runtime | `nginx:1.27-alpine` | Keep |
| **cloudflared** | **`cloudflare/cloudflared:2026.7.3`** | **Pinned** (was `:latest`) — matches local image built 2026-07-23 |

## Package majors (spot check)

| Package | Pinned / installed | Action |
|---------|-------------------|--------|
| FastAPI | 0.115.6 | Keep — no forced major this wave |
| Starlette | 0.41.3 | Keep (FastAPI pin) |
| SQLAlchemy | 2.0.51 | Keep |
| Alembic | 1.14.0 | Keep |
| Pydantic | 2.13.4 | Keep |
| httpx | 0.28.1 | Keep |
| cryptography | 44.0.2 | Keep (OAuth token encryption) |
| uvicorn | 0.34.0 | Keep |
| React / React DOM | 19.2.8 | Keep |
| Vite | 8.2.1 | Keep |
| React Query | 5.101.4 | Keep |
| TypeScript | 6.0.3 | Keep |

No dependency upgrades applied in this wave (confirm with Trish before any install). Additive OAuth stack already present.

## Native / ops debt

| Item | Status |
|------|--------|
| Pin cloudflared | **Done** — `infra/compose/compose.yaml` |
| Compose healthchecks (postgres, api, web) | Present; keep |
| cloudflared `restart: unless-stopped` | Present |
| Tunnel token in gitignored `.env` | Documented — [CLOUDFLARE-TUNNEL.md](./CLOUDFLARE-TUNNEL.md) |
| Pytest vs live Compose DB bleed | Known ops/test gap; not a hygiene blocker |
| Base-image CVE deep scan | **Deferred** — optional follow-up; not blocking W3 entry |

## Docs pins

- ADR index includes ADR-005 / ADR-006; Painted Time Maps reflected in roadmap + Quick Start
- USER-GUIDE / CLOUDFLARE-TUNNEL: update image tag reference to `2026.7.3`
- CHANGELOG Unreleased notes this hygiene exit

## Checklist

- [x] Pin Python, Node, Postgres, Nginx image versions (reviewed; no drift)
- [x] Audit FastAPI, SQLAlchemy, Alembic, Vite, React majors (spot check; keep)
- [x] Pin cloudflared (drop `:latest`)
- [ ] Review container base image CVEs — deferred (optional)
- [x] Update doc pins / record this pass
- [x] Record hygiene exit for W3 entry (this file)

## Operator note

After pulling this commit, recreate the tunnel connector once so it uses the pinned tag:

```powershell
docker compose -f infra/compose/compose.yaml --profile tunnel up -d --force-recreate cloudflared
```
