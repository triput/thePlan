# Manual checklist (Trish)

Standalone operator checklist for browser / CLI verification of shipped F1–F3 work.  
Canonical copy — tick boxes here. Feature delivery docs link here instead of duplicating lists.

**As of 2026-10-09:** tip on `cursor` `main` includes F3-W2 through `93dbbcb` (plus Move-to Space `0c36ee2`).  
Automated suites are green; this list is the remaining human gate before calling F1–F3 “done” in the paper trail.

---

## Setup

- [ ] Compose API (and web) up; household DB reachable
- [ ] `cd apps/api` → `alembic upgrade head` → at least **`023_schedule_outcome_provenance`** (implies F1 `020` + F2 `021` + F3 `022`/`023`)
- [ ] Web: signed in as yourself
- [ ] CLI: `theplan auth login` against the same API (for CLI rows below)

---

## F1 — Planning handoff

Delivery: [F1-HANDOFF.md](./F1-HANDOFF.md)

- [ ] `theplan handoff propose --file …` then `--format text` — tree matches JSON entities; propose JSON `payload` shows embedded duration/priority defaults
- [ ] Apply with a fresh UUID key; `theplan handoff receipt --idempotency-key …` matches apply JSON; second apply shows `replayed: true`
- [ ] Epic, project, or **task** detail in web shows **source refs** after a handoff / task-only graft that included `source_refs`
- [ ] Graft tasks under an existing section: host project `schedule_style` unchanged; new tasks respect handoff `schedule_policy`
- [ ] `theplan deps list|add|remove` round-trip against two real task IDs
- [ ] `theplan epics|projects|sections` list/get/create/patch against owned entities
- [ ] Outline re-import still **duplicates** (handoff idempotency does **not** apply to outline)

---

## F2 — Kanban

Delivery: [F2-KANBAN.md](./F2-KANBAN.md)

- [ ] Project view: toggle **Board**; columns Ready / In progress / Waiting / Done; WIP summary matches In progress + Waiting totals
- [ ] **Work** board: epic / project filters narrow cards; archived containers not offered in project picker; All / All = owner-wide (inbox + projects, no date filter)
- [ ] **Move to…** menu moves a card; CLI `theplan tasks get --id …` shows matching `workflow_state`, `board_column`, `board_revision`
- [ ] **Keyboard:** focus **Move to…** select → **Space** opens the dropdown (does **not** open task details) — fix `0c36ee2`; browser retest
- [ ] Drag within a column (insert before/after peer); drag to another column (Waiting prompts for note, then applies saved insert hints); drop on **Done** runs completion policy when parent has open children
- [ ] **Load more** on an open column and on **Done** when totals exceed page size
- [ ] Complete recurring task on board → toast “next occurrence”; card lands in **Ready**, not Done
- [ ] Move completed task to In progress → uncomplete + workflow in one step; list view shows same state
- [ ] **Roots only** toggle hides subtasks; column headers may still show API totals (known quirk)
- [ ] Today / Upcoming board: scheduled-but-not-due tasks still appear when blocks overlap the smart range
- [ ] Stale board: complete in one session → workflow with stale revision in another → **409** `BOARD_REVISION_CONFLICT`
- [ ] Default list/board hides tasks in archived project or epic; opening archived **project** detail still lists its tasks
- [ ] `theplan tasks workflow --id … --column waiting --expected-revision N --waiting-note "…"` then list with `--workflow waiting --board-order`

---

## F3 — Scheduler explanations

Delivery: [F3-SCHEDULER-EXPLANATIONS.md](./F3-SCHEDULER-EXPLANATIONS.md)

### Core (W1)

- [ ] **Update Schedule** on a mix of auto + manual/bundle tasks → run completes; manual/bundle show exclusion explanations
- [ ] Task with pinned blocks covering full estimate → “covered by pins”; replan does not add unpinned blocks for that task
- [ ] Dependent with unfinished blocker → **blocked** prerequisite; after blocker completes + replan → dependent can show **placed**
- [ ] Partial fit in horizon → **horizon exhausted**; past deadline with zero placement → **no suitable slot** / **deadline limit** as appropriate
- [ ] Task never replanned → **Why this schedule?** never-evaluated copy (no fabricated story)
- [ ] Change estimate or deadline after a run → stale badge + named categories on next panel load (no auto-replan)
- [ ] `theplan schedule explain --task-id …` JSON includes `human_summary` matching `summary_text`
- [ ] `theplan schedule runs list` / `get --id …` / `explanations --id …` match API pagination and owner scope
- [ ] Second user cannot read another owner’s run or explanation (**404**)

### W2 spot-checks

- [ ] Completed / trashed / archived (project or epic) → lifecycle exclusion copy; manual/bundle on **archived** project → lifecycle wins over style exclusion
- [ ] Dependency cycle → **`blocked_dependency_cycle`** (only cycle members; downstream is prerequisite-blocked)
- [ ] Deadline binding → **`unplaced_deadline_limit`** when applicable
- [ ] Placed task after replan: explanation has **`algorithm_version`: `f3-w2`** and **`placement_facts`**

---

## Not on this gate (parked)

Do not block F1–F3 close on these; they live elsewhere:

| Item | Where |
|------|--------|
| Prerequisite explanations show UUIDs (want titles) | F3 backlog — final polish pass |
| Overbooked copy mentions deadlines when blocker is a prerequisite | F3 backlog — final polish pass |
| `priority_ups` / `time_map_overrides` stale compare | F3 W3 |
| Schedule-run summary web UI | F3 W3 / later |
| Full F2-D a11y/touch matrix beyond Move-to Space | F2 known limitations |
| DEF-028 calendar mirror delete recovery | Deferred |

---

## Sign-off

When a section is done, note date + “ok” here (optional):

| Wave | Done | Notes |
|------|------|-------|
| Setup | | |
| F1 | | |
| F2 | | |
| F3 | | |
