# Dependency Hygiene — 0.7.0 Entry (Full Pass)

**Date:** 2026-10-12  
**Mode:** Full hygiene wave (not a quick scan)  
**Result:** **Open / in progress** — inventory + product version alignment recorded; **no dependency upgrades applied this turn**  
**Recorded for:** **0.7.0 Scheduling/Settings** train after R3 / F-series freeze; gates **S1** scheduler feature work  
**Hygiene tip SHA (start):** `ef838bc5f71e29e30d1ca17feda11088c8cedfd9` (`main` @ `cursor/main`)  
**Product locks:** Dex discovery **v1.16**; [SCHEDULING-SETTINGS-SPEC.md](./SCHEDULING-SETTINGS-SPEC.md) **v1.4.3**  
**Basis:** [HYGIENE-W3.md](./HYGIENE-W3.md) + [HYGIENE-R4-QUICKSCAN.md](./HYGIENE-R4-QUICKSCAN.md) + live pin / outdated audit 2026-10-12

## Scope

| In this wave | Out / deferred |
|--------------|----------------|
| Toolchain + container pin review | Blind major upgrades (need Trish greenlight) |
| api / web / cli / desktop dep inventory | S1+ Scheduling/Settings feature code |
| Doc pins + CHANGELOG **[0.7.0]** section | Settings **About** UI (product: **S3**) |
| Product version strings → **0.7.0** | Single cross-app version source (follow-up below) |
| Record proposed upgrade set for Trish | Compose rebuild / tunnel recreate (ask first) |

## Toolchain pins

| Layer | Pin / observed | Action |
|-------|----------------|--------|
| API Docker image | `python:3.12-slim` | Keep |
| Local API venv | Python **3.14.5** (`.venv`); host also **3.11.9** | Acceptable vs `requires-python` ≥3.11; Docker remains 3.12 — note host/venv drift |
| Web Docker build | `node:22-alpine` | Keep |
| Host Node / npm | **v26.8.1** / **12.2.0** | Fine for local Vite; Compose uses Node 22 |
| Postgres | `postgres:16-alpine` | Keep |
| Nginx runtime | `nginx:1.27-alpine` | Keep |
| cloudflared | `cloudflare/cloudflared:2026.7.3` | Keep (pinned W3; not `:latest`) |
| pgAdmin (tools profile) | `dpage/pgadmin4:8` | Keep |

## Package majors — inventory (2026-10-12)

**No installs / bumps applied.** Confirm with Trish before any non-trivial upgrade wave or Compose rebuild.

### API (`apps/api/requirements.txt` / `pyproject.toml`)

| Package | Pinned / installed | Latest (outdated) | Proposal |
|---------|--------------------|-------------------|----------|
| FastAPI | 0.115.6 | **0.143.0** | Propose staged bump after Starlette compatibility check — **do not jump blind** |
| Starlette | 0.41.3 | **1.7.0** (major) | **Hold** — FastAPI pin owns this; major is risky |
| SQLAlchemy | 2.0.51 | **2.1.4** (2.1 line) | Propose dedicated review wave; not a drive-by |
| Alembic | 1.14.0 | **1.20.0** | Propose minor/major with SQLAlchemy plan |
| Pydantic | pin 2.13.4 / venv **2.14.0** | 2.14.1 | **Drift:** venv ahead of requirements — reconcile pin vs install before upgrades |
| pydantic-settings | 2.7.0 | **2.15.0** | Propose with Pydantic reconcile |
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

| Package | Range / current | Wanted / latest | Proposal |
|---------|-----------------|-----------------|----------|
| React / React DOM | ^19.2.8 → 19.2.8 | **19.3.0** | Safe-ish patch/minor within 19 — propose with web test suite |
| Vite | ^8.2.0 → 8.2.1 | **8.3.4** | Propose minor |
| React Query | ^5.101.4 | **5.104.2** | Propose minor |
| TypeScript | ~6.0.2 → 6.0.3 | **7.0.2** (major) | **Hold** — TS 7 needs explicit greenlight |
| @types/node | ^24.13.3 | wanted 24.x / latest **26.x** | Keep on 24 line unless Node major story changes |
| oxlint | ^1.75.0 → 1.78.0 | **1.87.0** | Propose minor |
| @vitejs/plugin-react | ^6.0.4 → 6.0.5 | **6.1.2** | Propose with Vite |

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
| API venv Python 3.14 vs Docker 3.12 | Documented; prefer aligning local venv to 3.12 when convenient |
| requirements.txt vs venv Pydantic drift | Reconcile before any FastAPI/Pydantic bump |

## Docs pins

- Spec: [SCHEDULING-SETTINGS-SPEC.md](./SCHEDULING-SETTINGS-SPEC.md) v1.4.3
- Dex ledger: [redesign/SCHEDULING-SETTINGS-DEX-DISCOVERY-REVIEW-2026-10-12.md](./redesign/SCHEDULING-SETTINGS-DEX-DISCOVERY-REVIEW-2026-10-12.md) v1.16
- Roadmap: [07-wave-roadmap.md](./07-wave-roadmap.md) — 0.7.0 train after hygiene
- Changelog: root [CHANGELOG.md](../CHANGELOG.md) **[0.7.0]** Unreleased / in-progress
- Prior full pass: [HYGIENE-W3.md](./HYGIENE-W3.md); last quick scan: [HYGIENE-R4-QUICKSCAN.md](./HYGIENE-R4-QUICKSCAN.md)

## Checklist

- [x] Record hygiene tip SHA
- [x] Review Python / Node / Postgres / Nginx / cloudflared pins
- [x] Inventory api / web / cli / desktop outdated majors (document; no blind upgrades)
- [x] Align product version strings to **0.7.0**
- [x] Document shared-version follow-up + About → **S3**
- [x] Update CHANGELOG + roadmap note + docs index pin
- [ ] Reconcile API requirements.txt vs venv (Pydantic) — next hygiene action
- [ ] Proposed safe upgrade batch (Trish approve) — see below
- [ ] Optional CVE deep scan — deferred
- [ ] Hygiene **exit / pass** — after approved upgrades (or explicit keep-all) + smoke
- [ ] S1 feature work — **blocked** until hygiene exit

## Proposed next hygiene actions (for Trish)

1. **Reconcile pins:** freeze `pydantic` / `pydantic_core` in `requirements.txt` to match intentional install (or reinstall from pins).
2. **Safe web batch (low drama):** React 19.3.x, Vite 8.3.x, React Query 5.104.x, oxlint, `@vitejs/plugin-react` — then `npm test` + `npm run build`.
3. **Desktop CLI:** `@tauri-apps/cli` → 2.12.x + sidecar smoke (optional same day).
4. **API — hold FastAPI/Starlette/SQLAlchemy 2.1** until a dedicated review; optionally schedule cryptography + psycopg minor with OAuth + DB smoke.
5. **Exit criteria:** checklist complete, no forced majors without greenlight, tip commit on `cursor` when Trish asks to push.

## Operator note

No pin mutations this turn — **no** Compose recreate required for hygiene entry. After any approved upgrade wave:

```powershell
docker compose -f infra/compose/compose.yaml up -d --build api web
```

Do **not** `--profile tunnel` on the shared SUPERNOVA token unless Trish asks.
