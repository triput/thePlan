# Matt → Dex: T08 ownership fake packaging and staged invocation, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T08-Packet-Staging-Review-2026-11-13.md` (`1D278C3C432941122076A014B83FF3E40D983F22D09886D0D318B13278E869EE`).
- **Method:** read-only hashing, byte comparison, text diff, and reading the unchanged launcher's result contract.
- **Not done:** imports, interpreter parsing, compilation, tests, helper invocation or execution.

## Verdict: accepted, with qualifications (no blocker)

### Pins
- **Packaging `scheduler-t08-ownership-fake-prep-dex-v1`:** `B768B3AF…964D`, 14 rows, 0 mismatches.
- **Staging `scheduler-t08-ownership-fake-dex-v1`:** `E8E67089…672F`, 18 rows, 0 mismatches. There are 9 packet files and no `FAKE-NATIVE-PROVIDER-*` outputs.
- **Subjects** (JoinedTLS `76017776`, runner `C7A0D2DC`) are byte-identical across v3, packaging and staging.
- **Helpers** (wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`) are byte-identical to the Google fake staging that ran.
- **Packaging to staging:** the checker `9A8146CB`, EXPECTED `3B66FBB3`, the subjects and the helpers are identical.

### Checker delta from v3 `6BE2B15B` to `9A8146CB`: protocol only
- **Added:** the `EXPECTED` path; `CONTROL_IDS` (7); `MUTANT_IDS` (3).
- **New preamble in `run()`:** it reads EXPECTED and requires `kind` == `t08-ownership-fake-expected`, the exact control and mutant order, and `reported_predicates` == 9.
- **Control rows** become `{"observed":"PASS","control_kind":…}`.
- **Two new checks:** `require(list(mutation_results) == list(MUTANT_IDS))` and `require(list(controls) == list(CONTROL_IDS))`.
- **The result becomes the generic envelope:** `kind` = `fake-native-provider-structural-result`, `prep_is_not_pass` true, `launch_authorized` false, `passed` 7, `failed` 0, `control_ids_in_order`, `nested_predicates` 9, `endpoint` unbound, `native_proof` false. The mutants move under `ACTUAL-SOURCE-MUTANTS`.
- **Unchanged:**
  - every property oracle (`foreign_check`, `foreign_close`, `owner_use_close`, `reuse`, `native_wiring`);
  - the 3 mutant anchors, including the l.176 `def open(self)`-qualified reuse anchor;
  - the unique-anchor guard and the prefix matching;
  - the fakes;
  - the exclusive `RESULT.open("xb")`;
  - STOP → stderr `STOP:<type>` and exit 125.
- **Imports** are stdlib only: `ast`, `hashlib`, `json`, `sys`, `types`, `pathlib`. No threads, sockets, TLS or application imports.

### Launcher compatibility (`launch_check.py` `D22C37E3`, l.134–172 and l.430–541)
- The launcher reads EXPECTED's `control_ids_in_order`; `3B66FBB3` lists the same 7, in order.
- **Result validation:** it requires `kind` (match), `prep_is_not_pass` true (match), `endpoint` unbound (match), `failed` == 0 (match), an equal `control_ids_in_order` (match), and every control `observed` == PASS (match).
- **Process checks:** it requires exit 0 with zero stdout and stderr. The checker prints nothing on PASS, and exits 125 with stderr on any STOP, which the launcher refuses.
- **Outputs:** pre-existing result or receipt files are refused, and the checker's `xb` write is exclusive.
- **Result:** compatible.

### Admission graph and command
- **Preparation to staging,** for both OUTER and VERIFICATION: only `launch_authorized` false → true and the note change. VERIFICATION also takes the dependent OUTER pin, `B22074CA` → `3B10C2F2E6B8D85CE83585C1FFAAE2E943FF7CE76889495BE697D7C529B7D300`.
- **OUTER pins:** interpreter `5F7B89A6`, launcher `D22C37E3`, checker `9A8146CB`, EXPECTED `3B66FBB3`. Check 120 s, total 135 s, no separate outer timeout.
- **VERIFICATION:** 8 packet pins and 6 runtime pins (python.exe, the DLL, the json trio, `ast.py`). **All 14 verified on disk.** Caps 262144 / 65536, joins 5, kill wait 5, check 120, total 135.
- **Closed graph:** OUTER does not pin VERIFICATION, and the wrapper roots on VERIFICATION.
- **`Reviewed-T08-Ownership-Fake-Command.ps1.txt`** = `0CDC2C7D46C5C93784D0E5268A7258C898134FAFBDFE5AD2868EEB3E8F405261`. It is this staging root's own `packet\Invoke-Fake.ps1` with `-AdmissionSHA256 8754AC3588CC1AEC9B54DDF48D76CA8F9D08A37DD3BA8C0670B55FD9B79FE82A`, equal to VERIFICATION on disk.

### Counts and scope
- 7 ordered controls and 3 exact mutants in order. The 9 reported units are 6 non-mutant controls plus 3 mutant oracles, not native obligations.
- `Review-and-Commands.md` states this truthfully, along with the named-fake scope, structural-only native wiring, the partial runtime and the 135 s bound with its exclusions.

## Qualifications
1. **Unexecuted.** The checker's syntax and behavior have not run, so the first run may still STOP on an authoring defect.
2. **`passed: 7` is a literal.** It is sound only because every control failure raises before the result is written.
3. **Partial runtime provenance.** 6 pins; `hashlib`, `types`, `pathlib`, the extensions and the environment are unpinned.
4. **Fakes, not native proof.** The owner identity, socket, budget and factory are named fakes. Native wiring is structural only. Real foreign-thread and TLS ownership, the case body and its fault retirement remain unproved.
5. **Native qualifications carried forward** from `4C8B135D`: cleanup-failure aggregation and the orderly-close inference.
6. **No authority.** The machine flags are scaffolding. A run needs Trish's exact one-shot approval of `0CDC2C7D`, and Google native stays first and separately pending.

**Preserved:** all predecessors (v1–v3 source, packaging, the native T08 root, the Google roots). Endpoint unbound; all holds stay.

Signed: Matt
