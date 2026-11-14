# Native MS-REFRESH retirement barrier: focused fake verification preparation v1 (HELD)

Matt, November 13, 2026. This is for `Matt-thePlan-Scheduler-MS-Refresh-Retirement-Preparation-2026-11-13.md` (`6ED9B65F…9350`). It's the companion to `scheduler-native-provider-ms-refresh-retire-prep-matt-v1`.

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`, and no PASS is claimed.

## Roles and pins
- **Immutable lineage, byte-identical:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`. No new executable helper.
- **New:**
  - checker `BF7A73557E23969413F8AA4FE84767E48DB00F9C95AF7C0B41E39C75C50C71D8`;
  - EXPECTED `22CE02C4FC8EE632E3D3DABB484934E3DDEA5FA50011995E525064F4A77D4DD2`;
  - OUTER `25BB93FD1AD4BC287685950D6FFE66F2E918308D2EE4E15131AA0417AABB4558`;
  - VERIFICATION `B42F0AC3754B60AFA86EA46B1FA65690F2F3E7CEF2DC09EF4A225158B16F6FA1` (21 packet pins, the same 10 partial runtime pins).
- **JSON:** OUTER and VERIFICATION were produced from the reviewed T05 client-cause templates by binary-mode substitutions and a pin-list splice, then text-checked.

## Subjects (15)
- **Runner:** source `4CBF198E` (MS invalid-grant prep v2) and candidate `1A95E834`, plus their diff (2 hunks).
- **Runner-config:** source `10106B82` and candidate `D4C8BDBD`, plus their diff (1 hunk).
- **Launch-config:** source `45844289` and candidate `09C9D618`.
- **Docker-ops:** source `BC6F33B2` and candidate `9455026A`.
- **Payload manifests:** source `D9F14FF1` and candidate `CC02F38C` (257 rows each).
- **Nested manifests:** source `545C6BDD` and candidate `C83A5E9E` (269 rows each).
- **Peer dependency:** `np_provider_peer.py` `BFB271D7`, unchanged.

## Controls: 10 top-level, 41 nested
- **SUBJECT-PINS** (1).
- **RUNTIME-PROVENANCE** (7, partial).
- **DIFF-REDERIVATION** (2).
- **PRESERVED-OUTSIDE-CHANGE** (2, structural):
  - the only differing top-level unit is `_run_np_v_ms_refresh`;
  - the helper text is byte-identical.
- **RETIREMENT-HELPER** (7, behavioral): the extracted unchanged `_retire_selected_peer_then_observe` with a named fake peer that publishes its final exchange row during the bounded join. Covers:
  - the post-join state;
  - worker error refused;
  - an empty-string error refused (distinct from None);
  - unjoined refused;
  - `PeerRetirementUnknown` and other exceptions propagate as the same object;
  - exactly one retire attempt on every path.
- **REFRESH-BARRIER-WIRING** (4, structural):
  - exactly one helper call;
  - `retirement_attempted = True` immediately before it and `retirement_done = True` immediately after;
  - no `retire_owned` call in the body, and the single `finally` retire is guarded by `retirement_attempted`;
  - no `sanitized_state` call in the body; every `peer_state` read comes after the barrier, which comes before the oracles and the passing receipt.
  - **Stated honestly:** this is structural evidence, not a behavioral run of the case.
- **REFRESH-ASSERTIONS-PRESERVED** (3, structural):
  - the main body equals the source with the snapshot replaced in place by the 3-statement barrier and the 4-statement late retirement removed;
  - setup, handlers and `finally` are identical;
  - the SuiteStop messages are the source's minus only the subsumed late "peer worker unjoined" check.
- **BATCH-CONFIG** (6):
  - the runner-config and launch-config batch and gates;
  - truthful gate notes;
  - docker-ops differs only by the 7-path rename;
  - the evidence, public-CA and read-only `/public-ca` bind agree;
  - payload delta exactly 2 rows; nested delta exactly 5 rows.
- **PRIOR-FAKE-APPLICABILITY** (2):
  - the selected-retirement fake PASS 13/85 (`A8CDBF04`) ran over this exact source runner, so its helper properties map;
  - its MS-INVALID/NONEXPIRED body checks don't transfer to MS-REFRESH;
  - the peer, transcript, routes, suite, integrated runner, seeds, PKI script and validator rows are unchanged.
- **ACTUAL-SOURCE-MUTANTS** (7):
  - **behavioral (3):** `worker_error_guard_removed`, `worker_error_truthiness`, `helper_pre_join_snapshot`;
  - **structural (4):** `body_pre_join_snapshot`, `body_second_retirement`, `attempt_guard_missing`, `helper_ignored`.
  - Every anchor was checked unique in the whole candidate runner text, and each mutant has its own failure prefix.

## Not proved
Native refresh, T06 closure, peer timing, worker scheduling, and any native TLS, database or provider behavior.

## Limits
120 s, plus a 5 s kill/wait, plus two 5 s reader joins: 135 s nominal. Capture is 64 KiB per stream, the result 256 KiB, and runtime provenance is partial.

## Future command
`Future-Command-HELD.ps1.txt` (admission `B42F0AC3…`). **Not authorized.**
