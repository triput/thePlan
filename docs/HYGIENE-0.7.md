# Dependency Hygiene — 0.7.0 Entry (Full Pass)

**Date:** 2026-10-12  
**Mode:** Full hygiene wave (not a quick scan)  
**Result:** **Exit / pass** — 2026-10-12 (Trish authorized exit with remaining majors **held**)  
**Recorded for:** **0.7.0 Scheduling/Settings** train after R3 / F-series freeze; **S1** unblocked for planning/implementation after [0.7-S0-MIGRATION-CONTRACT.md](./delivery/0.7-S0-MIGRATION-CONTRACT.md)  
**Hygiene tip SHA (start):** `ef838bc5f71e29e30d1ca17feda11088c8cedfd9` (`main` @ `cursor/main`)  
**Compose smoke docs SHA:** `5d32ec8bdc7fc4d6f6893efbeb3adc722b8908a7`  
**Hygiene exit SHA:** `2dbe3214fd0c376a7c6a4565d9cd4b70eb354bc3`  
**Product locks:** Dex discovery **v1.16**; [SCHEDULING-SETTINGS-SPEC.md](./SCHEDULING-SETTINGS-SPEC.md) **v1.4.3**  
**Basis:** [HYGIENE-W3.md](./HYGIENE-W3.md) + [HYGIENE-R4-QUICKSCAN.md](./HYGIENE-R4-QUICKSCAN.md) + live pin / outdated audit 2026-10-12

## Applied this exit (2026-10-12)

| Item | Evidence |
|------|----------|
| Product version **0.7.0** | api / cli / web / desktop strings aligned (see Product version alignment) |
| Pydantic **2.14.x** reconcile | pins + venv + container import **2.14.1** — safe-batch + Compose smoke sections below |
| Safe web batch | React 19.3.0, Vite 8.3.4, RQ 5.104.2, oxlint, etc. — safe-batch test evidence |
| Compose smoke (no tunnel) | [Compose smoke](#compose-smoke-2026-10-12-no-tunnel) — tip `5d32ec8…` |

## Hold for this exit (explicit)

| Item | Status |
|------|--------|
| FastAPI / Starlette majors | **Hold** — dedicated review |
| SQLAlchemy **2.1** (+ Alembic with that plan) | **Hold** |
| TypeScript **7** | **Hold** — explicit greenlight only |
| Desktop `@tauri-apps/cli` → 2.12.x | **Hold** (optional) |
| cryptography / psycopg minors | **Hold** (optional; OAuth + DB smoke when scheduled) |
| Base-image CVE deep scan | Deferred (same as W3 / R4) |

## Scope

| In this wave | Out / deferred |
|--------------|----------------|
| Toolchain + container pin review | Blind major upgrades (need Trish greenlight) |
| api / web / cli / desktop dep inventory | Large S1 feature code (waits contract + no Trish objection) |
| Doc pins + CHANGELOG **[0.7.0]** section | Settings **About** UI (product: **S3**) |
| Product version strings → **0.7.0** | Single cross-app version source (follow-up below) |
| Safe batch + Compose smoke + **exit / pass** | Held majors / optional minors above |

## Toolchain pins

| Layer | Pin / observed | Action |
|-------|----------------|--------|
| API Docker image | `python:3.12-slim` | Keep |
| Local API venv | **`apps/api/.venv`** (created this wave if missing); host also **3.11.9** | Acceptable vs `requires-python` ≥3.11; Docker remains 3.12 — note host/venv drift |
| Web Docker build | `node:22-alpine` | Keep |
| Host Node / npm | **v26.8.1** / **12.2.0** | Fine for local Vite; Compose uses Node 22 |
| Postgres | `postgres:16-alpine` | Keep |
| Nginx runtime | `nginx:1.27-alpine` | Keep |
| cloudflared | `cloudflare/cloudflared:2026.7.3` | Keep (pinned W3; not `:latest`) |
| pgAdmin (tools profile) | `dpage/pgadmin4:8` | Keep |

## Package majors — inventory (2026-10-12)

**Safe batch applied 2026-10-12 (Trish authorized).** FastAPI/Starlette/SQLAlchemy majors still **Hold**. Confirm before Compose rebuild.

### API (`apps/api/requirements.txt` / `pyproject.toml`)

| Package | Pinned / installed | Latest (outdated) | Status |
|---------|--------------------|-------------------|--------|
| FastAPI | 0.115.6 | **0.143.0** | **Hold** — staged bump after Starlette compatibility check |
| Starlette | 0.41.3 | **1.7.0** (major) | **Hold** — FastAPI pin owns this; major is risky |
| SQLAlchemy | 2.0.51 | **2.1.4** (2.1 line) | **Hold** — dedicated review wave |
| Alembic | 1.14.0 | **1.20.0** | **Hold** — with SQLAlchemy plan |
| Pydantic | **2.14.1** | 2.14.1 | **Applied** — pin matches `apps/api/.venv` |
| pydantic_core | **2.50.1** | 2.50.1 | **Applied** — matches Pydantic 2.14.1 |
| pydantic-settings | **2.14.2** | **2.15.0** | **Applied** — 2.14 line with Pydantic 2.14 (not 2.15 jump) |
| typing-inspection | **0.4.4** | 0.4.4 | **Applied** — Pydantic 2.14.1 requires ≥0.4.4 |
| httpx | 0.28.1 | 0.28.1 | Keep |
| cryptography | 44.0.2 | **50.0.2** | Propose security-minded bump; test OAuth token encrypt/decrypt |
| uvicorn | 0.34.0 | **0.54.0** | Propose after FastAPI plan |
| psycopg / binary | 3.2.13 | **3.3.6** | Propose minor after smoke |
| pytest | 9.1.1 | (not flagged in first page) | Keep unless needed |

### CLI (`apps/cli/pyproject.toml`)

| Package | Range | Latest | Proposal |
|---------|-------|--------|----------|
| httpx | `>=0.27.0,<1` | 0.28.1 | Keep |

### Web (`apps/web/package.json`)

| Package | Range / installed | Latest | Status |
|---------|---------------------|--------|--------|
| React / React DOM | **19.3.0** | 19.3.0 | **Applied** |
| Vite | **8.3.4** | 8.3.4 | **Applied** |
| React Query | **5.104.2** | 5.104.2 | **Applied** |
| TypeScript | ~6.0.2 → **6.0.3** (lockfile) | **7.0.2** (major) | **Hold** — TS 7 needs explicit greenlight |
| @types/react / @types/react-dom | **19.3.0** | 19.3.0 | **Applied** |
| @types/node | ^24.13.3 | wanted 24.x / latest **26.x** | Keep on 24 line unless Node major story changes |
| oxlint | **1.87.0** | 1.87.0 | **Applied** |
| @vitejs/plugin-react | **6.1.2** | 6.1.2 | **Applied** |

### Desktop (`apps/desktop`)

| Package / crate | Current | Latest | Proposal |
|-----------------|---------|--------|----------|
| `@tauri-apps/cli` | 2.11.4 | **2.12.2** | Propose minor; smoke sidecar after |
| `tauri` / `tauri-build` (Cargo) | `2` | (semver range) | Spot-check on next desktop smoke; not blocking hygiene entry |

## Alembic head

| Item | Value |
|------|-------|
| Head revision | **`027_saved_filter_presentation`** (F7 saved views) |
| Pre-0.7.0 note | Scheduling/Settings schema work lands **after** hygiene exit + S0 migration contract — do not invent migrations in this entry turn |

## Product version alignment (this turn)

| Surface | Was | Now |
|---------|-----|-----|
| `apps/api/pyproject.toml` | 0.1.0 | **0.7.0** |
| `apps/api/app/main.py` FastAPI `version=` | 0.1.0 | **0.7.0** |
| `apps/cli/pyproject.toml` | 0.1.0 | **0.7.0** |
| `apps/cli/theplan/__init__.py` `__version__` | 0.1.0 | **0.7.0** |
| `apps/web/package.json` | 0.0.0 | **0.7.0** |
| `apps/desktop/package.json` | 0.1.0 | **0.7.0** |
| `apps/desktop/src-tauri/tauri.conf.json` | 0.1.0 | **0.7.0** |
| `apps/desktop/src-tauri/Cargo.toml` | 0.1.0 | **0.7.0** |

**Shared source of truth:** Not unified this turn (Python / npm / Cargo / Tauri). Literals synced to **0.7.0**.  
**Follow-up (hygiene or early S0):** pick one SoT (e.g. root `VERSION` or `apps/api` package metadata) and wire consumers; Settings **About** displays it in **S3** per product lock — do not build About UI in hygiene.

## Native / ops debt

| Item | Status |
|------|--------|
| cloudflared pin | Still good (`2026.7.3`) |
| Compose healthchecks | Present |
| Base-image CVE deep scan | **Deferred** (same as W3 / R4) |
| Pytest vs live Compose DB bleed | Known ops gap; not a hygiene blocker |
| API venv Python vs Docker 3.12 | **`apps/api/.venv`** for local pytest; Docker remains 3.12 |
| requirements.txt vs venv Pydantic drift | **Reconciled** 2026-10-12 (2.14.1 / 2.50.1 / settings 2.14.2) |

## Docs pins

- Spec: [SCHEDULING-SETTINGS-SPEC.md](./SCHEDULING-SETTINGS-SPEC.md) v1.4.3
- Dex ledger: [redesign/SCHEDULING-SETTINGS-DEX-DISCOVERY-REVIEW-2026-10-12.md](./redesign/SCHEDULING-SETTINGS-DEX-DISCOVERY-REVIEW-2026-10-12.md) v1.16
- Roadmap: [07-wave-roadmap.md](./07-wave-roadmap.md) — 0.7.0 hygiene exited; S1 via migration contract
- Changelog: root [CHANGELOG.md](../CHANGELOG.md) **[0.7.0]** Unreleased / in-progress
- Pre-S1 contract: [delivery/0.7-S0-MIGRATION-CONTRACT.md](./delivery/0.7-S0-MIGRATION-CONTRACT.md)
- Prior full pass: [HYGIENE-W3.md](./HYGIENE-W3.md); last quick scan: [HYGIENE-R4-QUICKSCAN.md](./HYGIENE-R4-QUICKSCAN.md)

## Checklist

- [x] Record hygiene tip SHA
- [x] Review Python / Node / Postgres / Nginx / cloudflared pins
- [x] Inventory api / web / cli / desktop outdated majors (document; no blind upgrades)
- [x] Align product version strings to **0.7.0**
- [x] Document shared-version follow-up + About → **S3**
- [x] Update CHANGELOG + roadmap note + docs index pin
- [x] Reconcile API requirements.txt vs venv (Pydantic) — **2026-10-12**
- [x] Safe upgrade batch (web + Pydantic) — Trish authorized **2026-10-12**
- [x] Compose smoke (api/web/scheduler rebuild, no tunnel) — **2026-10-12** / commit `5d32ec8`
- [x] Hygiene **exit / pass** — 2026-10-12; FastAPI/Starlette/SQLAlchemy 2.1 / TS7 / optional desktop+crypto/psycopg **held**
- [x] S1 planning/implementation — **unblocked** after [0.7-S0-MIGRATION-CONTRACT.md](./delivery/0.7-S0-MIGRATION-CONTRACT.md) (large S1 code waits Trish non-objection to contract)
- [ ] Desktop: `@tauri-apps/cli` → 2.12.x + sidecar smoke (**optional / held**)
- [ ] API optional minors: cryptography, psycopg (**optional / held**)
- [ ] Optional CVE deep scan — deferred

## Safe batch — test evidence (2026-10-12)

| Surface | Command | Result |
|---------|---------|--------|
| API venv | `apps/api/.venv` → `python -c "import pydantic; …"` | pydantic **2.14.1**, pydantic_core **2.50.1**, pydantic-settings **2.14.2** |
| API pytest | `pytest tests/test_settings.py tests/test_schedule_worker.py tests/test_e10_schema.py -q` | **32 passed** |
| Web unit | `npm test` (`apps/web`) | **57 passed** (21 suites) |
| Web build | `npm run build` | **green** (Vite 8.3.4) |

## Compose smoke (2026-10-12, no tunnel)

`docker compose -f infra/compose/compose.yaml up -d --build api web scheduler`

| Check | Result |
|-------|--------|
| `GET /health` | `{"status":"ok"}` |
| OpenAPI `info.version` | **0.7.0** |
| API container `pydantic.__version__` | **2.14.1** |
| `GET http://127.0.0.1:8080/` | **200** (login shell) |
| Assist `/api/v1/assist/status` unauthenticated | **401** `UNAUTHENTICATED` (expected) |

## Remaining (held — not exit blockers)

1. **Desktop CLI:** `@tauri-apps/cli` → 2.12.x + sidecar smoke (optional).
2. **API majors:** FastAPI / Starlette / SQLAlchemy 2.1 — dedicated review wave.
3. **TypeScript 7** — explicit greenlight only.
4. **Optional minors:** cryptography + psycopg with OAuth + DB smoke.
5. **CVE deep scan** — deferred.

## Operator note

Compose smoke for the Pydantic/web rebuild **ran 2026-10-12** (`up -d --build api web scheduler`, no tunnel). Re-run only if pins change again:

```powershell
docker compose -f infra/compose/compose.yaml up -d --build api web scheduler
```

Do **not** `--profile tunnel` on the shared SUPERNOVA token unless Trish asks.
