# ADR-001: Technology Stack

**Status:** Accepted  
**Date:** 2026-08-09  
**Context:** Wave 1 documentation — stack selection for personal productivity app.

## Decision

| Layer | Technology |
|-------|------------|
| Language (backend) | Python 3.12+ |
| API framework | FastAPI |
| ORM / migrations | SQLAlchemy 2, Alembic |
| Language (frontend) | TypeScript |
| Frontend tooling | Vite |
| UI framework | React |
| Database | PostgreSQL 16+ |
| Local runtime | Docker Compose |
| Desktop (later) | Tauri 2 |

**Rejected:** Flutter (mobile/desktop), Electron (weight), Next.js SSR (unnecessary for SPA + API split).

## Rationale

- **Python backend:** Operator's strongest language; excellent fit for scheduling math, NL parser, and calendar workers in P2.
- **FastAPI:** Async-capable, OpenAPI generation, fast CRUD iteration.
- **SQLAlchemy 2 + Alembic:** Mature Postgres ORM with migration discipline matching [001_baseline.sql](../sql/001_baseline.sql).
- **Vite + React + TypeScript:** Speed-first SPA with optimistic UI; TypeScript for maintainability; team conversant in JS ecosystem.
- **PostgreSQL:** Relational integrity for hierarchy, dependencies, and scheduling queries.
- **Tauri 2 (P3):** Lightweight desktop wrapping the same web UI; avoids Dart/Flutter second codebase.

## Consequences

- Domain logic lives exclusively in the API; web and Tauri are thin clients of [05-api-contract.md](../05-api-contract.md).
- Repo layout: `apps/api`, `apps/web`, `infra/compose`, `docs/`.
- OpenAPI spec generated from FastAPI for client codegen optional.
- No server-side rendering requirement; SEO is non-goal for personal app.

## Related

- [ADR-004-container-runtime.md](./ADR-004-container-runtime.md)
- [ADR-005-scheduler-decoupling.md](./ADR-005-scheduler-decoupling.md)
