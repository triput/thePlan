# NP-V-MS-INVALID fixture: focused fake verification preparation v1 (HELD)

Matt, November 13, 2026. This is for `Matt-thePlan-Scheduler-MS-Invalid-Grant-Preparation-2026-11-13.md` (`66D01613…EA54`). It's the companion to the frozen `scheduler-native-provider-ms-invalid-prep-matt-v1`.

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`, and no PASS is claimed.

## Roles and pins
- **Reused byte-identical (lineage of every reviewed fake packet):** wrapper `Invoke-Fake.ps1` `AE84E632`, outer `verify_admission.py` `7DCA32E2`, launcher `launch_check.py` `D22C37E3`. No new executable prep helper.
- **New:**
  - checker `5EF756D2A57A42D320C59F5A74E75466F329D0AD2A2F883D110B954D7EB9FF29`;
  - EXPECTED `ACAE496EB81141FD563FAFB258A30509F1F0051C6F6FC3E50FF46872933F69F2`;
  - OUTER `2368640E758767EDB194CC3D5C9F05D4D8A8531BDCDD0D7A7A60650CC0670E5A`;
  - VERIFICATION `C17C8884266AF27C17B75D1B45A3343E6C1FFB627F187690A816A3000048DB77`, which has 31 packet pins and 10 runtime pins, all re-verified by hash.
- **JSON paths:** every Windows path string in OUTER and VERIFICATION is written with escaped `\\` and was checked by text review.
- **Runtime (partial scope):** the same 10 files as earlier fakes. Importing `http.client` loads `socket` and `ssl`, but no socket or SSL object is constructed.

## Subjects (25)
- **Source and candidate pairs** (T05 v3 source → MS-invalid v1 candidate): runner, transcript, suite, runner-config and payload manifest.
- **Their four diffs:** runner 3 hunks, transcript 2, suite 1, runner-config 1.
- **Unchanged supporting files:** role 10 seed, peer `BFB271D7`, the candidate launch-config, and 8 unchanged application files: `covering_http_transport`, `covering_transport_policy`, `covering_joined_https`, `microsoft_calendar`, `covering_domain_adapters`, `covering_refresh_import`, `covering_refresh`, `covering_domain_dispatch`.

## Controls: 12 top-level, 65 nested, in order
1. **SUBJECT-PINS** (1).
2. **RUNTIME-PROVENANCE** (7).
3. **DIFF-REDERIVATION** (4).
4. **PRESERVED-OUTSIDE-CHANGE** (3, structural): exact top-level partitions.
5. **SCRIPT-SELECTION** (5, whole-module fake):
   - the tenant path fix;
   - only the request path changed;
   - the exact 400 wire, derived from the unchanged serializer and identical to the source script's bytes;
   - the one-exchange inventory;
   - every other catalog script, including Google, is unchanged.
6. **CLIENT-OAUTH-CLASSIFICATION** (12; behavioral host parser except the last case):
   - the complete 400 invalid_grant object gives the typed `CoveringReauthorizationRequired`;
   - 400 with another error, 401, non-object, malformed, truncated, EOF after send, and a send failure each give UNKNOWN. The send-failure case has sent=True marked before the raise.
   - an open failure with sent=False gives the original exception;
   - a close failure after invalid_grant gives a new UNKNOWN with the reauthorization as primary;
   - under purpose `event`, the same body is not classified;
   - **structural:** `JoinedTLS.send` marks `sent=True` before `sock.send`.
7. **OWNING-REFRESH-UNITS** (4; extracted production units with named fakes):
   - `get_valid_access_token` sends one tenant-path POST and raises before any account write, flush, validation, encrypt or decode;
   - the adapter `token` returns `TokenRejected(CALENDAR_ACCOUNT_DISCONNECTED)` with exactly one `terminal(commit=False)`;
   - a wrong terminal gives UNKNOWN;
   - a non-reauthorization exception propagates without a terminal call.
8. **PUBLIC-RESULT-CONTRACT** (4):
   - the preflight row shape;
   - `no_op` when nothing was imported, and the `failed` outcome is distinct;
   - **structural:** dispatch's `TokenRejected` branch appends the preflight row and continues before `run_target`.
9. **RUNNER-WIRING** (9, structural):
   - default JoinedTLS;
   - observers saved before installation;
   - all three restored first in both the inner and outer `finally`;
   - the wrappers preserve the identity of the return value and of the re-raised exception;
   - the oracle constants are exact (including `token_rollback_ack`);
   - every STOP comparison comes before `check_oracles_immediate`, which comes before the receipt;
   - the single-subscription expired seed;
   - three setup sessions with separate before and after measurements;
   - the mapper and the five implemented IDs.
10. **BATCH-CONFIG** (3): runner config, launch config (single-case batch, gates false, own root, no foreign root, unchanged caps), and an exact 4-row payload delta.
11. **PRIOR-FAKE-APPLICABILITY** (3): T05 units identical, refresh units identical, peer and seed unchanged. **The non-transferred claims are listed in the result.**
12. **ACTUAL-SOURCE-MUTANTS** (10), each detected only by its targeted prefix:
    - **behavioral (5):** `path_fix_reverted`, `transport_accepts_any_400`, `send_state_ignored`, `adapter_except_sets_changed`, `adapter_except_removed`;
    - **structural (5):** `joined_marks_sent_after_send`, `terminal_row_commit`, `observer_restore_removed`, `counted_request_swallows`, `two_subscriptions_seed`.

## Not proved
- **Native behavior:** native TLS, the runtime native client exception, the native PostgreSQL ROLLBACK acknowledgement, persisted DB state, the ASGI response, and peer or worker retirement.
- **Not derived:** exact `coverage_action` and `scheduling_readiness` values; these are recorded only.

## Limits
- **Timing:** 120 s, plus at most one 5 s kill/wait, plus two 5 s reader joins: 135 s nominal.
- **Capture:** 64 KiB per stream; 256 KiB for the result.
- **Success** requires exit 0, no output, clean readers and the exact 12-control/65-nested inventory. A failure stops and preserves.

## Future command
`Future-Command-HELD.ps1.txt` (admission `C17C8884…DB77`). **Not authorized.**
