# Fake-only T07 retirement verification v6 — REVIEW (authoring, not executed)

Status: AUTHORING ONLY / PREPARATION. `launch_ready=false`. `executed_in_preparation=false`.
Supersedes tipped v5 TIP `0EF2EFD5AC028D5CCBDADB974C6632F090DF526788467079483D79799B834685` (immutable).
v1–v4 also immutable. Source pins E942/2E6A/84F5. No check/admit/invoke execution.

## Dex blockers closed (p1794429291 / p1794429755 + remaining p1794429171)
1. Event: Ports.apply drives extracted importer owning try/except; `_pull_provider` invokes fake-backed CoveringHTTP (not direct HTTP outside that try).
2. OAuth: Ports.token routes extracted `refresh_access_token` through CoveringHTTP oauth exchange.
3. Exchange exception captured at HTTP boundary before owning-caller handling; terminal domain catch compared by object identity.
4. R07: exact configured `FakeOpenPrimaryError` only; 1 method/raw close; zero sends; no UNKNOWN alternative branch.
5. Original O-CALLER-EVENT: importer swallows fault → later target admitted (contract miss).

## Controls
41 named / 36 functional; C-OUT-VE/C-OUT-UNK retained.
