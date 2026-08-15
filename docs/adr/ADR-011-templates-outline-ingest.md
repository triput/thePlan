# ADR-011: Templates + outline ingest (Theme F)

**Status:** Accepted  
**Date:** 2026-08-14  
**Context:** Assist prove-it and honesty cut shipped ([ADR-010](./ADR-010-slm-assist.md)). Operator has a Coursera specialization outline as a local JSON file ([testdata/outlines/](../testdata/outlines/README.md)) and wants Epic → Project → Section → Task expansion without hand-entry or an in-app Coursera client. Templates were cataloged as W4; Theme F pulls a **narrow** templates+ingest prove-it forward.

## Decision

### Product shape

| In | Out |
|----|-----|
| **Outline ingest** — paste/upload JSON matching the fixture contract (`certificate` → `courses` → `modules` → `tasks`) | Coursera HTTP client, scraper, plugin, progress sync, xAPI/LTI |
| **Built-in template pack** `coursera_specialization` — mapping + labeling rules in code | First-class template CRUD / DB catalog (later if needed) |
| **Propose → review → apply** (deterministic; no LLM required) | Auto-apply; Assist free-text as the syllabus path |
| Create epic / projects / sections / tasks + labels from `task_type` | Todoist import (stays W3+); schedule blocks; due dates invented from curriculum |

### Hierarchy mapping (`coursera_specialization`)

| Outline | thePlan |
|---------|---------|
| `certificate.title` (+ provider/platform in description) | **Epic** |
| each `course` | **Project** under that epic (`course.url` → project description or notes field if present) |
| each `module` | **Section** under that project |
| each `task` | **Task** in that section |

Task fields:

- `title` ← outline task title (optional light cleanup of `"Video: "` / `"(Optional) "` prefixes — non-blocking polish)
- `estimated_duration_minutes` ← `duration_minutes` (clamp to product limits where needed)
- Labels ← `task_type` (create-if-missing, lowercased): `video`, `reading`, `assignment`, `lab`, `app_item`, `discussion`, `podcast`, `project`, …
- If `optional: true` → also attach label `optional`
- Preserve order via `sort_order` / creation order matching `*_order` fields
- Store outline synthetic `id` in task **description** as a single machine line (`outline_id: c01-m01-t01`) for later re-import experiments — **not** a uniqueness constraint in prove-it

### Optional items

Default **include** optional tasks. Propose request flag `skip_optional: bool = false` so the operator can drop them before apply.

### API (prove-it)

| Endpoint | Role |
|----------|------|
| `POST /api/v1/outlines/propose` | Validate JSON + template id → structured action tree (or ordered flat actions with parent keys) for review |
| `POST /api/v1/outlines/apply` | Persist **approved** actions under the current user (same ownership rules as CRUD) |

No Ollama dependency. Soft-fail validation with clear errors; never blocks normal CRUD.

### UI

Outline import entry (Settings or top-bar near Assist): paste JSON or upload `.json` → Propose → editable review (titles, skip rows, skip optional toggle) → Approve.

Reuse Assist’s review→confirm UX pattern; do **not** route syllabus JSON through the Assist LLM.

### Golden fixture

[`testdata/outlines/ibm_rag_agentic_ai_professional_certificate_curriculum.json`](../testdata/outlines/ibm_rag_agentic_ai_professional_certificate_curriculum.json) is the v1 contract and CI fixture (~10 courses / 30 modules / 417 tasks).

### Implementation slices

1. **Parse + propose** — schemas, `outline_parse` / template pack, API propose, tests against fixture  
2. **Apply** — transactional (or ordered) create epic→projects→sections→tasks+labels; tests  
3. **UI** — paste/upload → review → apply  
4. **Docs** — operator note + catalog/roadmap wave pin

### Non-goals (explicit)

- Progress / grade / locked sync from Coursera  
- Deduping re-imports (prove-it may duplicate if applied twice)  
- Markdown/CSV outline variants (JSON first; other formats later adapters)  
- General template marketplace or user-authored template editor  
- Extending Assist vocabulary (`create_project` from free text) — separate Theme B cut

## Consequences

- Templates move from pure W4 wishlist to **W3+ Theme F prove-it** for this pack only.  
- Assist stays free-text candy ([ADR-010](./ADR-010-slm-assist.md)); outline ingest is a sibling deterministic pipeline.  
- Large applies (~400 tasks) need progress feedback and may be slow in UI — acceptable for prove-it; batch/chunk later if needed.  
- Accept this ADR gates implementation (same session boundary as prior slices).

## Related

- [ADR-010-slm-assist.md](./ADR-010-slm-assist.md)  
- [testdata/outlines/README.md](../testdata/outlines/README.md)  
- [OUTLINE-INGEST.md](../OUTLINE-INGEST.md)  
- [03-feature-catalog.md](../03-feature-catalog.md)  
- [07-wave-roadmap.md](../07-wave-roadmap.md)  
