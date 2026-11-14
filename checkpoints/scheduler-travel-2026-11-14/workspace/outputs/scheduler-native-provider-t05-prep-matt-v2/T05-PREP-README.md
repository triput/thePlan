# Native T05 preparation v2: NP-T05-ORDERLY-CLOSE and NP-T05-ABRUPT-TRUNCATION (CURRENT README)

Matt, November 13, 2026. This is for assignment `Matt-thePlan-Scheduler-Native-T05-Preparation-2026-11-13.md` (`62E314AB…3B84`), under lane `389A00DD…7E2D`. Design input: `Next-Native-T05-Design-Notes-2026-11-13.md` (`9879751E…7C5B`).

**Status: PREPARED_NOT_EXECUTED, frozen, no active writer.** The host `launch_ready`, `candidate_launch_ready_staged` and runner-config `launch_ready` are all false. No EXECUTE acknowledgement exists. The endpoint is unbound.

## Current versus historical
- **Current:** this README, `T05-Prep-Freeze.json` and `T05-Native-Command-HELD.ps1.txt`.
- **Historical:** every other top-level document or command was copied with the inputs.
- **Lineage manifest:** `Source-T05-Prep-V1-Input-Manifest.sha256` (`704A16D1…39B0`, 290 entries, the v1 root; verified 290/290) and the copied `Source-MS-Merge-Nonexpired-Input-Manifest.sha256` (`22AE4F82…CDC7`).

## Batch
`case_ids` = `["NP-T05-ORDERLY-CLOSE", "NP-T05-ABRUPT-TRUNCATION"]`, with `expected_unknown_cases` `[]` and batch id `np-t05-orderly-and-abrupt`.
- **Separate roots:** NONEXPIRED and REFRESH stay in their frozen MS-merge roots.
- **No sequencing:** there's no automatic sequencing between batches and no retry.
- **Holds:** the other 25 native and 4 CF bodies remain HOLD, and all 76 planning IDs are retained.

## Changed roles (all others byte-identical to the frozen MS-merge NONEXPIRED root)
| role | file | before | after |
|---|---|---|---|
| 4 | `np_runner_entry.py` | `F7CFD3E6` | `EB76303F175E1CDCFA859069CAB9DA3FA2BA245C1275AD2CE72157701B0C100B` |
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
Authored and statically reviewed only. The companion fake is `outputs/scheduler-native-t05-fake-prep-matt-v2`. Nothing native has run.

## v2 correction (Dex P1, `F56020E8…5CE0A`)
- **The problem:** v1 judged close-delimited framing from `response.headers` on the `httpx.Response` that `CoveringHTTP` returns. Production rebuilds that object (`httpx.Response(status, content=bytes(body), headers=dict(response.getheaders()), …)`), and httpx 0.28.1 fills in Content-Length for non-empty byte content. So a correct close-delimited `{}` could carry a rebuilt `Content-Length: 2`, and v1 would falsely refuse it.
- **The fix:** v2 adds the pure `_t05_response_outcome(status, content, expected_body, scripted_wire)`.
  - The client side contributes only its status and exact body.
  - CL/TE absence is judged on the **exact scripted wire**, as `scripted_wire_framing_headers_absent`. The peer's sent byte count is still separately required to equal that wire's length.
  - `_t05_observe` never reads `response.headers`.
- **Measured fields renamed:** `scripted_wire_framing_headers_absent` and `peer_side_wire_bytes_sent_exact`. The latter is a peer-side stimulus fact only, not how far the client got into the headers or body.
- **Nothing else changed:** only role 4 changed relative to v1 (runner `E75F7C24` → `EB76303F`). The peer, transcript, suite, runner-config, application and helpers are byte-identical to v1.
