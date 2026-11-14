# Worker-exception observer diagnostic: focused fake verification v2 preparation (HELD)

Matt, November 12, 2026. This responds to Dex's review `Matt-thePlan-Scheduler-Worker-Diagnostic-Checker-Review-2026-11-12.md` (`0603526D…C530`), finding **B1**. It's the companion to the frozen native successor `outputs/scheduler-native-provider-worker-diagnostic-prep-matt-v1` (runner `341074AE…`, launch-config `EBE26FB5…`), which is unchanged.

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`. No PASS is claimed.

## The single correction (v1 → v2)
- **Baseline:** a fresh copy of `scheduler-native-worker-diagnostic-fake-prep-matt-v1` (manifest `A2EEE664…7985`, verified 15/15 before and after the copy). v1 is preserved.
- **Change:** `packet/verify/check_native_provider.py`, mutant table lines 974, 976, 979, 980 and 983. One excess `)` was removed from each line, because the outer `(lambda …, prefix)` tuple had closed before its prefix element. That's 5 lines removed and 5 added; no other byte changed.
  - The checker goes from `38BE55DF…C4E4` to **`C283F512F15FEFDD3CCAD3F1525229C350035BEB564FB77DE542BCA2C73397ED`**, which equals Dex's expected hash.
  - The checker's `PACKET_NAME` keeps the v1 lineage label so the diff stays minimal.
- **Byte-identical:**
  - all 10 controls, the 47 nested entries, assertions, message prefixes and the 5 mutants;
  - all 6 subjects;
  - EXPECTED `AEC7B0DB…5FA9`, whose packet label also keeps v1 lineage;
  - the wrapper `AE84E632…`, outer admission `7DCA32E2…` and launcher `D22C37E3…`.
- **Data refreshed:**
  - OUTER → **`AF10CFE7ABC61D0DB9DDAF6F0EE80E2CF664F9938EAC8AF5A2E85E99AAA44D43`** (checker pin, packet label, note);
  - VERIFICATION → **`AAA6C38692096AE373820D97F53BBE6EB65DE53B919DEC0FF7BD722374071175`** (checker and OUTER pins, packet label, note; 12 packet pins plus 1 runtime pin, all re-verified against disk).
  - Both are `launch_authorized=false`.

## Independent re-review
After the fix, a text bracket-balance scan over the whole checker (strings and comments stripped) shows no negative depth anywhere and a final depth of 0. Before the fix, it flagged only these five lines. I found no other concrete defect. This is a text heuristic, not a parse.

## Controls
These are unchanged from v1; see the v1 `Launch-Decision.md`:
1. SUBJECT-PINS
2. DIFF-REDERIVATION
3. PRESERVED-OUTSIDE-CHANGE
4. PRODUCTION-BOUNDARY-STRUCTURE
5. OBSERVER-SUCCESS-IDENTITY
6. OBSERVER-EXCEPTION-IDENTITY
7. RESTORE-WIRING
8. CHAINING-WIRING
9. PRODUCER-HOST-END-TO-END
10. ACTUAL-SOURCE-MUTANTS

## Not proved
- **Unobserved fault sites:** a fault in `CoveringRoleConnector(...)` construction, or anything else before `run_bounded_domain`, is not observed. The STOP then stays unchained.
- **Native details:** the real classes, frames and paths, and the 503/401/422/504 discrimination itself.
- **Thread hand-off:** under `anyio.to_thread` it's structural only.
- **Native host path:** not exercised.

## Limits (inherited launcher)
- **Timing:** 120 s, plus at most one 5 s kill/wait, plus two 5 s reader joins: 135 s nominal, with no separate outer timeout.
- **Capture:** 64 KiB per stream; 256 KiB for the result.
- **Success** requires exit 0, no output, clean EOF readers and the exact ordered 10-control inventory. The checker also enforces the nested inventory.
- **Exclusive evidence** goes under `packet/verify/`; a failure stops and preserves, with no retry.

## Future command
`Future-Command-HELD.ps1.txt` (admission `AAA6C386…`). The wrapper refuses while the flags are false.
