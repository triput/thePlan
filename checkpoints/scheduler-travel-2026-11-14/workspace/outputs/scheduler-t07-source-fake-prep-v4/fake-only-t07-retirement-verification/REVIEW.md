# Fake-only T07 retirement verification v4 — REVIEW (authoring, not executed)

Status: AUTHORING ONLY / PREPARATION. `launch_ready=false`. `executed_in_preparation=false`.
Supersedes tipped v3 TIP `A6F1A2C395F8655E676F39B6553DF77BCD125F021DB585F0CFFEEC93440ED89F` (v3 immutable; full 234+3 payload SHA256SUMS).
v1/v2 also immutable. Carries v2 oracle-gap fixes. Source pins unchanged E942/2E6A/84F5.
No check/admit/invoke execution. D2 one-shot not launched.

## Dex blockers closed (p1794428147 / p1794428226)
1. Caller/no-later drives actual extracted `CoveringRoleConnector.run_target` + `run_bounded_domain` with coherent fake deps, shared event trace, same cleanup Unknown object, unconditional observed counters (no helper rewrite of later_*).
2. R07/R08: reset then apply sock faults (or pass through `sock_faults`); assert configured fault reached. R08 requires exactly 2 method closes (inner open + outer HTTP finally) and exactly 1 raw close.
3. `M-MUTATE-OUTER-UNKNOWN` retains outer-object mutation sensitivity; `M-ALLOW-LATER` is a separately named continuation mutant via admission.stop rebind + same functional oracle. No 39-control ceiling (40 named).

## Pins
payload/SHA256SUMS carried from v3 (234 API + 3 bases). Source-Changes.diff root-only.

## Wrapper
See `Jim-Static-Read-Invoke-Verification.md` — SHA256 `1DEA20EC…` — **NO BLOCKER**.

## Controls
40 named / 32 functional (4 mutations including M-ALLOW-LATER); C-OUT-VE and C-OUT-UNK retained.
