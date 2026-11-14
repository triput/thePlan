# Next native T05 increment — design notes, no execution authority

Dex, 2026-11-13. This is a queued design note, not a second Matt assignment. The active assignment remains independent MS-merge staged-fake review. Existing authoring scope and execution holds apply.

The accepted goal still includes all required bounded transport contracts. Current merged runner declares31 cases but implements only NONEXPIRED and REFRESH;29 bodies deliberately HOLD. The76 planning requirements remain indexed. Source declarations, fake prerequisites and actual native evidence must remain separate.

## Constraints confirmed from the frozen merged source

Peer17EA148E `_http_response_bytes` automatically appends Content-Length when absent. It cannot currently produce the close-delimited positive required by NP-T05-ORDERLY-CLOSE. A request to emit Transfer-Encoding without Content-Length would also receive an automatically appended length and test conflicting framing rather than the intended chunk transcript.

The same peer's orderly branch calls unwrap, tolerates OSError, closes locally and records an attempt. That tolerance is intentional for existing multiple-connection verticals. JoinedTLS has suppress_ragged_eofs=False and local-only close. A successful client receipt of close_notify does not require successful reciprocal two-way unwrap at the peer. Conversely, the scripted attempt alone does not prove what the client received. Do not undo the peer-close correction or use its notes as the TLS oracle.

## Proposed next bounded design

Use the existing peer/transcript/runner/check roles in a fresh successor. Add explicit finite fixture framing selection with a default that preserves every existing vertical wire byte. Distinguish automatic fixed length, explicit fixed length, close-delimited and exact raw chunk framing; reject inconsistent combinations before sending. Preserve malformed/truncated framing as explicitly selected negative scripts, not serializer accidents. Pin exact header/body wire bytes and finite transcript inventories in preparation checks.

For native EOF, observe the actual pinned native parser/JoinedTLS client result, exact useful body or exception classification, the selected transcript, and confirmed owned-resource retirement. Do not log raw requests, credentials, keys, response bodies or unrestricted errors. Establish a complete close-delimited positive separately from short fixed-length valid-JSON prefix refusal and abrupt TLS truncation. Short invalid-JSON and complete invalid-JSON must remain distinct: the former fails completeness before decoding; the latter reaches decoding and fails there. Native chunk terminators/trailers need their own exact observations; a fixed-length test cannot close them.

A peer unwrap OSError does not by itself fail an otherwise properly observed orderly client path; an unjoined peer or uncertain resource retirement does. A script label or an attempted-unwrap note cannot close the proof requirement. Preserve primary failure versus cleanup uncertainty contracts and all approved diagnostic disclosure limits.

Reuse verified finite framing/helper proofs for unchanged source predicates only. Map every T05 requirement and supplementary chunk/TLS distinction to the matching evidence or explicit open gap; do not claim a whole-family PASS from a successful TLS example. Keep existing verticals and their pending command versions immutable. Do not merge this increment into a native launch without focused preparation review and exact one-shot approval.

## Decision boundary

This note recommends a fixture design within existing named authoring roles and preserves the already-approved product framing policy. It adds no application behavior, policy restriction, source edits, imports, parsing, compilation, test/helper invocation, sockets, TLS generation, native execution or cleanup authority. Any need to change an immutable helper or application bytes must return as a separate bounded decision.

Signed: Dex
