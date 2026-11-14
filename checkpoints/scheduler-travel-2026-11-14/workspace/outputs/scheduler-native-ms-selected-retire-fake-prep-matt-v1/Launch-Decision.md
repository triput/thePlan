# Selected-case retirement correction: focused fake verification preparation v1 (HELD)

Matt, November 13, 2026. This is for `Matt-thePlan-Scheduler-MS-Selected-Retirement-Correction-2026-11-13.md` (`BB93F31E…0DF4`).

It covers both separately held native successors:
- `scheduler-native-provider-ms-invalid-prep-matt-v2` (parent `6144365E…`);
- `scheduler-native-provider-ms-nonexpired-retire-prep-matt-v1` (parent `F6DBB551…`).

It succeeds the unexecuted `scheduler-native-ms-invalid-fake-prep-matt-v1` (`B5183A40…`), which is preserved.

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`, and no PASS is claimed.

## Roles and pins
- **Immutable lineage, byte-identical:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`. No new executable helper.
- **New:**
  - checker `0E8714EED6AC110ABDD430958FA05CBCED4EC457F2802E1A96B555929D40FEF0`;
  - EXPECTED `ED7A7EC25879A43779F449E39CADBDAD52C9699CDD60DF7FFB1A42E2AB263A38`;
  - OUTER `2F037FD8DACBBC765CF0FE27006538EFD6BB098F67FACEAF87A3A5B0B2B8AD31`;
  - VERIFICATION `F2CDD04F56CF321419AB12196F29F3AACC48B3A90F57A0977DB0E2B703695440`, which has 41 packet pins and the same 10 runtime pins, all re-verified by hash.
- **JSON paths:** text-checked for `\\` escaping. OUTER and VERIFICATION were edited in place, or spliced, from the correctly escaped v1 files.

## Subjects (35)
- **Carried from fake v1 (25):** the runner candidate is now invalid-grant v2 (`4CBF198E`), with the cumulative T05 v3 → v2 runner diff (3 hunks), the v2 launch-config and the v2 payload manifest.
- **New (10):** NONEXPIRED source runner `341074AE` and candidate `A2C32A20`, their diff (3 hunks), source and candidate runner-config (`E132A138` → `9411AC38`, plus a 1-hunk diff), source and candidate launch-config (`4C065AEF` → `9BE3C57D`), and source and candidate payload manifests (`5F94DD7D` → `58352979`).

## Controls: 13 top-level, 85 nested
**All 65 v1 checks are kept,** now against the v2 runner. The additions:
- **DIFF-REDERIVATION** (+2): the NONEXPIRED runner and runner-config.
- **PRESERVED-OUTSIDE-CHANGE** (+1, structural):
  - the NONEXPIRED runner partition is exactly `{_retire_selected_peer_then_observe, _run_np_v_ms_nonexpired}`;
  - the invalid-grant runner partition now also includes the helper.
- **RETIREMENT-BARRIER** (new, 10):
  - **Behavioral (6), the actual extracted helper with a named fake peer.** The fake peer publishes its final inventory row during the join.
    - joined with no error gives one `retire_owned(5.0)`, then the state, and the final inventory includes the row published during the join;
    - joined with a worker error gives a STOP, with no state read;
    - unjoined gives a STOP;
    - `PeerRetirementUnknown` and any other exception propagate as the same object;
    - there is exactly one attempt on all five paths.
  - **Structural (4):**
    - the helper text is identical in both runners;
    - in **both** selected bodies, `retirement_attempted = True` immediately precedes the single barrier call; there's no direct `retire_owned` or `sanitized_state` in the main try body and one failure-path retirement in `finally`; every `peer_state` use follows the barrier; and the barrier comes before `check_oracles_immediate`, which comes before the receipt (`passed`, `workers_joined` True; `expected_unknown` False);
    - the NONEXPIRED body's STOP-message set equals the source set minus the removed "peer worker unjoined — UNKNOWN".
- **BATCH-CONFIG** (+3), NONEXPIRED:
  - the runner config differs from the source only in `launch_ready`, now false;
  - the launch config has gates false, its own root, no foreign root, the same key set, and every key equal to the source except the 7 allowed fields;
  - the payload delta is exactly runner plus runner-config, with peer `17EA148E` unchanged.
- **ACTUAL-SOURCE-MUTANTS** (+4):
  - **behavioral:** `worker_error_admission_removed` → "retire:worker error refused"; `snapshot_moved_before_join` → "retire:post-join state";
  - **structural:** `body_snapshot_before_barrier` (NONEXPIRED) and `body_second_retirement` (invalid-grant).
  - **Totals:** 7 behavioral and 7 structural mutants.

## Not proved
- **Native behavior:** native peer retirement timing, TLS, the client exception class, the PostgreSQL acknowledgement, persisted state and the ASGI response.
- **Not certified:** MS-REFRESH's inherited boundary and the other unselected bodies.

## Limits
- **Timing:** 120 s, plus at most one 5 s kill/wait, plus two 5 s reader joins: 135 s nominal.
- **Capture:** 64 KiB per stream; 256 KiB for the result.
- **Success** requires exit 0, no output, clean readers and the exact 13-control/85-nested inventory.

## Future command
`Future-Command-HELD.ps1.txt` (admission `F2CDD04F…5440`). **Not authorized.**
