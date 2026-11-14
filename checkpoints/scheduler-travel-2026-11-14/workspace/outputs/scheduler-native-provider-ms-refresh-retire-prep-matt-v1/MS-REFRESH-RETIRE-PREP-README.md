# Native MS-REFRESH retirement-barrier preparation v1 (HELD)

Matt, November 13, 2026. This is for Dex `Matt-thePlan-Scheduler-MS-Refresh-Retirement-Preparation-2026-11-13.md` (`6ED9B65F34F5138A69AD64ADEE2832696EFC39A9297DCF181F936665442C9350`), under lane `389A00DD…7E2D`.

**Status:** PREPARED_NOT_EXECUTED.
- **Current documents in this root:** this README, `MS-Refresh-Retire-Prep-Freeze.json` and `MS-Refresh-Retire-Native-Command-HELD.ps1.txt`.
- **Copied documents are history only, not current invocation authority.** That covers every other README, freeze, review, receipt, `*Command*.ps1.txt` and `Source-*.sha256` copied from the source.
- **Source preserved:** `scheduler-native-provider-ms-invalid-prep-matt-v2`, parent `6144365E…` (297), runner `4CBF198E…`. It was verified 297/297 before copying, and its lineage is `Source-MS-Invalid-Prep-V2-Input-Manifest.sha256`.

## Change (role 4 only)
In `_run_np_v_ms_refresh`:
- the pre-join `peer_state = peer.sanitized_state()` is replaced **in place** by:
  - `retirement_attempted = True`;
  - `retirement, peer_state = _retire_selected_peer_then_observe(peer, join_seconds=5.0)`;
  - `retirement_done = True`.
  
  This puts it before the existing exchange and inventory assertions.
- The later direct retirement block is removed: the attempt mark, `retire_owned`, the done flag and the joined check.

**What stays the same:**
- The helper is byte-identical. It requires `joined is True` and `worker_error_kind is None`.
- The `finally` guard is unchanged, so once the helper has been marked as attempted, a raise never causes a second attempt.
- Every other assertion, handler, the cleanup precedence and the remaining unjoined-thread check are unchanged.

## Data
- **runner-config:** `case_ids` is `NP-V-MS-INVALID` → `NP-V-MS-REFRESH`. No expected UNKNOWN; gates false.
- **launch-config:**
  - `batch_id` is `np-v-ms-refresh-single-case` and the case list is the same;
  - the payload pin is updated and own-root paths are used;
  - the candidate note is truthful about its gates "as authored", and any later staging that flips a gate must restate it;
  - the r1 note is marked historical.
- **docker-ops:** root rename only (7 paths). Its machine flags are data only.
- **Evidence:** `<root>\scheduler-native-provider-diagnostic-launch-v1.evidence` is absent. The default receipt is `native-provider-host-receipt.jsonl`, and there is no `-ReceiptPath`. The CA goes to `<evidence>\public-ca`, bound read-only at `/public-ca`.

## Not done
- No execution, import, parsing, compilation or test.
- No Docker, PKI, database or provider operation; no installation or activation.
- Endpoint unbound; all holds stay.
- No native refresh or T06 closure is claimed.
