# Fake-only T07 retirement verification v7 — REVIEW (authoring, not executed)

Status: AUTHORING ONLY / PREPARATION. `launch_ready=false`. `executed_in_preparation=false`.
Supersedes tipped v6 TIP `671E008FA26ABB3EFC4BBCBB32B57C3828A50CAB2ABC343A039B29FE2F2CB599` (immutable; Dex prelaunch withdrew ACCEPT).
v1–v5 also immutable. Source pins E942/2E6A/84F5 **unchanged**. No check/admit/invoke execution. No serialization probe. No launch.

## Dex blockers closed (B1 / B2 + batch)
1. **B1 serialization:** `prior_completed` projected to explicit primitive fields (`subscription_id`, `status`, `phase`, `outcome`, `FAKE_TRANSACTION_ACKNOWLEDGMENT`); originals retained for SUB-1 behavior assertions; no `default=str` / repr / `__dict__` / evidence drop.
2. **B2 C-R01:** removed `... and False: pass`; instrumented fake response close; asserts exactly one response-close + one transport-close + valid returned result.
3. **C-R12:** instrumented fake socket; closed/owner/socket identity unchanged + zero raw close; fake-thread scope explicit (`FAKE-OWNER-ID-NOT-THREAD`).
4. **C-PROV-BOUNDARY-ACCEPT:** exercises `assert_provenance_boundary` on valid UNKNOWN/provenance tuples before PASS; negatives retained.
5. **C-R10/R11:** truthful HTTP 500 `server_error` JSON stimulus for R10; removed assumed `later_admission=False` measurement; continuation proof remains integrated domain counters. Distinct malformed/lost-response obligations remain **open**.

## Controls
41 named / 36 functional; C-OUT-VE/C-OUT-UNK retained; unexpected-outcome refusal preserved.

## Non-claims
Does not authorize launch, imports/compile/tests, host packet/admission/commands edits, production source changes, or full T07 / T01–T08 closure.
