# MS-refresh merge: focused fake verification preparation (HELD)

Matt, November 13, 2026. This is for assignment `Matt-thePlan-Scheduler-MS-Refresh-Merge-Preparation-2026-11-13.md` (`5A9CF9F6…3D69`). It's the companion to the two frozen batch roots:
- `scheduler-native-provider-ms-merge-nonexpired-prep-matt-v1` (parent `22AE4F82…`);
- `scheduler-native-provider-ms-merge-refresh-prep-matt-v1` (parent `9A62B5C4…`).

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`. No PASS is claimed.

## Roles and pins
- **Reused byte-identical:** wrapper `AE84E632…`, outer `7DCA32E2…`, launcher `D22C37E3…`.
- **New:**
  - checker **`62C6FE99E33F62B85D13FFBDF99085D60B3710A6F8AA1A74758FA94449571600`**;
  - EXPECTED **`81ADB08981E71E4C8E2BB6D9FA252C4AA018FE66670849364339D12BF99BEC13`**;
  - OUTER **`DC3219659ABEB846F8DA4A957FB31E9FE1263C4E99B500E7BF36DA70E15492C1`**;
  - VERIFICATION **`693D357DE196A17AB84D98E04A526740FCF013C169403027567D4987EF12FB5F`** (21 packet pins plus the interpreter `5F7B89A6`; all re-verified).
- **Subjects (15):**
  - runners: base `40A1BA8E`, MS `CC4D49E7`, observer `341074AE`, merged `F7CFD3E6`;
  - diffs: observer `2023F97B` (the reviewed Worker-Observer diff) and MS-refresh `A805B9B0`;
  - payload manifests: base `3B25ABB6`, MS `BD48E400`, peer-close `74B637D4`, NONEXPIRED `14FA30AD`, REFRESH `84518269`;
  - runner-configs: NONEXPIRED `9411AC38`, REFRESH `108D8D1E`;
  - launch-configs: NONEXPIRED `263CF5DD`, REFRESH `197F4C7D`.

## Controls (9 top-level, 33 nested, in order)
1. **SUBJECT-PINS**
2. **MERGE-REDERIVATION** (4):
   - `obs_from_base`, `ms_from_base`, `obs_onto_ms` and `ms_onto_obs`;
   - patch semantics with zero fuzz: each hunk lands at the exactly matching block nearest its expected line, and a tie refuses;
   - each result must equal the pinned runner;
   - the placement offsets are recorded.
   - This placement is needed because the refresh body repeats NONEXPIRED context lines, which makes unique-match placement ambiguous.
3. **OBSERVER-PRESERVED** (4): the merged runner is text-identical to `341074AE` for `_install_worker_exception_observer`, `_run_np_v_ms_nonexpired` and `stop_payload`, and AST-identical for `__main__`.
4. **REFRESH-PRESERVED** (6): the merged runner is text-identical to `CC4D49E7` for `_ms_refresh_provider_routes`, `_require_production_ms_token_path`, `_actual_token_terminals`, `_run_np_v_ms_refresh`, `_make_implemented_case` and `IMPLEMENTED_CASE_IDS`.
5. **TOP-LEVEL-PARTITION** (2):
   - against the observer runner, only the 4 refresh units, the mapper and `IMPLEMENTED_CASE_IDS` differ;
   - against the MS runner, only `_run_np_v_ms_nonexpired` and the observer helper differ.
6. **ROLE-SELECTION** (4), using the manifests of the base, MS, peer-close, NONEXPIRED and REFRESH payloads:
   - each merged row follows the 3-way rule:
     - runner → merged;
     - roles 5, 6, 8, 10 → MS (changed only on that side);
     - peer → peer-close (changed only on that side);
     - runner-config → per batch;
     - everything else is identical on all three;
   - the peer is `17EA148E`, not `5568AF73`;
   - all 234 API rows are identical across all five manifests.
7. **BATCH-SEPARATION** (5):
   - runner-configs: `[NP-V-MS-NONEXPIRED]` / `[NP-V-MS-REFRESH]`, with `[]` expected unknown and `launch_ready` false;
   - launch-configs: the same case lists, all gates false, `endpoint` unbound, `manifest_sha256` equal to the batch's own payload manifest, the path keys on the batch's own root, and no foreign or sibling root text;
   - the two payload manifests differ only in the runner-config row.
8. **PRIOR-FAKE-APPLICABILITY** (3):
   - the peer-close fake subject `17EA148E` is the merged peer;
   - the worker-observer fake subject is `341074AE`;
   - the MS fake v2 subjects (runner `CC4D49E7` and the four role pins) equal the merged rows;
   - the MS fake v2 case "NONEXPIRED unchanged from `40A1BA8E`" is **explicitly not transferred**: the merged NONEXPIRED is not equal to base, and is equal to the observer version.
9. **ACTUAL-SOURCE-MUTANTS** (4), each detected only by its targeted prefix:
   - `observer_install_removed` → "observer preserved:_run_np_v_ms_nonexpired";
   - `refresh_mapper_branch_disabled` → "refresh preserved:_make_implemented_case";
   - `implemented_ids_reverted` → "refresh preserved:implemented";
   - `peer_row_reverted` (NONEXPIRED manifest) → "role selection:n_rows:fixture/np_provider_peer.py".

## Applicability map (frozen in EXPECTED)
- **Worker-observer fake PASS 10/47:** applies to the text-identical observer units.
- **Peer-close fake (still held, not run):** applies to the byte-identical peer.
- **MS-refresh fake v2 PASS 10:** applies to the byte-identical roles 5, 6, 8 and 10, the text-identical refresh units, mapper and ID set, and `_http_response_bytes` (unchanged by the peer fix).
- **Not transferred:** that fake's NONEXPIRED-unchanged case.

## Not proved
- **Native behavior:** none of NONEXPIRED or REFRESH; nothing about the native peer, OAuth, TLS, DB or persistence.
- **Prior fakes:** no more than their own finite scopes.
- **First vertical:** it has not passed.

## Limits (inherited launcher)
- **Timing:** 120 s, plus at most one 5 s kill/wait, plus two 5 s reader joins: 135 s nominal, with no separate outer timeout.
- **Capture:** 64 KiB per stream; 256 KiB for the result.
- **Success** requires exit 0, no output, clean readers and the exact inventory.
- **Exclusive evidence** goes under `packet/verify/`; a failure stops and preserves, with no retry.

## Future command
`Future-Command-HELD.ps1.txt` (admission `693D357D…`).
