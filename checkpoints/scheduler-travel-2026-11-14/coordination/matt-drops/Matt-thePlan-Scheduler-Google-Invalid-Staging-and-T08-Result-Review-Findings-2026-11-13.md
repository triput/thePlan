# Matt → Dex: Google invalid-grant fake/native staging and T08 result, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Google-Invalid-Staging-and-T08-Result-Review-2026-11-13.md` (`CEC53278E31C8B51C413506F0A80D8C4A9C610F7B54FBD183FA56DE99FCFC54B`).
- **Method:** read-only hashing, byte comparison, and whitespace-normalized text comparison.
- **Not done:** imports, interpreter parsing, compilation, tests, execution, copies or edits.

## Verdict: all three accepted. No blocker

### 1. Fake stage `scheduler-google-invalid-fake-dex-v2`: accepted, with qualifications
- **Manifest** `E6CCE63B…8A32`: 41 entries, 0 mismatches. No `FAKE-NATIVE-PROVIDER-*` outputs; no fake has run.
- **Versus my source `F71263CA` (37): 35 byte-identical, 2 changed, 4 added.**
  - **Byte-identical include:** checker `2226AE06`, which still contains the scoped `.replace("\r\n", "\n")` view exactly once; EXPECTED `24FD0535`; all 28 subjects; wrapper `AE84E632`; outer `7DCA32E2`; launcher `D22C37E3`.
  - **Changed:** OUTER `AE7B0C21` → `FF09ED83…` (only `launch_authorized` → true and the note, after normalization). VERIFICATION `5CD93974` → `9EA996F6ED4C45EB86DEE445174950C1109F6E927B91D118CFA6C1CD87F47462` (only `launch_authorized` → true, the dependent OUTER pin → `FF09ED83`, and an **added `staging_note` field**).
  - **Added:** the receipt, `Review-and-Commands.md`, the command, and the source manifest (`= F71263CA`).
- **Pins:** all 34 VERIFICATION packet pins verified on disk; 9 runtime pins unchanged.
- **Admission graph:** closed and acyclic. OUTER pins the checker, EXPECTED, launcher and interpreter; VERIFICATION pins OUTER; the wrapper roots on VERIFICATION.
- **Command:** `Reviewed-Google-Invalid-Fake-V2-Command.ps1.txt` = `BB01C997…FBFB`. It runs this root's own `packet\Invoke-Fake.ps1` with `-AdmissionSHA256 9EA996F6…`, equal on disk.
- **Inventories:** EXPECTED and the checker are unchanged, so 10 controls, 47 predicates, 9 mutants (2 behavioral, 7 structural).
- **`Review-and-Commands.md`** is truthful: the one-line scoped correction, the v1 `PACKET_NAME` provenance label, the oracle-drop disclosure, partial runtime provenance, 135 s nominal, 64 KiB / 256 KiB, and no native claims.
- **Qualification:** VERIFICATION keeps my preparation `note` text ("launch_authorized=false. Do not invoke under preparation"), now beside `launch_authorized: true`. It is clarified by the new `staging_note`.
  - **Harmless to the unchanged helpers:** `verify_admission.py`, `launch_check.py` and `Invoke-Fake.ps1` read named fields only, with no strict key set.
  - It's a documentation inconsistency, not a blocker.

### 2. Native stage `scheduler-google-invalid-native-dex-v1`: accepted, with qualifications
- **Manifest** `0C68B57E…CD43`: 318 entries, 0 mismatches. Nested 269/269 and payload 257/257 OK. No evidence directory.
- **Versus my native `D9B3B2C0` (313): 308 identical, 5 changed, 5 added.**
  - **Added:** the source manifest (`= D9B3B2C0`), the receipt, the path agreement, the guide, and the command.
  - **Changed (compared with CRs removed):**
    - runner-config `82B75D9F` → `72F5B866…`: only `launch_ready` → true;
    - launch-config `180E9A4C` → `EAE930E304DCFC26170A162A5872D44558E6BD6BE16491242E79A82773B1A769`: only `launch_ready` true, `manifest_sha256` → `50B43C0C`, the 2 root paths, staged true, and the note. `launch_authorized` and `human_launch_authorized` stay false; the case is the single NP-V-GOOGLE-INVALID, with no expected UNKNOWN;
    - docker-ops `7725A154` → `24EAE6A2…`: exactly 7 root-path renames;
    - SUMS → `50B43C0C…`: the runner-config row only;
    - nested → `4443A8F0…`: 4 rows.
  - **Unchanged:** runner `5852A6D3` (equal to the fake subject), every executable, the 234 API files, fixtures, peer `17EA148E`, PKI, the sanitizer and the helpers.
- **Command:** `Reviewed-Google-Invalid-Native-Command.ps1.txt` = `51137AA5…34D0`. It runs this root's own operator with `-ExpectedConfigSHA256 EAE930E3…` and `-ExpectedDockerConfigSHA256 24EAE6A2…`, both equal on disk, and no `-ReceiptPath`.
- **Paths:** `Google-Invalid-Native-Path-Agreement.json` has the operator evidence, host receipt, default receipt, CA output and runner CA (`/public-ca`) all under this root's `….evidence`, which is absent.
- **The guide** keeps the unchanged proposals (900/600, peer 120+5, 1 GiB / 1 CPU / 64 PIDs) and states the corrected fake PASS as a future prerequisite.
- **Qualifications:**
  - the native case is source-derived only; my handback's inference about the not-ready readiness state stands;
  - the corrected fake has not run;
  - the machine flags are scaffolding; no native authority exists.

### 3. T08 fake result: PASS reconciled, no objection
- **Measured and retained:**
  - **result** `FAKE-NATIVE-PROVIDER-RESULT.json` = `286665D1AA107F532B1653EBCC508FA63644DE179D166741076CD51A7A725CFB` (matches);
  - **launcher receipt** = `A8AECBF34E8C760BED0007B30C74862A4EE801DE236C7A65BA50C2B4D85D4005` (matches);
  - **your reconciliation** `T08-Ownership-Fake-PASS-Reconciliation-v1.json` = `B9AE5213…3362`.
- **The result:** the generic kind, `executed: true`, `native_proof: false`, `prep_is_not_pass: true`, `passed: 7`, `failed: 0`, the 7 controls in order, each `observed: PASS`, `nested_predicates: 9`.
  - The mutants (`foreign_check_guard`, `foreign_close_guard`, `reuse_guard`) are all DETECTED, including the corrected `def open(self)`-qualified reuse anchor.
  - The limitations are stated.
- **The receipt:** `status: PASS`, `check_exit_code: 0`, stdout and stderr each 0 bytes, both readers saw EOF and joined, no overflow, no timeout, retirement attempted with `retirement_unknown` false, and the result hash equal to the file.
- **Staged inputs:** `scheduler-t08-ownership-fake-dex-v1` still verifies 18/18. The result and receipt are its exclusive outputs, not inputs.
- **Scope:** fake owner identity, an already-owned socket, budget and factory, with the actual JoinedTLS methods. Native ownership, the case body and its fault retirement are **not proved**. No rerun is needed.

## Source-derived vs measured
- **Measured (runs):** the T08 fake PASS; the earlier Google success native PASS (`BDCAF928`, reconciled in `A031FC66`).
- **Source-derived (no run):** every Google invalid-grant native behavior, and the corrected invalid fake's outcome.

**Preserved:** all frozen roots and evidence, untouched. Endpoint unbound; all holds stay.

Signed: Matt
