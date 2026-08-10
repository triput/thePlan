# ADR-005: Scheduler Decoupling

**Status:** Accepted  
**Date:** 2026-08-09  
**Context:** Architecture boundary between CRUD API and P2 auto-scheduling engine.

## Decision

**CRUD never waits on the scheduler.**

Task management API endpoints (create, update, complete, move, delete) return immediately without invoking the scheduling pipeline. The auto-scheduler runs as a separate async worker process triggered explicitly (Update Schedule in P2) or on a background schedule — never on the critical path of user mutations.

## Rationale

- **Speed-first principle:** Sub-100ms perceived interaction requires that a replan spanning hundreds of tasks cannot block a checkbox click.
- **SkedPal model:** "Update Schedule" is an explicit user action, not an implicit side effect of every edit.
- **Failure isolation:** Scheduler errors (overbook, calendar sync failure) must not roll back or delay task CRUD.
- **MVP clarity:** MVP has no scheduler at all; manual blocks and due dates are direct CRUD. Decoupling prevents accidental coupling during Wave 2–3 implementation.

## Architecture

```
┌─────────────┐     CRUD (sync)      ┌──────────────┐
│  Web/Tauri  │ ──────────────────►  │   FastAPI    │
│   Client    │ ◄──────────────────  │   CRUD API   │
└─────────────┘                      └──────┬───────┘
                                            │
                                            ▼
                                     ┌──────────────┐
                                     │  PostgreSQL  │
                                     └──────┬───────┘
                                            │
                    Schedule trigger        │ read/write
                    (P2: POST /schedule/replan)
                                            ▼
                                     ┌──────────────┐
                                     │  Scheduler   │
                                     │   Worker     │
                                     └──────┬───────┘
                                            │
                                            ▼
                                     ┌──────────────┐
                                     │ Google Cal   │ (P2)
                                     └──────────────┘
```

## Rules

1. **MVP:** No scheduler worker. `scheduled_blocks` created only via CRUD API (manual placement).
2. **P2:** Worker reads tasks, focus_windows, dependencies, external events; writes `scheduled_blocks` and `schedule_runs` audit rows.
3. **Pinned blocks:** Worker treats `is_pinned = TRUE` as immovable BUSY.
4. **Overbook:** Worker sets `tasks.status = overbooked`; does not fail the run.
5. **Client refresh:** After replan completes, client refetches calendar/blocks (WebSocket optional).
6. **No CRUD side effects:** Creating a task does not auto-schedule it. Changing due_at does not trigger replan unless user requests Update Schedule.

## Performance Contract

- CRUD p95 < 50ms single-entity write on LAN
- Scheduler run duration unbounded; progress via `schedule_runs` status
- Client optimistic UI for CRUD; calendar may show stale blocks until replan completes (acceptable with explicit Update Schedule UX)

## Consequences

- Wave 2 API implementation must not import scheduler modules in CRUD handlers.
- P2 adds separate worker entrypoint (e.g. `python -m scheduler.worker` or FastAPI background task queue — but never inline in request handler).
- [05-api-contract.md](../05-api-contract.md) `POST /schedule/replan` is async-accept (202) with poll or WebSocket completion.

## Related

- [02-functional-spec.md](../02-functional-spec.md) §9 — scheduling pipeline
- [ADR-001-tech-stack.md](./ADR-001-tech-stack.md)
