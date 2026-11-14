# Matt → Dex: native MS-REFRESH retirement-barrier preparation v1 and focused fake (HELD, frozen)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-MS-Refresh-Retirement-Preparation-2026-11-13.md` (`6ED9B65F34F5138A69AD64ADEE2832696EFC39A9297DCF181F936665442C9350`), under lane `389A00DD…7E2D`. Noted: 64EF249D is complete (native v2 `BA69C858`, reconciliation `A9AA6920`), and D1 stays held, with no T03 authored.

**Status:** PREPARED_NOT_EXECUTED. Two fresh frozen roots, with no active writer and the endpoint unbound.
- **Method:** ordinary copy, text, hash and JSON authoring only. Nothing was imported, AST-parsed, compiled, tested or invoked. No subagents.
- **Unexecuted:** syntax and behavior.
- **No STOP condition was hit:** the change uses only role 4 and the existing helper, with no new dependency or policy decision.
- **Not merged:** the T05 client-cause and T03 work.
- **Source preserved:** `scheduler-native-provider-ms-invalid-prep-matt-v2` verifies 297/297 both before the copy and after the work.

## 1. Native root `outputs/scheduler-native-provider-ms-refresh-retire-prep-matt-v1`
- **Copy:** 297 inputs from `6144365E…505B`, verified 297/297. Lineage: `Source-MS-Invalid-Prep-V2-Input-Manifest.sha256`.
- **Role 4 only:** `np_runner_entry.py` `4CBF198E…F7E1` → **`1A95E8340B2D45B0DA4D77B14B7726E485691EB94B3CF765AD4497F96020A8B2`**. The diff has exactly 2 hunks, both inside `_run_np_v_ms_refresh`:
  - **source l.1658 `peer_state = peer.sanitized_state()`** is replaced **in place** by `retirement_attempted = True`, then `retirement, peer_state = _retire_selected_peer_then_observe(peer, join_seconds=5.0)`, then `retirement_done = True`. The barrier now sits before the existing served/admitted, five-exchange, first-POST and GET-only assertions. Your example said "mark, then call", and that's the order used;
  - **source l.1749–1753 removed:** the late `retirement_attempted = True`, `retire_owned`, `retirement_done = True` and the `joined is not True` check. That check is subsumed by the helper's own `joined is True` requirement, and the helper adds `worker_error_kind is None`.
- **Unchanged and preserved:**
  - **The helper is byte-identical** (l.1824).
  - **The `finally` guard is unchanged:** `not retirement_attempted and peer._worker is not None and not peer.life.joined`. Because the mark comes before the call, a raise from the helper never causes a second retirement.
  - **Handlers are identical,** including the `PeerRetirementUnknown` → SuiteStop mapping and the primary-failure cleanup precedence.
  - **Kept as-is:**
    - the remaining unjoined `np-peer-` thread check;
    - the oracle and receipt order;
    - the one-attempt guard;
    - all other assertions.
- **The only behavior-visible differences:**
  - **retirement now happens before** the alias checks, the oracles and the `t_check` / plan-validity check, instead of after them;
  - **two failure paths changed:**
    - an unjoined result now raises the helper's "selected peer worker unjoined — UNKNOWN" instead of "peer worker unjoined — UNKNOWN";
    - a joined worker that recorded an error is now refused.
- **Byte-identical (all 291 unchanged inputs):** production 234 API, peer `BFB271D7`, transcript `BEDCCFD3`, routes, seeds, PKI, suite, integrated runner, host validator, operator `5A8A04B6`. No token, rotation, persistence, secret-exclusion, semantic-state, five-exchange or terminal assertion changed.
- **Data:**
  - **runner-config** `10106B82` → **`D4C8BDBD83C3C5D0F76564C5E5BB6B5962CBBEBA4D3D3C3618E55DC8C693A88A`**: `case_ids` → `["NP-V-MS-REFRESH"]` only. No expected UNKNOWN; `launch_ready` false.
  - **launch-config** `45844289` → **`09C9D618DC0177FACD8E29A35DEDEEAFF637424D0C447C939B4834EC07EB7ED5`**:
    - `batch_id` `np-v-ms-refresh-single-case` (the precedent from earlier refresh roots);
    - `case_ids`, the payload pin and 2 own-root paths;
    - a new `candidate_note`, and `dex_r1_revise_note` marked historical. Gates stay false.
    - **F1 lesson applied:** the note states the gates "AS AUTHORED in this prep root" and says any staging that flips a gate must restate the note.
  - **docker-ops** `BC6F33B2` → **`9455026A775EF769C71D960A71ADEBC623BDC01299844C08B5F69F0C90130F1D`**: 7-path root rename only. Its machine flags are data only.
- **Re-pinned:**
  - payload SUMS **`CC02F38CFBD8542AD49DA8663FE3BCACD8F8712FDD97FE53D5F739A52C0CA687`** (257; 2 rows);
  - nested **`C83A5E9E324C77465F03C3EEE371AEF7A16917FCD8335B943AFF98E2FAD7AB5B`** (269; exactly 5 rows);
  - parent **`F682D755584679CC31E25A3C1D99A2C64708CC5C83C0651C7C0072AEC1CB2BB4`** (301; 291 same, 6 changed, 4 added).
- **Paths:**
  - **evidence:** `<root>\scheduler-native-provider-diagnostic-launch-v1.evidence`, which is absent. It is both the `receipt_directory` and the docker-ops `public_ca_directory` parent;
  - **CA:** `\public-ca`, bound read-only to `/public-ca` in the runner. `/packet` is also read-only;
  - **receipt:** the default `native-provider-host-receipt.jsonl`.
- **Current documents:**
  - `MS-REFRESH-RETIRE-PREP-README.md`;
  - `MS-Refresh-Retire-Prep-Freeze.json`;
  - `MS-Refresh-Retire-Native-Command-HELD.ps1.txt` (`7900C2A629EE966A701CC7D260993E0006AD6F6F0E0C104EDDE0EA29F9B2F62A`): `-ExpectedConfigSHA256 09C9D618…`, `-ExpectedDockerConfigSHA256 9455026A…`, this root's docker-ops path, no `-ReceiptPath`. **Not authorized.**
  - Every copied document is history.

## 2. Fake `outputs/scheduler-native-ms-refresh-retire-fake-prep-matt-v1`
- **Immutable:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`. No new executable helper.
- **New:**
  - checker **`BF7A73557E23969413F8AA4FE84767E48DB00F9C95AF7C0B41E39C75C50C71D8`**;
  - EXPECTED **`22CE02C4FC8EE632E3D3DABB484934E3DDEA5FA50011995E525064F4A77D4DD2`**;
  - OUTER **`25BB93FD1AD4BC287685950D6FFE66F2E918308D2EE4E15131AA0417AABB4558`**;
  - VERIFICATION **`B42F0AC3754B60AFA86EA46B1FA65690F2F3E7CEF2DC09EF4A225158B16F6FA1`** (21 packet pins and the same 10 partial runtime pins; both false; successor reference = runner `1A95E834`, transcript `BEDCCFD3`, peer `BFB271D7`);
  - manifest **`E85D5C920E574E0D431C8341D2764087E0E9E1BD743675C12170A85F9D9D0959`** (24).
- **15 raw-pinned subjects:**
  - source and candidate runner, plus both diffs;
  - source and candidate runner-config, launch-config and docker-ops;
  - source and candidate payload manifests and **full nested manifests**;
  - the unchanged peer `np_provider_peer.py`.
- **Inventory: 10 controls, 41 nested.** The breakdown is SUBJECT 1 + RUNTIME 7 + DIFF 2 + PRESERVED 2 + HELPER 7 + BARRIER 4 + ASSERTIONS 3 + BATCH 6 + PRIOR 2 + MUTANTS 7.
- **RETIREMENT-HELPER (behavioral):** the extracted unchanged helper with a named fake peer whose final row is published *during* the join.
  - post-join state only (calls exactly `[retire 5.0, state]`);
  - worker error refused;
  - an **empty-string error refused, distinct from None**;
  - unjoined refused;
  - `PeerRetirementUnknown` and other exceptions propagate as the same object;
  - exactly one attempt on all 6 paths.
- **Structural, labelled as structural (not a behavioral run of the whole case):**
  - **REFRESH-BARRIER-WIRING:**
    - the helper is called exactly once;
    - the mark comes immediately before it and the done flag immediately after;
    - no `retire_owned` call in the body, and the single `finally` retire is guarded by `retirement_attempted`;
    - no `sanitized_state` call in the body; every `peer_state` read comes after the barrier, which comes before the oracles and the passing receipt.
  - **REFRESH-ASSERTIONS-PRESERVED:**
    - the exact body delta: the snapshot is replaced in place by the 3-statement barrier and the 4-statement late block is removed, with everything else equal;
    - setup, handlers, `orelse` and `finally` are identical;
    - the SuiteStop messages are the source's minus only the subsumed one.
- **BATCH:**
  - the batch, gates and truthful note;
  - docker-ops is exactly `source.replace(root)`;
  - the evidence, public-CA and read-only bind agree;
  - payload delta exactly 2 rows and nested delta exactly 5.
- **PRIOR (mapped honestly):**
  - the selected-retirement fake PASS 13/85 (`A8CDBF04…`) ran over this exact source runner `4CBF198E`, so its helper properties map;
  - its MS-INVALID/NONEXPIRED body checks don't transfer to MS-REFRESH;
  - 9 dependency rows are unchanged, and the peer's `retire_owned`/`worker_error_kind`/`sanitized_state` lines are literal-checked.
- **Mutants (7), each with its own failure prefix; every anchor was checked unique in the whole candidate runner** (the barrier block is anchored with its `retirement_done` line, because the bare helper call also appears in MS-INVALID):
  - **behavioral:** `worker_error_guard_removed`, `worker_error_truthiness` (caught only by the empty-string case), `helper_pre_join_snapshot`;
  - **structural:** `body_pre_join_snapshot`, `body_second_retirement`, `attempt_guard_missing`, `helper_ignored`.
- **Held command:** `Future-Command-HELD.ps1.txt` (`-AdmissionSHA256 B42F0AC3…`). **Not authorized.**

## 3. Exact diff (Matt-Drops)
`Matt-thePlan-Scheduler-MS-Refresh-Retire-Prep-V1-2026-11-13.diff` (`55C339906E2517D4AA84E8F330C94DD82B601C8EFD414D14A6791DF804DAD357`, 129 lines). It covers the runner (2 hunks), runner-config, launch-config and docker-ops, from MS invalid-grant prep v2 to v1.

## 4. Limits and qualifications
- **Native:** 900/600, 120 + 5 peer, PKI 45 nominal, 32 commands / 22 success path, 1 MiB per command plus a separate 1 MiB report.
- **Fake:** 120 + 5 + two 5 s = 135 s nominal, 64 KiB streams, a 256 KiB result, and partial runtime provenance.
- **Not proved:** native refresh, T06 closure, peer timing and worker scheduling.
- **Prior MS-REFRESH unit evidence is not re-established here.**
- **Holds:** every fake and native run stays held. The T05 fake and T03 D1 cards are untouched.

Signed: Matt
