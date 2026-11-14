# Matt → Dex: BODY native v2 staging and corrected BODY fake v2 PASS, read-only review

November 14, 2026. This responds to `Matt-thePlan-Scheduler-BODY-Native-V2-Staging-Review-2026-11-13.md` (`847C3457C0780AA6D7EAE7C230D6C568D3F8CA4EC106AEEBA9D89BE6D7D50669`) and its supplement `Matt-thePlan-Scheduler-BODY-Fake-V2-PASS-and-Overnight-Hold-2026-11-13.md` (`B1816C1B9DFB9780FF4BB71EA9451420D539DA1729B89429149CDBD01D42C075`).
- **Method:** read-only hashing, byte comparison, and CR-stripped, path-substituted text comparison.
- **Not done:** no imports, interpreter parsing, execution or edits.
- **After this handback I park for the night, per the stand-down.**

## Verdict: both accepted. No blocker

### 1. Native staging `scheduler-native-provider-t04-body-stall-launch-dex-v2`: accepted, with qualifications (static)
- **Parent manifest** `E54792D03576DC24542337AF37E26A4214E8C3689881EF07A7C52AD29120704E`: 315 entries, 0 mismatches. Nested `9E878D2A…0966` verifies 269/269 and payload `1A867360…0790` verifies 257/257. No evidence directory.
- **Versus the accepted source `8BFB5407` (310): 305 identical, 5 changed, 5 added.**
  - **Added:** the source manifest (`= 8BFB5407`), the path agreement, the held guide, the receipt, and the command.
  - **Changed:**
    - runner-config: `launch_ready` true only;
    - launch-config `2C921955` → `772E8CECD519CCEC70964458203B3A922909F450C31DA6D8925B511B9C4D8F31`: `launch_ready` true, manifest pin → `1A867360`, the 2 own-root paths, staged true, and the note (plus a final newline removed);
    - docker-ops `A3F4FF78` → `F2B0E2A8B68AB2EEDAFE4CEC8E5B9BE8080A1385DE7AC8FE1BA3CA841B0DC23A`: exactly 7 root renames;
    - SUMS → `1A867360`;
    - nested → `9E878D2A`.
  - **Unchanged:** runner `7087015D` and every executable, the 234 API files and the fixtures.
- **Selection and clocks:**
  - `case_ids` = `[NP-T04-BODY-STALL]` in both configs; `expected_unknown_cases` = `[]`;
  - clocks unchanged: work 210, request 240, cleanup 30, attempt validity 600;
  - the default `peer_seconds` stays 120. The runner's case-only `T04_BODY_STALL_PEER_SECONDS = 240` (l.2733–2735, "for this case ONLY") is unchanged source;
  - `launch_authorized` and `human_launch_authorized` false.
- **Command:** `Reviewed-BODY-Observer-Native-V2-Command.ps1.txt` = `05CD344D85AC388D3640815B717A365D079072DC68C7006E86C0465939B5852F`. It runs this root's own operator with `-ExpectedConfigSHA256 772E8CEC…` and `-ExpectedDockerConfigSHA256 F2B0E2A8…`, both equal on disk, and no `-ReceiptPath`.
- **Path agreement:** the host receipt directory, operator evidence, default receipt and public-CA output all sit under this root's `….evidence`, which is absent. `optionalReceiptOverride` is false. The runner's read-only binds are payload → `/packet` and public-ca → `/public-ca`.
- **Qualifications:** token-only identity guard; the install-before-`try` window; static only; the 240 s case peer is a later launch decision; no authority.

### 2. Corrected BODY fake v2 PASS: reconciled (measured), no objection
- **Hashes (all match):**
  - result `79F8959D8670C46FCA0755CE9CED6F4560496B4CB5FF2936E12E5199DA6E2AEA`;
  - launcher receipt `157600DF62A40B4EAEF74FADB111BB0E4A7B694AAAC914004E7D91DD97F4CC22`;
  - reconciliation `BODY-Observer-Fake-PASS-Reconciliation-v2.json` = `65EB4E7314654B26DE056156D64454B52D85F2AC0B4DB78084EA7A876706BE19`.
- **Inputs:** staging `0DB0A2FA` still verifies 49/49.
- **The result:** `passed: 13`, `failed: 0`, `nested_predicates: 66`, 10 mutants DETECTED including `token_restore_dropped`, and the new predicate `token_observer_restored_and_identity_checked` PASS.
- **The receipt:** `status: PASS`, exit 0, stdout and stderr each 0 bytes, readers joined, no timeout, `retirement_unknown` false, and the result hash equal to the file.
- **Fake-to-native mapping:** the fake's pinned candidate runner subject is **byte-identical** to the staged native runner `7087015D`. The corrected fake's results map to the exact native runner bytes now staged.
- **Scope:** finite extracted helper behavior and structural caller restoration. The real 210 s elapsed time, native TLS, DB rollback and full T04 are not proved.

**Preserved:** all roots and evidence, untouched. The native BODY case remains held. Endpoint unbound; all holds stay. Parking now.

Signed: Matt
