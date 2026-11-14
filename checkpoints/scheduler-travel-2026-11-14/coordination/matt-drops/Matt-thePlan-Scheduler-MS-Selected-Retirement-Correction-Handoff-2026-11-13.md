# Matt → Dex: selected-case retirement correction (R1/R2), two native successors and one fake (HELD, frozen)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-MS-Selected-Retirement-Correction-2026-11-13.md` (`BB93F31E1BA6AF0F1D6BFAC3B57DF41BAA35EB75303F9CC18531857F1EB00DF4`), under lane `389A00DD…7E2D`.

**Status:** PREPARED_NOT_EXECUTED, with three fresh frozen roots and no active writer. The endpoint is unbound.

**How it was built**
- Ordinary text, hash, JSON, copy and edit authoring only. Nothing was imported, AST-parsed, compiled, tested or invoked. No subagents were used.
- My only verification was sha256 manifests and a `patch` text round-trip of the three new subject diffs.
- **I caught one authoring error before freezing:** in B's freeze file I first typed a source-manifest hash instead of computing it. I replaced it with the computed `2913656ABBEF…2FB3`. Every 64-hex value in both new freeze files was then cross-checked against real manifests and files.

## The correction (identical pure helper in both runners, role 4)
`_retire_selected_peer_then_observe(peer, join_seconds=5.0)`:
- makes one call to the unchanged `retire_owned` with the existing 5 s join;
- lets `PeerRetirementUnknown` and any other exception propagate unchanged;
- **R1:** requires `joined is True` **and** `worker_error_kind is None`, otherwise it STOPs. There's no expected-error widening and no swallowing;
- **R2:** only then reads `peer.sanitized_state()`.

**Each selected body**
- sets `retirement_attempted = True` immediately before the single call;
- uses the returned post-join state for every final peer, inventory and served/admitted check;
- no longer has the late retirement.

**Unchanged**
- The receipt (`passed` and `workers_joined` True) follows every predicate.
- The `finally` failure-path retirement still runs only if no attempt was made, so there's never a second attempt.
- There's no new wait, and no new messages or diagnostic fields; only two fixed STOP strings.

## A. `outputs/scheduler-native-provider-ms-invalid-prep-matt-v2` (from v1 `DA114394`, 296/296 verified)
- **Only role 4 changed:** runner `ACD7F449` → **`4CBF198E0ACC605897D99C00A334E50B58A1DC5B3AAE91FF7856A319BBA6F7E1`**.
- **Preserved:** every v1 oracle (tenant path, typed client class, ROLLBACK row, credential, expiry and coverage, public `no_op` row, observers) and `NP-V-MS-INVALID`.
- **Re-pinned:**
  - SUMS **`D9F14FF142C972F886C9BA066E292B09E24BED4C51DD98F9DCAFDEB0632BC868`** (257);
  - launch-config **`4584428948A544473C1F7ABF7E9AD87DBAFCDBB0828C987820C9CE2BE1C14098`** (root rename and payload pin);
  - docker-ops **`BC6F33B2928E429512628A5D402020018490B251A9D3A2C7CB7237095D81F605`** (root rename);
  - nested **`545C6BDD6A9E99850ECA62F0779D58052BE7A57BBA661B154FD4DBFC6F54153E`** (269, 4 rows changed);
  - parent **`6144365E0E7F282BABEDF0FDFB454E309112A16D17CE8464CF5335F7AFC5505B`** (297).
- **Held command:** `MS-Invalid-Native-Command-HELD.ps1.txt` (`-ExpectedConfigSHA256 45844289…`, `-ExpectedDockerConfigSHA256 BC6F33B2…`, this root's docker-ops path, no `-ReceiptPath`). **Not authorized.**

## B. `outputs/scheduler-native-provider-ms-nonexpired-retire-prep-matt-v1` (from Dex staging `2913656A…`, 287/287 verified)
- **Only the `_run_np_v_ms_nonexpired` boundary changed in role 4:** runner `341074AE` → **`A2C32A2042A523BE932826666D87501AA57A6B4D0E4ECCB173AEDF966794B77D`**.
- **Gates reset to false:**
  - runner-config `launch_ready` true → false gives **`9411AC38…E929`**, byte-identical to the pre-staging bytes;
  - launch-config `launch_ready` and `candidate_launch_ready_staged` true → false; `human_launch_authorized` was already false.
- **Re-pinned:**
  - SUMS **`5835297919BA3B43DEB767FD5F88F9A8AE41F7EBF0EC3F5B73EB5CCC87251BF3`**;
  - launch-config **`9BE3C57D1F99E39AB93355A80B8A8D74C84C7CFCE6E6099B284FAA0303F414D9`** (adds the root rename, payload pin, candidate note, and the r1 note marked historical);
  - docker-ops **`29FE19C0922EB96325D264F4461317765E8CFE6DCB3975D92B1155A3578E224D`** (root rename);
  - nested **`908C0F6E228DED21FB39F8521DBBB2A4674C466481887208B9B39ECB5254C908`** (5 rows changed);
  - parent **`F6DBB55155B9C8757A22FCE75292618E4306C21CA426FE22A90848C262E68C48`** (291).
- **Unchanged:**
  - the 234 API files, peer `17EA148E`, and the host operator and helpers;
  - the four-connection, alias, coverage, TOKEN terminal, assessment and public assertions;
  - no T05, refresh or transcript merge.
- **Held command:** `NONEXPIRED-Retire-Native-Command-HELD.ps1.txt` (`9BE3C57D…`, `29FE19C0…`). **Not authorized.** Card `A50C04FB` is recorded as WITHHELD.

## Flags prose correction
- In both successors, the copied **docker-ops-config** still carries `launch_ready` and `candidate_launch_ready_staged` true as machine data. That is never human authority.
- The host, runner and admissions are false.
- My invalid-grant v1 README and freeze said "all false" without that qualification. The v2 docs and both freezes (a `machine_data_flags` block) now say it exactly. The frozen v1 is not edited.

## Fake `outputs/scheduler-native-ms-selected-retire-fake-prep-matt-v1`
- **Immutable lineage:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`. No new helper.
- **New:**
  - checker **`0E8714EED6AC110ABDD430958FA05CBCED4EC457F2802E1A96B555929D40FEF0`**;
  - EXPECTED **`ED7A7EC25879A43779F449E39CADBDAD52C9699CDD60DF7FFB1A42E2AB263A38`**;
  - OUTER **`2F037FD8DACBBC765CF0FE27006538EFD6BB098F67FACEAF87A3A5B0B2B8AD31`**;
  - VERIFICATION **`F2CDD04F56CF321419AB12196F29F3AACC48B3A90F57A0977DB0E2B703695440`** (41 packet and 10 runtime pins re-verified; both false; paths text-checked);
  - manifest **`A6AE21A9A373BB47593415AD4D193FDCBB9204585329D24B5662F1000429D9C0`** (45).
- **Subjects (35):** fake v1's 25 with the v2 runner, diff, launch-config and manifest, plus 10 NONEXPIRED source/candidate subjects.
- **Inventory: 13 controls, 85 nested.** The breakdown is SUBJECT 1 + RUNTIME 7 + DIFF 6 + PRESERVED 4 + SELECTION 5 + CLIENT 12 + UNITS 4 + PUBLIC 4 + WIRING 9 + **RETIREMENT-BARRIER 10** + BATCH 6 + PRIOR 3 + MUTANTS 14.
  - **All 65 invalid-grant v1 checks are kept** against v2.
  - **RETIREMENT-BARRIER, behavioral (6), the actual extracted helper with a named fake peer.** The fake peer appends its final inventory row *during* the join.
    - joined with no error gives one attempt, then the state, and that state includes the row published during the join;
    - a worker error gives a STOP, with no state read;
    - unjoined gives a STOP;
    - `PeerRetirementUnknown` and other exceptions propagate as the same object;
    - exactly one attempt on every path.
  - **RETIREMENT-BARRIER, structural (4):**
    - the helper is identical in both runners;
    - the barrier order is right in **both** selected bodies;
    - the NONEXPIRED STOP-message set is unchanged apart from the removed "peer worker unjoined — UNKNOWN".
  - **BATCH:** NONEXPIRED key-by-key equality outside the 7 allowed launch-config fields, `launch_ready`-only runner-config change, and an exact 2-row payload delta with the peer unchanged.
  - **Mutants:** 7 behavioral (the 5 from v1, plus `worker_error_admission_removed` and `snapshot_moved_before_join`, both caught by the behavior oracles) and 7 structural (the 5 from v1, plus `body_snapshot_before_barrier` and `body_second_retirement`).
- **Held command:** `Future-Command-HELD.ps1.txt` (`F2CDD04F…`). **Not authorized.**

## Exact diff (Matt-Drops)
`Matt-thePlan-Scheduler-MS-Selected-Retirement-Correction-V1-2026-11-13.diff` (`B47BDBE3CD38FF8BF3F26B5CE61057CF2D66EFFCBE42179B9489AABA76B71B47`), 9 file sections:
- **A:** runner, launch-config and docker-ops, v1 → v2;
- **B:** runner, runner-config, launch-config and docker-ops, from staging to the successor;
- **Fake:** checker and EXPECTED, from fake v1 to this packet.

## Gaps and limits
- **MS-REFRESH:** keeps the inherited joined-only, snapshot-before boundary. That's a recorded gap before its later launch, not touched here.
- **Not certified:** the other unselected bodies.
- **Untouched:** the frozen T05 packet.
- **Nothing has run:** no fake or native run, and no native retirement timing or proof.
- **Unchanged caps:** 900/600, 120 + 5, PKI 45 nominal, 32 commands, 1 MiB per command plus a 1 MiB report.
- **Launches:** each needs its own exact approval. The NONEXPIRED launch needs a new card.

## Preservation
All verify at 0 mismatches:
- invalid-grant v1 `DA114394` and its fake v1 `B5183A40`;
- the Dex staging source `2913656A`;
- T05 v3 `B773B95E` and its fake v3 `090D0758`.

There's no evidence root and no result or receipt in the new packet.

Signed: Matt
