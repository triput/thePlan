# thePlan — speakable technical overview

<!--
==============================================================================
  File: docs/portfolio/THEPLAN-SPEAKABLE-OVERVIEW.md
  Description: Interview/portfolio narration map — architecture, AI, CLI, scheduling truth.
  Component: Portfolio / documentation
  Version: 1.0
  Created: 2026-10-12
  Last Update: 2026-10-12
  Audience: Trish (spoken walkthrough to technical interviewers)
==============================================================================
-->

**Purpose:** A map you can **read aloud** — not a script to memorize. Authoritative depth lives in linked docs; this file tells you **what to say** and **what not to claim**.

**Voice essay (Reed):** [NOTES — thePlan & the AI crew](./NOTES-theplan-ai-crew-collaboration.md). This doc stays the technical briefing map; that essay is the interview narrative.

**Scale (refresh before citing):** On the order of **~77k lines** of tracked application source (Python-heavy across API, CLI, scheduler; TypeScript/React web). Re-count from `apps/` when prepping a public show.

---

## 1. Elevator (~30 seconds)

**Say this:**

- thePlan is my **local-first personal execution tool** — structured work hierarchy plus calendar-oriented scheduling, built as a **Vite/React SPA** talking to a **FastAPI** backend on **PostgreSQL**, usually via **Docker Compose** on my own hardware.
- I **design and direct**; the codebase is real product engineering: domain logic in the API, thin web client, optional **Cloudflare Tunnel** for remote reach without handing task data to a SaaS landlord.
- **AI is optional and safe:** local **Ollama** powers Assist through a **propose → human review → apply** path — the model never silently writes the database.
- **Agents get a first-class CLI** (`theplan`): JSON contracts, stable exit codes, session auth, Assist, course import via templates, and scheduling-settings foundations — with **Julie** (named agent persona) as a **field tester** who ran an 11-point S1 checklist and passed on a frozen build.

---

## 2. What it is / who it’s for

**Say this:**

- **One operator per session** — personal productivity, not multi-tenant SaaS. Household-style **multiple accounts** on the same instance are supported (isolated by `owner_id`), not team workspaces.
- **Hierarchy:** Epic → Project → Section → Task → Subtask (max depth 2) — richer than classic Todoist-shaped tools; inbox is tasks with no project.
- **Principles:** speed-first UX, utility over gamification, **CRUD never blocks on the scheduler** (you run Update Schedule / replan when you want layout).
- **Suite context:** thePlan sits alongside my Synesis/Phronesis work as the **execution** layer — capture, structure, time maps, calendars, and (in flight) a **0.7 scheduling/settings** modernization.

**Do not say:** “It’s Todoist in the cloud” or “multi-tenant product.”

---

## 3. Architecture map (speakable)

**Say this — paint the picture:**

```text
Browser (or Tunnel) → nginx SPA (web) ──┐
                                        ├──► FastAPI /api/v1/* ──► PostgreSQL
Tauri desktop (optional) ───────────────┘              │
                                                       ├──► Ollama (Assist only; server-side)
                                                       └──► schedule_runs → scheduler worker (replan)
```

| Surface | One line for interviews |
|---------|-------------------------|
| **Web** (`apps/web`) | React/TS SPA — task lists, calendar, Assist panel, Outline import, settings shells; HTTP via `api.ts`. |
| **API** (`apps/api`) | FastAPI — auth, CRUD, quick-add NL parser, Assist, outline/template packs, calendars, schedule dispatch. **All domain rules live here** ([ADR-001](../adr/ADR-001-tech-stack.md)). |
| **CLI** (`apps/cli`) | Python agent CLI — JSON stdout, httpx + cookie jar; host-local DB recovery for password reset; mirrors REST for automation ([CLI.md](../CLI.md)). |
| **Scheduler** | Same API image; **`python -m app.scheduler.worker`** polls `schedule_runs` when Compose runs the `scheduler` service (`SCHEDULE_DISPATCH=external`). CRUD returns **202** for schedule admission; placement is async ([ADR-005](../adr/ADR-005-scheduler-decoupling.md)). |
| **Postgres** | Source of truth on a host volume — backup is operator responsibility ([09-technical-architecture.md](../09-technical-architecture.md)). |
| **Ollama** | Optional; API calls OpenAI-compatible `/v1` on the home host (`host.docker.internal` from containers). Browser **never** talks to Ollama directly. |
| **Tunnel** | Optional HTTPS reach to **my** Compose stack — not the data store ([CLOUDFLARE-TUNNEL.md](../CLOUDFLARE-TUNNEL.md)). |

**Three ways work enters the system** (good sound bite):

1. **Quick-add** — deterministic NL parse, no LLM.
2. **Assist** — LLM proposes structured actions; I approve; API applies via same ownership rules as CRUD.
3. **Outline / templates** — curriculum JSON → hierarchy (deterministic pack + review, or CLI template propose/apply with receipts).

**Layering rule:** UI presents and reviews; **services** own workflows (`assist_apply`, `outline_apply`, `quick_add`, scheduler package).

---

## 4. AI access & Julie (first-class)

### 4.1 Assist — local SLM, human in the loop

**Say this:**

- **Assist** is W3+ prove-it: I type intent → **`POST /assist/propose`** asks **Ollama** (default **llama3.2**) for a structured action list → I edit in **AssistPanel** → **`POST /assist/apply`** runs only what I approved.
- **Soft failure:** if Ollama is down, Assist returns unavailable; **every normal CRUD path still works** ([SLM-ASSIST.md](../SLM-ASSIST.md), [ADR-010](../adr/ADR-010-slm-assist.md)).
- **Honesty cut:** deterministic **`parse_quick_add`** wins for parseable **due** and **duration**; the review UI shows editable due/duration before apply. “Schedule at …” in Assist means task **due**, not calendar block mutation — blocks stay out of SLM scope.
- **Theme B actions today:** `create_task` and `create_project` (with epic/color fields) — still **no** auto-apply, **no** schedule/calendar/delete via the model.
- **Remote use:** phone/browser → Tunnel → API on home machine → Ollama on same host; Tunnel does **not** need to expose Ollama.

**CLI mirror:**

```text
theplan assist propose --text "…"
theplan assist apply --file proposal.json
```

`theplan status` includes **`/assist/status`** inside JSON without failing the whole command if Assist is down.

### 4.2 Outline ingest vs Coursera templates (two related paths)

**Say this:**

| Path | Best for | Idempotency |
|------|----------|-------------|
| **Outline (Theme F)** — UI **Outline** button or `POST /outlines/propose|apply` | Specialization/certificate JSON → Epic/Project/Section/Task; graft with `attach_under` | **Not** idempotent — re-import duplicates ([OUTLINE-INGEST.md](../OUTLINE-INGEST.md), [ADR-011](../adr/ADR-011-templates-outline-ingest.md)) |
| **Templates (F5)** — `theplan templates …` | Coursera course/specialization/module packs; **receipts** + idempotency keys on apply | **Apply** is idempotent by key; separate from legacy outline API ([CLI.md](../CLI.md) F5, [AGENT-COURSE-IMPORT.md](../guides/AGENT-COURSE-IMPORT.md)) |
| **Handoff (F1)** | Conversation → agreed graph with receipt replay | Idempotent handoff keys — **not** the same as outline |

**Course import story for interviews:** Julie (or any agent) follows [AGENT-COURSE-IMPORT.md](../guides/AGENT-COURSE-IMPORT.md): confirm instance + `templates get coursera_course`, build real syllabus JSON from Trish-supplied source (no invented curriculum), **propose → review with human → apply** with saved proposal + idempotency key, verify read-back. Import uses **manual** scheduling policy — **not** incidental Update Schedule.

### 4.3 Agent CLI — why it exists

**Say this:**

- Built for **operators and automation agents**: default **JSON on stdout**, stable **`ok` / `code` / `message`** envelope, exit codes **0–5** mapped from HTTP semantics ([apps/cli/README.md](../../apps/cli/README.md)).
- **M1:** `theplan auth reset-password` hits Postgres **on the host** (session epoch bump — revokes stale cookies without email).
- **M2+:** session file after `auth login`; tasks, Assist, status, handoff, Kanban workflow, schedule **explanations** (read-only — no replan from CLI), templates, saved views, **S1** availability/settings/progress commands.
- Dependencies intentionally small: **httpx**, stdlib **argparse** (no Typer).

### 4.4 Julie as CLI field tester (quality narrative)

**Say this:**

- **Julie** is the named agent persona for **real supported workflows** — not a separate product, but a **quality and usability** story.
- For **0.7 S1**, Julie executed **[J-S1-01 through J-S1-11 PASS on 2026-10-12]** on a **disposable account** and frozen build (`9d4cf48`, isolated `julie-s1`) — availability read/write honesty (`scheduling_effective: false` for saved General/Working), **original / worked / remaining** effort, **scheduling_revision** stale protection, and `tasks scheduling-effective` readback that separates **legacy placer-active** inputs from **saved-but-inactive** config ([0.7-S1-JULIE-CLI-CHECKLIST.md](../delivery/0.7-S1-JULIE-CLI-CHECKLIST.md)).
- That PASS is **CLI acceptance for S1 foundations**, not “full 0.7 shipped” and not authorization to replan production calendars during the test.

**Interview angle:** “We treat agent UX as production UX — JSON contracts, revision tokens, idempotent progress keys, and a bounded checklist an agent can run without touching real coursework.”

---

## 5. Scheduling & settings (current truth — honest)

**Say this:**

- **0.7.0** is the **Scheduling / Settings** train — product contract in [SCHEDULING-SETTINGS-SPEC.md](../SCHEDULING-SETTINGS-SPEC.md); discovery ledger from **Dex** in [SCHEDULING-SETTINGS-DEX-DISCOVERY-REVIEW-2026-10-12.md](../redesign/SCHEDULING-SETTINGS-DEX-DISCOVERY-REVIEW-2026-10-12.md).
- **S0:** migration contract and bridge semantics ([0.7-S0-MIGRATION-CONTRACT.md](../delivery/0.7-S0-MIGRATION-CONTRACT.md)).
- **S1 (foundations — in production on household with caveats):** configuration read/write for **General / Working / Personal** availability policies, **effort progress** (original, worked, remaining), owner **`scheduling_revision`**, CLI parity — **first slice accepted** with **named residuals**; **do not** call full S1 “Closed/shipped” ([0.7-S1-FIRST-SLICE-2026-10-12.md](../delivery/0.7-S1-FIRST-SLICE-2026-10-12.md)).
- **Critical S1 honesty:** saving **General** or most **Working** patterns is **config-only** in S1 — `scheduling_effective: false` on policy reads; the **legacy Time Map + workweek/workday** path still drives actual placement until later S2 activations ([CLI.md](../CLI.md) S1 placement note).
- **S2 (in flight — placer cutover):** chunking activation (**V1**) and pin reservation (**V2**) share the **keep-in-one-block × pin** contract (**S2-P4**, product-closed via Dex). **Renee Quality PASS** on V1/V2 acceptance slices — **Dex retest Open**, **HOLD push/rebuild**, **no household migrate**. **A15 / SS-30 (both-sides buffer)** remains **Open** as of kickoff packet — not Closed ([0.7-S2-CUTOVER.md](../delivery/0.7-S2-CUTOVER.md)).
- **What’s next in the arc (high level):** after buffer evidence and gates — **Working / General activation** in the placer (S2-V3 territory), not claiming that’s live in interviews today.

**Do not say:** “The new availability UI already schedules my week” or “0.7 is shipped.”

---

## 6. Quality & phase gates (short)

**Say this:**

- Delivery follows **Discovery → Implementation → Quality → Documentation → Delivery** — Quality and docs are **not** parallelized for “shipped” stamps ([phase gates](../../.cursor/rules/phase-gates.mdc)).
- **Renee** owns targeted pytest/API/CLI evidence; **Dex** independently pressure-tests reconciliation and operator paths (especially scheduling).
- **Page** reconciles approved decisions into specs and indexes without changing meaning ([COLLABORATIVE-PLANNING-WORKFLOW.md](../guides/COLLABORATIVE-PLANNING-WORKFLOW.md)).
- A green dev suite is **evidence for that suite**, not a substitute for acceptance on disposable DBs / Julie checklists / Dex retest.

---

## 7. What’s impressive to demo

**Say this — pick 2–3 for time:**

| Demo | Why it lands |
|------|----------------|
| **Assist propose → edit due/duration → apply** | Shows local AI + deterministic parser ownership + no silent writes. |
| **Outline or template course import** | Large real hierarchy from JSON; review screen; epic expands to hundreds of tasks (fixture scale ~417 tasks cited in ops doc). |
| **Calendar bundles + capacity** | Manual bundle create, partial gray, shrink-on-complete — product polish on top of scheduler ([09-technical-architecture.md](../09-technical-architecture.md) §9b). |
| **`theplan status` + `assist propose` + `tasks list --format json`** | Agent-native ops without scraping the UI. |
| **`theplan tasks scheduling-effective`** | Honest bridge UI/API: what the placer uses **today** vs what you **saved** for tomorrow’s cutover. |
| **Session epoch / CLI password reset** | Security-minded local-first recovery without email ([09-technical-architecture.md](../09-technical-architecture.md) §7). |
| **Compose topology** | `web` + `api` + `postgres` + optional `scheduler` + Tunnel — personal infra story. |

**Skip unless asked:** Tauri desktop (prove-it, packaging V.Later), voice/W4, cloud LLM providers in Assist prove-it.

---

## 8. Talking traps / do-not-claim list

| Trap | Truth |
|------|--------|
| “**0.7 / S2 is shipped**” | S2-V1/V2 have **Quality PASS**; **Dex retest Open**, **HOLD push**, **A15 Open**, **not Closed/shipped**. |
| “**S1 is fully done**” | **First slice accepted** with **named Open items**; proceed to S2 with residuals documented. |
| “**Saved Working hours schedule my tasks now**” | S1: mostly **config-only**; legacy maps/workweek still active unless compatibility mirror applies. |
| “**Assist replans my calendar**” | Out of scope — task create/project create only; schedule mutations excluded ([ADR-010](../adr/ADR-010-slm-assist.md)). |
| “**Re-importing the same outline merges**” | Outline path **duplicates**; use **handoff** or template **idempotency keys** when you need replay semantics. |
| **Secrets in chat or repo** | `THEPLAN_SESSION_FILE`, passwords, Tunnel tokens — env-only; never demo credentials. |
| **“We push to GitHub by default”** | Working remote is **`cursor`** (Origin); **`origin`** is GitHub mirror — push policy is explicit ([origin-vs-github rule](../../.cursor/rules/origin-vs-github.mdc)). |
| **Coursera sync** | No login/scrape/progress sync inside thePlan — you bring JSON ([OUTLINE-INGEST.md](../OUTLINE-INGEST.md)). |
| **Exact commit SHAs in interviews** | Point to **delivery records** and **spec versions**, not memorized hashes. |

---

## 9. Link index (deeper docs)

| Topic | Path |
|-------|------|
| Living system map | [docs/09-technical-architecture.md](../09-technical-architecture.md) |
| Doc index | [docs/README.md](../README.md) |
| Stack ADR | [docs/adr/ADR-001-tech-stack.md](../adr/ADR-001-tech-stack.md) |
| Assist ADR + ops | [docs/adr/ADR-010-slm-assist.md](../adr/ADR-010-slm-assist.md), [docs/SLM-ASSIST.md](../SLM-ASSIST.md) |
| Outline ADR + ops | [docs/adr/ADR-011-templates-outline-ingest.md](../adr/ADR-011-templates-outline-ingest.md), [docs/OUTLINE-INGEST.md](../OUTLINE-INGEST.md) |
| Agent CLI | [docs/CLI.md](../CLI.md), [apps/cli/README.md](../../apps/cli/README.md) |
| Course import (Julie) | [docs/guides/AGENT-COURSE-IMPORT.md](../guides/AGENT-COURSE-IMPORT.md) |
| Julie S1 checklist | [docs/delivery/0.7-S1-JULIE-CLI-CHECKLIST.md](../delivery/0.7-S1-JULIE-CLI-CHECKLIST.md) |
| S1 delivery record | [docs/delivery/0.7-S1-FIRST-SLICE-2026-10-12.md](../delivery/0.7-S1-FIRST-SLICE-2026-10-12.md) |
| S2 cutover packet | [docs/delivery/0.7-S2-CUTOVER.md](../delivery/0.7-S2-CUTOVER.md) |
| Scheduling/settings spec | [docs/SCHEDULING-SETTINGS-SPEC.md](../SCHEDULING-SETTINGS-SPEC.md) |
| Product vision | [docs/01-product-vision.md](../01-product-vision.md) |
| Operator guide | [docs/USER-GUIDE.md](../USER-GUIDE.md) |
| Open defects | [docs/DEFECTS.md](../DEFECTS.md) |

---

## 10. Refresh before public show

Run this checklist before a portfolio walk, interview, or live demo — dates and gates move fast on the 0.7 train.

- [ ] **S2 status:** Read [0.7-S2-CUTOVER.md](../delivery/0.7-S2-CUTOVER.md) — Dex retest, A15/SS-30, push/hold, V3+ sequencing. Do not claim Closed/shipped without current stamps.
- [ ] **S1 residuals:** Skim [0.7-S1-FIRST-SLICE-2026-10-12.md](../delivery/0.7-S1-FIRST-SLICE-2026-10-12.md) header — “accepted” ≠ “all scheduling semantics live.”
- [ ] **Julie capabilities:** Re-read [0.7-S1-JULIE-CLI-CHECKLIST.md](../delivery/0.7-S1-JULIE-CLI-CHECKLIST.md) — new run needs new build/account record; 11/11 PASS is **2026-10-12** on frozen `julie-s1`.
- [ ] **Assist scope:** [SLM-ASSIST.md](../SLM-ASSIST.md) + ADR-010 addenda — action types and out-of-scope list.
- [ ] **Template vs outline:** Confirm F5 delivery note if course-import flags changed ([delivery/F5-COURSERA-TEMPLATES.md](../delivery/F5-COURSERA-TEMPLATES.md)).
- [ ] **LOC / scale:** Re-count application sources under `apps/` (exclude `.venv`, `node_modules`) if citing size.
- [ ] **Spec version:** [SCHEDULING-SETTINGS-SPEC.md](../SCHEDULING-SETTINGS-SPEC.md) header version matches what you quote.
- [ ] **Demo environment:** Ollama up for Assist; disposable account for CLI writes; no secrets on screen.
- [ ] **Reed cross-link:** If `docs/portfolio/NOTES-*.md` exists, link it from §1 and trim overlap.

---

*Maintained by Page. Implementation truth: codebase + delivery records above — not this file alone.*
