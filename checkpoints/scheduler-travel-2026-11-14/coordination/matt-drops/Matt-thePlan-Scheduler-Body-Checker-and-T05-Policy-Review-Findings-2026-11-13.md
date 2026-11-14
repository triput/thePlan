# Matt → Dex: BODY-STALL checker correction and T05 BrokenPipe policy, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Body-Checker-and-T05-Policy-Review-2026-11-13.md` (`E717A53C067E2E0DF36927D0FE7E5B99FCEC0A45286734EA39AA357A9A42F863`).
- **Method:** read-only text, hash and whitespace-normalized comparison. No imports, parsing, execution, scratch or code edits, or subagents.
- **Status of my roots:** my frozen T03 and BODY-STALL roots are unchanged.

## A. BODY-STALL checker correction: qualified static acceptance, no blocker
**Pins:**
- `scheduler-native-t04-body-stall-fake-dex-v1`: manifest `33FAEB13697C4D840D7055D1A880EB3B3F967DEF77ECBA5C7A6740CE098E0947`, 40 entries, 0 mismatches. There's no `.evidence` and no result or launch receipt.
- My source `37F978FD` still verifies 35/35.

**Versus my 35 inputs:**
- **4 changed:**
  - checker `DFB2D438` → `950863A9C0BF691945D0BD77CE5BADD0EA305679A5B9FB31607F48D21F0F96D0`;
  - EXPECTED `FBD0E892` → `7E2E5CB3DBD2D360FA8CE1A9E352F2419DB374911B25847D4A39A3DB84CB4F70`;
  - OUTER `9262A248` → `87B6F113…`;
  - VERIFICATION `90D28CA7` → `E9DA1CF5E5730D9C6AC4996353CD0D810C7D2A9E24EE2F67DD7F309156B45523`.
- **5 added:** the CURRENT doc (`C8EE4287`), the receipt (`C3002940`), the diff (`BAA06C10`), the command (`2A9D65D0`) and the source manifest (`37F978FD`).
- **31 byte-identical:** all 26 subjects, wrapper, outer and launcher.

**Exact delta:** the checker changes in only two places, and stays LF.
1. **`transcript_namespace`:** `with Sandbox(("transcript_subject",))` puts an owned `ModuleType`, and the **decorated** definitions run in `module.__dict__`.
   - The decorators and future annotations are preserved, since `exec_units` / `unit_text` are unchanged.
   - The module is removed on exit, and the returned namespace keeps the functions' `__globals__`.
   - Instantiation after exit needs no module lookup.
2. **`oracle_transcript` gains 3 cases:**
   - `namespace_removed_after_success`;
   - `preexisting_module_refused_unchanged`: the inner `Sandbox.__enter__` raises `WitnessFailure("sandbox precondition")` before any put, so the ambient entry is identical;
   - `definition_failure_identity_and_cleanup`: a patched `globals()["exec_units"]`, looked up at call time in the same `__main__` globals, raises inside the registered module. Its identity is preserved, the owned entry is removed, and the original is restored in `finally`.
   
   I traced all three against the Sandbox semantics, and they hold.
- **EXPECTED** changes only by those 3 names and 61 → 64.
- **OUTER and VERIFICATION** change only the pins (checker/EXPECTED; checker/EXPECTED/OUTER), `launch_authorized` → true, and the notes.
- **Pins:** all 32 packet pins match on disk, and the 10 runtime pins are unchanged.
- **Command:** this root's wrapper, with `-AdmissionSHA256 E9DA1CF5…`, which equals VERIFICATION on disk.

**Other prelaunch defects (my original code, re-traced):** none found.
- The window module defines a `NamedTuple`, not a dataclass. Its string annotations become `ForwardRef`s with no module lookup.
- No other extracted unit defines a dataclass.
- The wiring `post`-try is unique, and its last statement is `response_at = monotonic()`.
- The 9 mutant anchors are unchanged and unique.

**Qualification:** this is static only. Syntax and behavior are unexecuted, the inherited `PACKET_NAME` labels are provenance, and machine readiness is not authority.

## B. T05 native BrokenPipe evidence and the policy question
**Pins:**
- receipt `174E1BE136693014C7B9F5F1E885342604BF50FC52B0B9BAB83412EC6CC9EB13` (31 rows: attempt, 2 created, 12 + 12 command/output, CA transfer, negative control, `runner_stop`, `stopped`);
- trace `FD3877736081277F5EC1745B470E85E9EC7BC19B898B7356DD0E59BD00309F00`;
- runner `1AEDEE93`, peer `BFB271D7`.

**Retained, directly re-read from `runner_stop`:**
- **SuiteStop frames:** `np_runner_entry` 2466 → integrated 39 → 2245 → 2205 → **2112** → 1970 → **1966** → **1949**.
- **BrokenPipeError frames:** 2088 (`http.request`) → `covering_http_transport` **345** (`response.read(8192)`) → **83** (`self.fp.read(amt)`) → **51** (`_Reader.readinto` → `transport.receive`) → `covering_joined_https` **112** (`self.sock.recv`).
- `truncated` true, with no errno or message.
- **So the failure surfaced during the body read, after `response.begin()` and the header gates.** This stage evidence is retained (owned frames), not only assertion-level.

**Assertion-level only:** reaching l.2112 means the `_t05_observe` guards ran. That covers peer retirement joined with no `worker_error_kind`, plus the exact admitted/served/request/response/close-mode/bytes inventory. No per-case row was retained, and case 1 (orderly) has no retained PASS row.

**Source fact that matters for the policy:** the abrupt peer (`np_provider_peer` l.423–440) does `setsockopt(SO_LINGER, (1, 0))`, then `shutdown(SHUT_RDWR)`, then `close()`.
- At source level that sends a FIN (shutdown) and then an RST (linger-0 close), back to back.
- **Inference [I]:** whether the client's next `recv` first meets the FIN (ragged EOF → `SSLEOFError`) or the RST (→ `ConnectionResetError`, or this run's `BrokenPipeError`) depends on scheduling.
- The stimulus itself mixes two termination modes, which is consistent with the observed class not being one of the two pre-listed. I don't infer the errno or OpenSSL path that turned it into EPIPE on a receive.

**My recommendation (reasoned disagreement with admitting BrokenPipe as the primary fix):**
1. **Preferred: make the stimulus deterministic** rather than widen the oracle. Split the current mixed close into two finite scripts (a role 7/8 fixture design, a decision for Trish):
   - **(a) ragged EOF:** `shutdown(SHUT_WR)` without unwrap and without linger-0, so a FIN with no RST. Expect exactly `("exception", "SSLEOFError", "ssl")`. This is the property "TLS truncation without close_notify" names;
   - **(b) optional transport reset:** linger-0 close without a prior shutdown, so an RST only. Expect a finite reset family `{ConnectionResetError, BrokenPipeError}/builtins` as a stated fail-closed hypothesis.
   
   Both keep `IncompleteRead`, JSON, other OS errors and UNKNOWN as STOP.
2. **If a minimal change is preferred instead:** admitting exactly `("exception", "BrokenPipeError", "builtins")` for `abrupt_distinct` only is defensible on this evidence, because:
   - the retained frames place it in the JoinedTLS receive during the body read;
   - the peer guards ran clean (assertion-level);
   - it is a reset-family class, not a framing acceptance;
   - `IncompleteRead` stays refused.
   
   **But** require stronger stage evidence on any future PASS, because a PASS receipt wouldn't carry the STOP diagnostic. Add an in-memory, finite stage check before classification: the innermost owned frame's function is `JoinedTLS.receive`, and an enclosing frame is `_GuardedHTTPResponse.read`. Match by function name, not line number. Record one typed field, `client_failure_stage: "joined_tls_receive_during_body_read"`, in the measured fields (not the STOP schema). Without that, the class alone could admit a BrokenPipe from another stage.
3. **Either way:**
   - no post-hoc PASS for this stopped run;
   - no `OSError` broadening;
   - production code unchanged;
   - and run the T05 fake equivalent of the new predicate (a fake BrokenPipe raised at a non-receive stage must STOP) before any native rerun card.

**Not established:** the EPIPE/OpenSSL mechanism, FIN-versus-RST ordering on the wire, case-1 PASS retention, and any full T05 or ingress composition.

## Separation
- **A:** qualified static acceptance, no blocker.
- **B:** evidence reconciled. Recommendation: (1) deterministic split preferred, with (2) as a narrower alternative carrying a mandatory stage check. Both are decisions for you and Trish.
- **Held:** all execution, with every pack and all failed evidence preserved.

Signed: Matt
