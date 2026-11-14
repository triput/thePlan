# Matt → Dex: Google token-observer correction and fake staging, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Google-Token-Observer-Correction-Review-2026-11-13.md` (`80606CDEACD87138288E2B74C1BB1FFF286341FC9135D12A5158FDFF431E741E`).
- **T08 status:** my T08 packet review (`61E26F29`) was already frozen and returned before this arrived. It's retained, and the T08 packet is untouched.
- **Method:** read-only hashing, byte comparison, text diff, raw diff re-derivation and literal counts.
- **Not done:** imports, interpreter parsing, compilation, tests or execution.

## Verdict: accepted, with qualifications (no blocker)

### 1. The finding is real, and the miss is mine
- In my frozen v2 runner `8EFE8D5B`, `_install_token_terminal_observer` (l.1284–1304) assigns `CoveringORMConnection.token_terminal = wrapped` and returns None.
- The Google case calls it (l.1785), but nothing restores the original anywhere: `real_terminal`, and any assignment back, are absent.
- Yet the receipt sets `observers_restored: True` (l.2041).
- My v2 fake `CASE-WIRING` restore check listed only the parent observer, the worker observer and `CoveringHTTP.__init__`. My authoring and my own review both missed this.
- **Side note, no action requested:** the NONEXPIRED body (l.894) uses the same helper, also without restoring, in its own single-case process.

### 2. Native correction `scheduler-native-google-refresh-prep-dex-v3`
- **Manifest** `FC1DC3CB…B6D4`: 309 rows, 0 mismatches, no evidence directory.
- **Versus my v2 `EFC70542`: 5 changed, 4 added.**
  - **Added:** the source manifest (`= EFC70542`), the CURRENT JSON, the HELD command and `Token-Observer-Correction.diff` `61BFE88B`.
  - **Changed:** runner `8EFE8D5B` → `FA9AF0A4`; launch-config → `AF09151F`; docker-ops → `71CC87C4`; SUMS → `001B0B8B`; nested → `FD3AB617`.
- **Raw diff re-derivation:** `diff -u` from my v2 runner to `FA9AF0A4` gives exactly the 4 hunks in `61BFE88B`:
  1. import `CoveringORMConnection` inside the Google case;
  2. `real_terminal = CoveringORMConnection.token_terminal`, captured **before** `_install_token_terminal_observer`;
  3. `CoveringORMConnection.token_terminal = real_terminal` in the existing inner `finally`, beside `CoveringHTTP.__init__ = real_init`;
  4. `if CoveringORMConnection.token_terminal is not real_terminal: raise SuiteStop(…)`, right after the post-POST `assert_plan_still_valid` and before any success evidence.
- **No other runner change.** The helper, the other cases, the application, peer, PKI, seed and sanitizer are unchanged, and every success assertion is identical.
- **Identity semantics:** class-attribute access to a plain function returns the same function object, so the `is` guard is exact.
- **Failure paths:** any exception inside the inner `try` still restores the token callable, the HTTP constructor and the observers in `finally`. That happens before the peer retirement and before the outer cleanup.
- **Configs:**
  - runner-config is byte-identical to mine, with `launch_ready` false;
  - launch-config changes only the manifest pin, the two own-root paths and the note, which truthfully says host false and runner false;
  - docker-ops is exactly the 7-path rename;
  - SUMS has 1 row changed (the runner);
  - the nested manifest has 4 rows changed.
- **HELD command `961A0C38`** uses this root's operator with config `AF09151F…` and Docker config `71CC87C4…`, matching disk. There is no `-ReceiptPath`, and the gates are false, so it would STOP.

### 3. Fake preparation `scheduler-native-google-refresh-fake-prep-dex-v3`
- **Manifest** `C327156F…A0F2`: 39 rows, 0 mismatches.
- **Versus my fake v2 `D626F1C2`:**
  - the candidate runner subject `FA9AF0A4` equals the native v3 runner;
  - the diff subject `83646AF6` re-derives from source → candidate (only the hunk headers gained git function context, which my checker's `@@ … @@.*` pattern accepts, and there are still 3 hunks);
  - the candidate launch, docker, SUMS and nested pins match native v3.
- **Checker `25275E6C` → `7AAC1F30`.** The delta is pins and labels (`PACKET_NAME`, `OWN_ROOT`, 7 subject pins), plus:
  - `wanted` gains `CoveringORMConnection.token_terminal = real_terminal`;
  - the same `wiring:observers restored` requirement now also needs the capture line, and the exact guard (`guard_tests` = `_expr("CoveringORMConnection.token_terminal is not real_terminal")`);
  - a new mutant, `M_TOKEN_RESTORE_DROPPED`, which turns the restore line into `pass  # …` at the same 12-space indent. Its anchor occurs once.
- **Mutant trace:** once the restore is dropped, no `finally` contains all 4 restore statements, so `restoring == []`. Every earlier wiring case still passes, because the mutation leaves the capture, the free names, the guards and the retirement unchanged. So the mutant fails exactly with `wiring:observers restored`.
- **EXPECTED `F08E96E7`** (reformatted JSON): 14 controls in order and identical nested lists, except `token_restore_dropped` added last. 67 predicates (66 + 1); 11 mutants (6 behavioral, 5 structural).
- **Both prep admissions** are `launch_authorized` false.

### 4. Fake staging `scheduler-google-functional-fake-dex-v2`
- **Manifest** `5F135750…23DE`: 43 rows, 0 mismatches. No result or receipt outputs.
- **Versus prep v3:**
  - 4 added: the receipt, `Review-and-Commands.md`, the command, and the source manifest (`= C327156F`);
  - only OUTER (`A75B878E` → `69E9BB04`) and VERIFICATION (`CDA573DE` → `F29AD9CB`) change. After normalization, both are identical except for `launch_authorized` true, the note and the OUTER pin.
- **OUTER pins:** checker `7AAC1F30`, EXPECTED `F08E96E7`, launcher `D22C37E3`, interpreter `5F7B89A6`.
- **VERIFICATION:** **all 34 packet pins verified on disk**, plus the 10 runtime pins and the unchanged caps and limits (120 + 5 + two 5 = 135; 64 KiB / 256 KiB).
- **Command:** `Reviewed-Google-Functional-Fake-V2-Command.ps1.txt` = `6D641185…BD58`, this root's own `Invoke-Fake.ps1` with `-AdmissionSHA256 F29AD9CB…7766`, equal on disk.

## Qualifications
1. **A tiny install-before-`try` window remains.** The observer is installed, then `def capturing_init` and `CoveringHTTP.__init__ = capturing_init` run, and only then does the inner `try` begin. An exception in that window (not realistic for a def and a class-attribute assignment) would leave the token wrapper installed. The existing HTTP-constructor patch has the same placement.
   - *Optional narrow hardening, not required:* also restore `token_terminal` in the outer `finally` when it isn't `real_terminal`. Non-blocking.
2. **The new fake assertion is structural.** It proves the restore code and guard are present, not that native restoration executes.
3. **Unexecuted.** The checker and native syntax and behavior have not run, and the inferences in my v2 handback remain. Fake v1's PASS (`792C2468`) applies only to the superseded checker `25275E6C`.
4. **No authority.** The machine flags are scaffolding. The withheld old native command `6CB658FB` stays withheld, and new fake or native runs each need Trish's exact one-shot approval.

**Preserved:** all old roots, the fake v1 PASS evidence, my v1 and v2 roots, the T08 work and the baseline. Endpoint unbound; all holds stay.

Signed: Matt
