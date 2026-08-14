# SLM Assist — operator note

**ADR:** [ADR-010 — Local SLM Assist](./adr/ADR-010-slm-assist.md) (Accepted).  
**Wave:** W3+ prove-it. Voice stays W4. Desktop packaging stays V.Later.

## What this is

Optional Assist: you type what you want → thePlan asks a local model (default **Ollama**) for a structured action list → you **review and approve** → existing task/label APIs apply the work. If Ollama is down, Assist fails soft; **all normal CRUD still works**.

UI: top bar **Assist** button → Propose → edit/remove → Approve. Settings → Assist shows reachability.

## Topology (Tunnel-friendly)

```
Phone/browser → Cloudflare Tunnel → thePlan API (home host) → Ollama (same host)
```

The browser never talks to Ollama. Remote Assist only needs API + Ollama reachable to each other on the home machine.

## Recommended setup (native Ollama)

1. Install [Ollama](https://ollama.com/) on Windows (host app — not required in Docker for prove-it).
2. Confirm it starts at login (Startup folder shortcut is fine).
3. Pull the default model: `ollama pull llama3.2`
4. Probe: `http://127.0.0.1:11434/api/tags` should respond.
5. Env defaults (OpenAI-compatible):
   - `ASSIST_BASE_URL=http://127.0.0.1:11434/v1` (host-run API)
   - `ASSIST_MODEL=llama3.2`
   - `ASSIST_ENABLED=true`

### API in Docker, Ollama on host

Compose defaults `ASSIST_BASE_URL=http://host.docker.internal:11434/v1`. Do not expose Ollama through the Cloudflare Tunnel unless you intentionally want that (prove-it does not).

### Ollama in Docker (optional, later)

Possible for a single Compose farm; GPU passthrough on Docker Desktop Windows is the sharp edge. Native Ollama is preferred for this prove-it.

## Cloud models

Not in prove-it. The client is OpenAI-compatible so a later Settings/`base_url` + API key swap can target OpenAI/Azure/etc. without a rewrite.

## Out of scope here

Voice/STT, auto-apply, schedule mutations via SLM, multi-provider Settings matrix, packaging.
