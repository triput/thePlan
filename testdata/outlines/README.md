# Outline fixtures

Operator-owned curriculum dumps for Theme F (templates + outline ingest).

| File | Source |
|------|--------|
| [`ibm_rag_agentic_ai_professional_certificate_curriculum.json`](./ibm_rag_agentic_ai_professional_certificate_curriculum.json) | IBM RAG and Agentic AI Professional Certificate on Coursera. Public curriculum structure captured 2026-08-14 (via ChatGPT Coursera plugin / catalog). Not scraped by thePlan; no progress sync. |

**Shape (reference for Theme F ingest):** `certificate` → `courses[]` → `modules[]` → `tasks[]` with `task_type`, `duration_minutes`, `optional`, order fields, and synthetic `id`s.

thePlan must never call Coursera APIs. Ingest is file paste/upload only.
