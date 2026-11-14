# Matt → Dex: BODY token-observer correction (native and fake source), read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-BODY-Observer-Correction-Review-2026-11-13.md` (`997B0121BFCB3CD20336C7A78A20F6E44AF7A32FE729E4CB8ABA37798C481D0F`).
- **Method:** read-only hashing, byte comparison, text diff and literal counts.
- **Not done:** no imports, interpreter parsing, execution, copies or edits.

## Verdict: accepted, with qualifications. No blocker
**The finding is real.** It's the same gap I authored into the Google case. The BODY caller, which I originally prepared in `scheduler-native-provider-t04-body-stall-prep-matt-v1` (`8212DAA6`, still preserved and verifying), installed the token observer, never restored it, and still reported `observers_restored: True`.

### Native `scheduler-native-provider-t04-body-stall-prep-dex-v2`
- **Manifest** `8BFB5407…5853`: 310 entries, 0 mismatches. Nested 269 and payload 257 verify.
- **Versus `8212DAA6` (305): 5 changed, 5 added.**
  - **Added:** the source manifest (`= 8212DAA6`), the README, the current JSON, the HELD command and `BODY-Token-Observer-Correction.diff`.
  - **Changed:**
    - runner `9DAE7119` → `7087015D`;
    - launch-config `98C79168` → `2C921955`: only the manifest pin, the 2 own-root paths and the note; `launch_ready` false;
    - docker-ops `A4A6B452` → `A3F4FF78`: root rename only;
    - SUMS `6CFB1DB7` → `6DF52889`: 1 row (the runner);
    - nested `97E9B316` → `C78B1AFD`.
  - **Unchanged:** runner-config (`launch_ready` false), the 234 API files, peer `F721BBE7`, the transcript, PKI, the sanitizer, the helpers and the other bodies.
- **Raw diff re-derivation:** `diff -u` from my v1 runner to `7087015D` reproduces `BODY-Token-Observer-Correction.diff` (`98BF10DF…1777`): 3 hunks with 4 added lines only.
  1. import `CoveringORMConnection` inside `_run_np_t04_body_stall`;
  2. `real_terminal = CoveringORMConnection.token_terminal` before `_install_token_terminal_observer`;
  3. the restore in the existing inner `finally`, beside `CoveringHTTP.__init__ = real_init`;
  4. the guard `if CoveringORMConnection.token_terminal is not real_terminal: raise SuiteStop(…)`, right after that `finally` and before any context, budget, response or evidence check.
  
  All prior assertions, clocks, the 240 s peer, rollback, no-later-admission, assessment and state oracles are untouched.
- **Patch inventory of the BODY case (my own lesson applied):**
  - token terminal (now captured, restored and guarded);
  - `CoveringHTTP.__init__` (restored);
  - the worker observer and `_install_t04_parent_and_target_observers` (both restored unconditionally in the same `finally`);
  - `transport.request` (restored in both the inner and outer `finally`).
  
  No other unrestored patch is present.

### Fake `scheduler-native-t04-body-stall-fake-prep-dex-v2`
- **Manifest** `EBB3BED6…BCD0`: 45 entries, 0 mismatches. No result or receipt outputs were copied.
- **Versus the passed fake `33FAEB13` (40): 9 changed, 5 added.**
  - **Changed:** the candidate subjects (runner, diff, launch and docker configs, both candidate manifests) now equal native v2 exactly, plus the checker, EXPECTED, OUTER and VERIFICATION.
  - **Added:** the source manifest, the checker diff, the receipt, the HELD command and the CURRENT doc.
  - **Byte-identical:** wrapper, outer helper and launcher.
- **Pins:** all 32 VERIFICATION packet pins verified on disk. Both admissions are `launch_authorized` false.
- **Checker `950863A9` → `94128112`.** The changed lines are identical to `BODY-Observer-Checker-Correction.diff` (`54B94AF4`); only the hunk headers carry git function context. The delta:
  - pins and labels (`OWN_ROOT` and 6 candidate pins);
  - the mutation anchor `M_RUN_TOKEN_RESTORE`;
  - one new `RUNNER-WIRING` predicate, `token_observer_restored_and_identity_checked`: the capture in `main.body`, the assignment in `inner.finalbody`, and the identity-guard If with SuiteStop in `main.body`;
  - one new mutant, `token_restore_dropped`.
- **Mutant trace:**
  - The anchor is the multi-line restore block that begins with the BODY-only `restore_target_observers` lines, so its global count is 1. (The bare token-restore line alone occurs twice, because the Google refresh body also has it.)
  - The mutation replaces only the restore with `pass`.
  - The earlier `observers_restored_in_finally` check requires only the target and worker restore calls and `response_at`, so it still passes.
  - The new predicate then fails with exactly `wiring:token observer restored`. **The correct cause.**
- **Inventories:**
  - `RUNNER-WIRING` order in the checker equals EXPECTED, with the new predicate after `observers_restored_in_finally`;
  - the mutant dict order equals EXPECTED, with `token_restore_dropped` first;
  - 13 controls, 66 = 64 + 1 + 1 predicates, 10 mutants (7 behavioral, 3 structural);
  - all prior oracles and the Sandbox/dataclass correction are unchanged.

## Qualifications
1. **The guard is narrower than the restore.** The identity guard covers the token terminal only; `CoveringHTTP.__init__` is restored but not identity-guarded (same as Google v3).
2. **Install-before-`try` placement retained.** The observer is installed between `real_terminal = …` and the inner `try` (a def and the `CoveringHTTP.__init__` assignment), the same narrow window accepted for Google. The optional hardening I used in the invalid-grant case is not applied here. Non-blocking.
3. **The new predicate and mutant are structural.** Native restoration is unexecuted.
4. **The earlier PASS stays scoped.** The prior BODY fake PASS (13/64/9) remains valid only at its earlier scope and does not cover this correction. The v2 fake has not run.
5. **No authority.** The native BODY case has never run; the gates and human authority are false.

**Preserved:** `8212DAA6`, `33FAEB13` and all other roots and evidence, untouched. Endpoint unbound; all holds stay.

Signed: Matt
