# Covering response-framing compatibility decision

Dex for Trish, November 11, 2026. Policy decision only. The framing packet remains under static revision; no launch is requested here.

## Recommendation

Accept the following covering-only response-framing rules as one bounded compatibility policy. They make complete, unambiguous responses a prerequisite for treating JSON/OAuth data as acknowledged. Keep valid ordinary Content-Length, valid chunked responses and close-delimited JSON positives. A future native TLS run must distinguish orderly close_notify from abrupt truncation; byte fakes cannot prove that distinction.

## Exact accepted/refused behavior

1. Content-Length: allow one field with an unsigned ASCII decimal value after trimming only SP/HTAB. Leading zeroes remain accepted. Refuse repeated fields (including identical repeats), comma-list values, signs, empty/nondecimal values and other whitespace not removed by the real header parser. A valid fixed-length response must supply its complete declared body before JSON/OAuth classification.

2. Transfer-Encoding: allow one parser-visible value, case-insensitively exactly chunked, with the actual parser in chunked mode. Refuse repeated/list/mixed/unsupported encodings and any response containing both Transfer-Encoding and Content-Length. The existing pinned header parser strips leading field SP/HTAB after the colon, so that leading wire whitespace stays accepted. Trailing whitespace remains visible and is refused by this candidate to match the parser's actual chunked-mode recognition. This is parser-visible admission, not a claim that raw header bytes are preserved unchanged.

3. Recorded malformed-header defects: refuse a response when the actual header parser records a Message defect. This is a bounded defect gate, not a new complete HTTP grammar validator.

4. Chunk completion: require an unsigned hexadecimal chunk-size token (ordinary extensions remain supported), exact CRLF separators after chunk data and a complete final trailer terminator. Refuse colonless trailer field lines. Preserve the existing native trailer-count bound. This does not add broader trailer-name or extension grammar validation beyond the stated checks.

5. Close-delimited responses: retain them as supported, subject to the actual TLS closure distinction. The proposed covering-only suppress_ragged_eofs=False option prevents the stdlib's ragged-EOF suppression from treating an abrupt TLS termination as an ordinary empty read. The actual native clean-versus-abrupt behavior remains unproved until an independently reviewed and separately authorized synthetic native/TLS fixture demonstrates it. Complete self-delimiting responses do not acquire an extra EOF read or unwrap exchange.

## Compatibility cost and preserved contracts

An otherwise usable provider response with identical duplicate Content-Length, a comma-list representation, or trailing Transfer-Encoding whitespace may now refuse. I recommend that explicit restriction rather than accepting ambiguous framing. No blanket percent ban, URL rewrite, provider fallback or retry is added. The already approved D2 path policy and Microsoft routing policy stay unchanged.

Preserve deadlines, cumulative counters, send markers, OAuth lost-outcome UNKNOWN classification, transaction/rollback guards, ordered results, and independent response/transport retirement. A framing refusal is not permission to call an uncertain OAuth operation a known failure: existing after-send OAuth remapping to UNKNOWN still applies. Exact native integration/transport evidence and cleanup remain required by the full goal.

## Evidence and status

Read-only independent source review inspected candidate covering_http_transport.py SHA256 29CBD53C85E8D40185A5E7DF73DF85B752A34837D25FCD65DB6504AFB775B368 and covering_joined_https.py SHA256 760177767EA64A6129E788BA7828FBE998522706791E6CFC5DBB9C2D0C013427. All 468 application source-manifest pins in the frozen framing-v2 packet matched. Historical host-original T05 characterization identifies concrete incomplete-body/chunk/header acceptance defects; it is not candidate or native TLS verification.

The v2 packet has static admission/result-oracle issues already returned to Jim for a fresh successor (review C269FFC1CF3C2B793F2DA37CFA44D1FD796CF4DC79CB8041DCCEAE267A36603D). This policy decision does not accept that packet as launch-ready or claim its checks passed. It does not freeze erroneous future observations: any source/oracle discrepancy must still be reconciled honestly before launch review.

## Authority requested

Approve this compatibility policy only so the already authorized fresh-copy authoring can freeze truthful contract/oracle labels. No source-scope extension, imports, compilation, verification, helper invocation, execution, sockets, certificate generation, Docker/native run, installation, build, provider operations, deployment or endpoint binding is included. Exact commands, hashes, limits and independent review still precede every launch card. Endpoint unbound; all other holds stay.