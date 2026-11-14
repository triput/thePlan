# NP-V-MS-REFRESH preparation: CURRENT README

Matt, November 12, 2026.
- **Assignment:** `Matt-thePlan-Scheduler-MS-Refresh-Preparation-2026-11-12.md` (`F462C385…0009`).
- **Scope:** `Reconciled-Preparation-Scope.md` (`EAAFA222…488A`), under Trish's approved envelope `389A00DD…7E2D` (approval `5D1EA2F9…0CA4`).

**Status: PREPARED_NOT_EXECUTED, frozen, no active writer.** Host `launch_ready` and `candidate_launch_ready_staged` are false, and runner-config `launch_ready` is false. No EXECUTE acknowledgement exists. The endpoint is unbound. **No native REFRESH launch can happen before the shared-harness diagnostic native outcome is reconciled, and then only with a separate exact approval.**

## Current versus historical
- **Current:** this README, `MS-REFRESH-Prep-Freeze.json` and `Future-Native-Command-HELD.ps1.txt`.
- **Historical (byte-identical copies from the Dex diagnostic staging, not current authority):** `Dex-Staging-Receipt.json`, `Path-Agreement-Review.json`, `Review-and-Commands.md` and `Reviewed-Native-Command.ps1.txt` (it names the **dex-v1 staging** operator; do not use).
  - In the nested packet: `LAUNCH-PACKET-README.md`, `Launch-Packet-Freeze.json`, `Future-Native-Command-HELD.ps1.txt`, `SUCCESSOR-README.md`, `TIP-FREEZE.json`, `Launch-Decision.md`, `Static-Staging-Receipt.json` and `Reviewed-Command.ps1.txt`.
- **`Source-Input-Manifest-dex-v1.sha256`:** the copy-source manifest (`1C85559E…851A`, 274 entries), kept as lineage.

## Lineage
- Copied **only** the 274 manifest-listed files from `outputs/scheduler-native-provider-diagnostic-launch-dex-v1`. All 274 verified before copying and again after; there's no dynamic evidence and no private keys.
- The nested packet keeps the name `scheduler-native-provider-diagnostic-launch-v1`, so the immutable operator's fixed sibling evidence label resolves uniquely to `outputs\scheduler-ms-refresh-prep-matt-v1\scheduler-native-provider-diagnostic-launch-v1.evidence`, which is absent.

## Mutable fixture roles changed (all in `payload/fixture/`)
| Role | File | Before → after | Delta |
| --- | --- | --- | --- |
| 4 | `np_runner_entry.py` | `40A1BA8E` → `CC4D49E7` | **Added:** `_ms_refresh_provider_routes`, `_require_production_ms_token_path`, `_actual_token_terminals` and `_run_np_v_ms_refresh`, plus a REFRESH mapper branch and REFRESH in `IMPLEMENTED_CASE_IDS`. **Only one existing line changed** (the implemented set). NONEXPIRED, `_ms_provider_routes` and `stop_payload` are byte-identical. |
| 5 | `np_suite.py` | `AEC59FCD` → `46C9443D` | Added a `CASE_IMPLEMENTATION_NOTES["NP-V-MS-REFRESH"]` entry; all 76 IDs and `NATIVE_CASES` unchanged. |
| 6 | `np_receipts.py` | `69F59AF1` → `7F27A3C2` | Narrow allowlist adding two keys: `token_commit` and `token_terminal_sequence`. |
| 8 | `np_provider_transcript.py` | `CFAB2D06` → `0AA3BC09` | `ms_token_endpoint_path` and `MS_TOKEN_ENDPOINT_PATH` derived once from `FIXTURE_MS_TENANT` (= `/common/oauth2/v2.0/token`). The `MS-TOKEN-SUCCESS` path uses it, and its body holds the declared synthetic refreshed and rotated values. Added `ms_refresh_connection_inventory` (exactly 5). The NONEXPIRED and invalid-grant scripts are unchanged (the invalid-grant path fix is deferred, per Q3). |
| 10 | `np_auth_seed.py` | `66FEEA81` → `2ADFA3AD` | Added the declared synthetic seed, refreshed and rotated labels, and the read-only `measure_account_credential_state`: decrypt in-fixture, semantic match booleans, expiry instant, short ciphertext hashes. The seed function is byte-identical. |

## Data changes
- **`payload/runner-config.json`** (`E132A138` → `108D8D1E`): `launch_ready` false; `case_ids` `["NP-V-MS-REFRESH"]`; `expected_unknown_cases` `[]`; `first_vertical_case_ids` kept as NONEXPIRED; added `refresh_increment_batch_case_ids` and `implemented_case_ids`.
- **`payload/SHA256SUMS.txt`:** 257 pins with 6 re-pinned; aggregate `3B25ABB6` → **`BD48E400924E8D6DD17597F7845E20FC01F1889AFEEAD743880CB3BF2623472D`**.
- **`host/launch-config.json`** → **`6558688B…FCC4`**:
  - `launch_ready` and `candidate_launch_ready_staged` false;
  - `batch_id` `np-v-ms-refresh-single-case`; `case_ids` REFRESH; `implemented_case_ids` both;
  - `manifest_sha256` `BD48E400…`; paths moved to the new parent;
  - candidate and refresh notes updated.
  - `static_success_docker_command_count` (22) is carried from the host Docker operation sequence, which is case-independent. **It was not re-derived in this preparation.**
- **`host/docker-ops-config.json`** → **`8AAF7795…0D34`**: only its 7 path values moved to the new parent.
- **Immutable:** the operator `Invoke-Native-Provider.ps1` `5A8A04B6…`, `docker_transport.py` `7F7EA820…`, the peer, route and PKI files, and all 234 API files.

## Static path agreement (review only)
All 9 absolute config paths resolve under `…\scheduler-ms-refresh-prep-matt-v1\scheduler-native-provider-diagnostic-launch-v1[\…]`, or to its sibling `.evidence` (public-CA directory, CA bind, receipt directory). The operator's evidence label resolves to the same sibling root, and the future command omits `-ReceiptPath`.

## Evidence design implemented (static source; not run)
- The production token URL is cross-checked at runtime against the pinned `_token_url(_normalize_tenant(...))` before any request.
- **Before:** expiry at or before the plan time, and seed values present.
- **After:** fresh session reads; refreshed access and rotated refresh are plaintext-equal; seed values gone; expiry later than the final check plus 30 s. **Ciphertext hashes are recorded but never the pass basis.**
- Public `overall_outcome == "success"`; two `results[]` rows with `phase=import` and `status=ok` for the requested IDs; coverage, readiness and revision checks; `assessment_error is None`; alias rewrite.
- Native TOKEN terminals, observer marker filtered: exactly `[COMMIT_ACKNOWLEDGED (commit), ROLLBACK_ACKNOWLEDGED (no commit)]`.
- Requests: OAuth count 1; client order `[POST oauth, GET identity, GET identity, GET event, GET event]`; peer served equals admitted equals 5, with the first exchange `POST /common/oauth2/v2.0/token`.
- The same budget-identity proof as NONEXPIRED, default JoinedTLS, real monotonic clocks, one bounded retirement, no injection, freezing or retry.

## Runtime assumptions (validated only by an authorized native run)
- One synthetic peer serves both vendor hostnames.
- The second target's TOKEN re-read rolls back with no request.
- The production response, terminals and persistence behave as statically traced.
- The shared harness itself has no native PASS yet.
