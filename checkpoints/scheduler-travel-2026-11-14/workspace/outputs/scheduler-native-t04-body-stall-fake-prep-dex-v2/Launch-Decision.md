# Native T04 BODY-STALL: focused fake verification preparation v1 (HELD)

Matt, November 13, 2026. This is for Dex `F465A4E2…F196`, under Trish-approved decision `4F2F3B3F…804B`. It's the companion to `scheduler-native-provider-t04-body-stall-prep-matt-v1`.

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`, and no PASS is claimed.

## Roles and pins
- **Immutable lineage, byte-identical:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`. No new executable helper.
- **New:**
  - checker `DFB2D438…3CDF`;
  - EXPECTED `FBD0E892…66B4`;
  - VERIFICATION `90D28CA7…92FD` (32 packet pins, the same 10 partial runtime pins).

## Controls: 13 top-level, 61 nested
1. **SUBJECT-PINS** (1).
2. **RUNTIME-PROVENANCE** (7, partial).
3. **DIFF-REDERIVATION** (5): runner, peer, transcript, suite, runner-config.
4. **PRESERVED-OUTSIDE-CHANGE** (4, structural):
   - the runner adds exactly the listed units and changes only `IMPLEMENTED_CASE_IDS` and `_make_implemented_case`;
   - in the peer, only `PeerLifecycle` and the methods `_send_response`/`_hold_stall`/`execute_script`/`sanitized_state` change;
   - the transcript adds exactly 4 units;
   - the suite changes only its notes.
5. **PEER-CLEAN-STOP** (6). Behavioral cases use the actual `_hold_stall`/`_send_response` with a fake clock, select and self:
   - a retired clean return;
   - a deadline stays an error with the unchanged message;
   - a stop seen at or after the deadline is still a deadline;
   - a body stall sends exactly the head with `Content-Length: 12`;
   - a header stall sends nothing.
   - Plus one structural case: the instants are recorded.
6. **TRANSCRIPT-STALL-SCRIPT** (4):
   - exactly three exchanges;
   - the exact path and query with a `stall_body` close;
   - the positive-Content-Length head through the actual serializer;
   - a bad query is refused.
7. **QUERY-DERIVATION** (3), using the actual runner unit over the actual window module and the actual calendarView param builders:
   - an exact literal;
   - an offset window normalized to UTC;
   - an invalid window refused.
8. **TIMING-PREDICATE** (4):
   - ordered values are accepted;
   - each of 6 inequality violations STOPs;
   - a `deadline` reason STOPs;
   - a missing, non-finite or integer instant STOPs.
   - No epsilon anywhere.
9. **RUNNER-WIRING** (6, structural):
   - the 240 s case peer life only, with the other 4 bodies still at 120;
   - `clock=monotonic`;
   - a single retirement barrier;
   - timing after retirement;
   - observers restored in `finally`;
   - the allowlisted `token_terminal_sequence` key and the single oracle.
10. **OBSERVERS** (3): same return and exception, the disposition recorded, and exact restoration.
11. **RECEIPT-RETENTION** (3):
    - every emitted key passes the actual `_forbidden_key`;
    - typed evidence survives the actual `redact_mapping`;
    - the privacy filter is unchanged.
12. **CONFIG-AND-IMMUTABLES** (6):
    - runner-config and launch-config;
    - the docker rename;
    - a 5-row payload delta and an 8-row nested delta;
    - all 234 API files and the named helpers immutable.
13. **ACTUAL-SOURCE-MUTANTS** (9):
    - **behavioral (7):** `peer_lax_stop`, `peer_deadline_returns`, `peer_body_sent`, `timing_epsilon`, `timing_no_reason`, `observer_copy_return`, `query_top_changed`;
    - **structural (2):** `default_peer_life`, `dropped_token_key`.
    - Every anchor is unique in the whole candidate text, and each mutant has its own failure prefix.

## Not proved
Native elapsed time, the 240 s peer behavior, TLS, selector scheduling, the database, native terminals, the recorder disposition, and any T04 requirement.

## Limits
120 s, plus a 5 s kill/wait, plus two 5 s reader joins: 135 s nominal. Capture is 64 KiB per stream and the result 256 KiB. No temporary files. Runtime provenance is partial.

## Future command
`Future-Command-HELD.ps1.txt` (admission `90D28CA7…`). **Not authorized.**
