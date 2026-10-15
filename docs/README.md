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
| [09-technical-architecture.md](./09-technical-architecture.md) | **Living** system map + diagrams (topology, layers, pipelines) — Round 4 catch-up 2026-08-27 |
| [REFACTOR-ASSESSMENT.md](./REFACTOR-ASSESSMENT.md) | DEF-011 refactor inventory + ordered cut list (assessment only; greenlight before code moves) |
| [WAVE-1-EXIT.md](./WAVE-1-EXIT.md) | Wave 1 exit record — delivered epics, criteria met, known gaps |
| [WAVE-1.5-EXIT.md](./WAVE-1.5-EXIT.md) | Wave 1.5 exit record — auth, recurrence, reminders, ops, closeout UI |
| [DEFECTS.md](./DEFECTS.md) | Open product defects (non-wave-blocker) |
| [HYGIENE-W1.5-QUICKSCAN.md](./HYGIENE-W1.5-QUICKSCAN.md) | W1.5 dependency hygiene quick scan (gate exited) |
| [HYGIENE-W2-QUICKSCAN.md](./HYGIENE-W2-QUICKSCAN.md) | W2 dependency hygiene quick scan (gate exited) |
| [HYGIENE-W3.md](./HYGIENE-W3.md) | W3 entry full hygiene (gate exited 2026-08-12) |
| [HYGIENE-R4-QUICKSCAN.md](./HYGIENE-R4-QUICKSCAN.md) | Round 4 dependency hygiene quick scan (2026-08-27) |
| [HYGIENE-0.7.md](./HYGIENE-0.7.md) | **0.7.0** Scheduling/Settings hygiene entry (open 2026-10-12; gates S1) |
| [USER-GUIDE.md](./USER-GUIDE.md) | Operator guide — Compose, auth/recovery CLI, batch & calendar, Assist, trash/archive |
| [guides/QUICK-START.md](./guides/QUICK-START.md) | Guest quick start — live instance UI tour (no ops/setup) |
| [guides/AGENT-COURSE-IMPORT.md](./guides/AGENT-COURSE-IMPORT.md) | Julie-facing course import through the CLI; reusable workflow, verification, and handoff template |
| [guides/COLLABORATIVE-PLANNING-WORKFLOW.md](./guides/COLLABORATIVE-PLANNING-WORKFLOW.md) | Approved baseline for human-led planning, decision capture, reconciliation, and evidence-based delivery; open to refinement |
| [CLOUDFLARE-TUNNEL.md](./CLOUDFLARE-TUNNEL.md) | Optional Cloudflare Tunnel (+ Access) for remote access |
| [MICROSOFT-CALENDAR.md](./MICROSOFT-CALENDAR.md) | Microsoft Calendar Entra app setup (W3 Slice 2) |
| [DESKTOP.md](./DESKTOP.md) | Tauri desktop prove-it operator note (W3 Slice 3) |
| [SLM-ASSIST.md](./SLM-ASSIST.md) | Local SLM Assist operator note (W3+; ADR-010) |
| [CHANGELOG.md](../CHANGELOG.md) | Release history (root) |

**Status:** Wave 1 exited **2026-08-10**. Wave 1.5 exited **2026-08-10** ([WAVE-1.5-EXIT.md](./WAVE-1.5-EXIT.md)); W1.6 shipped. **W2a/W2b core complete.** **W2c parked.** **W3 Slice 1–3 shipped.** **W3+ SLM Assist + Theme F outline ingest shipped** — [ADR-010](./adr/ADR-010-slm-assist.md), [ADR-011](./adr/ADR-011-templates-outline-ingest.md) — system map [09-technical-architecture.md](./09-technical-architecture.md) — [07-wave-roadmap.md](./07-wave-roadmap.md).

## Product exploration

| Document | Description |
|----------|-------------|
| [THEPLAN-PRODUCT-EXPLORATION.md](./THEPLAN-PRODUCT-EXPLORATION.md) | Commercialization, self-hosted Docker distribution, and optional bundled local Assist; exploration only, outside current 0.7 delivery scope |

## Portfolio & interview prep

| Document | Description |
|----------|-------------|
| [portfolio/THEPLAN-SPEAKABLE-OVERVIEW.md](../../TrishPutnam.com/docs/portfolio/THEPLAN-SPEAKABLE-OVERVIEW.md) | Speakable technical map — architecture, AI/Julie, scheduling truth, do-not-claim |
| [portfolio/NOTES-theplan-ai-crew-collaboration.md](../../TrishPutnam.com/docs/portfolio/NOTES-theplan-ai-crew-collaboration.md) | Reed voice essay — designer/TPM/DoD with AI crew; Julie-led |

Refresh both before any public show-and-tell (living footnotes / §10 checklists).

## Scheduling / Settings pass (next version)

| Document | Description |
|----------|-------------|
| [SCHEDULING-SETTINGS-SPEC.md](./SCHEDULING-SETTINGS-SPEC.md) | Approved product contract (v1.4.3) — **0.7.0** Scheduling/Settings pass; About/version; acceptance matrix |
| [redesign/SCHEDULING-SETTINGS-DEX-DISCOVERY-REVIEW-2026-10-12.md](./redesign/SCHEDULING-SETTINGS-DEX-DISCOVERY-REVIEW-2026-10-12.md) | Dex discovery decision ledger (v1.16) — rationale and fixtures |
| [delivery/0.7-S2-CUTOVER.md](./delivery/0.7-S2-CUTOVER.md) | S2 placer cutover kick packet — slices V1–V7, acceptance, Dex gates |
| [delivery/0.7-S2-V3-DISCOVERY.md](./delivery/0.7-S2-V3-DISCOVERY.md) | **S2-V3 Discovery Open** — Working/General, divergence, window math (coding truth after Discovery exits) |

Traces [DEF-032–033, DEF-036–041](./DEFECTS.md). Hygiene entry open — [HYGIENE-0.7.md](./HYGIENE-0.7.md); gates S1. S2-V1/V2 on cursor; **S2-V3 Discovery in progress** — not Closed/shipped.

## Dev

| Document | Description |
|----------|-------------|
| [CLI.md](./CLI.md) | Agent CLI — install, env vars, JSON/exit codes, M1 reset-password, M2 auth/tasks/assist/status |
| [dev/FILE-HEADERS.md](./dev/FILE-HEADERS.md) | Module/file header convention (Python docstrings + TS/TSX info blocks) |

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
| [adr/ADR-009-tauri-desktop.md](./adr/ADR-009-tauri-desktop.md) | W3 Slice 3 — Tauri prove-it shell + API sidecar |
| [adr/ADR-010-slm-assist.md](./adr/ADR-010-slm-assist.md) | W3+ — local SLM Assist (Ollama; review→confirm→apply) — Accepted |
| [adr/ADR-011-templates-outline-ingest.md](./adr/ADR-011-templates-outline-ingest.md) | W3+ Theme F — outline ingest / `coursera_specialization` pack — Accepted |
| [OUTLINE-INGEST.md](./OUTLINE-INGEST.md) | Theme F operator note |

## Legacy

| Path | Description |
|------|-------------|
| [_legacy/](./_legacy/) | Early combined draft superseded by this package |
