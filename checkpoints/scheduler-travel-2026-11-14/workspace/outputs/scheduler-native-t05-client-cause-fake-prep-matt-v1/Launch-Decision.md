# Native T05 client-cause diagnostic: focused fake verification preparation v1 (HELD)

Matt, November 13, 2026. This is for `…T05-Client-Cause-Diagnostic-Preparation-2026-11-13.md` (`9F9FF48E…D511`). It's the companion to `scheduler-native-provider-t05-client-cause-prep-matt-v1` (parent `59DC1797…`).

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`, and no PASS is claimed.

## Roles and pins
- **Immutable lineage, byte-identical:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`. No new executable helper.
- **New:**
  - checker `93260CA296CCDDFA739660BC832849B2FA0B169D18ACC3A7845E7C1E566CC5F1`;
  - EXPECTED `D7CBC81F5C4A42F673FC73B30A4AFA78C6FD7979F4653D015D8BE461AD0751A5`;
  - OUTER `DE6587CD71D812219499411651CA617A8C098F458CE87A22511B23DD97DE8A9E`;
  - VERIFICATION `B1940DA6B009770F7F90875AD3695B74951A0DC280B91160361590636DBFE20F` (17 packet pins and the same 10 partial runtime pins).
- **JSON paths:** OUTER and VERIFICATION were produced from correctly escaped templates by binary-mode in-place edits and a splice, then text-checked.

## Subjects (11)
- **Runner:** source `1D70164C` (the failed-run staging) and candidate `1AEDEE93`, plus their diff (3 hunks).
- **Runner-config:** source `9E45F6B6` and candidate `96782CB4`, plus their diff (1 hunk).
- **Launch-config:** source `A9E72456` and candidate `39AAEE8B`.
- **Payload manifests:** source `EEBC1403` and candidate `4076B0D2`.
- **Host validator:** `docker_transport.py` `7F7EA820`.

## Controls: 10 top-level, 38 nested
- **SUBJECT-PINS** (1).
- **RUNTIME-PROVENANCE** (7, partial).
- **DIFF-REDERIVATION** (2).
- **PRESERVED-OUTSIDE-CHANGE** (1, structural): exactly `{_t05_observe, _t05_classify_or_chain}`.
- **CHAIN-HELPER** (5, behavioral): the extracted candidate helper with the unchanged classifier and tuples, and a named fake `np_suite.SuiteStop`.
  - the admitted label is unchanged;
  - the same guard object is raised with `__cause__` being the same client object, with `__suppress_context__` True;
  - with no client exception, a bare re-raise: no cause, no suppression, no context;
  - an unexpected classifier exception propagates as the same object;
  - the client exception is not mutated.
- **OBSERVE-WIRING** (4, structural):
  - `client_exc` is initialized to None before the peer try;
  - it's captured only in the client request handler, before the unchanged outcome tuple;
  - the single helper call comes after the retirement and inventory checks, outside the peer try;
  - no direct classifier call remains.
  - **Stated honestly:** this is structural evidence about order, not a behavioral run of `_t05_observe`.
- **STOP-PRODUCER-AND-VALIDATOR** (7, behavioral): the actual `stop_payload` over a temporary sandboxed owned root (a hash-pinned fake owned module that raises the client exceptions), and the actual host `DockerOps._record_runner_stop` with a named fake self.
  - secret markers are absent;
  - the exact chain kinds and owned frames;
  - non-owned frames are dropped and `truncated` is set;
  - a cleanup UNKNOWN chain of 3 is preserved;
  - a suppressed context is still followed, which is the producer's actual cause-else-context semantics;
  - a 4-link chain is cut to 3, frames are cut to 8, and the line stays at most 4096 bytes;
  - a missing manifest falls back to `{status, kind}`.
  - The validator accepts every line.
- **BATCH-CONFIG** (3): gates false, key-by-key equality outside the 7 allowed launch fields, a `launch_ready`-only runner-config change, and an exact 2-row payload delta.
- **PRIOR-FAKE-APPLICABILITY** (2): the T05 units are identical except `_t05_observe`, and the peer, transcript, suite, integrated runner and validator are unchanged.
- **ACTUAL-SOURCE-MUTANTS** (6):
  - **behavioral (4):** `cause_dropped`, `wrong_cause`, `none_fallback_chained`, `producer_exports_message` (a real export fault);
  - **structural (2):** `chain_before_retirement`, `capture_dropped`.
  - Every anchor was checked unique in the whole runner text.
  - Adding a harmless internal message isn't counted as a privacy defect.

## Not proved
Which client exception a native run produces, native TLS/EOF behavior, and peer timing.

## Limits
120 s, plus a 5 s kill/wait, plus two 5 s reader joins: 135 s nominal. Capture is 64 KiB per stream, the result 256 KiB, and runtime provenance is partial. The temporary owned root exists only inside the check.

## Future command
`Future-Command-HELD.ps1.txt` (admission `B1940DA6…`). **Not authorized.**
