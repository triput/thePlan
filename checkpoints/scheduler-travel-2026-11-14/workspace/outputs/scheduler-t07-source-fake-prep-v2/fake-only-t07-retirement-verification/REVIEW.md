# Fake-only T07 retirement verification v2 — REVIEW (authoring, not executed)

Status: AUTHORING ONLY / PREPARATION. `launch_ready=false`. `executed_in_preparation=false`.
Supersedes tipped v1 TIP `24C39F303DC279B812FE4BC1FF4A27B05B8633B81D2CE72ECCBA67F275BBB855` (v1 immutable).
No check/admit/invoke execution. D2 one-shot not launched. Source pins unchanged E942/2E6A/84F5.

## Oracle gaps closed (Dex p1794427286 / p1794427379)
1. Caller/no-later via extracted CoveringRoleAdmission ports + connector UNKNOWN preserve; mutation allows continuation and is detected.
2. Importer: complete owning try/except AST from `import_covering_subscription_cache` (pull `_pull_provider` try); original+candidate; no dump-comment search; no except-body-alone; no imitation handler.
3. R07/R08/R09 drive CoveringHTTP→JoinedTLS with instrumented fake socket; method vs raw close counted; R08 asserts one raw close + outer method close.
4. Mutations rebind actual CoveringHTTP.request / role-stop behavior; same oracle unmutated vs mutant; globals restored.
5. Inventory drives `compare_to_expected` with good/missing/duplicate/reordered/altered.
6. Provenance boundary finite max + shape checks before sanitize; O-R04/O-R05 observe actual classes; O-ID-OS drives prepare OSError try.

## CRLF-aware extract
Raw pinned newline_kind recorded (lf/crlf/mixed); no LF-only refuse. Base `covering_refresh_import.py` remains CRLF witness.

## Wrapper
See `Jim-Static-Read-Invoke-Verification.md` — SHA256 `1DEA20EC…` — **NO BLOCKER**.

## Controls
39 named / 31 functional; C-OUT-VE and C-OUT-UNK retained.
