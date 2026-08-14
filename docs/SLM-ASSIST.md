# SLM Assist — operator note

**ADR:** [ADR-010 — Local SLM Assist](./adr/ADR-010-slm-assist.md) (Proposed — accept before implementation).  
**Wave:** W3+ prove-it. Voice stays W4. Desktop packaging stays V.Later.

## What this is

Optional Assist: you type what you want → thePlan asks a local model (default **Ollama**) for a structured action list → you **review and approve** → existing task/label APIs apply the work. If Ollama is down, Assist fails soft; **all normal CRUD still works**.

## Topology (Tunnel-friendly)

```
Phone/browser → Cloudflare Tunnel → thePlan API (home host) → Ollama (same host)
```

The browser never talks to Ollama. Remote Assist only needs API + Ollama reachable to each other on the home machine.

## Recommended setup (native Ollama)

1. Install [Ollama](https://ollama.com/) on Windows (host app — not required in Docker for prove-it).
2. Confirm it starts at login (Startup folder shortcut is fine).
3. Pull a model (exact default pinned when Assist ships; until then any instruct-capable small model works for smoke).
4. Probe: `http://127.0.0.1:11434/api/tags` should respond.
5. API defaults: OpenAI-compatible base `http://127.0.0.1:11434/v1` + configured model name.

### API in Docker, Ollama on host

Point the API at `http://host.docker.internal:11434/v1` (Docker Desktop Windows). Do not expose Ollama through the Cloudflare Tunnel unless you intentionally want that (prove-it does not).

### Ollama in Docker (optional, later)

Possible for a single Compose farm; GPU passthrough on Docker Desktop Windows is the sharp edge. Native Ollama is preferred for this prove-it.

## Cloud models

Not in prove-it. The client is OpenAI-compatible so a later Settings/`base_url` + API key swap can target OpenAI/Azure/etc. without a rewrite.

## Out of scope here

Voice/STT, auto-apply, schedule mutations via SLM, multi-provider Settings matrix, packaging.
