# Outline fixtures

Operator-owned curriculum dumps for Theme F (templates + outline ingest).

| File | Source |
|------|--------|
| [`ibm_rag_agentic_ai_professional_certificate_curriculum.json`](./ibm_rag_agentic_ai_professional_certificate_curriculum.json) | IBM RAG and Agentic AI Professional Certificate on Coursera. Public curriculum structure captured 2026-08-14 (via ChatGPT Coursera plugin / catalog). Not scraped by thePlan; no progress sync. |
| [`blank_hierarchy_v1.json`](./blank_hierarchy_v1.json) | Fillable generic template — copy, rename fields, add rows. Same v1 contract as the Coursera fixture. Use template pack `hierarchy_v1` or `coursera_specialization` (same mapper). |

**Shape (reference for Theme F ingest):** `certificate` → `courses[]` → `modules[]` → `tasks[]` with `task_type`, `duration_minutes`, `optional`, order fields, and synthetic `id`s.

## Fill guide (`blank_hierarchy_v1.json`)

1. **certificate** — becomes the epic title; optional `provider`, `platform`, `source_url`, `notes` land in the epic description.
2. **courses[]** — each entry becomes a **project** under the epic (or under an existing epic when grafting — see [OUTLINE-INGEST.md](../../docs/OUTLINE-INGEST.md)).
3. **modules[]** — each becomes a **section** under its course/project.
4. **tasks[]** — each becomes a **task** with labels from `task_type` (+ `optional` when true).

Field notes:

| Field | Required | Notes |
|-------|----------|-------|
| `course_order`, `module_order`, `task_order` | yes | Sort order in thePlan |
| `task_type` | yes | Label name (e.g. `video`, `reading`, `assignment`, `lab`, `project`) |
| `duration_minutes` | no | Clamped 1–1440; defaults to user setting if omitted |
| `optional` | no | Default false; prefix `(Optional)` in title is stripped on import |
| `id` | no | Stored as `outline_id:` line in task description for traceability |

**Graft fragments** (attach under existing parent — no duplicate epic):

| Attach under | Acceptable JSON shapes |
|--------------|------------------------|
| Epic | Full certificate JSON, or `course` / `courses[]` fragment |
| Project | `modules[]`, or `course.modules` from a single course |
| Section | `tasks[]`, or `module.tasks` from a single module |

Contract and product decisions: [ADR-011](../../docs/adr/ADR-011-templates-outline-ingest.md). Operator note: [OUTLINE-INGEST.md](../../docs/OUTLINE-INGEST.md).

thePlan must never call Coursera APIs. Ingest is file paste/upload only.
