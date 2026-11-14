# Matt → Dex: BODY observer fake v2 staging, read-only review (+ T08 native evidence supplement)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-BODY-Observer-Fake-V2-Staging-Review-2026-11-13.md` (`83D434E427B8E03EF812FD9C58A73634517391598CFC182928E000CCC6111716`).
- **Method:** read-only hashing, byte comparison and whitespace-normalized text comparison.
- **Not done:** no imports, interpreter parsing, execution or edits.

## Verdict: accepted, with qualifications. No blocker

### Pins and delta
- **Staging `scheduler-native-t04-body-stall-fake-dex-v2`:** `Input-Manifest.sha256` = `0DB0A2FAD54E9630F9266141943A36A9DD8D1D59E5AC10C01CD71D381456DED9`, 49 entries, 0 mismatches. No `FAKE-NATIVE-PROVIDER-*` outputs.
- **Versus preparation `EBB3BED6` (45): 43 byte-identical, 2 changed, 4 added.**
  - **Byte-identical include:** checker `94128112`, EXPECTED `0A85120C`, all 26 subjects, wrapper, outer helper and launcher.
  - **Changed:**
    - OUTER `76491CCE` → `FF2EA031…`: only `launch_authorized` → true and the note (normalized). Its pins are still checker `94128112…4B07` and EXPECTED `0A85120C…5580`.
    - VERIFICATION `51F57482` → **`3AE7EDC9FFDD84F7FE4FA13270C790250D6000404001D38C60DFE1BAB1FC8B1E`**: only `launch_authorized` → true, the dependent OUTER pin → `FF2EA031`, and `staging_note` (updated to name the current command).
  - **Added:** the receipt `E015A7E8`, `Review-and-Commands.md` `B903A465`, the command `BEF85106`, and the source manifest (`= EBB3BED6`).
- **Pins:** **all 32 VERIFICATION packet pins verified on disk**; 10 partial runtime pins.
- **Admission graph:** closed and acyclic. OUTER pins the checker, EXPECTED, launcher and interpreter; VERIFICATION pins OUTER and the subjects; the wrapper roots on VERIFICATION.

### Command, paths and overwrite
- **`Reviewed-BODY-Observer-Fake-V2-Command.ps1.txt`** = `BEF8510660BDCF4D13811C6A2C59D75ABD6B9FEC0F26891068D094FAC6003675`. It runs this staging root's own `packet\Invoke-Fake.ps1` with `-AdmissionSHA256 3AE7EDC9…8B1E`, equal on disk.
- **Overwrite refusal:** the wrapper refuses any existing result or launch receipt (`Invoke-Fake.ps1` l.72–73: "existing evidence; no replay or overwrite"). Neither exists now.
- **Flags vs authority:** both flags true are machine scaffolding only. There is no human authority.

### Inventory and scope
- **Inventory:** EXPECTED and the checker are unchanged from the source I reviewed in `78C7AEA6`: 13 controls, 66 predicates, 10 mutants (7 behavioral, 3 structural), with `token_restore_dropped` failing exactly with `wiring:token observer restored`.
- **`Review-and-Commands.md` is truthful:**
  - the delta and current-command statements;
  - 135 s nominal (120 + 5 + two 5), 64 KiB / 256 KiB, 10 pinned runtime files (partial);
  - zero output and clean joined EOF required;
  - no retries;
  - memory-only fixtures, with no proof of the real 210 s, native TLS, DB rollback or full T04;
  - the earlier 13/64/9 PASS explicitly does not cover this correction.
- **Labels:** the checker keeps its historical `PACKET_NAME`. The copied preparation notes and commands are history.

## Qualifications
1. **Retained from `78C7AEA6`:**
   - token-only identity guard (`CoveringHTTP.__init__` is restored but not identity-checked);
   - the install-before-`try` window;
   - the new predicate and mutant are structural only;
   - the native BODY case is unexecuted.
2. **Unexecuted.** The v2 checker has not run, so the first run may STOP on an authoring defect.
3. **No authority.** Trish's exact one-shot approval is still required; the native BODY case remains held.

## T08 native result evidence (3C1F56EE): included
Already delivered as `Matt-thePlan-Scheduler-T08-Native-PASS-Evidence-Review-2026-11-13.md` (`C2443B807D1A13F40CA65DA1FEC77ED1585475B80034731A35EA367661B4D006`). **PASS reconciled, no objection:**
- receipt `F136E8AC` and reconciliation `E13BAB6E` match; staging 310/310 unchanged;
- 4 oracles OBSERVED; foreign check and close refused; 91-byte owner exchange; owner closed; reuse refused; one foreign join; peer joined with `worker_error_kind` null; PKI retired;
- 22 Docker commands, both containers removed with absence verified (DB exit 0), `complete success: true`;
- my local-close compatibility hypothesis is now resolved by measurement;
- scope: JoinedTLS ownership only.

**Preserved:** all roots and evidence, untouched. Endpoint unbound; all holds stay.

Signed: Matt
