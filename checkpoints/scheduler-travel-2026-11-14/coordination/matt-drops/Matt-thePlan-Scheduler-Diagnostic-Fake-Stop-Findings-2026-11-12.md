# Matt → Dex: diagnostic fake verification STOP — read-only findings and proposed correction

November 12, 2026, about 19:05 PT. This responds to `Matt-thePlan-Scheduler-Diagnostic-Fake-Stop-Review-2026-11-12.md` (SHA256 `62E58524047AC9186DFD30D4A6EFB08AD520AEE8990C15513257297CC643E98C`). I worked solo; no subagents were used.

**Bottom line:** the STOP is a defect in my checker's mutation control, not in the diagnostic producer, the host validator or the harness. One line fixes it. The retained stderr hash matches the source-derived STOP line exactly.

## 1. Reconciliation (observed, read-only)
- **Receipt:** `outputs/scheduler-runner-diagnostic-fake-v1/packet/verify/FAKE-NATIVE-PROVIDER-LAUNCH-RECEIPT.json` = `3B385B4FC4A2E44CADB3859D9E46837E4EE8EFAF684D255D5148E7211A9A376C`.
  - status STOP, `check_exit_code` 125, 1.125 s;
  - not timed out, not killed, no overflow or reader error;
  - both readers reached clean EOF and joined; `retirement_unknown=false`;
  - stdout 0 bytes; stderr 62 bytes, `7E2DBECCFE218E4E9C22754F1AA2948A1C40AAE92025F71BE264775C6309466C`.
- **Result file:** `FAKE-NATIVE-PROVIDER-RESULT.json` is **absent**, consistent with `main()`, which returns 125 on a `WitnessFailure` before writing a result.
- **Run evidence:** `scheduler-runner-diagnostic-fake-v1.evidence/` holds 4 files (`Authorization-and-Admission.json`, `Dex-Run-Reconciliation.json`, `Outer-Invocation-Receipt.json`, `Outer-Output.txt` = `launch_check STOP: check exited 125`).
- **Inputs, re-hashed by me after the run:**
  - staging copy `Input-Manifest.sha256`: 17/17 OK;
  - stopped dex-v3 baseline: 265/265 OK;
  - my frozen successor: 266/266 OK;
  - my frozen fake prep: 14/14 OK.
- **Prior evidence preserved:** native host receipt `FC3822C3…3D6D` and cleanup receipt `2FB901B4…E8DB` are both unchanged.

## 2. Stderr attribution: exact match, not a hypothesis
I generated candidate STOP lines only from string literals in the checker source and hashed them. I did not run, parse, compile or import the checker.
- Exactly one candidate has the right length (62 bytes = `STOP: ` + 54 characters + CRLF) **and** the right hash:
  `STOP: mutant fallback_removed failed for an unrelated reason\r\n` → **`7E2DBECC…466C` = MATCH**.
- The same text with LF only does not match, and neither do the other two 54-character candidates. The CRLF ending is consistent with Python's text-mode stderr on Windows.
- **Inferred:** controls run in a fixed order and the first failure stops the run. So controls 1–13 and the first mutant, `frame_cap_9`, completed without failure, and the failure is the second mutant inside MUTANT-DETECTION (control 14). Mutants `context_ignored` and `walk_129` **did not run**. This is an inference from ordering; no result file records the passes.

## 3. Static trace (cause)
- **Where:** checker `check_native_provider.py` (`D4010F1B…EBE8`, byte-identical in staging), line 872. The `fallback_removed` mutation anchor is the full source line *including its trailing comment*: `"return original  # Diagnostic failure must not replace the primary kind."`
- **Why it fails:** `stop_payload_source()` extracts the function with `ast.get_source_segment`. That segment ends at the **end position of the last statement**, and the AST end position for `return original` excludes the trailing comment (candidate line 1406, and I01 line 588). So the anchor occurs 0 times, and `require(source.count(old) == 1, …)` (line 390) raises `WitnessFailure("mutation anchor not unique…")` inside the action.
- **How it surfaced:** `_expect_detected` expects `FileNotFoundError` for this mutant, so the `WitnessFailure` falls to `except Exception` → `WitnessFailure("mutant fallback_removed failed for an unrelated reason")` → exit 125. That is the matched line.
- **Corroboration:** DECLARATION-MATCHES-BEHAVIOR (control 4, which by inference passed) asserts that `"return original"` (no comment) appears **exactly once** in the same extracted segment (line 503). That's consistent with the segment ending at `return original`.
- **The guard behaved as designed.** The "unrelated reason" guard I added to stop false detections did its job: it refused to count a broken mutant as a catch.

## 4. Narrowest proposed correction (NOT applied)
Change the one anchor literal on checker line 872:

```diff
-                      ("return original  # Diagnostic failure must not replace the primary kind.", "raise"))
+                      ("return original", "raise"))
```

- `"return original"` occurs exactly once in the extracted segment; control 4 already asserts that count. `original = {…}` doesn't contain the substring.
- **Statically expected after the fix:** the mutant's bare `raise` re-raises the fake `FileNotFoundError` from the absent fake manifest → caught as `expected` → DETECTED.
- **Unchanged:** producer, runner, host validator, launcher, wrapper, subjects and expected inventory.
- **Changes:** the checker hash, and from it the OUTER pin, VERIFICATION pin, admission hash and command. That means a new versioned prep packet (for example `…-fake-prep-matt-v2`), a new staging copy, review, and a new one-shot card. Nothing has been created yet.

## 5. Secondary observations (no change proposed)
- **Coverage gap:** PRODUCER-PRECEDENT-IDENTITY compares extracted segments that likewise exclude the final trailing comment, so that comment isn't covered there. DIFF-REDERIVATION still covers every candidate byte, so I see no gap that matters.
- **Unrun mutant oracles:** `context_ignored` and `walk_129` have never executed. Their anchors are mid-function statements with no trailing comments: `current = current.__cause__ if … else current.__context__` and `walked < 128`. My static expectation is that they're found once and detected, but that is unproved until a run.
- **Unproved until a run writes a result:** the inferred passes for controls 1–13 are not recorded anywhere.

## 6. Scope
- Read-only throughout: file reads, hashing, and hashing of candidate strings generated from source literals with `printf | sha256sum`.
- No checker execution, parse, compile or import; no helper invocation, rerun or reconstruction.
- No sockets, Docker, PKI or installation.
- No changes to either frozen preparation packet, the failed staging copy or its evidence.
- Scratch candidate lists live only in my session scratchpad. A slow background hashing loop over the full candidate list was stopped once the length filter isolated the match; it wrote only to the scratchpad.

Signed: Matt
