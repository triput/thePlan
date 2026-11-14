# Native MS invalid_grant preparation v1: NP-V-MS-INVALID (CURRENT README)

Matt, November 13, 2026. This is for the assignment `Matt-thePlan-Scheduler-MS-Invalid-Grant-Preparation-2026-11-13.md` (`66D01613…EA54`), under lane `389A00DD…7E2D`, implementing the accepted design `74F493D8…`.

**Status: PREPARED_NOT_EXECUTED, frozen, no active writer.** Host `launch_ready`, `candidate_launch_ready_staged`, `human_launch_authorized` and runner-config `launch_ready` are all false. There is no EXECUTE acknowledgement, and the endpoint is unbound.

## Current versus historical
- **Current:** this README, `MS-Invalid-Prep-Freeze.json` and `MS-Invalid-Native-Command-HELD.ps1.txt`.
- **Historical, copied with the inputs:** the `T05-*` documents, `MS-Merge-*`, `Peer-Close-*`, `Worker-*` and every other top-level command, freeze or review. They describe earlier roots, not this one.
- **Lineage:** `Source-T05-Prep-V3-Input-Manifest.sha256` (`B773B95E…E59B`, 292 entries, verified 292/292).

## Batch
- `case_ids` is `["NP-V-MS-INVALID"]`, `expected_unknown_cases` is `[]`, and the batch id is `np-v-ms-invalid`.
- NONEXPIRED, REFRESH and T05 stay in their own frozen roots. There is no merge, no automatic sequencing and no retry.
- The T05 bodies remain implemented in the runner but are not in this batch.
- All 31 declarations and 76 planning IDs are unchanged.

## Changed roles (all others byte-identical to T05 v3)
| role | file | before | after |
|---|---|---|---|
| 4 | `np_runner_entry.py` | `1D70164C` | `ACD7F449…` (see SUMS) |
| 5 | `np_suite.py` | `9AED74EE` | `DAB88CB3…` (implementation note only) |
| 8 | `np_provider_transcript.py` | `562F61CD` | `BEDCCFD3…` |
| data | `runner-config.json` | `96782CB4` | `10106B82…` (`case_ids` only) |

## What changed
- **Transcript (role 8):**
  - `ms_token_invalid_grant_script()` now expects `path=MS_TOKEN_ENDPOINT_PATH`, the production tenant path. Before, it expected the tenant-less `/oauth2/v2.0/token`, which the peer's exact-path check would refuse.
  - Status 400, `Content-Type: application/json`, the 25-byte body `{"error":"invalid_grant"}`, auto framing and the orderly close_notify are unchanged.
  - New: `MS_INVALID_GRANT_EXCHANGE_COUNT = 1` and `ms_invalid_grant_connection_inventory()`.
  - The Google script and every other script byte are unchanged.
- **Suite (role 5):** a `CASE_IMPLEMENTATION_NOTES["NP-V-MS-INVALID"]` entry only. The declaration and oracle `token_rejected_after_unchanged_unit_rollback` (T06-INVALID-GRANT-MICROSOFT) are unchanged.
- **Runner (role 4):** `NP-V-MS-INVALID` is added to `IMPLEMENTED_CASE_IDS` and the mapper, with the new body `_run_np_v_ms_invalid()`. The body reuses the unchanged `_ms_refresh_provider_routes`, `_require_production_ms_token_path`, `_install_token_terminal_observer` and `_actual_token_terminals`, plus the production release-plan and ASGI ingress.
  - **Seed:** one expired Microsoft subscription on one account.
  - **Observers:** the `CoveringHTTP` constructor and request, the `token_terminal` observer and `CoveringRoleConnector.run_target` are each saved before installation and restored in `finally`, both inner and outer. The wrappers call the originals, return the same object, or re-raise the same exception object. Only the class name and module are recorded.
  - **STOP oracles, all before the receipt:**
    - exactly one `("POST", "oauth")` client request, whose outcome is exactly `("exception", "CoveringReauthorizationRequired", "app.services.covering_transport_policy")`;
    - exactly one native TOKEN row `{terminal: ROLLBACK_ACKNOWLEDGED, token_rollback_ack: True, commit_requested: False}`, with the observer marker row exactly once and kept apart;
    - `run_target` count 0;
    - HTTP 200, `overall_outcome` `no_op`, and one result row: phase `preflight`, status `preflight_rejected`, code `CALENDAR_ACCOUNT_DISCONNECTED`, effects `[]`, cause null, upserted 0;
    - `action_summary` with requested 1, preflight_rejected 1, and import attempted, ok and failed all 0;
    - separate fresh before and after native sessions show the semantic seed, refreshed and rotated booleans and the exact stored expiry unchanged, and coverage state equal;
    - the peer admitted and served 1, with one POST at the tenant path, request received, response sent, close mode `orderly_close_notify`, and `bytes_sent == len(_http_response_bytes(step))`.
  - **Recorded only:** `coverage_action.all_requested_covering_ok`, `scheduling_ready` and `assessment_error`. I didn't derive their exact values from `_assemble_final_assessment` in this preparation, so they don't establish final-assessment correctness or coverage.
  - Ciphertext hashes are supplementary only. The public code and `no_op` alone prove nothing about OAuth rejection, persistence or native rollback.

## Bounds (nominal; caps, not observed timings)
- **Peer:** one owned peer, 120 s plus a 5 s retire join.
- **Provider PKI:** generation 30 s, reap 5 s, two 5 s reader joins: 45 s nominal retirement.
- **Suite and runner:** suite 900 s, runner 600 s. The request clocks are unchanged (work 210, request 240, cleanup 30, attempt validity 600).
- **Docker:** 32 commands at most, of which 22 are source-derived success commands (unchanged).
- **Output:** 1 MiB of combined streams per command, plus a separate 1 MiB report.
- **Excluded:** operator startup, the outer wrapper, file, hash and fsync work, and OS latency. The inherited Docker CLI kill semantics give no daemon-side cancellation guarantee and no wait.
- **Retirement:** owned peer and PKI retirement. Cleanup is success-only by exact ID, with no failure cleanup.
- Supervisor expiry is UNKNOWN, never PASS.

## Prerequisites (truthful status)
- **Peer-close fake v2:** PASS 11/35 with 4 mutants (result `911AC7A0`, reconciliation `4A5B51B5`).
- **T05 fixture fake v2:** PASS 14/74 (result `C4771F53`, reconciliation `C52971E5`).
- There is no native JoinedTLS, OAuth or refresh PASS.
- Those fake passes don't transfer to the changed transcript script or the new runner body. The focused fake `outputs/scheduler-native-ms-invalid-fake-prep-matt-v1` covers them.

## Proof boundary
Authored and statically reviewed only. Nothing native has run.
