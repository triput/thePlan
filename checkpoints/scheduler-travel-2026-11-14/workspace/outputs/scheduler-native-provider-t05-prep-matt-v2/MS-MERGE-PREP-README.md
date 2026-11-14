# MS-refresh merge preparation: NP-V-MS-NONEXPIRED batch (CURRENT README)

Matt, November 13, 2026. This is for assignment `Matt-thePlan-Scheduler-MS-Refresh-Merge-Preparation-2026-11-13.md` (`5A9CF9F6…3D69`), under lane `389A00DD…7E2D`.

**Status: PREPARED_NOT_EXECUTED, frozen, no active writer.** The host `launch_ready`, `candidate_launch_ready_staged` and runner-config `launch_ready` are all false. No EXECUTE acknowledgement exists. The endpoint is unbound.

## Current versus historical
- **Current:** this README, `MS-Merge-Prep-Freeze.json` and `MS-Merge-Native-Command-HELD.ps1.txt`.
- **Historical:** every other top-level document or command was copied with the inputs (peer-close, worker-diag and dex-v1 lineage).
- **Lineage manifest:** `Source-Peer-Close-Prep-Input-Manifest.sha256` (`4F77BDEF…6E0C`, 282 entries).

## One of two separately selectable batches
- This root is the **NP-V-MS-NONEXPIRED** batch. Its sibling root, `scheduler-native-provider-ms-merge-{nonexpired,refresh}-prep-matt-v1`, holds the other batch.
- **Same bytes:** both roots carry byte-identical fixture and API bytes.
- **What differs:** `payload/runner-config.json` (here 9411AC38 (peer-close prep runner-config, unchanged)), the dependent payload manifest row, and the host configs (batch id, case list, paths).
- **Separate evidence:** each root has its own operator sibling evidence root; there's no automatic sequencing, and no case is expected to end UNKNOWN.

## Merged fixture set (identical in both batches)
- **Common base:** dex-v1 `1C85559E` (runner `40A1BA8E`).
- **Role 4 `np_runner_entry.py`** = **`F7CFD3E6BA0107B3482766C3A8FA505C5BADD287DF843FACAEA2E79CFFE5385C`**:
  - the worker-observer diff `2023F97B` (base → `341074AE`, 5 hunks) plus the MS-refresh diff `A805B9B0` (base → `CC4D49E7`, 3 hunks);
  - the hunks don't overlap;
  - applying them in both orders with fuzz 0 gives identical bytes.
- **Roles 5, 6, 8, 10** come from the MS-refresh prep, changed only on that side:
  - `np_suite.py` `46C9443D`;
  - `np_receipts.py` `7F27A3C2`;
  - `np_provider_transcript.py` `0AA3BC09`;
  - `np_auth_seed.py` `2ADFA3AD`.
- **Role 7 `np_provider_peer.py`** = **`17EA148E`**, the peer-close correction (changed only on that side). The old peer bug isn't reintroduced.
- **Unchanged:** the operator `5A8A04B6`, supervisor `A1ADA231`, Docker helper `7F7EA820` and all 234 API files. They're identical on all three lineages.
- **Observer scope:** the worker observer covers the NONEXPIRED POST only. The REFRESH case body is byte-identical to the reviewed MS-refresh prep and isn't observed; I didn't extend it.

## Proof boundary
Authored and statically reviewed only. The companion fake is `outputs/scheduler-ms-merge-fake-prep-matt-v1`. Nothing native has run, and the first vertical has not passed.
