# ADR-012: Calendar bundles (manual aggregate block)

**Status:** Accepted (Round 2 smash thin slice)  
**Date:** 2026-08-27  
**Context:** [DEF-019](../DEFECTS.md#def-019--calendar-bundles-for-micro-task-coursework-aggregate-block-keep-task-rows) — Coursera-style micro-tasks clutter the calendar. Operator wants **one** calendar block for a study session while members stay individual in lists/detail. ADR-006 stays replan-focused; this ADR locks the **manual** thin slice only. Do **not** invent knockout auto-replan here.

## Decision summary

Ship a **manual** path: operator selects tasks (or an existing parent) → **Block as bundle** → **one** `scheduled_blocks` row on the calendar, linked to member task ids (or parent + descendants). Members remain normal task rows. Lifecycle is gray + easy delete when members finish or leave the set; **Release / remove** clears the aggregate. Persistence is the cheapest workable option below.

## Locked decisions

### Product shape

| Piece | Lock |
|-------|------|
| **Calendar face** | **One** block per bundle — not N stripes for N members |
| **Task views** | Members stay individual in lists / detail (complete, edit, deps, labels unchanged) |
| **Membership** | Explicit member task ids **or** parent + descendants resolved at create |
| **Create path** | **Manual first** — select tasks or existing parent → **Block as bundle** |
| **Duration** | Synthetic/parent duration **or** sum of member estimates (operator-facing create chooses one rule; Jules implements the cheaper of the two that matches UI) |
| **Auto-replan** | **Out** — no knockout / scoped bundle materialization on Update Schedule in this smash |

### Persistence (cheapest that works)

| Choice | Verdict |
|--------|---------|
| **JSONB on `scheduled_blocks`** | **Locked** — one nullable column (e.g. `bundle_meta JSONB`); no join table |
| Thin `bundle_blocks` table | Deferred — cleaner FKs later if membership churn or querying demands it |

**Shape (illustrative):**

```json
{
  "kind": "bundle",
  "member_task_ids": ["…", "…"],
  "source": "selection" | "parent_subtree"
}
```

**Anchor `task_id`:** Keep existing `scheduled_blocks.task_id NOT NULL`. Use the **parent** when the operator picks an existing parent; otherwise use a designated **anchor member** (e.g. first selected). Full membership lives in `bundle_meta`, not as extra block rows.

**Detecting aggregates:** `bundle_meta IS NOT NULL` (and `kind = bundle`) — calendar renders one face; capacity tools treat the row as a normal block unless noted below.

### Lifecycle

| Event | Behavior |
|-------|----------|
| Member completed or moved/rescheduled out of membership | Aggregate **grays** and becomes **easy to delete** |
| All members completed | Gray + easy delete (dissolve-by-empty optional polish, not required) |
| **Release / remove** | Clears the aggregate block (delete the one `scheduled_blocks` row); does **not** delete member tasks |
| Partial complete | See **Addendum — Round 4 Wave A** (partial gray + shrink-on-partial) |

### Relation to `schedule_style.bundle`

Existing enum value still means **exclude from Update Schedule auto-placement** ([ADR-006](./ADR-006-fuzzy-scheduling.md), [DEF-014](../DEFECTS.md#def-014--exclude-unplanned--backlog-tasks-from-update-schedule)). This smash does **not** require flipping member styles; optional mark/clear is implementation detail, not a new product surface. Calendar-bundle UX ≠ W2c scoped auto-replan.

### DEF-020 capacity tools

[DEF-020](../DEFECTS.md#def-020--calendar-capacity-release-early-complete--bulk-clear) **release-remainder** and **clear-unpinned** should **eventually** apply to aggregate blocks the same as ordinary blocks (truncate/delete the one row). Wire when Jules ships the slice — do not invent special bundle capacity semantics in this ADR.

## Explicitly deferred

- Auto scoped bundle replan (project/epic session knockout → blocks)
- Auto-dissolve / expand-on-uncomplete beyond gray + shrink-on-complete (see addendum)
- Fairness interactions ([DEF-017](../DEFECTS.md#def-017--cross-project--epic-scheduling-fairness-day-domination))
- Separate `bundle_blocks` join table (unless JSONB proves insufficient)
- Replacing per-task tracking or inventing a second task entity

## Consequences

- ADR-006 replan contract unchanged — still **no** bundle materialization on Update Schedule.
- One Alembic column + API/UI for manual create and gray/remove is the smash budget.
- Accept gates Jules implementation; DEF-019 stays open until code ships.

## Related

- [DEF-019](../DEFECTS.md#def-019--calendar-bundles-for-micro-task-coursework-aggregate-block-keep-task-rows)  
- [DEF-020](../DEFECTS.md#def-020--calendar-capacity-release-early-complete--bulk-clear)  
- [ADR-006-fuzzy-scheduling.md](./ADR-006-fuzzy-scheduling.md)  
- [04-data-schema.md](../04-data-schema.md) — `scheduled_blocks`

---

## Addendum — Round 4 Wave A (partial gray + shrink-on-partial)

**Date:** 2026-08-27  
**Status:** Accepted (follow-on thin; still no auto-replan)

Supersedes the smash lock that deferred shrink-on-partial and the “gray only when all done” reading of the incomplete mid-state.

| Event | Behavior (updated) |
|-------|--------------------|
| **Any** live member completed | Aggregate **grays** (`bundle_inactive=true`). Still easy to delete; gray is calendar styling, not a delete gate. |
| All members completed / trashed / missing | Gray + easy delete (unchanged) |
| Partial complete (remaining incomplete members) | **Shrink** block `end_time` to start + sum of remaining live incomplete members’ `estimated_duration_minutes`, floored at 15 minutes (`_MIN_BUNDLE_MINUTES`). Only shortens; never expands on complete. |
| Release / remove | Unchanged — delete the one `scheduled_blocks` row; members stay |

**Explicitly still deferred:** auto-dissolve, expand-on-uncomplete, knockout auto-replan, membership churn sync beyond gray/shrink on complete.