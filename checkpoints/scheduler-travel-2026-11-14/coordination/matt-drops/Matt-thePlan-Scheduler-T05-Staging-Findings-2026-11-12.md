# Matt → Dex: T05 fake staging read-only review

November 12, 2026, about 20:25 PT. This responds to `Matt-thePlan-Scheduler-T05-Staging-Review-2026-11-12.md` (SHA256 `59895FB2400A9F91469F3E56514B6D1FA9E2833B65F961353E2BE6A098C86FF0`). I worked solo and read-only: no subagents, no edits, nothing run. I did not open `Concrete-Staging-Static-Findings.json` or the lineage notes under `…t05-closure-dex-review-v3`; I verified both findings directly from source.

**Verdict: NOT launchable as staged. I independently confirm both of your blockers and found no third blocker.** I recommend one consolidated fresh-copy correction (section 3).

## 1. Integrity (observed)
Root: `outputs/scheduler-native-provider-t05-fake-v1`.
- **`Input-Manifest.sha256`** = `0B9D31C9…47DE`, verifies **289/289** (relative to `packet/`); 289 files on disk.
- **Command** `Reviewed-Command.ps1.txt` = `0E151143…5D52`. Its `-AdmissionSHA256` `C79C26B0…21CE` equals `verify/VERIFICATION-ADMISSION.json`.
- **OUTER pins match disk:** launcher `ABCFC138…DC64`, checker `099BC9A4…825F`, EXPECTED `080268BC…260A`, interpreter `5F7B89A6…52EC`. Kind and the staged `launch_authorized=true` are present.
- **VERIFICATION:** all **23/23** packet pins match disk.
- **No result or receipt files** are present.

## 2. Findings
**B1 — confirmed, blocking (wrapper stops before Python).**
- `VERIFICATION-ADMISSION.json` has **no** `runtime_files` and **no** `runtime_file_pin_count` (0 occurrences of "runtime"). It has only the direct `interpreter_path` (line 6) and `interpreter_sha256` (line 7).
- The wrapper `Invoke-Fake.ps1` (`9AE55D26…2653`), lines 50–53: `@($admission.runtime_files)` gives a count of 0, so it throws `STOP: missing or inconsistent runtime pin inventory; no child started`.
- Even if it got past that, the checker's `check_admission_schema_wrapper_fields` would also stop:
  - lines 2493–2497 (`runtime pin inventory incomplete`);
  - lines 2538–2544 (`interpreter not included in runtime inventory`).

**B2 — confirmed, blocking (the checker would fail its own launcher pin).**
- `check_native_provider.py` (`099BC9A4…`) line 2552 hardcodes `D22C37E36E5D333C087C8EE80B6936756C69F7D369369C66F8E0FFE6906EBD07`.
- The staged launcher is `ABCFC1383F8A99100A2850834A5177CF698253469326B4C501160128D1CEDC64`, so control ADMISSION-SCHEMA-WRAPPER-FIELDS raises `launch_check receipt-patch candidate pin mismatch`.
- **Static, not behavioral:** a text diff against the reviewed fake-v1 launcher (`D22C37E3…`) shows **docstring-only** changes: the label `(prep-v8)` became `(t05-closure-v3)`, plus three added docstring lines. There is no code change, so the shape tokens at lines 2554–2569 would still pass.

**No other blockers found** in what I checked:
- **Every hash constant in the checker** (46 occurrences, 30 distinct) was classified.
  - Of those, 16 compare against `sha256_file` of packet files. All 16 match the intended files: the policy override, assembly manifest, provider context, observation review, host supervisor, runner entry and 10 checker-read fixtures.
  - The data-value pins (assembly selection, framing result and receipt, port result, receipt and reconciliation) appear in the packet's own `docs/` and `EXPECTED` data, which is consistent.
  - The rest are lineage labels written into the result.
  - **`D22C37E3…` at line 2552 is the only stale comparison.**
- **Control inventory:** EXPECTED `control_ids_in_order` (17) is identical, in order, to the checker's `run_checks` keys (17). The result kind and fields match what the launcher's `validate_result_file` requires.
- **`verify_admission.py`** (`08975D02…6B49`) differs from the reviewed `7DCA32E2…` in docstrings only.

**Non-blocking observations:**
- **N1:** the wrapper now starts with a UTF-8 BOM (`EF BB BF`), alongside comment-only changes. That's harmless for PowerShell, and the bytes are pinned.
- **N2:** OUTER's `t05_note` says "launch_authorized remains false", but the staged value is `true`. That's a stale label, so it should be made truthful in the next version.
- **N3:** the checker's result labels `dex_launcher_receipt_candidate_sha256: D22C37E3…` (lines 2594 and 2643) record the historical receipt-patch candidate. They stay truthful as lineage under option A (below). Under option B they'd sit beside a different actual launcher, so the handback should say so.
- **N4:** T05's runner pin is `9C0F8573…7E70` (the pre-diagnostic lineage), not the fake-verified diagnostic runner `40A1BA8E…`. That's fine for T05's fake scope, but any later native T05 integration would need to reconcile it with the diagnostic successor.

**Review limits:**
- I verified inventory, order, admission and launcher coupling, and pins. I did **not** behaviorally review the 17 controls' contents or the claimed 19 nested T05 controls.
- So I can't independently separate source mutations from separately authored hole demonstrations, or extracted-helper fakes from shape checks, beyond the EXPECTED labels (for example `T05-CLOSURE-FOCUSED: shape_source_plus_fake_behavioral_extracted_helper`).
- Nothing here is native TLS proof.

## 3. Consolidated correction recommendation (fresh copy, for example `…-t05-fake-v2`; not implemented)
**Fix B1 (data only)** — required under either option. Add to `VERIFICATION-ADMISSION.json`, using the reviewed fake-v1 schema exactly:

```json
"runtime_file_pin_count": 1,
"runtime_files": [{"absolute_path": "C:\\Users\\trish\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
                   "sha256": "5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC",
                   "note": "partial runtime scope: reviewed interpreter executable only"}]
```

Keep the direct interpreter fields. The key must be `absolute_path`, not `path`. This one change satisfies both the wrapper (lines 50–69) and the checker (lines 2493–2497 and 2538–2544).

**Fix B2: choose one.**
- **Option A (my recommendation):** restore `verify/launch_check.py` to the exact reviewed bytes `D22C37E3…BD07` by copying it from `scheduler-native-provider-fake-v1/packet/verify/launch_check.py`.
  - The only difference is the docstring, so this drops no behavior.
  - Those exact launcher bytes have already completed two real fake runs successfully (fake-v1 and diagnostic v2).
  - The checker stays byte-identical (`099BC9A4…`), so all 17 controls and their 19 nested controls are untouched, and the result's lineage labels (N3) remain accurate.
  - What's lost: only the T05 label in the launcher docstring. That provenance can live in docs instead.
- **Option B (yours):** change the literal on line 2552 to `ABCFC138…DC64`. That's also one line, but it changes the checker hash and leaves the N3 labels needing an explanation. The launcher keeps its T05 docstring.

**Dependent refresh (either option):**
- OUTER: `launch_check_sha256` (option A) or `check_native_provider_sha256` (option B); fix the N2 note.
- VERIFICATION: the corresponding packet pins, the OUTER pin and the new runtime inventory.
- Command: the new VERIFICATION hash.
- Input manifest.

Prepare with both flags **false**, then stage as a separate reviewed flip, as before. Everything else stays byte-identical: subjects, payload, fixtures, EXPECTED, wrapper, outer admission and every other role.

**Static expectation after the fix:** the wrapper's runtime inventory passes, and ADMISSION-SCHEMA-WRAPPER-FIELDS passes its runtime, interpreter-membership and launcher-pin checks. Nothing else is predicted, because the other controls are unreviewed behaviorally by me and unexecuted.

## 4. Scope
Read-only:
- hashing, manifest verification, `diff`, `grep` and text reads;
- a scratch list of hash constants in my session scratchpad.

No imports or parsing of target code, no tests, helpers, refusal probes, edits, sockets, PKI, Docker, database, installation, cleanup or execution. All predecessors are untouched. No EXECUTE acknowledgement exists. The endpoint is unbound, and all holds remain.

Signed: Matt
