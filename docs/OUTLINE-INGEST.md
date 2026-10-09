# Outline ingest (Theme F)

Operator-owned curriculum JSON → Epic / Project / Section / Task tree.  
ADR: [ADR-011](./adr/ADR-011-templates-outline-ingest.md). Golden fixture: [`testdata/outlines/`](../testdata/outlines/).

## What it is

- Built-in template packs: `coursera_specialization` (Coursera labeling) and `hierarchy_v1` (neutral alias — **same mapper**)
- API: `POST /api/v1/outlines/propose` then `POST /api/v1/outlines/apply`
- UI: **Outline** button (next to Assist) — paste or upload `.json`, review, approve
- **No** Coursera login, scrape, or progress sync inside thePlan

## Mapping

| Outline | thePlan |
|---------|---------|
| certificate | Epic |
| course | Project (under epic) |
| module | Section |
| task | Task + labels from `task_type` (+ `optional` when flagged) |

Durations come from `duration_minutes`. Optional items are included by default; check **Skip optional** on propose to drop them.

## How to import your specialization

1. Obtain a curriculum JSON in the fixture shape (ChatGPT Coursera plugin, DevTools save, hand-built — outside thePlan). Start from [`blank_hierarchy_v1.json`](../testdata/outlines/blank_hierarchy_v1.json) for non-Coursera bulk adds.
2. Open **Outline** → pick template (`coursera_specialization` or `hierarchy_v1`) → paste or choose the file.
3. Propose → skim/edit/remove rows → Approve.
4. After apply, thePlan opens the new epic (expanded). **Courses are projects** under that epic in the sidebar; **modules are sections** inside each course (visible in the epic’s grouped task list, or open a course for the sections bar).
5. Expect one epic, N projects, modules as sections, and many tasks (IBM RAG fixture ≈ 417 tasks). Large applies can take a moment.

Re-importing the same outline **will duplicate** entities in prove-it (no dedupe yet).

**F1 planning handoff** is separate: CLI/API `handoff propose|apply` with an idempotency key and persisted receipts ([delivery/F1-HANDOFF.md](./delivery/F1-HANDOFF.md), [NEXT-FEATURES-SPEC §4](./NEXT-FEATURES-SPEC.md#4-f1-cli-planning-handoff)). Use handoff for agreed conversation → structure with replay; use Outline for curriculum/template JSON. Handoff idempotency does not change outline behavior.

## Graft under existing hierarchy

Use **Attach under** in the Outline UI (or pass `attach_under` on propose):

```json
{
  "template_id": "hierarchy_v1",
  "outline": { "course": { "...": "..." } },
  "attach_under": { "kind": "epic", "id": "<existing-epic-uuid>" }
}
```

| `attach_under.kind` | Creates | Outline shapes |
|---------------------|---------|----------------|
| *(omit)* | Full tree (new epic) | Requires `certificate` + `courses[]` |
| `epic` | Projects + sections + tasks | Full certificate, or `course` / `courses[]` |
| `project` | Sections + tasks | `modules[]`, or single-course `modules` |
| `section` | Tasks only | `tasks[]`, or single-module `tasks` |

Apply actions may reference existing parents via `epic_id`, `project_id`, or `section_id` (propose sets these when grafting). Ownership is validated; unknown parent → `OUTLINE_ATTACH_NOT_FOUND` (404).

**Backlog:** re-import dedupe still unscheduled.

## Related

- Assist (free-text SLM) stays separate — [SLM-ASSIST.md](./SLM-ASSIST.md)
- Fixture README: [testdata/outlines/README.md](../testdata/outlines/README.md)
