# Native NP-T04-BODY-STALL preparation v1 (HELD)

Matt, November 13, 2026. This is for Dex `Matt-thePlan-Scheduler-T04-Body-Stall-Preparation-2026-11-13.md` (`F465A4E25C77BB4D0C9256E56A48F9AA1FDBB7185D9C8FA8A2282B4D2DBEF196`), under Trish-approved design/preparation decision `4F2F3B3F7BC5C274445865BB1B3B5B87C359A436BEC70F1F1406BC6A9C38804B` (`call_b68dab97…`) and lane `389A00DD…7E2D`.

**Status:** PREPARED_NOT_EXECUTED.
- Nothing was imported, parsed, compiled, tested or run.
- No Docker, PKI, socket or DB work.
- **Current documents:** this README, `T04-Body-Stall-Prep-Freeze.json` and `T04-Body-Stall-Native-Command-HELD.ps1.txt`. Every other copied document, command and `Source-*.sha256` is history.
- **Source preserved:** `scheduler-native-provider-ms-refresh-retire-prep-matt-v1`, parent `F682D755…` (301), verified before copying. Lineage: `Source-MS-Refresh-Retire-Prep-Input-Manifest.sha256`.

## Changed roles
- **Role 7, peer** (`np_provider_peer.py`):
  - the scripted header/body stall now runs through `_hold_stall`. It returns cleanly with `stall_exit_reason="retired"` only when the owner's stop event ends the stall strictly before the peer deadline. Deadline expiry still raises the unchanged `PeerLifecycleError` (reason `"deadline"`);
  - `execute_script` records `peer_started_at` / `peer_deadline_at`;
  - `sanitized_state` exports the five finite fields.
  - Nothing else changes.
- **Role 8, transcript** (`np_provider_transcript.py`):
  - `ms_graph_calendar_view_body_stall_script` declares an exact path and query, a 200 response with a `PLACEHOLDER` Content-Length (12 for the `{"value":[]}` template) and a `stall_body` close;
  - `ms_body_stall_connection_inventory` is exactly 3 connections: the two NONEXPIRED identity scripts plus the stall.
- **Role 4, runner** (`np_runner_entry.py`): additive only.
  - **`_run_np_t04_body_stall`** and its constants;
  - **`_t04_body_stall_exact_query`:** the fixture derivation, cross-checked against the production `microsoft_calendar_view_list_params`, using the same `urlencode(..., doseq=True)` as `CoveringHTTP`;
  - **`_install_t04_parent_and_target_observers`:** same-return/same-exception and restorable;
  - **failure-column read** and the **finite timing predicate**;
  - **case-specific `T04_BODY_STALL_PEER_SECONDS = 240`**, checked equal to runner-config `t04_body_stall_peer_seconds`;
  - **registration:** `IMPLEMENTED_CASE_IDS` and the mapper.
  - Every existing body is byte-identical and keeps `PEER_SECONDS_DEFAULT = 120`.
- **Role 5, suite** (`np_suite.py`): the `CASE_IMPLEMENTATION_NOTES` entry only. The registry is unchanged.
- **Data:**
  - runner-config: case `NP-T04-BODY-STALL` and `t04_body_stall_peer_seconds` 240;
  - launch-config: batch `np-v-t04-body-stall-single-case`, case, the same key, payload pin, 2 own-root paths, and a candidate note truthful "as authored";
  - docker-ops: 7-path root rename only.
- **Unchanged:** all 234 API files, routes, seeds, PKI scripts, receipts sanitizer, host validator, operator, integrated runner and `docker_transport.py`.

## Gates and paths
- **Gates:** host `launch_ready` false, candidate staging false, runner `launch_ready` false, human authority false.
- **Evidence:** `<root>\scheduler-native-provider-diagnostic-launch-v1.evidence` is absent. The default receipt applies (no `-ReceiptPath`), and the public CA is bound read-only at `/public-ca`.
- **No native run is authorized,** including the 240 s case peer life.
