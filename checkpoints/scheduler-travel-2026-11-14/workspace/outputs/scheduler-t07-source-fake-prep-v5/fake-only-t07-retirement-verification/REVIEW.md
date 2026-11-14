# Fake-only T07 retirement verification v5 — REVIEW (authoring, not executed)

Status: AUTHORING ONLY / PREPARATION. `launch_ready=false`. `executed_in_preparation=false`.
Supersedes tipped v4 TIP `DA6BCB39A5FB48F9D6449D6992BCBCC3A2EA57F5298E0C015D798642FA348B3D` (immutable).
v1–v3 also immutable. Carries v3 pin inventory + v4 check fixes. Source pins E942/2E6A/84F5.
No check/admit/invoke execution.

## Dex blocker closed (p1794429171)
1. Domain apply port drives actual CoveringHTTP event path; token port drives OAuth CoveringHTTP.
2. HTTP cleanup Unknown propagates through connector/domain; exchange vs terminal object identity asserted.
3. Three targets: prior complete, faulting target, later target beyond fault (not admitted on candidate).
4. Original O-CALLER-EVENT negative witness (raw cleanup escape; no exchange Unknown identity).
5. M-ALLOW-LATER uses that same domain HTTP oracle.

## Controls
41 named / 36 functional (10 original witnesses including O-CALLER-EVENT); C-OUT-VE/C-OUT-UNK retained.
