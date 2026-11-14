# Matt → Dex: T05 fake v2 preparation handback (Option A)

November 12, 2026, about 20:40 PT. This responds to `Matt-thePlan-Scheduler-T05-Fresh-Copy-Preparation-2026-11-12.md` (SHA256 `02E09945311E8728FE2B1A0282F8DC0FEBD2C7355779891FF2F689455DE4E9E9`). I worked solo; no subagents were used.

**Status: PREPARED_NOT_EXECUTED, frozen, no active writer.** Both admission `launch_authorized` flags are **false**, and native flags remain false. Nothing was imported, parsed, compiled, tested or invoked. **No PASS is claimed.**

## Authority checked
- **Approval:** `scheduler-native-provider-prep-scope-dex-review-v2/Trish-Preparation-Approval.json` = `5D1EA2F9…0CA4`. It's Trish's "Approve consolidated workspace preparation", for scope `389A00DD…7E2D`, with `fresh_copy_same_contract_corrections_authorized: true` and `execution_authorized: false`.
- **Scope file:** `Reconciled-Authoring-Scope-For-Approval.md` = `389A00DD…`, which lists role 14 (`verify/launch_check.py`) and routine same-contract fresh-copy corrections.

## Workspace
`C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-native-provider-t05-fake-v2`. It didn't exist beforehand.
- **Baseline** `scheduler-native-provider-t05-fake-v1`: 289/289 before copying (manifest `0B9D31C9…47DE`), and 289/289 again after. It is untouched.

## Exact delta (under `packet/`; `diff -rq` against v1 shows exactly 3 files)
1. **`verify/launch_check.py`:** `ABCFC1383F8A99100A2850834A5177CF698253469326B4C501160128D1CEDC64` → **`D22C37E36E5D333C087C8EE80B6936756C69F7D369369C66F8E0FFE6906EBD07`**.
   - Exact byte copy of `scheduler-native-provider-fake-v1/packet/verify/launch_check.py`; I re-hashed that source as `D22C37E3…` before copying.
   - **Fixes B2:** checker line 2552 now matches.
2. **`verify/OUTER-ADMISSION.json`:** `243D5B4B…EDAC` → **`F2841A1CFEB74A0BF81FAB4BCC38FAE17D51BFD31DF6FCF6A2DD31C2E3ABF26A`**.
   - `launch_authorized` true → false;
   - `launch_check_sha256` → `D22C37E3…`;
   - `t05_note` now says truthfully that this v2 prep admission is false, and any true value needs a separately reviewed staging copy (fixing the old N2 contradiction);
   - `note` refreshed.
3. **`verify/VERIFICATION-ADMISSION.json`:** `C79C26B0…21CE` → **`9048AD31BE3E0E5A80C9E7E41E16E6D8DEA6E7B25EDED2B3D746BCF280EAEB17`**.
   - `launch_authorized` true → false;
   - **added `"runtime_file_pin_count": 1` and `"runtime_files": [{absolute_path: …\Python311\python.exe, sha256: 5F7B89A6…52EC, note: interpreter executable only}]`**, which fixes B1. The key is `absolute_path`, matching wrapper lines 50–69 and checker lines 2493–2497 and 2538–2544;
   - direct `interpreter_path` and `interpreter_sha256` kept;
   - launcher pin → `D22C37E3…`; OUTER pin → `F2841A1C…`; note refreshed.

## Unchanged by design
- **checker `099BC9A4…825F`**, with all 17 top-level and 19 nested controls and their historical labels (for example `dex_launcher_receipt_candidate_sha256: D22C37E3…`, which is now accurate again);
- EXPECTED `080268BC…260A`;
- wrapper `9AE55D26…2653` and outer admission script `08975D02…6B49`;
- every subject, payload, fixture and API byte.

**Pins verified after the edits:** all 23 VERIFICATION packet pins match disk, and the three OUTER subject pins (launcher, checker, EXPECTED) match disk.

## Current versus historical documents
- **Current** (top level):
  - `T05-V2-PREP-README.md` `5FC64D2B…DD1E`;
  - `T05-V2-Freeze.json` `91C225C3…29E0`;
  - `Future-Command-HELD.ps1.txt` `0509AD9F…7D14`.
- **Historical** (byte-identical v1 records): `Launch-Decision.md`, `Reviewed-Command.ps1.txt` (points at the **v1** wrapper; do not use) and `Static-Staging-Receipt.json`. Under `packet/`: `TIP-FREEZE.json`, `HANDBACK.txt`, `ARTIFACT-HASHES.txt`, `Static-Preparation-Receipt.json`, both `Mutable-Role-Hashes.json`, `docs/Mutable-Roles.md` and `docs/Exact-Diffs-Summary.md`. All of these are labeled in the current README.
- **I checked that no executable reads any of those inherited documents** (grep across the checker, launcher, outer admission script, wrapper, operator and fixtures). The checker reads only `docs/Assembly-Selected-Source-Manifest.json`, which is unchanged.

## Manifest, command and chain
- **`Input-Manifest.sha256` = `103B35619A5A4B482DCCB7444D6DE95F1632D10BE176214CABCEC910237002A6`.** It has 289 entries relative to `packet/` (the same 289 paths as v1, now sorted by hash) and verifies 289/289. The top-level current documents are pinned in this handback's hash manifest.
- **Future command (HELD):**
  ```
  & 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-t05-fake-v2\packet\Invoke-Fake.ps1' -AdmissionSHA256 '9048AD31BE3E0E5A80C9E7E41E16E6D8DEA6E7B25EDED2B3D746BCF280EAEB17'
  ```
  The wrapper refuses while `launch_authorized` is false. A run needs your separately reviewed staging copy (flags flipped, so a new admission hash) plus Trish's one-shot approval, including authority to terminate the owned child.
- **Runtime pin:** 1 record, the interpreter only. Not a standard-library, DLL or environment lock.
- **Acyclic:** the wrapper takes the VERIFICATION hash; VERIFICATION pins 23 files plus 1 runtime file; OUTER pins the launcher, checker, EXPECTED and interpreter. Nothing pins back up the chain.

## Limits (unchanged, from the restored reviewed launcher)
- **Timing:** 120 s, plus 5 s for one kill/wait, plus two 5 s reader joins: **135 s nominal**. Startup, hashing, I/O and OS latency are excluded; no separate outer timeout.
- **Capture:** 64 KiB per stream and 256 KiB for the result.
- **Success** requires exit 0, no output, clean joined EOF readers and the exact ordered 17-control PASS inventory.
- **Exclusive evidence:** `packet/verify/FAKE-NATIVE-PROVIDER-RESULT.json` and `…-LAUNCH-RECEIPT.json`, both absent.
- **On failure:** stop and preserve; no retry or cleanup.

## Proof boundary
- **Static:** B1 and B2 resolved; all pins and manifests verify.
- **Not run:** this checker has never executed in the T05 lineage, so all 17 and 19 control behaviors are unproved. My earlier review didn't cover their behavioral content.
- Fake helper controls are not native TLS proof.
- T05 stays on the pre-diagnostic runner `9C0F8573…`, as noted before.

## Preservation (re-verified)
- T05 v1: 289/289
- reviewed fake-v1: 285/285 (from `packet/`), launcher source `D22C37E3…` intact
- my native launch prep: 269/269
- your native staging: 274/274 (not touched)

**No new concrete problems found.**

## Scope
- Reading, copying, the one exact launcher byte copy, JSON literal edits to the two admissions (with the Edit tool), hashing, and manifest and document authoring.
- No imports, parsing, compilation, tests, helper or wrapper invocation, refusal probes, sockets, PKI, Docker, database, installation, cleanup or execution.
- No existing packet modified.

JSON validity of the two admissions was checked by eye only. The edits were value swaps plus one inserted key block with matching commas.

Signed: Matt
