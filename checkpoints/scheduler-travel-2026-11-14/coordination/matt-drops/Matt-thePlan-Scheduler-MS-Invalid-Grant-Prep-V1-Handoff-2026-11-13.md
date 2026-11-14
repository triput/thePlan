# Matt → Dex: NP-V-MS-INVALID preparation v1 (native fixture and focused fake), HELD and frozen

November 13, 2026. This responds to `Matt-thePlan-Scheduler-MS-Invalid-Grant-Preparation-2026-11-13.md` (`66D016138E4B51CBA41BCCB7B7A091E754F57D225E1729EE6B829F30B08EEA54`), under lane `389A00DD…7E2D`, implementing design `74F493D8`.

**Status:** PREPARED_NOT_EXECUTED. Both roots are frozen with no active writer, and all gates and admissions are false. The endpoint is unbound.

**How it was built**
- Ordinary text, hash, JSON, copy and edit authoring only.
- Nothing was imported, AST-parsed, compiled, tested or invoked.
- My only verification was sha256 manifest checks and a `patch` text round-trip of the four diffs into scratch.
- JSON string spellings were text-reviewed for Windows path escaping. One heredoc collapsed `\\` to `\` in OUTER during authoring; I caught it and rewrote the file exactly before pinning.
- No subagents were used. All predecessors are preserved.

## 1. Native root `outputs/scheduler-native-provider-ms-invalid-prep-matt-v1`
- **Copy:** the 292 T05 v3 inputs (`B773B95E…`), verified 292/292. The lineage manifest is `Source-T05-Prep-V3-Input-Manifest.sha256`.
- **Changed roles 4, 5 and 8, plus data (full SHA256):**
  - runner `1D70164C…` → **`ACD7F4493492DC01406558374E4B2EC46E8CDDA59FAE4FD2195FC0B154006FF1`**;
  - suite `9AED74EE…` → **`DAB88CB352189411EED6A2181417CB813D592406598D89192FF307E9081205A1`** (implementation note only; the 31 declarations and 76 planning IDs are unchanged);
  - transcript `562F61CD…` → **`BEDCCFD3C3E8F776C4EC0B3379F863E976C73AF350DD6AE8B308518AB4A47735`**;
  - runner-config `96782CB4…` → **`10106B8278033FC0DBC83D5841446F2D2B7476960C90DB654AF4AAF25549E004`** (`case_ids ["NP-V-MS-INVALID"]` only).
- **Unchanged:** peer `BFB271D7`, seed `2ADFA3AD`, all 234 API files, the operator, supervisor and Docker helper, and the T05, refresh and nonexpired runner units (text-identical).
- **Re-pinned:**
  - payload `SHA256SUMS.txt` **`8A1FCA71DBD9DB51293E36691DD8DAB1757BB4CCD1A84E1C2F3636CA3F5B880D`** (257, 0 mismatches);
  - launch-config **`5ECEBDF37270C9ADBB46573C3507FA25354189188FEB79CF167E2155A95A3D4D`**: root rename, `batch_id np-v-ms-invalid`, `case_ids`, `implemented_case_ids` plus `NP-V-MS-INVALID`, the payload pin and the candidate note; all gates false;
  - docker-ops **`B9FF7DCAA10657964398924754F179AFDF1EEB8FCAF6838E34AEBED36BBBFDE2`** (root rename only);
  - nested **`5D2B94D040EE18E6E3D8C52A98915CCF3DFC9F5738B22830A65CF5A286BA4D66`** (269; exactly 7 rows changed);
  - parent **`DA1143947EC03F61C02171A4339283AF1D44CB623B43472E7737EBAABDCD11FA`** (296; 8 changed and 4 added versus v3).
- **Current docs:** `MS-INVALID-PREP-README.md`, `MS-Invalid-Prep-Freeze.json` and `MS-Invalid-Native-Command-HELD.ps1.txt` (`-ExpectedConfigSHA256 5ECEBDF3…`, `-ExpectedDockerConfigSHA256 B9FF7DCA…`, this root's docker-ops path, no `-ReceiptPath`). **Not authorized.**
  - The copied `T05-*`, `MS-Merge-*`, `Peer-Close-*` and `Worker-*` documents are labelled as history in the README.

## 2. What changed, reconciled to your qualifications
1. **Transcript (Q1):** only `ms_token_invalid_grant_script` changed, and only its request path, which is now `MS_TOKEN_ENDPOINT_PATH`.
   - Status 400, Content-Type, the 25-byte object, auto framing and the orderly close are unchanged.
   - Added: `MS_INVALID_GRANT_EXCHANGE_COUNT = 1` and `ms_invalid_grant_connection_inventory()`.
   - Google and every other script byte are unchanged.
   - **The wire oracle is derived from source:** the fake runs the unchanged peer serializer and requires the exact bytes and equality with the source script's send step.
2. **Send state (Q2):** the fake no longer uses method names as shorthand.
   - `FakeTransport.send` marks `sent=True` **before** raising, mirroring the actual `JoinedTLS.send`. That order is a separate structural check, with a mutant that reorders it.
   - A send failure gives UNKNOWN. Only an open failure with `sent=False` gives the original exception, which a mutant ignoring `transport.sent` breaks.
3. **Terminal rows (Q3):** the oracle requires exactly `[{"terminal": "ROLLBACK_ACKNOWLEDGED", "token_rollback_ack": True, "commit_requested": False}]` from `_actual_token_terminals`, and the observer marker row exactly once, kept apart. A COMMIT, extra, missing or wrong-acknowledgement row STOPs.
4. **Observers (Q4):**
   - **Saved before installation:** `CoveringHTTP.__init__`, `CoveringORMConnection.token_terminal` and `CoveringRoleConnector.run_target` are saved.
   - **Restored:** all three are restored first in **both** the inner and outer `finally`; the transport request is restored too.
   - **Identity preserved:** `counted_request` records only the class name and module, then re-raises the same object or returns the same result. `counted_run_target` returns the original's value.
   - **No changes to behavior:** nothing changes provider, result or transaction behavior, and there are no new messages or public codes.
5. **Measurements (Q5):** two separate fresh native setup sessions, before and after.
   - The before session requires the seed booleans `True` and refreshed/rotated `False`.
   - The after session requires those booleans **and the exact `expiry` string** to equal before, plus coverage state equal.
   - Also required: `run_target` count 0, exactly one OAuth POST with the typed class, and one peer exchange.
   - Ciphertext hashes are supplementary only.
6. **Assessment fields (Q6): recorded only.** `coverage_action` and `scheduling_readiness` (`all_requested_covering_ok`, `scheduling_ready`, `assessment_error`) are recorded but not asserted. I didn't derive them from `_assemble_final_assessment` in this preparation, and they establish nothing about final-assessment correctness or coverage.
   - **Asserted from source:** HTTP 200, `overall_outcome` `no_op`, the one preflight row (`preflight`, `preflight_rejected`, `CALENDAR_ACCOUNT_DISCONNECTED`, `[]`, null, 0) and `action_summary` requested 1 / preflight_rejected 1 / import 0/0/0.
7. **The fake (Q7):** see §3.
8. **Bounds (Q8):**
   - one owned peer, 120 s plus a 5 s join;
   - provider PKI 30 s, plus 5 s reap, plus two 5 s reader joins: 45 s nominal;
   - suite 900 s, runner 600 s;
   - 32 Docker commands at most, 22 of them source-derived success commands (unchanged);
   - 1 MiB of combined streams per command, plus a separate 1 MiB report.
   - **Excluded:** startup, outer wrapper, file, hash and fsync work, and OS latency. The inherited Docker CLI kill semantics mean no wait and no daemon-side cancellation guarantee.
   - **Retirement:** owned peer and PKI retirement; cleanup is success-only by exact ID, with no failure cleanup. The operations are the same as the existing batch shape, so no cap was recomputed or widened.
9. **Prerequisites (Q9):**
   - peer-close fake v2 PASS 11/35 with 4 mutants (result `911AC7A0`, reconciliation `4A5B51B5`);
   - T05 fixture fake v2 PASS 14/74 (result `C4771F53`, reconciliation `C52971E5`).
   - Both apply only to their unchanged units.
   - There is no native JoinedTLS, OAuth or refresh PASS.

## 3. Fake `outputs/scheduler-native-ms-invalid-fake-prep-matt-v1`
- **Immutable lineage:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3` (byte-identical). No new executable prep helper.
- **New:**
  - checker **`5EF756D2A57A42D320C59F5A74E75466F329D0AD2A2F883D110B954D7EB9FF29`**;
  - EXPECTED **`ACAE496EB81141FD563FAFB258A30509F1F0051C6F6FC3E50FF46872933F69F2`**;
  - OUTER **`2368640E758767EDB194CC3D5C9F05D4D8A8531BDCDD0D7A7A60650CC0670E5A`**;
  - VERIFICATION **`C17C8884266AF27C17B75D1B45A3343E6C1FFB627F187690A816A3000048DB77`** (31 packet and 10 runtime pins, all re-verified by hash; both false);
  - manifest **`B5183A403276CE08850B72AB76EE3D8B284EE394887C3426B007B199F46A5167`** (34).
- **Subjects (25):** the source/candidate runner, transcript, suite, runner-config and manifest; four diffs (3/2/1/1 hunks); seed; peer; the candidate launch-config; and 8 unchanged application files.
- **Inventory: 12 controls, 65 nested.** The breakdown is SUBJECT-PINS 1 + RUNTIME 7 + DIFF 4 + PRESERVED 3 + SCRIPT-SELECTION 5 + CLIENT-OAUTH 12 + OWNING-REFRESH-UNITS 4 + PUBLIC-RESULT 4 + RUNNER-WIRING 9 + BATCH 3 + PRIOR 3 + MUTANTS 10.
- **Kinds of check:**
  - **Behavioral host parser (actual policy and transport, actual `http.client` and `json`):** 11 client cases.
  - **Behavioral extracted units with named fakes:**
    - `get_valid_access_token`: one POST, then a raise before any write, flush, validation, encrypt or decode;
    - adapter `token`: `TokenRejected` plus exactly one `commit=False`; a wrong terminal gives UNKNOWN; another exception propagates;
    - the `_static_preflight_result`/`_result_row`/`_derive_overall_outcome` row and `no_op`.
  - **Structural:** PRESERVED; RUNNER-WIRING (9); `JoinedTLS.send` order; and dispatch skipping `run_target` after `TokenRejected`.
  - **Mutants:** 5 behavioral (path reverted, any 400 accepted, send state ignored, adapter `changed=True`, adapter `except` removed) and 5 structural (JoinedTLS order, terminal row COMMIT, observer restore removed, `counted_request` swallows, two subscriptions).
  - The host parser is not native TLS.
- **Held command:** `Future-Command-HELD.ps1.txt` → `…\scheduler-native-ms-invalid-fake-prep-matt-v1\packet\Invoke-Fake.ps1 -AdmissionSHA256 C17C8884…`. `Launch-Decision.md` describes the current packet. **Not authorized.**

## 4. Exact diff (Matt-Drops)
`Matt-thePlan-Scheduler-MS-Invalid-Grant-Prep-V1-2026-11-13.diff` (`D0BE4BB477AE16712A7A2E11E1158BAE4E729540983BE9D03DEF78A72E454D87`): from T05 v3 to MS-invalid v1 for the runner, transcript, suite and runner-config. These are exactly the fake's four subject diffs.

## 5. Remaining gaps
- **No PASS yet:** the fake has not run.
- **Native-only properties are unproved:** native TLS read and close, the runtime client class, the PostgreSQL ROLLBACK acknowledgement, persisted state, the ASGI response, and peer and PKI retirement.
- **Assessment fields:** exact `coverage_action`/`scheduling_readiness` values are recorded only.
- **Not covered:** Google invalid_grant (its script path is unexamined), and non-invalid_grant native negatives.
- **Launch requirements:** a launch would need the fake PASS, a reviewed staging copy, Dex's EXECUTE acknowledgement and Trish's one-shot approval.

## Preservation
All verify at 0 mismatches:
- T05 native v1, v2 and v3 (`704A16D1`, `C36E3078`, `B773B95E`);
- T05 fake v1, v2 and v3 (`4C556393`, `C1FB0387`, `090D0758`);
- MS-merge NONEXPIRED `22AE4F82` and REFRESH `9A62B5C4`.

There's no evidence root and no result or receipt in the new packet. I didn't touch the native peer-close decision pending with Trish. The endpoint is unbound, and all holds stay.

Signed: Matt
