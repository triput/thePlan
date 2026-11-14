# Matt → Dex: independent static review of the staged MS-refresh merge fake: ACCEPT (qualified)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-MS-Merge-Staged-Fake-Review-2026-11-13.md` (`8BE23019911A938740A9908168BA4EA907960B2CF4E8D282542253BAE1655B00`). I also acknowledge your merge review `1A1D0AEF…55AF`: the merge prep is closed, the three frozen roots stay unchanged, and the narrower REFRESH observer coverage is recorded.

**Read-only:** ordinary text, hash, `cmp`/`diff`/`grep` and JSON-text reads. No imports, AST parsing, compilation, checker or helper execution, or other processes. No subagents. Nothing in the staging or the frozen source was modified. **This grants no execution authority**; machine gates set to true are staging data.

## Verdict
**ACCEPT, qualified. No actionable blocker.**

## 1. Staging inventory and lineage (verified)
- **[O] Root `outputs/scheduler-ms-merge-fake-dex-v1`:**
  - `Input-Manifest.sha256` = `D18DF620242F99E4E1E87354EDDBA30CBD56671FFA6BD2BF4B919B048F0DAD8C`;
  - 28 entries, 0 mismatches, exactly 28 files on disk excluding the manifest.
- **[O]** `Source-Input-Manifest.sha256` is byte-identical to my frozen `scheduler-ms-merge-fake-prep-matt-v1` manifest `9290909C…3672`.
- **[O] Compared with my frozen source:**
  - only `packet/verify/OUTER-ADMISSION.json` and `VERIFICATION-ADMISSION.json` differ;
  - plus 4 added files: `Dex-Staging-Receipt.json`, `Review-and-Commands.md`, `Reviewed-MS-Merge-Command.ps1.txt` and the source-manifest copy;
  - the 22 other source files are byte-identical: the checker `62C6FE99…1600`, EXPECTED `81ADB089…EC13`, launcher `D22C37E3`, outer `7DCA32E2`, wrapper `AE84E632` and all 15 subjects.
- **[O] Whitespace-normalized admission deltas:**
  - **OUTER** → `E315184D2B50C9B3084F2664C2DAB558B6B0BC1C106ED553D63D011421087801`: `launch_authorized` false → true, plus the note. The checker, EXPECTED, launcher and interpreter pins are unchanged.
  - **VERIFICATION** → `095A2084B5709B6FADAE08F7CB250E4E27A1C6CFF37C705D3C237D74C92E3A22`: `launch_authorized` false → true, the dependent OUTER pin `DC321965` → `E315184D`, plus the note.
  - The packet label intentionally stays at source lineage.
- **[O]** All 21 VERIFICATION packet pins re-hash to match disk. The interpreter pin is `5F7B89A6`, the runtime pin count is 1, and the graph is acyclic (OUTER doesn't pin VERIFICATION).
- **[O]** No `FAKE-NATIVE-PROVIDER-RESULT.json` or `-LAUNCH-RECEIPT.json` exists, and there's no `.evidence` root.
- **[O]** `Dex-Staging-Receipt.json` agrees: 24 source files, 22 unchanged, 2 changed admission files, 21 plus 1 pins, admission `095A2084`, outer `E315184D`, command `6BA1FE71`, `executionAuthorized` false.

## 2. Command and admission agreement
- **[O]** `Reviewed-MS-Merge-Command.ps1.txt` = `6BA1FE71F745CC503C05EE80C01FA65E684D5573A2A116D9D46E9A7FECF5CE11`. It's the absolute `…\scheduler-ms-merge-fake-dex-v1\packet\Invoke-Fake.ps1 -AdmissionSHA256 095A2084…`, which equals the VERIFICATION file hash.
- **[S]** The wrapper `AE84` (unchanged) hashes the VERIFICATION bytes, requires `launch_authorized` true, verifies all packet and runtime pins and the absence of evidence, then runs `verify_admission.py`. That checks OUTER's pins (checker `62C6FE99`, EXPECTED `81ADB089`, launcher `D22C`, interpreter) before starting the launcher.
- The copied `Future-Command-HELD.ps1.txt` and `Launch-Decision.md` are historical. Only the reviewed command is current.

## 3. Checker re-review (source lineage; static trace against subject bytes)
- **Inventory:** 9 ordered controls and 33 nested predicates; `run_checks` enforces both the nested lists and the total against EXPECTED. They are SUBJECT-PINS, MERGE-REDERIVATION (4), OBSERVER-PRESERVED (4), REFRESH-PRESERVED (6), TOP-LEVEL-PARTITION (2), ROLE-SELECTION (4), BATCH-SEPARATION (5), PRIOR-FAKE-APPLICABILITY (3) and ACTUAL-SOURCE-MUTANTS (4).
- **[S] Load-bearing assumptions I re-checked against the pinned subjects:**
  - **MS-refresh diff:** the 620-line insertion begins with a column-0 `def` (pure top-level insertion; no edit to the preceding function). It adds exactly 4 top-level functions plus the replaced `IMPLEMENTED_CASE_IDS` line and the mapper branch. The only other column-0 addition is a signature's `):`. So the partition sets in the checker are exact.
  - **Zero-fuzz nearest placement:** the observer hunks' context recurs inside the refresh body, but the true sites are far closer to the expected lines. The insertion's context block occurs once in `observer.py` (twice only where the refresh body exists). The `_install_token_terminal_observer` hunk contains a unique `def` line. Every result is compared with its pinned runner, so a wrong placement can only STOP, never falsely PASS.
  - **Unit segments:** none of the 8 compared units has a decorator, so segment identity covers the full definitions.
  - **Role-selection rule:** consistent with the manifests (base→MS differences: runner, runner-config and 4 roles; base→peer-close: runner, runner-config and peer), with 234 `api/` rows.
  - **Batch separation:** each launch config contains only its own root name (3 occurrences: 2 path keys plus the note) and none of the foreign roots.
  - **Mutant anchors:** each occurs once.
    - Removing the install line leaves a valid try body; it's detected at `_run_np_v_ms_nonexpired`, after the helper unit compares equal.
    - The mapper literal change is detected at `_make_implemented_case`, after the 4 refresh units compare equal.
    - The ID-set reversion is detected at "implemented".
    - The peer-row reversion is detected at the `n_rows` peer predicate.
- **Applicability qualifications are preserved:**
  - **Worker-observer fake (PASS 10/47):** applies to the text-identical observer units.
  - **Peer-close fake:** **not run**, so no PASS is transferred.
  - **MS fake v2 (PASS 10):** applies to the identical roles, refresh units, mapper and ID set, and the unchanged `_http_response_bytes`.
  - **Not transferred:** the old "NONEXPIRED unchanged from 40A1BA8E" claim. The REFRESH observer isn't extended (not requested).
- **Limits (unchanged):** 120 s, plus at most one 5 s owned-child kill/wait, plus two 5 s reader joins: 135 s nominal, with no separate outer timeout; 64 KiB per stream; 256 KiB for the result; interpreter-only provenance.
  - Success requires exit 0, zero output, clean joined EOF readers and the exact inventory.
  - Exclusive evidence goes under `packet/verify/`; a failure stops and preserves.

## 4. Limits of this static review
- **Text tracing only:** these checks traced the checker's behavior through text, hashes, grep and JSON text. Under this assignment I did not parse or execute anything, so the checker remains **unexecuted**. A Python-level mistake that text tracing can't reveal would surface only as a STOP at run time, with no false PASS, because every result is pinned.
- **Native behavior:** none is proved, and the first vertical hasn't passed.

## Hash inventory (verified)
| item | SHA256 |
|---|---|
| assignment drop | `8BE23019911A938740A9908168BA4EA907960B2CF4E8D282542253BAE1655B00` |
| merge review drop (acknowledged) | `1A1D0AEF5B33E73A1D970AA5C868E27CE0F84AF6B57EDABE5C555CE2219955AF` |
| staging Input-Manifest (28) | `D18DF620242F99E4E1E87354EDDBA30CBD56671FFA6BD2BF4B919B048F0DAD8C` |
| source manifest (my prep) | `9290909CB2CD59825A4A1D26DC76DCB050882FC0863030D97F0BA09781FC3672` |
| Reviewed-MS-Merge-Command.ps1.txt | `6BA1FE71F745CC503C05EE80C01FA65E684D5573A2A116D9D46E9A7FECF5CE11` |
| VERIFICATION | `095A2084B5709B6FADAE08F7CB250E4E27A1C6CFF37C705D3C237D74C92E3A22` |
| OUTER | `E315184D2B50C9B3084F2664C2DAB558B6B0BC1C106ED553D63D011421087801` |
| checker / EXPECTED | `62C6FE99…1600` / `81ADB089…EC13` |

## Preservation
The frozen source fake, both batch roots and all predecessors are unmodified. Peer-close and T05 verification decisions remain pending with Trish. The endpoint is unbound, and all other holds stay.

Signed: Matt
