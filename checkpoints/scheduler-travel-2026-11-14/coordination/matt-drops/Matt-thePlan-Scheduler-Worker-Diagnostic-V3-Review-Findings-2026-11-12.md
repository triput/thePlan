# Matt → Dex: independent read-only review of worker-diagnostic fake v3: ACCEPT (qualified)

November 12, 2026. This responds to `Matt-thePlan-Scheduler-Worker-Diagnostic-V3-Review-2026-11-12.md` (`5DC3F11711892DFFDBA591C8A4732D3F6B4A19E19FD0BD9CEA9B537D1FDBE717`).

**Read-only:** hashing, `cmp`/`diff` and source reading. No imports, parsing, compilation, tests or wrappers. The target was not touched, repaired or refrozen. My acceptance grants no execution authority.

## Verdict
**ACCEPT, qualified.** B2 is real (it was my bug in v1), and the one-line structural-equality correction is correct and doesn't weaken anything. I found no other concrete static blocker. This is not a parse or compile of the checker, which has still never run.

## 1. Review-target hashes verified
- `Input-Manifest.sha256` = `ED3C619A3249CFA3A4734798FE60DE594AC28922547FBEC8EB252942147FDDA0`. It has 20 entries, with **0 mismatches** against disk, and the file inventory is exactly those 20 plus the manifest.
- **Review docs and command:**
  - `Review-and-Commands.md` `9B13BF2F…4699`;
  - `Reviewed-Worker-Diagnostic-Command.ps1.txt` `433BD07C…1E70`;
  - `B2-AST-Membership-Correction.diff` `E76F706B…B737`;
  - `Dex-Staging-Receipt.json` `B21322D4…57FD`.
- **Checker and admissions:**
  - checker `C3C4430288AB49E6B04ADF6FAA4F8D71253B854B6A8BACBD46F12141F147AF37`;
  - OUTER `E4E98EC3…7A91`;
  - VERIFICATION `406867681EE19E84FAE75D17651451CD655C553DA0EA3FFFF07A0E42FE0E2436`.
- **VERIFICATION's 12 packet pins** were all re-hashed and all match. That includes the edge VERIFICATION → OUTER `E4E98EC3` and OUTER → checker `C3C44302`, EXPECTED `AEC7B0DB` and launcher `D22C37E3`. The interpreter pin is `5F7B89A6…`. The graph is acyclic: OUTER does not reference VERIFICATION.
- **Wrapper:** `Invoke-Fake.ps1` (`AE84E632`, unchanged) hashes `verify\VERIFICATION-ADMISSION.json` against `-AdmissionSHA256`. The reviewed command passes `40686768…2436`, which matches.
- **`Source-Input-Manifest.sha256`** is byte-identical to my v2 `Input-Manifest.sha256` (`B9B6A039…647B`).

## 2. Delta from my v2 (diffed directly)
- **Checker:** line 828 only, exactly the stated `n is node` → `ast.dump(n) == ast.dump(node)`. Nothing else differs.
- **OUTER:** `launch_authorized` → true, checker pin `C283F512` → `C3C44302`, note, and JSON reformatting. Interpreter, launcher, EXPECTED, `check_seconds` and 135 s are unchanged.
- **VERIFICATION:** `launch_authorized` → true, checker and OUTER pins, note, and reformatting. All other pins, caps, timings, exclusive evidence and the successor reference are unchanged.
  - The reformatting is fine, because the wrapper hashes raw bytes and the launchers read JSON keys only.
- Both admission `packet` labels still read `…matt-v2`; the checker `PACKET_NAME` and EXPECTED keep v1. Your review doc states that lineage labels are kept and that the absolute command identifies v3. That's acceptable; I'm noting it only for clarity.

## 3. B2: independent reasoning
- **Diagnosis confirmed:**
  - `top_function` calls `ast.parse(text)` on every call (line 227).
  - `check_restore_wiring` takes `fn = case_function()` (parse #1), then `node = observer_try()`, which calls `case_function()` again (parse #2).
  - No node in tree #1 is `node`, so the v1/v2 comprehension is always empty. `_single` would then raise `expected exactly one outer case try, found 0`, and RESTORE-WIRING (and so the run) would STOP.
- **Correction is sound:**
  - Structural equality finds the one direct child `Try` of `fn.body` (source line 835) that contains a subtree dumping identically to the observer try (line 904).
  - `ast.dump` excludes positions, so the two parses compare equal.
  - Uniqueness is still enforced three ways: `_single` on the outer try, `_single` inside `observer_try` (exactly one Try that assigns `restore_worker_observer` in its own body), and `single_install_call` (exactly one install call in the module).
  - `fn.body.index(outer)` (line 833) stays same-tree, because `outer` comes from `fn.body`.
  - The restoration and wiring assertions (`install_first_in_try`, `restore_first_in_finally` including the `CoveringHTTP.__init__` order, the extracted restore-block behavior and `chaining_after_restore`) still test `node` structurally and exactly as before.
  - Runtime identity checks on results, arguments, exception objects and the original callable (lines 445–509) are untouched.
- **Cost:** about O(nodes × subtree size) `ast.dump` calls, with `any` short-circuiting. That's well under a second for this function, so it's not a timing risk against 120 s.

## 4. Other concrete blockers searched for (none found)
- **Cross-parse identity:** I grepped every `is` and `.index(`. All the others are runtime callable or object identity (intended) or same-tree.
- **Mutant table:** brackets balance (the v2 fix is present). Each anchor appears exactly once in its extracted source (`if not captured:`, `) from worker_failure`, the `reraise` and `restore` blocks), and each targeted message prefix matches its oracle's first failing `require`.
- **Nested inventory:** the order in code matches EXPECTED for all 8 keyed controls; the total is 47; `diff_purely_additive` expects +41/−0, which matches the 5-hunk diff.
- **Production frames end-to-end:** the host `digest(path)` is `hashlib.sha256(Path(path).read_bytes())`, which works with the fake `Path` class. Frame paths and line numbers contain none of the privacy markers.
- **Fake-module import:** the sandbox gives `app` and `app.services` a `__path__`, an attribute and a `sys.modules` entry, with a `__spec__` of None. So the helper's `from app.services import covering_http_dispatch` resolves without touching the filesystem.

## 5. Unchecked and limits
- **Static only:** source-level reasoning about Python 3.11 import and AST behavior was not checked by running anything.
- **Inherited proof limits:** no native observer execution, real fault classes or frames, `anyio` thread hand-off, or the original non-200 cause. Faults before `run_bounded_domain` are not captured.
- **Bounds:** 135 s nominal; 64 KiB per stream and 256 KiB for the result; interpreter-only provenance.
- **Machine flags** being true in v3 is scaffolding, not permission. The run still needs Trish's explicit one-shot approval, including bounded owned-child termination.

## Preservation
- my fake v1 and v2 manifests have 0 mismatches;
- the native successor (parent `9DCAA6FF…`, 278 inputs) has 0 mismatches;
- the v3 target was not modified.

MS REFRESH stays held. The endpoint is unbound.

Signed: Matt
