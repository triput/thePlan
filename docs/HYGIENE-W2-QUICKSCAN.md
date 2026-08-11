# Dependency Hygiene — W2 Quick Scan

**Date:** 2026-08-10  
**Mode:** Quick scan (not full CVE audit)  
**Result:** **Exit / pass** — proceed with Wave 2a (Google Calendar)  
**Recorded for:** Wave 2 entry after [WAVE-1.5-EXIT.md](./WAVE-1.5-EXIT.md)  
**Basis:** Same-day pins as [HYGIENE-W1.5-QUICKSCAN.md](./HYGIENE-W1.5-QUICKSCAN.md); spot-checked for drift

## Toolchain pins

| Layer | Pin / observed | Notes |
|-------|----------------|-------|
| API Docker image | `python:3.12-slim` | Unchanged |
| Web Docker build | `node:22-alpine` | Unchanged |
| Postgres | `postgres:16-alpine` | Unchanged |
| Nginx runtime | `nginx:1.27-alpine` | Unchanged |
| cloudflared | `cloudflare/cloudflared:latest` | Ops profile only; pin later if desired |

## Package majors (spot check)

| Package | Pinned / installed | Action |
|---------|-------------------|--------|
| FastAPI | 0.115.6 | Keep |
| SQLAlchemy | 2.0.51 | Keep |
| Alembic | 1.14.0 | Keep |
| Pydantic | 2.13.4 | Keep |
| httpx | 0.28.1 | Keep — use for Google API |
| React / Vite | 19.2.x / 8.2.x | Keep |
| React Query | 5.101.x | Keep |

No forced majors to start W2a. **Expected additive deps when implementing OAuth:** token encryption (e.g. `cryptography` / Fernet) — confirm with Trish before installing.

## Container / docs

- W1.5 / W1.6 exit records current.
- Full CVE scan of base images still deferred (same as W1.5 follow-up).
- Pytest vs live Compose + `SESSION_HTTPS_ONLY` remains an ops/test gap (not a hygiene blocker).

## Checklist

- [x] Pin Python, Node, Postgres image versions (reviewed; no drift)
- [x] Audit FastAPI, SQLAlchemy, Alembic, Vite, React majors (spot check)
- [ ] Review container base image CVEs — deferred to next **full** hygiene wave
- [x] Update doc pins / record this quick-scan
- [x] Record quick-scan for W2 entry (this file)
