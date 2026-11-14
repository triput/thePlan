# Matt → Dex: diagnostic fake v2 preparation handback

November 12, 2026, about 19:30 PT. This responds to `Matt-thePlan-Scheduler-Diagnostic-Fake-V2-Preparation-2026-11-12.md` (SHA256 `7BC58DDF384A0100E0F7DDE6899A2A0E4A24DB779E540123A56526BE947D49EF`). I also acknowledge `Matt-thePlan-Scheduler-Stop-Findings-Reconciled-2026-11-12.md` (`4AC09F33…F714`). I worked solo; no subagents were used.

**Status: v2 is authored and frozen. No writer is active.** Nothing was imported, parsed, compiled, tested, verified or run. Both `launch_authorized` flags are false, and no EXECUTE acknowledgement exists. **No PASS is claimed.**

## Workspace and baseline
- **v2:** `C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-native-provider-runner-diagnostic-fake-prep-matt-v2`. It didn't exist beforehand.
- **Baseline:** v1 `…-fake-prep-matt-v1`, manifest `398F8A3C…CA3D`, verified 14/14 before copying and again after.
- **Approval receipt read:** `scheduler-runner-diagnostic-fake-v1.evidence/Fresh-Copy-Preparation-Approval.json`.
- **Diff re-hashed:** `Proposed-Fallback-Mutation-Anchor.diff` = `41E0506D…01F0`.
- **Not copied:** no result, receipt or failed staging evidence.

## Exact source change (the only executable-byte change)
`patch -p1` applied the approved diff (dry run first) to `packet/verify/check_native_provider.py`, line 872:
```
-                      ("return original  # Diagnostic failure must not replace the primary kind.", "raise"))
+                      ("return original", "raise"))
```
The checker hash goes from `D4010F1B…EBE8` to **`BA1C333D5109D38569B6784332B1291B1035EF88737D774D303F34F88D6C4C7A`**, which equals the expected candidate. It is LF only, and indentation is preserved. `diff` against v1 shows only line 872.

## Metadata refreshed (data only)
- **`packet/verify/OUTER-ADMISSION.json`:** checker pin, packet label → `…-v2`, note. New hash `22257FDEE02FD88893F2D1B5C5CC79F8DCD2205090C1B192D1DFEB9F47074723`. `launch_authorized` is false.
- **`packet/verify/VERIFICATION-ADMISSION.json`:** checker pin, OUTER pin, packet label → `…-v2`, note. New hash `DD9FB1BDD48077A5CD053930AA0A50B49026B9731C2B456D370D5BECDBA3D99C`. `launch_authorized` is false. Its 11 packet pins plus 1 runtime pin are otherwise unchanged.
- **`Launch-Decision.md`** (`ADCB9D68…C0CB`) and **`Future-Command-HELD.ps1.txt`** (`5F9836FB…39C6`) were rewritten for v2, so no v1 command or decision text remains in v2. The v1 copies stay only in v1.
- **`Input-Manifest.sha256`:** `EB680C4B7F26A5124DA445B82B73E66A18A4A1CB92E3816C4932FD43D8B1B6A4`, 14 entries, verifies 14/14.
- **Change set:** `diff -rq` v1 against v2 shows exactly these six files: the checker, both admissions, both documents and the manifest.

## Byte-identical by design
- all 14 controls and assertions, the `FileNotFoundError` oracle, the replacement `raise` and the unique-anchor guard;
- subjects: original `7FBDCAEE…`, candidate `40A1BA8E…`, host `7F7EA820…`, producer `2A4602CC…`, diff `F6135717…`;
- `EXPECTED-FAKE-STRUCTURAL.json` `D6702FE7…EE32`;
- wrapper `AE84E632…`, launcher `D22C37E3…`, outer admission script `7DCA32E2…`.

**Retained v1 lineage labels:** the checker's `PACKET_NAME` and EXPECTED's `"packet"` still read `…-fake-prep-matt-v1`, as you instructed. So a v2 result file will report that label. The admissions, the document and the manifest identify v2.

## Inventories and chain
- **Packet pins (VERIFICATION, 11):**
  - `verify/check_native_provider.py` `BA1C333D…`
  - `verify/launch_check.py` `D22C37E3…`
  - `verify/verify_admission.py` `7DCA32E2…`
  - `verify/EXPECTED-FAKE-STRUCTURAL.json` `D6702FE7…`
  - `verify/OUTER-ADMISSION.json` `22257FDE…`
  - `Invoke-Fake.ps1` `AE84E632…`
  - the five subjects listed above
- **Runtime (1, interpreter only):** `C:\Users\trish\AppData\Local\Programs\Python\Python311\python.exe` `5F7B89A6…52EC`. Not a standard-library, DLL or environment lock.
- **Acyclic chain:** the wrapper takes the VERIFICATION hash as an argument; VERIFICATION pins OUTER and the other 10 files; OUTER pins the checker, launcher, EXPECTED and interpreter. Nothing pins back up the chain.

## Exact future command (HELD)
```
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-runner-diagnostic-fake-prep-matt-v2\packet\Invoke-Fake.ps1' -AdmissionSHA256 'DD9FB1BDD48077A5CD053930AA0A50B49026B9731C2B456D370D5BECDBA3D99C'
```
Against this prep admission the wrapper refuses before starting any child. A run needs:
- a reviewed staging change that flips both booleans;
- the resulting new admission hash;
- Trish's one-shot approval, including authority to terminate the one owned child.

## Limits (unchanged)
- **Timing:** 120 s checker budget, plus 5 s for one kill/wait, plus two 5 s reader joins: **135 s nominal**. Startup, hashing, I/O and OS latency are excluded; there is no separate outer timeout.
- **Capture:** 64 KiB per stream and 256 KiB for the result.
- **Success** requires exit 0, no stdout or stderr output, joined clean EOF readers and the exact ordered 14-control PASS inventory.
- **Exclusive fresh evidence:** `packet/verify/FAKE-NATIVE-PROVIDER-RESULT.json` and `…-LAUNCH-RECEIPT.json`, both absent.
- **On failure, timeout, mismatch or UNKNOWN:** stop and preserve evidence; no retry, repair, rerun or cleanup.

## Proof status
- **Authored:** the one-line correction plus refreshed metadata.
- **Static:** the diff applies cleanly, hashes match, the scope diff is exactly six files, and the manifests verify.
- **Fake proof: not run.**
  - The corrected checker is unexecuted. Controls 1–13 passing in the v1 run is an ordering inference only.
  - The `context_ignored` and `walk_129` mutant oracles have never executed.
  - The `fallback_removed` mutant is statically expected to be detected via the fake `FileNotFoundError`.
- **Native proof: not run.**

## Preservation (re-verified after v2 work)
- v1 fake prep: 14/14
- failed staging `scheduler-runner-diagnostic-fake-v1`: 17/17, receipt still `3B385B4F…`, `.evidence` untouched (it now holds 9 files, all yours)
- successor `…-prep-matt-v1`: 266/266

## Scope statement
- Only reading, copying, the one literal `patch`, hashing, and JSON, manifest and document authoring.
- No imports, parsing, compilation, tests, helper or checker invocation, verification, rerun, installation, sockets, PKI, Docker, database, native execution or Git, and no `F:/Code Repo/ThePlan` edits.
- No cleanup, and no predecessor or evidence modified.
- One process note: my first attempt to rewrite the two documents was refused by my editor because the copied files hadn't been read first. I read and rewrote them, then regenerated the manifest. The intermediate manifest was overwritten before freezing, and no other file was affected.

Signed: Matt
