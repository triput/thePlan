# Technical Architecture (living)

**Status:** Catch-up — Round 4 (2026-08-27); initial draft 2026-08-14  
**Purpose:** One place to hang “how thePlan is put together *now*” after organic growth from a small planner. Product behavior stays in [02-functional-spec.md](./02-functional-spec.md); decisions stay in [adr/](./adr/); this doc is the **system map**.

**Update when:** topology, major pipelines, or layering rules change. Track gaps as [DEF-012](./DEFECTS.md#def-012--living-technical-architecture--diagrams-catch-up). Pair deep cleanup with [DEF-011](./DEFECTS.md#def-011--refactor-assessment-modularize--de-mix-layers) / [REFACTOR-ASSESSMENT.md](./REFACTOR-ASSESSMENT.md).

---

## 1. One-liner

Personal **local-first** planner: **Vite/React** SPA → **FastAPI** → **PostgreSQL**, usually via **Docker Compose**, often reached remotely through **Cloudflare Tunnel**, with optional **Tauri** desktop shell and **Ollama** for Assist. Domain logic belongs in the API; the web UI is a thin client.

---

## 2. Runtime topology

Daily driver is **your** Postgres + API (+ web), not a multi-tenant SaaS. Cloud is used for *reach* (Tunnel) and *tools* (AI assist host, package registries)—not as the landlord of task data ([ADR-003](./adr/ADR-003-local-first-auth.md), [CLOUDFLARE-TUNNEL.md](./CLOUDFLARE-TUNNEL.md)).

```mermaid
flowchart LR
  subgraph operator [Operator devices]
    Browser[Browser]
    Tauri[Tauri desktop optional]
  end

  subgraph edge [Reach]
    Tunnel[Cloudflare Tunnel]
  end

  subgraph host [Home host]
    Web[web nginx SPA]
    API[api FastAPI]
    PG[(PostgreSQL)]
    Ollama[Ollama host optional]
  end

  Browser --> Tunnel
  Tunnel --> Web
  Tunnel --> API
  Browser --> Web
  Browser --> API
  Tauri --> API
  Web --> API
  API --> PG
  API --> Ollama
```

| Piece | Role | Notes |
|-------|------|--------|
| `web` | Static SPA (nginx in Compose) | Same-origin or `VITE_API_URL`; cookies/session to API |
| `api` | FastAPI `/api/v1/*` | Migrations, auth, CRUD, Assist, Outline, calendars, schedule |
| `postgres` | Source of truth | Volume on host; backup is operator responsibility |
| Tunnel | Remote HTTPS | e.g. `plan.silverhelmet.com` → local Compose |
| Ollama | Assist model host | Native Windows often; Compose API uses `host.docker.internal:11434` |
| Tauri | Desktop prove-it | Sidecar API on loopback; packaging V.Later ([ADR-009](./adr/ADR-009-tauri-desktop.md)) |

Compose entry: [infra/compose/compose.yaml](../infra/compose/compose.yaml).

---

## 3. Repository layout

```text
apps/api/          FastAPI app, Alembic, pytest
apps/web/          Vite + React + TypeScript SPA
apps/desktop/      Tauri 2 prove-it shell
infra/compose/     Docker Compose
docs/              Vision, specs, ADRs, ops notes, this map
testdata/outlines/ Outline JSON fixtures (Theme F)
```

Neutral code identifiers (`apps/api`, not branded package names). Product name of record: **thePlan**.

---

## 4. Layering (where logic should live)

```mermaid
flowchart TB
  UI[apps/web components]
  Client[apps/web api.ts]
  Routes[api routes]
  Services[api services]
  Models[SQLAlchemy models]
  DB[(Postgres)]

  UI --> Client
  Client --> Routes
  Routes --> Services
  Services --> Models
  Models --> DB
```

| Layer | Responsibility | Anti-pattern |
|-------|----------------|--------------|
| **Web UI** | Presentation, review/edit before apply, optimistic UX | Re-implementing ownership, scheduling math, or outline mapping |
| **`api.ts`** | HTTP + DTO shapes | Business rules |
| **Routes** | Auth dependency, validate request/response schemas, status codes | Fat domain workflows |
| **Services** | Domain workflows (Assist enrich/apply, outline propose/apply, schedule, calendar sync) | Reaching into React |
| **Models / Alembic** | Persistence | Feature policy |

ADR-001 consequence: **domain logic lives exclusively in the API**. Rapid Theme F / Assist growth may have strained that in places—see DEF-011.

---

## 5. Domain hierarchy (mental model)

```mermaid
flowchart TB
  Epic[Epic]
  Project[Project]
  Section[Section]
  Task[Task]
  Label[Label]

  Epic --> Project
  Project --> Section
  Section --> Task
  Project --> Task
  Task --> Label
```

- **Inbox:** tasks with `project_id IS NULL`.
- **Nesting:** task → subtask → nested subtask (max depth 2).
- **Outline mapping (Theme F):** certificate → Epic; course → Project; module → Section; item → Task + `task_type` labels ([ADR-011](./adr/ADR-011-templates-outline-ingest.md), [OUTLINE-INGEST.md](./OUTLINE-INGEST.md)).

Details: [04-data-schema.md](./04-data-schema.md), [02-functional-spec.md](./02-functional-spec.md) §1.

---

## 6. Major write pipelines

Three ways work enters the system. All **mutating** Assist/Outline paths are **propose → human review → apply** (no silent bulk write from a model).

```mermaid
flowchart LR
  subgraph capture [Capture]
    QA[Quick-add NL]
    Assist[Assist free text]
    Outline[Outline JSON file]
    CRUD[Direct CRUD UI]
  end

  subgraph apiSide [API]
    Parse[parse_quick_add]
    LLM[assist_llm + enrich]
    Pack[outline_templates pack]
    ApplyA[assist_apply]
    ApplyO[outline_apply]
    TaskSvc[task/project/section/epic routes]
  end

  QA --> Parse --> TaskSvc
  Assist --> LLM --> ApplyA --> TaskSvc
  Outline --> Pack --> ApplyO --> TaskSvc
  CRUD --> TaskSvc
```

| Pipeline | Propose | Apply | LLM? |
|----------|---------|-------|------|
| **Quick-add** | Client parse preview via `/quick-add/parse` | Client `POST /tasks` | No |
| **Assist** | `/assist/propose` (Ollama; enrich from `parse_quick_add`) | `/assist/apply` (`create_task` only today) | Yes (soft-fail if down) |
| **Outline** | `/outlines/propose` (deterministic pack) | `/outlines/apply` (epic/project/section/task) | No |
| **CRUD** | n/a | Direct REST | No |

**Scheduler:** CRUD and Assist/Outline must **never block** on Update Schedule / placement ([ADR-005](./adr/ADR-005-scheduler-decoupling.md)). Operator runs schedule when they want a layout.

**Calendars:** Google (W2a) and Microsoft (W3) sync are separate workers/routes; busy/mirror rules in their ADRs—not mixed into task CRUD.

---

## 7. Auth & tenancy

- Local accounts + session cookies; household admin patterns per W1.5 / ADR-007.
- **Single-user personal product** tenancy model ([ADR-002](./adr/ADR-002-single-user.md)) with multi-account household capability for family use—not a public multi-tenant SaaS.
- Ownership checks on every mutating path (`owner_id`).
- **Session revocation (DEF-027):** each user has a `session_epoch` counter in Postgres; login writes the current epoch into the session cookie, and auth dependencies reject cookies whose epoch no longer matches (password change and host recovery bump the counter). Locked-out operators reset via host-local **`theplan auth reset-password`** ([CLI.md](./CLI.md), package `apps/cli`) without hand-editing SQL or assuming email delivery.

---

## 8. Frontend map (hang details here)

| Area | Primary homes |
|------|----------------|
| Shell / nav | `App.tsx`, `Sidebar.tsx` |
| Task list / section grouping | `TaskList.tsx` (project + epic grouping; ⊞ subtree select); batch chrome in `TaskBatchBar.tsx` |
| Task detail (right panel) | `TaskDetailPanel.tsx` — resizable ([DEF-008](./DEFECTS.md)); section bodies in `TaskDetailSection.tsx` + `TaskDetailScheduling` / `Recurrence` / `Deps` / `Labels` / `Advanced` / `Promote` / `CreateProject` |
| Trash | `TrashView.tsx` — soft-delete restore, empty all, purge older than N days |
| Archived | `ArchivedView.tsx` — archived epics/projects + unarchive |
| Quick-add | `QuickAdd.tsx` |
| Assist | `AssistPanel.tsx` |
| Outline import | `OutlineImportPanel.tsx` (Theme F; attach_under / blank hierarchy pack) |
| Calendar | `CalendarView.tsx` (grid); `CalendarToolbar.tsx` + `CalendarBlockMenu.tsx` (capacity + block actions); bundles; release-remainder; clear-unpinned |
| Settings | `SettingsPanel.tsx` (shell); domain sections under `components/settings/*` |
| HTTP DTOs | `api.ts` |

---

## 9. Backend map

| Area | Primary homes |
|------|----------------|
| App wiring | `apps/api/app/main.py` |
| Routes | `apps/api/app/api/routes/*.py` |
| Assist | `services/assist_llm.py`, `assist_apply.py` |
| Outline | `services/outline_templates.py`, `outline_apply.py` |
| Quick-add NL | `services/quick_add.py` |
| Soft-delete / trash | `services/task_helpers.py` + `DELETE /tasks/trash?older_than_days=` |
| Task PATCH / batch field rules | `services/task_patch.py` (section-project, plan bind, label merge); route in `routes/tasks.py` |
| Batch patch | `PATCH /tasks/batch` in `routes/tasks.py` |
| Calendar bundles | `services/bundle_blocks.py` + `POST /scheduled-blocks/bundle` ([ADR-012](./adr/ADR-012-calendar-bundles.md)) |
| Promote / demote | `services/hierarchy_promote.py` ([DEF-023](./DEFECTS.md)) |
| Schedule / fuzzy | `scheduler/*` + [ADR-006](./adr/ADR-006-fuzzy-scheduling.md) |
| Models | `apps/api/app/models/` — domain modules (`mixins`, `user`, `hierarchy`, `task`, `label`, `calendar`, `schedule`, `enums`) + barrel `__init__.py` (DEF-011 Cut #7); Alembic head **016** |
| Schemas | `apps/api/app/schemas/` — domain modules (`common`, `auth`, `settings`, `hierarchy`, `tasks`, `labels`, `calendar`, `search`, `assist`, `outlines`) + barrel `__init__.py` (DEF-011 Cut #6) |

---

## 9b. Smash-shipped surfaces (Round 2–4) — quick map

```mermaid
flowchart TB
  subgraph lists [Lists]
    Batch[PATCH /tasks/batch]
    SoftDel[deleted_at soft-delete]
    Trash[TrashView restore / purge]
  end

  subgraph cal [Calendar]
    Bundle[POST /scheduled-blocks/bundle]
    Gray[bundle_inactive partial gray]
    Shrink[shrink on member complete]
    Cap[release-remainder / clear-unpinned]
  end

  subgraph hier [Hierarchy]
    Promote[promote/demote entity ops]
    Outline[outline attach_under / graft]
  end

  TaskList --> Batch
  TaskList --> SoftDel --> Trash
  TaskList --> Bundle
  Bundle --> Gray
  Complete[POST /tasks/id/complete] --> Shrink
  CalendarView --> Cap
  Detail[TaskDetail / Edit forms] --> Promote
  OutlineUI[OutlineImportPanel] --> Outline
```

| Surface | Contract / ADR | Notes |
|---------|----------------|-------|
| Bulk edit | `PATCH /tasks/batch` | Style, labels, due, move project, delete→soft |
| Soft-delete | Alembic `015`, trash list/restore, empty + older-than purge | No background cron |
| Bundles | [ADR-012](./adr/ADR-012-calendar-bundles.md), Alembic `016` | Manual create; partial gray + shrink-on-complete (R4) |
| Capacity | DEF-020 | Release remainder + clear unpinned |
| Promote/demote | DEF-023 | No schema change — transactional rewire |
| Outline graft | [ADR-011](./adr/ADR-011-templates-outline-ingest.md) | `attach_under`, blank `hierarchy_v1` |

---

## 10. Docs map (what to open for what)

| Need | Doc |
|------|-----|
| Why / non-goals | [01-product-vision.md](./01-product-vision.md) |
| Observable behavior | [02-functional-spec.md](./02-functional-spec.md) |
| Feature ↔ wave | [03-feature-catalog.md](./03-feature-catalog.md), [07-wave-roadmap.md](./07-wave-roadmap.md) |
| Tables | [04-data-schema.md](./04-data-schema.md) |
| REST | [05-api-contract.md](./05-api-contract.md) |
| Decisions | [adr/](./adr/) |
| Refactor cut list | [REFACTOR-ASSESSMENT.md](./REFACTOR-ASSESSMENT.md) |
| Dependency hygiene | [HYGIENE-R4-QUICKSCAN.md](./HYGIENE-R4-QUICKSCAN.md), [HYGIENE-W3.md](./HYGIENE-W3.md) |
| Ops | [USER-GUIDE.md](./USER-GUIDE.md), [CLOUDFLARE-TUNNEL.md](./CLOUDFLARE-TUNNEL.md), [SLM-ASSIST.md](./SLM-ASSIST.md), [OUTLINE-INGEST.md](./OUTLINE-INGEST.md), [DESKTOP.md](./DESKTOP.md) |
| Agent / automation CLI | [CLI.md](./CLI.md) — JSON contract, exit codes, M1 recovery + M2 HTTP commands |
| Open polish | [DEFECTS.md](./DEFECTS.md) |

---

## 11. Known gaps (honest)

- Functional spec / feature catalog still carry some **pre–Theme F** wording; trust ADRs + this map + DEFECTS for newest surfaces until a doc sync pass.
- API contract may lag newest smash endpoints slightly—OpenAPI from the running API is authoritative for exact shapes.
- Service boundaries: DEF-011 Cut wave **#1–#7 landed** (#6 schemas, #7 models **2026-10-08**); **App.css** carve (#8) — [REFACTOR-ASSESSMENT.md](./REFACTOR-ASSESSMENT.md).
- This file will grow: calendar sync sequence diagrams, auth sequence, Update Schedule pipeline detail, etc.

---

## Related

- [DEF-012](./DEFECTS.md#def-012--living-technical-architecture--diagrams-catch-up) — keep this map current  
- [DEF-011](./DEFECTS.md#def-011--refactor-assessment-modularize--de-mix-layers) — modularize assessment  
- [REFACTOR-ASSESSMENT.md](./REFACTOR-ASSESSMENT.md) · [HYGIENE-R4-QUICKSCAN.md](./HYGIENE-R4-QUICKSCAN.md)  
- [ADR-001](./adr/ADR-001-tech-stack.md) · [ADR-010](./adr/ADR-010-slm-assist.md) · [ADR-011](./adr/ADR-011-templates-outline-ingest.md) · [ADR-012](./adr/ADR-012-calendar-bundles.md)
