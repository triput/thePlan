# ADR-010: Local SLM Assist (Ollama prove-it)

**Status:** Proposed  
**Date:** 2026-08-14  
**Context:** W3 core (Account → MS Calendar → Tauri) shipped. Roadmap **W3+** leads with local SLM assist ([07-wave-roadmap.md](../07-wave-roadmap.md), [03-feature-catalog.md](../03-feature-catalog.md)). Operator daily driver remains **Cloudflare Tunnel**; Tauri single-installer / bundled Postgres tabled to **V.Later**. Voice stays **W4**. Prefer review→confirm over auto-apply for first ship.

## Decision

### Scope (W3+ SLM prove-it)

| In | Out |
|----|-----|
| Local **Ollama** as default model host | Cloud provider setup / API keys / multi-provider UI (follow-on) |
| **OpenAI-compatible** HTTP client (`base_url` + `model`, Ollama `/v1`) | Voice / STT |
| `POST /api/v1/assist/propose` → structured action list | Auto-apply / confidence auto-commit |
| Review UI → operator approve → `POST /api/v1/assist/apply` | Schedule mutation, Update Schedule, calendar write, delete/bulk destroy |
| Narrow actions: create task(s); optional label attach / create-if-missing | Habits, Kanban, Todoist import |
| Assist optional: Ollama down → soft fail; **CRUD never blocked** | Desktop packaging / MSI / embedded Postgres (V.Later) |

### Runtime topology

- Browser (local or via Tunnel) talks only to thePlan API.
- API calls Ollama (or any OpenAI-compatible endpoint) using server-side config.
- Remote Assist works when API and Ollama share the home host (or Compose network). Prefer **native Windows Ollama** (already Startup-folder); Docker Ollama optional later, not required for prove-it.
- Default: `http://127.0.0.1:11434/v1`. If API runs in Compose and Ollama on host, document `host.docker.internal:11434`.

### Apply model

1. Operator enters free text in Assist UI.
2. **Propose** returns a structured action list (and enough context to render a review card). Model does not write to the DB.
3. Operator edits/removes actions as needed, then **Approves**.
4. **Apply** executes the **approved** list via existing task/label services (same ownership rules as CRUD). Prefer name resolution patterns already used by quick-add.
5. Deterministic quick-add remains the fast path; Assist is additive candy.

### Config

| Item | Lock |
|------|------|
| Base URL | Env / settings — default `http://127.0.0.1:11434/v1` |
| Model | Env / settings — pin a documented default in operator note |
| Enable | Soft: unreachable → `503 ASSIST_UNAVAILABLE` (or equivalent); UI shows assist unavailable |
| Secrets | No cloud keys in prove-it |

### Non-goals

- Voice input / STT (W4)
- Auto-apply
- SLM-driven schedule mutations (advisory-only hints may be a later W3+ slice)
- Cloud LLM wiring in this cut (client shape allows a later Settings swap)
- Replacing quick-add
- Packaging / single installer (V.Later)

## Consequences

- ADR accept gates Assist API/UI implementation (same session boundary as prior slices).
- CI must mock the model HTTP — never require a live Ollama daemon.
- Tunnel operators need Ollama up on the API host for Assist; thePlan without Assist stays fully usable.

## Related

- [ADR-001-tech-stack.md](./ADR-001-tech-stack.md)
- [ADR-005-scheduler-decoupling.md](./ADR-005-scheduler-decoupling.md)
- [07-wave-roadmap.md](../07-wave-roadmap.md)
- [03-feature-catalog.md](../03-feature-catalog.md)
- [SLM-ASSIST.md](../SLM-ASSIST.md)
- [CLOUDFLARE-TUNNEL.md](../CLOUDFLARE-TUNNEL.md)
- [DESKTOP.md](../DESKTOP.md)
