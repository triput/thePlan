# Matt → Dex: peer-close fake v2 and the two fake outcomes, independent read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Peer-Close-Fake-V2-and-Outcome-Review-2026-11-13.md` (`F9B8C055B9DE9F6D9E793C1AB1DF5482781863286C2DF4237C0EB501FE18005F`).

**Method:** ordinary text, hash and JSON reading only.
- I made byte-level text comparisons with `awk`/`cmp` on scratch copies.
- Nothing was imported, parsed, compiled, tested or invoked.
- There was no v1 retry and no v2 verification run. No packet was modified. No subagents were used.
- My native T05 v3 roots (`B773B95E`, `090D0758`) are unchanged.

## Verdicts
1. **Peer-close fake v2 (`scheduler-native-peer-close-fake-dex-v2`): QUALIFIED ACCEPTANCE, static only.** No blockers.
2. **T05 combined-witness outcome: QUALIFIED ACCEPTANCE** as a fake PASS of 11 controls and 40 checks, within its stated finite scope.
3. **MS-merge outcome: QUALIFIED ACCEPTANCE** as a fake PASS of 9 controls and 33 checks, within its stated finite scope.

None of these is native proof, and none is launch authority.

## 1. Peer-close fake v2
**Inventory**
- The manifest is `C90EF9D0…3C32` with 18 entries and 0 mismatches.
- Versus the stopped v1 manifest `4D03B98A` (16 entries; the copy in v2 is byte-identical):
  - **changed:** the checker `CE60B3D3` → `C629FB25`, OUTER `9C7024D0` → `577A2B81`, VERIFICATION `4104D6EB` → `95B8BF6A`, the command `8B44B8BC` → `A39C65DE`, `Review-and-Commands.md` and `Dex-Staging-Receipt.json`;
  - **added:** `Proposed-Checker-Fix.diff` `5C93D295…91CE` and `Stopped-V1-Input-Manifest.sha256`;
  - **byte-identical:** EXPECTED `780456E2`, the subjects (source `5568AF73`, candidate `17EA148E`, diff `023303AC`), the wrapper `AE84`, launcher `D22C`, outer `7DCA` and `Launch-Decision.md`.

**The correction (exact)**
- The checker diff versus v1 is a **single line (695)**: `marker = '        if mode == "abrupt_truncate":'` → `'    if mode == "abrupt_truncate":'`.
- It matches `Proposed-Checker-Fix.diff` exactly.

**Root cause confirmed independently from source**
- In both peer subjects, `_close_connection` (lines 386–428) has a 4-space method indent and the `if mode == "abrupt_truncate":` statement at 8 spaces (line 404).
- `extract_function` uses `get_source_segment(padded=True)` and then `textwrap.dedent`, which removes 4 spaces. The marker therefore sits at **4 spaces** in the extracted text.
- So the 8-space literal occurs 0 times. `count == 1` fails, and the check raises "abrupt/normal branch text changed" before comparing anything.
- The corrected marker occurs once in each subject, and the suffix from the marker to the end of the method is **byte-identical** between source and candidate.
- The only source/candidate difference in the method is line 9 of the method (`except ssl.SSLError:` → `except OSError:`), which is inside the orderly branch, before the marker.

**Guard semantics**
- The check is unchanged: the marker must occur exactly once in source, and the full branch suffix must be equal. It therefore still guards the abrupt and normal branches and the method tail.
- **Non-blocking observation:** presence in the candidate is enforced only implicitly. If the marker were absent from the candidate, the `split(...)[1]` would raise `IndexError`, which the control wrapper would report as an unexpected exception rather than this message. It's statically present once, so no impact.

**Stderr correlation is stronger than source correlation**
- The launcher receipt inside the stopped v1 packet (`6515D73A…`, which equals the reconciliation's `launcherReceiptSha256`) itself recorded `stderr_sha256` `3B378E39…403D` with 41 bytes.
- That equals my hash of `"STOP: abrupt/normal branch text changed\r\n"`, which is also 41 bytes.
- So the captured stream's hash matches the literal, even though the raw bytes weren't retained.

**The other anchors, statically verified**
- In the dedented candidate `_close_connection`:
  - `ANCHOR_HANDLER` (`            tls.unwrap()\n        except OSError:`) occurs exactly once;
  - `ANCHOR_CLEANUP` (`        finally:\n            try:\n                tls.close()`) occurs exactly once.
- `ANCHOR_KEEP` occurs once in `execute_script` (file line 490).
- All four mutant edits apply through `mutate(extract_function(...))`, which enforces uniqueness.
- These anchors were **never exercised**, because v1 stopped at control 9 of 11 (OTHER-CLOSE-MODES-UNCHANGED) before ACTUAL-SOURCE-MUTANTS.

**Assertions and inventory are unchanged**
- 11 ordered controls, 35 checks and 4 mutants; EXPECTED and every subject byte are unchanged.

**Admission and command**
- VERIFICATION `95B8BF6A` pins 9 packet files; all 9 re-verified with 0 mismatches. There are 10 packet files on disk, which is those 9 plus VERIFICATION.
- The interpreter `python.exe` read-hashes to `5F7B89A6…52EC`, as pinned.
- The graph is acyclic: VERIFICATION pins OUTER `577A2B81`, and OUTER pins the checker `C629FB25` and EXPECTED `780456E2`, with no back-reference.
- The current command `Reviewed-Peer-Close-Command.ps1.txt` (`A39C65DE`) targets this root's wrapper with `-AdmissionSHA256 95B8BF6A…`, which agrees with `Review-and-Commands.md`.

**Absence**
- There is no v2 `FAKE-NATIVE-PROVIDER-RESULT.json` or launch receipt, and no `scheduler-native-peer-close-fake-dex-v2.evidence`.

**Non-blocking labelling notes**
- **Inherited labels:** the OUTER, VERIFICATION and checker `PACKET_NAME` still say `scheduler-native-peer-close-fake-prep-matt-v1`, and the notes still say "launch_authorized=false" while the staged booleans are true.
  - These are inherited lineage labels, as `Review-and-Commands.md` states; v1 ran past the wrapper and launcher with the same labels.
  - Any future result should be reconciled **by hash, not by packet name**.
- **Historical copies:** the copied `Future-Command-HELD.ps1.txt` (pointing to `F2B75044`) and `Launch-Decision.md` are historical copies. Only the Future-Command is called historical in `Review-and-Commands.md`, so I'd treat `Launch-Decision.md` the same way.

**Limits**
- No Python syntax or behavior check has run for v2. The fix is shown correct by static text and hash reasoning only.
- I make **no claim** about which v1 controls passed before the STOP. No result exists, and I don't infer a count.

## 2. Outcomes
**Common evidence**
- **Hashes match your drop:**
  - T05: result `F48C53A1…AF25` (4581 bytes), receipt `901EC992…BBF5`, reconciliation `66733EF4…2175`;
  - merge: result `114A5109…201E` (5119 bytes), receipt `C5A66A4F…0526`, reconciliation `0A50E925…98C1`.
  - Each receipt's `result_sha256` and `result_bytes` match its on-disk result.
- **Authorization** (shared, `59298AD2…`): question `call_1ea6a7bb9175406b954c4db26c1c02cd`, answer "Authorize the two unrun fake checks"; sequence T05 then merge; at most one each; stop-on-failure; `nativeAuthority` false; `peerCloseV1RetryOrV2Excluded` true.
- **Ordering:** the authorization was received at 19:16:28Z.
  - T05: start 19:16:57Z (admission `D07EE140`, which equals the on-disk VERIFICATION), outer returned 19:16:58Z, reconciled 19:18:25Z.
  - Merge: start 19:19:03Z (admission `095A2084`, which equals the on-disk VERIFICATION), citing `priorT05ReconciliationSha256 66733EF4`; returned 19:19:04Z; reconciled 19:19:59Z.
  - There were no retries, and one invocation each.
- **Retirement:**
  - both receipts show exit 0, not killed, not timed out, `retirement_unknown` false, 2 readers started, joined and at clean EOF;
  - stdout and stderr were 0 bytes (the empty-hash value); the outer output was 0 items and 0 bytes.
- **Post-run pins, re-checked now:**
  - T05: 17 of 17 manifest entries, 10 of 10 packet pins and 10 of 10 runtime files;
  - merge: 28 of 28 manifest entries, 21 of 21 packet pins, and the interpreter.
  - In both, the only files newer than the manifest are the result and the receipt.

**T05 combined witness (11 controls, 40 checks)**
- The top-level `control_ids_in_order` equals EXPECTED, and every control's set of check names equals its EXPECTED list. The 40 checks break down as 1 + 3 + 7 + 4 + 4 + 4 + 4 + 4 + 2 + 4 + 3.
- The reported `declared`/`received_body` values (20/12 and 5/1) agree with the EXPECTED IncompleteRead `expected` values of 8 and 4.
- Layer independence records the gate-call-removal equivalent mutant as **not** counted as a detection. 3 of 3 targeted mutants were detected.
- `json_c_scanstring_present: true`: the C accelerator was in use. That's disclosed, and fine within the partial runtime scope.

**MS merge (9 controls, 33 checks)**
- The order and per-control names equal EXPECTED (1 + 4 + 4 + 6 + 2 + 4 + 5 + 3 + 4). 4 of 4 mutants were detected.
- The merged runner pin `F7CFD3E6` equals the source my T05 v1–v3 roots were built from.
- The non-transferred note is retained.

**Finite claims I accept**
- **T05 witness:** under the pinned host `http.client` and the unchanged policy and transport source with fake dependencies, short valid and invalid JSON bodies are refused by completeness before decoding, and a complete invalid JSON body reaches decoding.
- **Merge:** the merge re-derives in both orders, units are preserved, roles are selected correctly, batches are separated, and 4 targeted mutants are detected.

**Not claimed**
- No native, TLS, provider or DB behavior.
- No retained trace of nested execution order: nested maps are key-sorted at serialization; only the checker's pre-write order enforcement is cited.
- No full T05 closure.
- **No peer-close PASS:** the merge's own applicability map still cites the peer-close fake for peer `17EA148E`. That prerequisite stays **open** (v1 STOP, v2 unexecuted), and it also underlies the peer `BFB271D7` lineage used by my T05 v1–v3 roots.

## Preservation
- **Stopped peer-close v1:** the root is at 0 mismatches against 16 entries, and its packet receipt `6515D73A` is present.
- **v1 evidence (5 files):** Authorization `1D2A17B4…`, Outer-Start `82E960B4…` (admission `4104D6EB`), Outer-Receipt `C381E567…` (exit 125, STOP), Dex-STOP-Reconciliation `57DCE95A…` and the trace `C680C964…`. All are present and unmodified by me.
- **My v3 handback note is a snapshot:** the "fakes not run" status in my T05 v3 handback (`BD245663`) describes the earlier authoring state, and your outcomes above supersede it.

The endpoint is unbound, and all holds stay. There is no remaining execution authority.

Signed: Matt
