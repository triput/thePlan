# Matt → Dex: MS-Refresh focused fake v2 (B1 CRLF fix) handback

November 12, 2026, about 23:00 PT. This responds to `Matt-thePlan-Scheduler-MS-Refresh-Prep-Review-2026-11-12.md` (SHA256 `F565FDE32F03199335DB635F8C49C71D427D52759828EEA59990AAB48ABEF92C`), under envelope `389A00DD…7E2D` and scope `EAAFA222…488A`. I worked solo.

**Status: frozen, no active writer.** Both admissions have `launch_authorized=false`. Nothing was imported, parsed, compiled, tested or invoked. No EXECUTE acknowledgement exists. The endpoint is unbound.

**B1 accepted: my defect.** I independently confirmed it. The production subject `microsoft_calendar.py` (`6A52B10F…D6EF`) has 2,252 CR bytes; the other 11 subjects have 0. v1's `b"\r" not in data` would have stopped SUBJECT-PINS. **G4:** thank you for the 22-call derivation; noted.

## Workspace
`C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-ms-refresh-fake-prep-matt-v2`. It didn't exist beforehand.
- **Base:** fake v1 (manifest `3FD4346A…60A7`), verified 21/21 before copying and after. It is untouched.
- **Fixture prep** `scheduler-ms-refresh-prep-matt-v1` re-verified 278/278 and is untouched.

## Exact checker diff (the only executable change)
`packet/verify/check_native_provider.py`, line 197:
```
-        require(b"\r" not in data, f"subject not LF:{rel}")
+        require(b"\r" not in data.replace(b"\r\n", b""), f"subject contains bare CR:{rel}")
```
- The hash goes from `532D8741…356C` to **`6F4D83C04640E596A806E19FFCECDA026662CEB51B6B138C3C79EFBDD1FD2971`**. It's your suggested predicate verbatim. The `replace` result is only a predicate input: raw-byte hashes are unchanged, the original decoded text still goes to AST, and nothing is normalized or written.
- **Process note:** my first attempt (an `awk` line replacement) silently didn't apply, because `awk -v` converts `\r` into a real CR. I caught it from the unchanged hash before anything else happened and applied the edit with an exact-text editor. The `diff` shows line 197 only.
- **My extra CRLF review (no further defect found):** the only other use of the CRLF subject is extraction of top-level `_LOGIN_BASE`, `_normalize_tenant` and `_token_url`. The dedent margin is empty for top-level functions, and `compile` accepts CRLF. No mutation anchors target the production text.

## Data refresh
- **`packet/verify/OUTER-ADMISSION.json`** → **`5F3FA66F3BFCEA320CC19AEC2BEF0845A8620BD6027B99296BA803FD1830D77F`:** checker pin; packet label `…-v2`; note. False.
- **`packet/verify/VERIFICATION-ADMISSION.json`** → **`A544D39F2A4A010D96190E2146DDDE0AF87EC42DF19C23170E29C273CA3DC79D`:** checker and OUTER pins; packet label; note. False. It has 18 packet pins (all re-verified against disk) and 1 runtime pin, the interpreter `5F7B89A6…`.
- **`Launch-Decision.md`** (`3E0D901E…EA58`) and **`Future-Command-HELD.ps1.txt`** (`6E67FEBE…0AA6`) were rewritten for v2.
- **`Input-Manifest.sha256`** = **`266C2904E73ABA7432331570F5AABA6E2434E7B01AC87B59A9C46DD219017CF8`** (21 entries, 21/21 OK). `diff -rq` against v1 shows exactly these six files.

## Unchanged
- all 10 controls, nested cases, assertions and the 4 actual-source mutants;
- all 12 subjects;
- EXPECTED `FD98745D…`;
- wrapper `AE84E632…`, outer admission `7DCA32E2…`, launcher `D22C37E3…`.

The checker's `PACKET_NAME` keeps its v1 lineage label, so the diff stays one line.

## Held command
```
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-ms-refresh-fake-prep-matt-v2\packet\Invoke-Fake.ps1' -AdmissionSHA256 'A544D39F2A4A010D96190E2146DDDE0AF87EC42DF19C23170E29C273CA3DC79D'
```
- The wrapper refuses while the flags are false.
- A run needs your reviewed staging flip and Trish's one-shot approval, including bounded owned-child termination.
- Bounds: 120 + 5 + 5 + 5 = 135 s nominal; 64 KiB per stream; 256 KiB for the result; exclusive evidence under `packet/verify/`.

## Proof boundary (unchanged)
- **Static only;** the checker has never executed.
- Everything listed under "Not proved" in v1 still stands: native OAuth, TLS, persistence and the second target remain unproved, and `_run_np_v_ms_refresh` is checked for shape only.
- The native REFRESH run waits on the diagnostic outcome plus its own approval.

## Scope
Copy, one exact-text edit, `sed` value and label swaps in two admissions, hashing, and document and manifest authoring. No execution of any kind. No packet other than the new v2 directory was modified.

Signed: Matt
