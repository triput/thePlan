# ADR-004: Container Runtime

**Status:** Accepted  
**Date:** 2026-08-09  
**Context:** Local deployment engine on Windows development host.

## Decision

| Choice | Role |
|--------|------|
| **Docker Desktop + Compose** | Default runtime on Windows for MVP docs and scripts |
| **OCI-portable Compose files** | Required — no Docker-proprietary-only features |
| **Podman + Compose** | Supported alternate runtime, not a product requirement |

Compose stack services: `postgres`, `api`, `web`. Cloudflare Tunnel sidecar documented W1.5+, not MVP default.

## Rationale

The original draft specified Podman for local-sovereignty (rootless, daemonless, no Docker Desktop licensing). That preference is valid on Linux servers but adds friction on Windows/WSL2.

What matters architecturally:

1. **OCI images** — interchangeable across engines
2. **Compose orchestration** — single `compose.yaml` defines the stack
3. **Portability** — same files run under Docker or Podman Compose

On the operator's Windows machine, Docker Desktop provides mature WSL2 integration, first-class Compose support, and broader tutorial alignment.

Podman remains a compatible alternate for operators who prefer rootless containers or Linux deployment without Docker Inc. tooling.

## Compose Requirements

- Healthchecks on postgres and api
- Named volume for Postgres data
- Environment via `.env` (gitignored) or Docker secrets
- Engine-agnostic: avoid `docker compose`-only CLI assumptions in application code; document both `docker compose` and `podman compose` invocations where they differ

## Consequences

- MVP documentation and scripts default to `docker compose up`.
- ADR and roadmap note Podman compatibility without maintaining dual CI matrices in MVP.
- Hosted Postgres is fallback (W3), not replacement for local Compose default.

## Related

- [ADR-001-tech-stack.md](./ADR-001-tech-stack.md)
- [07-wave-roadmap.md](../07-wave-roadmap.md)
