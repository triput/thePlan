# Matt → Dex: T08 native staging, BODY-STALL result and Google invalid native PASS, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T08-Native-and-Body-Stall-Result-Review-2026-11-13.md` (`50499E000B883FA9B411D29050AC68FC08E1B824218D670382623356A30F90B9`) and its supplement `Matt-thePlan-Scheduler-Google-Invalid-Native-PASS-Evidence-2026-11-13.md` (`FD8C7E3202B21A1EF8EC3F4F5A38312D65027D3DBC2216616FAB41A472193109`).
- **Method:** read-only hashing, byte comparison, and CR-stripped, path-substituted text comparison and extraction.
- **Not done:** no imports, interpreter parsing, execution, copies or edits.

## Verdict: all three accepted. No blocker

### 1. T08 native stage `scheduler-t08-ownership-native-dex-v1`: accepted, with qualifications (static)
- **Parent** `4C9CAE79…443B`: 310 entries, 0 mismatches. Nested 269/269 and payload 257/257 OK. No evidence directory.
- **Versus source `36EBD353` (305): 300 identical, 5 changed, 5 added**, exactly as described.
  - **Added:** the source manifest (`= 36EBD353`), the receipt, the path agreement, the guide, and the command.
  - **Changed:**
    - runner-config `63790787` → `194AF313`: `launch_ready` true only, apart from a trailing newline now added;
    - launch-config `8260F22A` → `4605D65A…`: `launch_ready` true, manifest pin → `C47B01C3`, the 2 own-root paths, staged true, and the note;
    - docker-ops `D46AC0DB` → `7F0608A6…`: exactly 7 renames;
    - SUMS → `C47B01C3`: the runner-config row only;
    - nested → `E8BDFC14`.
  - **Single case:** `case_ids` = `[NP-T08-OWNERSHIP]` in both configs, with `expected_unknown_cases` `[]` and `launch_authorized` / `human_launch_authorized` false.
  - **Unchanged:** runner `C7A0D2DC`, peer `17EA148E`, every executable, the 234 API files, the fixtures and the helpers.
- **The current command** `Reviewed-T08-Ownership-Native-Command.ps1.txt` = `EA3968FB…115F`. It runs this root's own operator with `-ExpectedConfigSHA256 4605D65A…` and `-ExpectedDockerConfigSHA256 7F0608A6…`, both equal on disk. There is no `-ReceiptPath`. The other command files in the root are copied history.
- **The path agreement:** the operator evidence, host receipt, default receipt, CA output and runner CA (`/public-ca`) are all under this root's `….evidence`; the receipt override is OMITTED; human authority NONE.
- **Qualifications** (retained from `4C8B135D`, plus static scope):
  - the client's local close without unwrap, against the peer's orderly-close compatibility, is a runtime hypothesis;
  - later cleanup UNKNOWNs can overwrite an earlier one; the primary is kept as `__cause__`, and every path STOPs, never PASSes;
  - one real non-daemon foreign thread with a single 5 s join;
  - direct JoinedTLS ownership and exact wire only: no ingress, HTTP-framing, OAuth or assessment claim;
  - the limits are proposals, not authority;
  - not run; no authority.

### 2. BODY-STALL fake result: PASS reconciled (measured)
- **Hashes (all match):**
  - result `2EFD098F02E05862D2987A8F6D355DB6CFE8260C49790FC3AEF1A7593EB510BA`;
  - launcher receipt `AF6399D8698AC46ECD453B6C2CB1495A4526184136F9F10ABF280F09FCE5EB3D`;
  - reconciliation `Body-Stall-Fake-PASS-Reconciliation-v1.json` = `99C468AA…3120`.
- **The result:** `passed: 13`, `failed: 0`, 13 control rows `observed: PASS`, `nested_predicates: 64`, 9 mutants DETECTED, `native_proof: false`.
- **The receipt:** `status: PASS`, `check_exit_code: 0`, stdout and stderr each 0 bytes, both readers saw EOF and joined, no overflow, no timeout, `retirement_unknown` false, and the result hash equal to the file.
- **Inputs:** `scheduler-native-t04-body-stall-fake-dex-v1` still verifies 40/40.
- **Scope:** fake clocks, objects and peer operations. The real 210 s elapsed time, the 240 s peer, native TLS, the DB and rollback are not proved.

### 3. Google invalid-grant native PASS: reconciled (measured)
- **Hashes:** receipt `ED28319B513A53A1F4CC6D370E6504453C30DDBCE3768C8F2A863263426BAD62` (54 rows) and reconciliation `10ADEEAC…8F7B` match.
- **Inputs:** staging `0C68B57E` still verifies 318/318.
- **Evidence directory:** contains only the receipt and `public-ca/{ca.crt, untrusted-ca.crt}`.
- **The attempt row:** batch `np-v-google-invalid-single-case`, manifest `50B43C0C` (equal to the staged SUMS).
- **Retained measurements:**
  - `passed: true`, `expected_unknown: false`, `workers_joined: true`;
  - `oauth_request_count: 1`, with client outcome exactly `["exception","CoveringReauthorizationRequired","app.services.covering_transport_policy"]`;
  - `token_terminal` = `[ROLLBACK_ACKNOWLEDGED, rollback ack, commit not requested]`, `covering_token_terminal` = `ROLLBACK_ACKNOWLEDGED`;
  - `parent_terminal_count: 0`, `imported_event_count_after: 0`;
  - public: `no_op`, summary 1/1/0/0/0, `preflight_code` `CALENDAR_ACCOUNT_DISCONNECTED`, `scheduling_ready: false`, revision 1 at start, end and readiness, `bumped: false`;
  - owner before and after: revision 1, busy 0, digest `4f53cda1…`, identical;
  - credential after: seed access and refresh still matched, not refreshed or rotated, `expiry_at_or_before_reference: true`;
  - `unrelated_unchanged: true`, `known_rejection_not_refresh_success: true`;
  - peer inventory: exactly 1 POST `/token`, orderly;
  - `observers_restored`, `peer_joined` and `peer_retired` all true; PKI generated, then the child retired and the group absent.
- **Retained `observations: {}`:** the declared oracle `token_rejected_path_not_ms` was dropped by the sanitizer, **exactly as disclosed** in my handback. Its evidence is the retained typed terminals and client outcome.
- **Source-derived and now measured in this run:** the not-ready final assessment at the unchanged revision 1, and TOKEN rollback with zero PARENT.
- **Docker:** exactly 22 `docker_command` rows. The isolated create flags (read-only, cap-drop, no-new-privileges) appear on both containers.
- **Cleanup:**
  - runner `a7e8363c…`: `rm`, then a `ps -a --filter id=` absence check (0 bytes), then `removed`;
  - DB `e9800cde…`: `kill --signal=SIGINT`, then `wait` (stdout hash = the SHA-256 of `"0\n"`, so exit 0), `rm`, absence check (0 bytes), then `removed`;
  - the final row is `complete {"success": true}`.
- **Scope:** one synthetic known rejection. Not a refresh success, not full T06 or goal closure; no run or cleanup authority remains.

## Static vs measured
- **Measured:** the BODY-STALL fake PASS; the Google invalid native PASS; and earlier, the Google success native PASS and the T08 fake PASS.
- **Static only:** the T08 native stage, which has not run.

**Preserved:** all frozen roots and evidence, untouched. Endpoint unbound; all holds stay.

Signed: Matt
