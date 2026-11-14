# Captured native source boundaries — offline follow-through

Dex, November 11, 2026. Read-only inspection of the exact three raw files collected by the one authorized native-v3 attempt. No captured file was imported/compiled/executed; no parser, TLS or additional Docker check. The run and resource cleanup were independently reconciled in Dex-Run-Reconciliation.json (5F8C311840561CF6E723C0BCDC3BFC13CFD43BA781C3F1B62E5EA35DEC06AEAA).

## Authoritative byte lane

Image sha256:c220110432cf4adbb4005518a02808b754e0efb050b5de202e71872fecdbd2ab. Files under ../scheduler-t05-native-provenance-dex-v3.evidence/:

| Raw file | Bytes | SHA256 |
| --- | ---: | --- |
| http-client.py.source | 59574 | C2C0694155837D72FC710A4138E5D1E53AE1A652B117A2E23A5B1B0DB527A0F9 |
| ssl.py.source | 51536 | 0061D6EF21088283498491064B79605B5C26C35DFF527AC850A417994D580AD3 |
| email-message.py.source | 48396 | BA32EFEA2602EA52E73028A2817AFDDCCCCACC4385B9800896556D5C22DB2B90 |

These are actual image bytes, distinct from the pinned host3.11 sources and a published CPython tag. Version provenance from prior runner receipts remains separate; this collection's direct proof is byte/image identity, not a new version or runtime capability probe.

## Confirmed source structures, not behavior results

- HTTPResponse.read(amt) still uses the bounded compatibility path: on EOF with a declared remainder it closes the file without raising IncompleteRead. The production application's read(8192) path therefore still needs an actual completeness witness; an unbounded read() behavior is not an adequate substitute.
- Content-Length int conversion ValueError is caught and sets length=None; negative lengths are discarded. A leading plus can parse. These source structures support the same distinction between original parser acceptance and proposed stricter HTTP policy; they are not native test outcomes.
- _get_chunk_left discards two bytes via _safe_read(2) without comparing them with CRLF. _read_next_chunk_size uses int(line,16), and the trailer loop tolerates empty reads and does not parse short trailer-field syntax. Complete trailer termination, syntax and separator integrity remain distinct witnesses.
- Message.get walks _headers and returns the first matching field through header_fetch_parse. Reversed repeated Transfer-Encoding field orders cannot be replaced by a comma-list stimulus; the actual field representation is part of the finite wire input.
- SSLContext.wrap_socket and SSLSocket construction default suppress_ragged_eofs=True. SSLSocket.recv delegates to read, whose SSL_ERROR_EOF handler returns empty bytes when suppression is enabled. This establishes a source mechanism, not proof of which concrete TLS teardown raises that error in the pinned runtime. Orderly close_notify, abrupt EOF and truncated body still need actual distinct synthetic TLS proof. No D4 option change is approved.

## Native guards that matter to the first stop condition

The captured http.client has _MAXLINE=65536, _MAXHEADERS=100 and _MAXINTERIMRESPONSES=100. Its interim loop processes at most100 iterations:100 consecutive CONTINUE responses exhaust the loop and raise HTTPException before a final response is read. The trailer loop increments trailers_read for each nonempty/nonblank trailer line and raises once trailers_read>100 (the101st such line).

The inspected pinned host3.11 client.py has no corresponding interim-response loop cap or trailer-count variable. The published3.12.16 notes anticipated these guards, but native collection now establishes that they exist in this exact image source. It still does not establish executed timing or outcomes.

A streaming native test can therefore hit a count/line/byte cap before the production work deadline. Its receipt must name that actual first guard. To prove actual handshake/header/body budget expiry, the separately approved fixture must avoid earlier caps for the intended case and preserve the real210s work/240s request/30s cumulative cleanup windows. Reusing a stream that hits the trailer count cap and labeling it deadline proof would not satisfy the accepted requirement.

## Consequences for the next packet

Keep Jim's host original-characterization v6 on its declared host parser lane. Do not silently substitute captured native sources into the host runtime or reuse a host result as native behavior. A later native parser/TLS packet must pin these captured byte hashes as provenance, preserve complete positive compatibility cases, freeze exact malformed/truncated inputs and original predictions, and label every injected dependency/first guard/retirement boundary.

The accepted76-ID transport planning inventory and additional variants remain intact. Native source provenance is now completed; native framing/TLS behavior and the full T05/T01–T08 contracts are not closed. No new source-change, fixture authoring, PKI, socket, installation or execution authority follows from this note. Endpoint unbound; all other holds stay.