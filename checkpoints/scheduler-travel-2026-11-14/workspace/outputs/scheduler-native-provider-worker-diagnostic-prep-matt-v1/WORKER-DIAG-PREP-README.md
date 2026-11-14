# Worker-exception observer diagnostic: CURRENT preparation README

Matt, November 12, 2026.
- **Assignment:** `Matt-thePlan-Scheduler-Worker-Diagnostic-Preparation-2026-11-12.md` (`F6F15372…27FD`).
- **Authority:** Trish's approved envelope `389A00DD…7E2D`: a same-contract fresh-successor role-4 correction after a failed-run diagnosis.
- **Disclosure:** within the already-approved diagnostic contract: classes plus manifest-owned paths and lines, at most 3 exceptions and 8 frames, 4096 bytes. This is reconciled in the assignment.

**Status: PREPARED_NOT_EXECUTED, frozen, no active writer.** The host `launch_ready`, `candidate_launch_ready_staged` and runner-config `launch_ready` are all false. No EXECUTE acknowledgement exists. The endpoint is unbound.

## Current versus historical
- **Current:** this README, `Worker-Diag-Prep-Freeze.json` and `Future-Native-Command-HELD.ps1.txt`.
- **Historical (copied, not current authority):** `Dex-Staging-Receipt.json`, `Path-Agreement-Review.json`, `Review-and-Commands.md` and `Reviewed-Native-Command.ps1.txt` (the **executed** dex-v1 command; do not use).
  - In the nested packet: `LAUNCH-PACKET-README.md`, `Launch-Packet-Freeze.json`, `Future-Native-Command-HELD.ps1.txt`, `SUCCESSOR-README.md`, `TIP-FREEZE.json`, `Launch-Decision.md`, `Static-Staging-Receipt.json` and `Reviewed-Command.ps1.txt`.
- **`Source-Input-Manifest-dex-v1.sha256`:** the copy-source manifest (`1C85559E…851A`, 274 entries), kept as lineage.

## Lineage
- Only the 274 manifest-listed inputs were copied from the executed `scheduler-native-provider-diagnostic-launch-dex-v1`, verified 274/274 before and after. No dynamic evidence, public CAs or keys.
- The nested packet name is kept, so the unchanged operator's sibling evidence label resolves to `…\scheduler-native-provider-worker-diagnostic-prep-matt-v1\scheduler-native-provider-diagnostic-launch-v1.evidence`, which is **absent**.

## The single executable change: role 4 `payload/fixture/np_runner_entry.py`
`40A1BA8E…F73F` → **`341074AEF88A9E438C0F488E6231572103E694FB5EB81D6F3AC6BD30517CD645`**. The change is **purely additive (+41 lines, 0 removed)**, and `stop_payload` is byte-identical.
1. **New helper** `_install_worker_exception_observer(captured)`:
   - swaps the module global `app.services.covering_http_dispatch.run_bounded_domain` (the one `_worker` looks up) for a delegate that calls the original with identical arguments and returns its identical result;
   - on `BaseException`, it retains **at most one** object (the first) and uses a **bare `raise`**;
   - it never formats or serializes the exception;
   - it returns a `restore()` that puts back the exact original.
2. **In `_run_np_v_ms_nonexpired`:**
   - two new locals (`worker_exceptions`, `restore_worker_observer`);
   - the install is the first statement inside the POST `try`;
   - the restore runs first and **unconditionally** in that `finally`, before any assertion.
3. **The non-200 branch** raises the **same** `SuiteStop(f"covering-refresh status:…")`, chained `from` the captured worker exception when one exists. Otherwise it's the original unchained raise. Framework-stop handling, exit codes and every other assertion are unchanged.

**Expected envelope on a non-200** (by the unchanged producer and host validator): `SuiteStop` → the worker exception (for example `CoveringRootOutcomeUnknown`, `ApiError` or `CoveringDeadlineExceeded`) → the original fault via the suppressed `__context__`. Each has up to 8 newest manifest-owned frames, including `api/app/**`, within the existing 3/8/128/4096 limits and fallback. **No status, message, body or locals.**

## Data changes
- **`payload/runner-config.json`** (`E132A138` → `9411AC38…E929`): `launch_ready` false; the batch is still `["NP-V-MS-NONEXPIRED"]` and `expected_unknown_cases` is `[]`.
- **`payload/SHA256SUMS.txt`:** 257 pins with 2 re-pinned; aggregate `3B25ABB6` → **`250CFD3C39944C2A238371B957267719900B861368CF8C3118DCB274052D2A70`**.
- **`host/launch-config.json`** → **`EBE26FB5…FBE1C`**: `launch_ready` and `candidate_launch_ready_staged` false; paths moved to the new parent; `manifest_sha256` `250CFD3C…`; candidate note. The batch is unchanged.
- **`host/docker-ops-config.json`** → **`CB2F70F5…DFDF7`**: only the 7 path values moved to the new parent.
- **Immutable:** the operator `5A8A04B6…`, Docker helper `7F7EA820…`, supervisor, peer, PKI, all 234 API files and every other fixture executable.

## Static path agreement
All 9 absolute config paths are under the new nested root or its sibling `.evidence`. The operator label resolves to that sibling. The held command omits `-ReceiptPath`. The success path is still 22 source-derived Docker calls against a cap of 32 (Dex's derivation; the case and Docker operations are unchanged).

## Proof boundary
Authored and statically reviewed only; nothing executed. The companion focused fake packet is `outputs/scheduler-native-worker-diagnostic-fake-prep-matt-v1`. Native behavior, including whether a worker exception is actually captured, is unproved until an authorized run.
