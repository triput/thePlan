# Outline ingest (Theme F)

Operator-owned curriculum JSON → Epic / Project / Section / Task tree.  
ADR: [ADR-011](./adr/ADR-011-templates-outline-ingest.md). Golden fixture: [`testdata/outlines/`](../testdata/outlines/).

## What it is

- Built-in template pack: `coursera_specialization`
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

1. Obtain a curriculum JSON in the fixture shape (ChatGPT Coursera plugin, DevTools save, hand-built — outside thePlan).
2. Open **Outline** → paste or choose the file.
3. Propose → skim/edit/remove rows → Approve.
4. After apply, thePlan opens the new epic (expanded). **Courses are projects** under that epic in the sidebar; **modules are sections** inside each course (visible in the epic’s grouped task list, or open a course for the sections bar).
5. Expect one epic, N projects, modules as sections, and many tasks (IBM RAG fixture ≈ 417 tasks). Large applies can take a moment.

Re-importing the same outline **will duplicate** entities in prove-it (no dedupe yet).

## Related

- Assist (free-text SLM) stays separate — [SLM-ASSIST.md](./SLM-ASSIST.md)
- Fixture README: [testdata/outlines/README.md](../testdata/outlines/README.md)
