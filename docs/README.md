# thePlan — Documentation Index

**Product name of record:** thePlan. Personal execution tool alongside the Synesis/Phronesis suite. Use neutral identifiers in code (`apps/api`, not branded package names).

## Terminology

| Term | Meaning |
|------|---------|
| **Wave tags** (MVP, W1.5, W2, W3) | Delivery waves — when a capability ships on the roadmap |
| **P1–P4** | Task priority only (enum, UI, UPS scoring) — not delivery waves |

See [07-wave-roadmap.md](./07-wave-roadmap.md) for wave sequencing and [03-feature-catalog.md](./03-feature-catalog.md) for per-feature wave tags.

## Wave 1 Package

| Document | Description |
|----------|-------------|
| [01-product-vision.md](./01-product-vision.md) | Product principles, scope, and non-goals |
| [02-functional-spec.md](./02-functional-spec.md) | Screens, entities, behaviors, parser rules, W2 scheduler semantics |
| [03-feature-catalog.md](./03-feature-catalog.md) | Todoist + SkedPal feature harvest with wave tags |
| [04-data-schema.md](./04-data-schema.md) | Tables, enums, indexes, conventions |
| [05-api-contract.md](./05-api-contract.md) | Versioned REST API for MVP resources |
| [06-mvp-backlog.md](./06-mvp-backlog.md) | Wave 1 (MVP) user stories and exit criteria |
| [07-wave-roadmap.md](./07-wave-roadmap.md) | MVP → W1.5 → W2 → W3 roadmap |
| [08-color-palette.md](./08-color-palette.md) | Entity presets + status accents (Synesis/Phronesis-aligned) |

**Status:** Wave 0 scaffold complete (`apps/api`, `apps/web`, `infra/compose`). Next: Wave 1 MVP features against [06-mvp-backlog.md](./06-mvp-backlog.md).

## SQL & ADRs

| Path | Description |
|------|-------------|
| [sql/001_baseline.sql](./sql/001_baseline.sql) | Executable PostgreSQL baseline DDL |
| [adr/ADR-001-tech-stack.md](./adr/ADR-001-tech-stack.md) | FastAPI, Vite+React, Postgres, Docker Compose |
| [adr/ADR-002-single-user.md](./adr/ADR-002-single-user.md) | Personal single-user tenancy |
| [adr/ADR-003-local-first-auth.md](./adr/ADR-003-local-first-auth.md) | Local-only MVP auth; login in W1.5 |
| [adr/ADR-004-container-runtime.md](./adr/ADR-004-container-runtime.md) | Docker Desktop default; OCI-portable Compose |
| [adr/ADR-005-scheduler-decoupling.md](./adr/ADR-005-scheduler-decoupling.md) | CRUD never waits on scheduler |

## Legacy

| Path | Description |
|------|-------------|
| [_legacy/](./_legacy/) | Early combined draft superseded by this package |
