# NP-V-MS-REFRESH focused fake verification v2: preparation (HELD)

Matt, November 12, 2026. Responds to Dex review `Matt-thePlan-Scheduler-MS-Refresh-Prep-Review-2026-11-12.md` (`F565FDE3…F92C`), finding **B1**. Companion to the fixture preparation `outputs/scheduler-ms-refresh-prep-matt-v1`, which is unchanged and frozen.

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`. No PASS is claimed.

## The single correction (v1 → v2)
- **Baseline:** a fresh copy of `scheduler-ms-refresh-fake-prep-matt-v1` (manifest `3FD4346A…60A7`, verified 21/21 before copying). v1 is preserved.
- **Change:** `packet/verify/check_native_provider.py`, line 197, in `check_subject_pins`:
  ```
  -        require(b"\r" not in data, f"subject not LF:{rel}")
  +        require(b"\r" not in data.replace(b"\r\n", b""), f"subject contains bare CR:{rel}")
  ```
  - The checker hash goes from `532D8741…356C` to **`6F4D83C04640E596A806E19FFCECDA026662CEB51B6B138C3C79EFBDD1FD2971`**.
  - **Why:** the unchanged production subject `subjects/production/microsoft_calendar.py` (`6A52B10F…D6EF`) is CRLF (2,252 CR bytes), so v1 would have stopped in SUBJECT-PINS.
  - The `replace` result is only a predicate input. Raw-byte hashes are unchanged, the original decoded text still goes to AST extraction, and no subject is normalized or rewritten.
- **Byte-identical:** all 10 top-level controls, nested cases, assertions and mutants; all 12 subjects; EXPECTED `FD98745D…`; wrapper `AE84E632…`, outer admission `7DCA32E2…`, launcher `D22C37E3…`. The checker's `PACKET_NAME` label intentionally keeps v1 lineage to avoid widening the diff.
- **Data refreshed:** OUTER → **`5F3FA66F3BFCEA320CC19AEC2BEF0845A8620BD6027B99296BA803FD1830D77F`** (checker pin, packet label, note); VERIFICATION → **`A544D39F2A4A010D96190E2146DDDE0AF87EC42DF19C23170E29C273CA3DC79D`** (checker and OUTER pins, packet label, note; 18 packet pins plus 1 runtime pin, all re-verified against disk). Both are `launch_authorized=false`.

## Controls (unchanged from v1; proof layer per control)
1. SUBJECT-PINS (raw_pin; now admits CRLF pairs and rejects bare CR).
2. NONEXPIRED-AND-DIAGNOSTIC-PRESERVED (extracted_text_identity).
3. TENANT-PATH-AGREEMENT (extracted_behavior_fake).
4. OAUTH-ROUTE-TABLE (extracted_behavior_fake).
5. REFRESH-INVENTORY-ORDER (extracted_behavior_fake).
6. SEMANTIC-PERSISTENCE-ADMISSION (extracted_behavior_fake).
7. SECRET-EXCLUSION-PROJECTION (extracted_behavior_fake).
8. REGISTRY-MAPPING (structural_source).
9. REFRESH-BODY-SHAPE (structural_source, shape only).
10. ACTUAL-SOURCE-MUTANTS (actual_source_mutant ×4).

Details are as in v1. **CRLF re-check:** the production functions extracted are top-level (`_LOGIN_BASE`, `_normalize_tenant`, `_token_url`), so the dedent margin is empty, and `compile` accepts CRLF source. No other control reads a CRLF subject.

## Not proved
- native OAuth over JoinedTLS;
- native persistence and real Fernet;
- the single peer serving both hostnames;
- the second target's ROLLBACK without a request;
- native TOKEN, IMPORT and ASSESSMENT terminals and the response;
- `_run_np_v_ms_refresh` behavior (shape only).

## Limits (inherited launcher)
- **Timing:** 120 s, plus at most one 5 s kill/wait, plus two 5 s reader joins: **135 s nominal**, with the same exclusions and no separate outer timeout.
- **Capture:** 64 KiB per stream and 256 KiB for the result.
- **Success** requires exit 0, no output, joined clean EOF readers and the exact ordered 10-control PASS inventory.
- **Exclusive evidence** goes under `packet/verify/`; a failure stops and preserves, with no retry.

## Future command
`Future-Command-HELD.ps1.txt` (admission `A544D39F…`). The wrapper refuses while the flags are false.
