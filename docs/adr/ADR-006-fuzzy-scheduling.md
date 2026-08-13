# ADR-006: Fuzzy Scheduling Contract (v1 Update Schedule)

**Status:** Accepted  
**Date:** 2026-08-12  
**Context:** W2b Plans B and settings expansion shipped (2026-08-11). Schema fence locked. Fuzzy algorithm planning session approved — lock v1 worker behavior before implementing Update Schedule.

## Decision summary

Update Schedule is **explicit user action only** ([ADR-005](./ADR-005-scheduler-decoupling.md)). The auto-scheduler worker implements fuzzy fit using the locked decisions below. The [schema fence locked 2026-08-11](../07-wave-roadmap.md#phase-2b--scheduler-skedpal-triad) remains in force; this ADR adds the replan contract, candidate set, slack/urgency rules, relaxation ladder, slice/fit, and overbook semantics for v1.

## Locked decisions

### Replan contract

| Rule | v1 lock |
|------|---------|
| **Trigger** | Explicit **Update Schedule** only — no CRUD side effects, no background/cron replan |
| **Horizon** | `upcoming_horizon_days` from `user_settings` (default **7**), starting **now** in user timezone |
| **Existing blocks** | Wipe all **unpinned** `scheduled_blocks` that **intersect** the horizon and rewrite; leave **pinned** blocks and **past** (pre-horizon) blocks alone |
| **Output** | Formal `scheduled_blocks` rows only — **no** knockout/bundle materialization in v1 |

### Candidate set

- Open incomplete tasks with **remaining duration > 0**
- Include `standalone` and `time_block` schedule styles; **exclude `bundle` from auto-placement in v1** (manual blocks for bundle tasks remain OK)
- Honor `task_dependencies` **topological order** in v1

### Slack / urgency

- **Hard floor:** `deadline_at` when set — never schedule finish after it; else mark task **overbooked**
- **Slack DueDate for U:** first defined of `deadline_at` → `soft_target_at` → `due_at`; if none, treat as large slack (low urgency)
- **`due_at` alone** is a soft preference for ordering, **not** an immovable wall

### Soft constraint relaxation ladder

When fit fails, apply in order:

1. **Preferred Time Map tiers** — try **green** bands first, then **yellow**, then **neutral** workday slots minus **red** bands (painted tiers shipped 2026-08-12)
2. **`strict_mode` map** — when the bound map has `strict_mode=true`, **do not** spill to neutral workday; only green/yellow bands apply
3. **Auto-defer** (`auto_defer_enabled`) — if plan / `soft_target_at` is past or unreachable in horizon, **slide for scheduling behavior only**; **do not** rewrite stored `soft_target_at` in v1
4. **Never** move pins or external busy; **never** violate `deadline_at`; **never** auto-place into **red** bands

### Slice & fit

- Respect `estimated_duration`, min block length (MBL from task / user settings), and max block
- Prefer **contiguous** placement in a window over scattered minimum slices
- Insert `inter_block_buffer_minutes` between auto-scheduled blocks
- Do not shrink below MBL **except** leftover rule: if remainder **< MBL** and **> 0** as the last remnant, place one final smaller slice

### Overbook

- Unplaceable before `deadline_at` → `tasks.status = overbooked`; schedule run still **succeeds**
- Thin UX (toast / count) deferred to a later slice

### Schema fence (reaffirm)

| Decision | Lock |
|----------|------|
| Default schedule style | **Standalone** |
| MBL | From user/default unless task overrides |
| Auto-defer | **On by default** |
| Pins + GCal busy | **Immovable BUSY** |
| Time Map preference tiers | Green → yellow → never red **in force** for bound maps (Painted Time Maps shipped 2026-08-12) |

## Explicitly out of v1

- Bundle → block conversion on replan
- Rule inheritance parent → child
- Sidebar → calendar drag
- Background / cron replan
- Writing slid soft targets back to DB

## UPS

Priority queue ordering uses the existing UPS formula in [02-functional-spec.md §9](../02-functional-spec.md#ups-formula). Weights come from `user_settings.ups_weights`. **No formula change** in this ADR.

## Consequences

- **Shipped (2026-08-12):** Update Schedule thin — `POST /schedule/replan` (202), `GET /schedule/runs/{id}`, in-process worker, Calendar button with poll
- **Shipped (2026-08-12):** Painted Time Maps — `time_map_bands` tiers, Settings multi-band editor, calendar color overlay, scheduler tier placement for bound maps
- **Next:** Wave 3 core and/or **W2c** (scheduler polish & catch-all — Time Map overrides, rule inheritance, scoped bundles, soft-delete, sidebar drag-schedule, compose worker; order vs W3 flexible)
- CRUD remains decoupled from scheduler ([ADR-005](./ADR-005-scheduler-decoupling.md))
- Bundled tasks stay manual until a later slice; roadmap “knockout → blocks on replan” applies post–v1
- Functional spec §9 retains product-level SkedPal semantics; worker implementers treat this ADR as the v1 source of truth for fit and replan

## Related

- [ADR-005-scheduler-decoupling.md](./ADR-005-scheduler-decoupling.md) — CRUD never waits on scheduler; explicit Update Schedule trigger
- [02-functional-spec.md §9](../02-functional-spec.md#9-wave-2--skedpal-scheduler-behaviors-spec-level) — SkedPal triad, UPS formula, buffer
- [07-wave-roadmap.md](../07-wave-roadmap.md) — W2b slice plan; **W2c** polish & catch-all; schema fence (2026-08-11)
- [04-data-schema.md](../04-data-schema.md) — `user_settings`, tasks, `scheduled_blocks`, dependencies
- [05-api-contract.md](../05-api-contract.md) — `POST /schedule/replan`, `GET /schedule/runs/{id}`
