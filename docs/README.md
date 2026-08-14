# thePlan — Documentation Index

**Product name of record:** thePlan. Personal execution tool alongside the Synesis/Phronesis suite. Use neutral identifiers in code (`apps/api`, not branded package names).

## Terminology

| Term | Meaning |
|------|---------|
| **Wave tags** (MVP, W1.5, W1.6, W2, W3) | Delivery waves — when a capability ships on the roadmap |
| **P1–P4** | Task priority only (enum, UI, UPS scoring) — not delivery waves |

See [07-wave-roadmap.md](./07-wave-roadmap.md) for wave sequencing and [03-feature-catalog.md](./03-feature-catalog.md) for per-feature wave tags.

## Wave 1 Product Doc Baseline

Product documentation package written for Wave 1 (MVP); kept as the baseline for W1.5+ updates.

| Document | Description |
|----------|-------------|
| [01-product-vision.md](./01-product-vision.md) | Product principles, scope, and non-goals |
| [02-functional-spec.md](./02-functional-spec.md) | Screens, entities, behaviors, parser rules, W2 scheduler semantics |
| [03-feature-catalog.md](./03-feature-catalog.md) | Todoist + SkedPal feature harvest with wave tags |
| [04-data-schema.md](./04-data-schema.md) | Tables, enums, indexes, conventions |
| [05-api-contract.md](./05-api-contract.md) | Versioned REST API for MVP resources |
| [06-mvp-backlog.md](./06-mvp-backlog.md) | Wave 1 (MVP) user stories and exit criteria |
| [07-wave-roadmap.md](./07-wave-roadmap.md) | MVP → W1.5 → W1.6 → W2a → W2b → W2c (parked) ↔ W3 / W3+ / W4 |
| [08-color-palette.md](./08-color-palette.md) | Entity presets + status accents (Synesis/Phronesis-aligned) |
| [WAVE-1-EXIT.md](./WAVE-1-EXIT.md) | Wave 1 exit record — delivered epics, criteria met, known gaps |
| [WAVE-1.5-EXIT.md](./WAVE-1.5-EXIT.md) | Wave 1.5 exit record — auth, recurrence, reminders, ops, closeout UI |
| [DEFECTS.md](./DEFECTS.md) | Open product defects (non-wave-blocker) |
| [HYGIENE-W1.5-QUICKSCAN.md](./HYGIENE-W1.5-QUICKSCAN.md) | W1.5 dependency hygiene quick scan (gate exited) |
| [HYGIENE-W2-QUICKSCAN.md](./HYGIENE-W2-QUICKSCAN.md) | W2 dependency hygiene quick scan (gate exited) |
| [HYGIENE-W3.md](./HYGIENE-W3.md) | W3 entry full hygiene (gate exited 2026-08-12) |
| [USER-GUIDE.md](./USER-GUIDE.md) | Operator guide — run stack, sign in, household admin, tasks, calendar |
| [guides/QUICK-START.md](./guides/QUICK-START.md) | Guest quick start — live instance UI tour (no ops/setup) |
| [CLOUDFLARE-TUNNEL.md](./CLOUDFLARE-TUNNEL.md) | Optional Cloudflare Tunnel (+ Access) for remote access |
| [MICROSOFT-CALENDAR.md](./MICROSOFT-CALENDAR.md) | Microsoft Calendar Entra app setup (W3 Slice 2) |
| [CHANGELOG.md](../CHANGELOG.md) | Release history (root) |

**Status:** Wave 1 exited **2026-08-10**. Wave 1.5 exited **2026-08-10** ([WAVE-1.5-EXIT.md](./WAVE-1.5-EXIT.md)); W1.6 shipped. **W2a/W2b core complete.** **W2c parked.** **W3 Slice 1–2 shipped** (Account + Microsoft Calendar); **next: Slice 3 Tauri** — [07-wave-roadmap.md](./07-wave-roadmap.md).

## SQL & ADRs

| Path | Description |
|------|-------------|
| [sql/001_baseline.sql](./sql/001_baseline.sql) | Executable PostgreSQL baseline DDL |
| [adr/ADR-001-tech-stack.md](./adr/ADR-001-tech-stack.md) | FastAPI, Vite+React, Postgres, Docker Compose |
| [adr/ADR-002-single-user.md](./adr/ADR-002-single-user.md) | Personal single-user tenancy |
| [adr/ADR-003-local-first-auth.md](./adr/ADR-003-local-first-auth.md) | Local-only MVP auth; login in W1.5 |
| [adr/ADR-004-container-runtime.md](./adr/ADR-004-container-runtime.md) | Docker Desktop default; OCI-portable Compose |
| [adr/ADR-005-scheduler-decoupling.md](./adr/ADR-005-scheduler-decoupling.md) | CRUD never waits on scheduler |
| [adr/ADR-006-fuzzy-scheduling.md](./adr/ADR-006-fuzzy-scheduling.md) | v1 fuzzy fit / Update Schedule replan contract |
| [adr/ADR-007-account-self-service.md](./adr/ADR-007-account-self-service.md) | W3 Slice 1 — self-service + forced password change |
| [adr/ADR-008-microsoft-calendar.md](./adr/ADR-008-microsoft-calendar.md) | W3 Slice 2 — Microsoft Graph calendar sync |

## Legacy

| Path | Description |
|------|-------------|
| [_legacy/](./_legacy/) | Early combined draft superseded by this package |
