# T05 chunk termination and TLS EOF — additional proof requirements

Dex, November 11, 2026. Read-only source/hash investigation and design notes. No parser, application, fixture, import, compile, test, socket or Docker execution. No source correction or executable fixture authoring. D2 verification remains held at its existing card. Jim's sole active assignment remains the documents-only T07 design.

## Current inspected sources

All application paths below are relative to the immutable packet/payload/workspace/apps/api/app/services copy beside this note.

| Subject | SHA256 |
| --- | --- |
| covering_http_transport.py | AECE10186CFFAE46D3EF2292D3772F1C287FD0A562AA9E764AAC4ABB10C861D8 |
| covering_joined_https.py | C58382900BE1C190ED39242B4992FE88E1155E55F7E8C33D32065DBFCC993468 |
| Host Python311/Lib/http/client.py | 3A752927A1257EDEBCABAD42CA9508AD532F91C15431755BFBE437A32AB13EB2 |
| Host Python311/Lib/ssl.py | 8A1E202A75758A3E1DDB88289AFAFB7DE2073220E0A7154DF70A7B73661F1E0E |

The two host library files were read from C:/Users/trish/AppData/Local/Programs/Python/Python311/Lib. The native runner's parser/SSL bytes and linked OpenSSL behavior have not been established by this investigation. Do not project host-source reasoning onto a native result without separate provenance. ssl.py is a newly identified future proof dependency; it is not added to the pending D2 execution scope or admission manifest.

## Newly distinguished parser branches

The earlier T05-Framing-Branch-Review.md correctly identifies that Content-Length truncation can reach EOF without IncompleteRead in bounded HTTPResponse.read(amt). The current application still uses read(8192) and then JSON validity. The additional chunk paths below cannot be collapsed into that fixed-length witness.

1. In host http/client.py `_get_chunk_left`, lines 568–570, the parser consumes `_safe_read(2)` after a data chunk and discards those bytes. It does not compare them with CRLF. `_safe_read` checks the byte count, not the byte values. Therefore two present but incorrect separator bytes need their own original witness, separate from a missing/short separator.
2. In `_read_and_discard_trailer`, lines 546–559, EOF ends trailer collection without raising. `_get_chunk_left` then sets chunk_left to None after zero-size chunk processing. Consequently zero chunk followed by EOF without the final trailer terminator can appear complete to this parser. Checking only chunk_left or isclosed would not establish the stricter framing invariant.
3. `_read_next_chunk_size`, lines 531–544, passes the line (minus any extension) to int(...,16) without an explicit CRLF check. Terminal chunk-size line ending variants need separate observation; do not assume strict rejection just because a size was decoded.

These are source-derived branches, not executed acceptances or proof of an exploitable native defect. Any later original witness must run the actual pinned application/parser path and record what it does before a corrected behavior is claimed.

## Concrete expansion of the existing F08/F09 obligations

The following are design byte spellings, not generated fixture files or an authorized run inventory. CRLF below means exact bytes 0D 0A. Prefix each with the later reviewed synthetic HTTP status/headers and use valid bounded object data `{}`. Freeze complete bytes, hashes, status/purpose, exception provenance and actual caller outcomes only under subsequent approved preparation.

| Distinct candidate | Chunk body spelling | Observation to require |
| --- | --- | --- |
| C-BASE | `2 CRLF {} CRLF 0 CRLF CRLF` | Complete positive, unchanged object, no extra exchange, independently observed retirement. |
| C-DATA-SHORT | `3 CRLF {}` then EOF | Actual incomplete chunk-data branch; no successful object exposure. |
| C-SEP-SHORT | `2 CRLF {}` then EOF or one separator byte | Separate zero-byte and one-byte short separator branches. |
| C-SEP-WRONG | `2 CRLF {} XX 0 CRLF CRLF` | Two wrong separator bytes versus the baseline. Record current parser/application acceptance or rejection; do not describe a two-byte count as validated CRLF. |
| C-ZERO-ABSENT | `2 CRLF {} CRLF` then EOF | Missing terminal chunk; distinct from terminal size present with missing trailer terminator. |
| C-TRAILER-EOF | `2 CRLF {} CRLF 0 CRLF` then EOF | Missing final blank line. Record whether original parser reports completion; a parser state flag is not a sufficient oracle. |
| C-ZERO-NO-CRLF | `2 CRLF {} CRLF 0` then EOF | Terminal size parsed without its CRLF; characterize independently. |
| C-TRAILER-LINE-EOF | `2 CRLF {} CRLF 0 CRLF X-Test: fixture CRLF` then EOF | Trailer line present but final terminator missing; no assumption that reading a trailer proves its completion. |
| C-TRAILER-MALFORMED | Complete chunk data followed by an invalid trailer field and final blank line | Characterize actual parser behavior; distinguish framing completeness from trailer syntax policy. |

Use the same distinctions with token-shaped and invalid_grant-shaped synthetic objects where complete remote acknowledgment changes classification. Preserve `sent` before the first send call and no replay. An event failure may be known after acknowledged DB rollback/parent retirement, while provider retirement uncertainty must still be represented and prevent unsafe continuation; coordinate that boundary with the pending T07 proposal.

## TLS EOF provenance changes the close-delimited question

JoinedTLS.open calls SSLContext.wrap_socket without specifying suppress_ragged_eofs. In the inspected host ssl.py lines 511–522, its default is True. SSLSocket.recv delegates to read at lines 1288–1295; read at lines 1157–1175 converts SSL_ERROR_EOF to an empty byte result when that option is enabled. Thus the current host source can erase the distinction between a TLS EOF error and ordinary empty receive before HTTP framing sees it. This is conditional on the linked TLS implementation producing that error and is not a live observation.

For fixed-length or chunk-framed responses, complete framing can be established independently of transport closure if the application validates the required framing. For a response with neither framing mechanism, accepting EOF as completion requires an explicit compatibility/completeness policy and proof of the relevant TLS EOF semantics. A generic fake receive returning empty bytes cannot prove that a real peer sent close_notify. Nor does successful local socket.close prove the remote response was complete.

Carry both orderly close_notify and abrupt peer closure into the later real isolated TLS proof for close-delimited responses. Do not silently set suppress_ragged_eofs=False, reject all close-delimited responses, switch to unbounded reads, introduce a second parser, or change token error policy under a fixture task. Those would be proposed source/compatibility changes requiring review. Any eventual decision brief should compare the concrete compatibility impact after reconciling the original witnesses and actual native runtime provenance.

## Integration and completion boundary

This note expands mandatory T05/T03/T04 witness distinctions; it does not replace the accepted T01–T08 matrix, the 59 initial plus17 deferred planning inventory, or T07's caller-level retirement requirements. Functional byte fakes, real local TLS/socket evidence and actual native caller/assessment outcomes remain separate proof layers. No runtime result or source fix is claimed. The Scheduler integration goal remains active and incomplete; endpoint remains unbound and all holds remain.
