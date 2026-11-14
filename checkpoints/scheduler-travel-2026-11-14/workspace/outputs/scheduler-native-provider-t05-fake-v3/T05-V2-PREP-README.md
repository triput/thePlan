# T05 fake v2: CURRENT preparation README

Matt, November 12, 2026. Assignment `Matt-thePlan-Scheduler-T05-Fresh-Copy-Preparation-2026-11-12.md` (`02E09945…E9E9`). It runs under Trish's approved consolidated scope `389A00DD…7E2D` (approval `5D1EA2F9…0CA4`: role 14 `verify/launch_check.py`, plus routine same-contract fresh-copy corrections).

**Status: PREPARED_NOT_EXECUTED, frozen, no active writer.** Both admission `launch_authorized` flags are **false**, and native flags remain false. Nothing was imported, parsed, compiled, tested or invoked. **No PASS is claimed.**

## Current versus historical
- **Current:** this README, `T05-V2-Freeze.json` and `Future-Command-HELD.ps1.txt` (admission `9048AD31…EB17`).
- **Historical (byte-identical v1 records, not current authority):** `Launch-Decision.md`, `Reviewed-Command.ps1.txt`, `Static-Staging-Receipt.json`, and under `packet/`: `TIP-FREEZE.json`, `HANDBACK.txt`, `ARTIFACT-HASHES.txt`, `Static-Preparation-Receipt.json`, `Mutable-Role-Hashes.json`, `docs/Mutable-Role-Hashes.json`, `docs/Mutable-Roles.md` and `docs/Exact-Diffs-Summary.md`.
  - These carry the v1 launcher `ABCFC138…`, the v1 OUTER `243D5B4B…` or the v1 admission `C79C26B0…`.
  - `Reviewed-Command.ps1.txt` points at the **v1** wrapper and must not be used.
  - No executable reads any of these files. The checker reads only `docs/Assembly-Selected-Source-Manifest.json`, which is unchanged.

## Exact delta from v1 (`scheduler-native-provider-t05-fake-v1`, 289/289 verified before copying, manifest `0B9D31C9…47DE`)
Under `packet/`, exactly three files differ:
1. **`verify/launch_check.py`:** `ABCFC138…DC64` → **`D22C37E36E5D333C087C8EE80B6936756C69F7D369369C66F8E0FFE6906EBD07`**. It's an exact byte copy of `scheduler-native-provider-fake-v1/packet/verify/launch_check.py` (source re-hashed before copying). v1 differed only in the opening docstring. This fixes **B2**: the checker's line 2552 pin now matches.
2. **`verify/OUTER-ADMISSION.json`:** `launch_authorized` true → **false**; `launch_check_sha256` → `D22C37E3…`; `t05_note` made truthful; `note` refreshed. New hash `F2841A1CFEB74A0BF81FAB4BCC38FAE17D51BFD31DF6FCF6A2DD31C2E3ABF26A`.
3. **`verify/VERIFICATION-ADMISSION.json`:**
   - `launch_authorized` true → **false**;
   - **added `runtime_file_pin_count: 1` and `runtime_files`**, a single record: `absolute_path` = the existing `interpreter_path`, `sha256` `5F7B89A6…52EC`, interpreter executable only. This fixes **B1**;
   - the launcher pin → `D22C37E3…`; the OUTER pin → `F2841A1C…`; `note` refreshed;
   - the direct `interpreter_path` and `interpreter_sha256` fields are kept.
   - New hash `9048AD31BE3E0E5A80C9E7E41E16E6D8DEA6E7B25EDED2B3D746BCF280EAEB17`.

**Unchanged:**
- checker `099BC9A4…825F`, with all 17 top-level and 19 nested controls and their historical labels;
- `EXPECTED-FAKE-STRUCTURAL.json` `080268BC…260A`;
- wrapper `9AE55D26…2653` and outer admission script `08975D02…6B49`;
- all subjects, payload, fixtures and API files; 23 packet pins (all re-verified against disk).

## Chain (acyclic)
- The wrapper takes the VERIFICATION hash as an argument.
- VERIFICATION pins 23 packet files, including OUTER (`F2841A1C…`), plus 1 runtime file (the interpreter).
- OUTER pins the launcher, checker, EXPECTED and interpreter.
- Nothing pins back up the chain.
- `Input-Manifest.sha256` covers the 289 files under `packet/`, with paths relative to `packet/`. These top-level current documents are pinned by the handback's hash manifest.

## Limits (unchanged, inherited from the reviewed launcher)
- **Timing:** checker budget 120 s, plus at most one 5 s kill/wait, plus two 5 s reader joins: **135 s nominal**. Startup, hashing, I/O and OS latency are excluded; there is no separate outer timeout.
- **Capture:** 64 KiB per stream and 256 KiB for the result.
- **Success** requires exit 0, no output, clean joined EOF readers and the exact ordered 17-control PASS inventory.
- **Exclusive evidence:** `packet/verify/FAKE-NATIVE-PROVIDER-RESULT.json` and `…-LAUNCH-RECEIPT.json`, both absent now.
- **On failure:** stop and preserve; no retry or cleanup.

## Proof boundary
- **Static:** B1 and B2 are resolved in the admission data and the launcher pin, and the pins verify.
- **Not run, so behavior is unproved:** the 17 and 19 controls. The checker has never executed in this packet lineage.
- Fake helper controls are not native TLS proof.
- T05 remains on the pre-diagnostic runner pin `9C0F8573…`.
