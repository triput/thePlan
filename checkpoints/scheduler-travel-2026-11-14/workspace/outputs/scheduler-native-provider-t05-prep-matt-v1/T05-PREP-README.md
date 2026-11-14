# Native T05 preparation: NP-T05-ORDERLY-CLOSE and NP-T05-ABRUPT-TRUNCATION (CURRENT README)

Matt, November 13, 2026. This is for assignment `Matt-thePlan-Scheduler-Native-T05-Preparation-2026-11-13.md` (`62E314AB…3B84`), under lane `389A00DD…7E2D`. Design input: `Next-Native-T05-Design-Notes-2026-11-13.md` (`9879751E…7C5B`).

**Status: PREPARED_NOT_EXECUTED, frozen, no active writer.** The host `launch_ready`, `candidate_launch_ready_staged` and runner-config `launch_ready` are all false. No EXECUTE acknowledgement exists. The endpoint is unbound.

## Current versus historical
- **Current:** this README, `T05-Prep-Freeze.json` and `T05-Native-Command-HELD.ps1.txt`.
- **Historical:** every other top-level document or command was copied with the inputs.
- **Lineage manifest:** `Source-MS-Merge-Nonexpired-Input-Manifest.sha256` (`22AE4F82…CDC7`, 286 entries; verified 286/286 before and after the copy).

## Batch
`case_ids` = `["NP-T05-ORDERLY-CLOSE", "NP-T05-ABRUPT-TRUNCATION"]`, with `expected_unknown_cases` `[]` and batch id `np-t05-orderly-and-abrupt`.
- **Separate roots:** NONEXPIRED and REFRESH stay in their frozen MS-merge roots.
- **No sequencing:** there's no automatic sequencing between batches and no retry.
- **Holds:** the other 25 native and 4 CF bodies remain HOLD, and all 76 planning IDs are retained.

## Changed roles (all others byte-identical to the frozen MS-merge NONEXPIRED root)
| role | file | before | after |
|---|---|---|---|
| 4 | `np_runner_entry.py` | `F7CFD3E6` | `E75F7C2426662A1AE68DF7D31998197916960E757998D21184FF388D2EAA4827` |
| 5 | `np_suite.py` | `46C9443D` | `E5C63D9CE7AA3E66784216B0E88D14434F7016E67E6D22931C58504D87209189` |
| 7 | `np_provider_peer.py` | `17EA148E` | `BFB271D770D08BC161E9613564ECA799B7E28884D8211E10228F5973A4A271BF` |
| 8 | `np_provider_transcript.py` | `0AA3BC09` | `46455CD603355E30819FBF944ADAC141DDE04D78E28C4F25783681A67A0212D8` |
| data | `runner-config.json` | `9411AC38` | `96782CB425239BC6F121949DABE16B4B53528E249BE625DD25A9811DA7D07E71` (only `case_ids`) |

**Unchanged:**
- the operator `5A8A04B6`, supervisor `A1ADA231`, Docker helper `7F7EA820`, integrated runner, bootstrap and DB helpers;
- all 234 API files;
- roles 6 and 10;
- the observer, refresh, stop producer and every existing assertion.

## What changed
- **Peer `_http_response_bytes`:** explicit framing selection, inserted at the top (+19/−0). The historical `auto` lines are untouched, so default wire bytes are identical.
  - `close_delimited` sends neither Content-Length nor Transfer-Encoding; the body ends at the orderly close.
  - These are refused before any send (the serializer runs before `_send_all` in the unchanged `_send_response`): an unknown mode, any Transfer-Encoding header, and Content-Length together with `close_delimited`.
  - Chunk framing isn't implemented; it stays an explicit open requirement.
- **Transcript:** `ExchangeStep` gains `framing: ResponseFraming = "auto"`. The `T05-ORDERLY-CLOSE-DELIMITED-COMPLETE` script now really is close-delimited; previously it declared `Content-Length: 2`.
- **Runner:**
  - `_t05_observe` builds one exchange through the production contract `CoveringRequestBudget` → `ProviderCounter(approved_provider_limits(), budget.work_remaining)` → `CoveringHTTP(counter, routes)` with the **default JoinedTLS** (asserted), on Google event routes with numeric loopback :443 and verify-full.
  - The framing is validated before the peer starts.
  - The peer is retired and joined before any classification. An unjoined peer, worker error, inventory or wire-length mismatch is a STOP.
  - `_t05_classify_client_outcome` is finite and fails closed:
    - complete close-delimited: exactly 200, exact body, no CL/TE → `ACCEPTED_AFTER_ORDERLY_CLOSE_NOTIFY`;
    - short Content-Length valid-JSON prefix: exactly `http.client.IncompleteRead` → `REFUSED_AFTER_ORDERLY_CLOSE_NOTIFY`;
    - abrupt: exactly `ssl.SSLEOFError` or `builtins.ConnectionResetError` → `OBSERVED`;
    - **anything else is a STOP.**
  - Two bodies, the mapper branches and `IMPLEMENTED_CASE_IDS`.
- **Suite:** implementation notes only. The 31 declarations and their oracles are unchanged.

## Report and diagnostic compatibility
- **Receipts:** the existing `case_result_receipt` with `observations`, plus `measured` holding only class names, booleans, status and script ids, and the sanitized peer inventory and retirement.
- **Never stored:** bodies, header values, credentials, keys or messages.
- **STOP:** the existing class/location-only producer.
- No schema is widened.

## Proof boundary
Authored and statically reviewed only. The companion fake is `outputs/scheduler-native-t05-fake-prep-matt-v1`. Nothing native has run.
