# EOF acknowledgment trace and narrow proposed TLS option
Dex, November 11, 2026. Offline source evidence; no imports, source implementation, compilation, socket operation or verification. The proposed increment lane remains pending Trish. D4/TLS-option implementation is not approved by this document.

## Causal chain
1. Accepted JoinedTLS.open calls SSLContext.wrap_socket with do_handshake_on_connect=False but no suppress_ragged_eofs argument (covering_joined_https.py lines61-62 in the pinned T07 source).
2. Captured native ssl.py lines449-460 default suppress_ragged_eofs=True and forward it into SSLSocket creation.
3. SSLSocket.recv forwards into read (lines1238-1245). Its read catches SSL_ERROR_EOF and, when suppression is enabled, returns empty bytes/zero rather than propagating the error (lines1107-1126).
4. JoinedTLS.receive forwards the resulting bytes unchanged after budget checks.
5. With neither an accepted Content-Length nor chunk framing, HTTPResponse.read(8192) treats empty bytes as response end. CoveringHTTP then JSON-decodes the collected prefix. A syntactically complete object is not evidence of orderly authenticated TLS end-of-message.

This is a source-supported failure mechanism, not a reproduced native runtime outcome. OpenSSL may surface a particular abrupt teardown differently. Preserve that uncertainty; a source read cannot replace actual native TLS EOF proof.

## Narrow engineering recommendation
Explicitly pass suppress_ragged_eofs=False at the existing covering-only wrap_socket call. The one-line unapplied diff and original/prospective raw-byte hashes are recorded beside this trace. No candidate source file was written. Keep verify-full CA/hostname checks, numeric destination, nonblocking handshake, shared deadline, local close, conservative sent marker and retirement behavior unchanged.

This option alone does not fix short Content-Length, wrong chunk separators or missing chunk/trailer terminators. The HTTP adapter also needs the bounded completion/framing gates identified in the reconciled design. Keep those in one coherent acknowledgment increment rather than presenting each gap as a separate feature.

## Minimal outcome distinctions required
| Case | Required observation |
| --- | --- |
| Valid close-delimited object followed by orderly close_notify | Retain the accepted positive; actual native TLS must demonstrate it |
| Same JSON prefix followed by abrupt TLS truncation | Must not become known object/token success or known invalid_grant; preserve UNKNOWN after possible OAuth send |
| Declared-length short body with syntactically valid object prefix | HTTP completeness gate rejects before decode/known outcome; independent of whether TLS close was orderly |
| Complete fixed-length or correctly terminated chunked response | Preserve complete-response positives; receipt of self-delimiting message boundaries is distinct from a later connection EOF |
| Response/transport retirement failure | Existing primary/provenance and UNKNOWN rules still apply; no success with uncertain owned retirement |

For complete fixed-length/chunked messages, do not invent a rule requiring a separate EOF read or TLS shutdown round trip after their already complete message boundary. For close-delimited messages, do not substitute a fake empty receive for orderly close_notify.

## Verification layers
An eventual fake-only check can verify option forwarding and exception propagation using fake SSL/socket objects; it cannot prove native teardown behavior. A separately authorized local synthetic TLS run must establish orderly and abrupt cases against the exact runner/OpenSSL and the final assembled source, with bounded peers and truthful retirement. No live provider or real credential is needed.

The final proof should cover actual send/ack classification through the owning OAuth/caller path where required, not only assert a low-level exception. Existing expected malformed/nonobject/encoding OAuth UNKNOWN controls remain applicable at their actual recorded scope. No retry, fallback or later unsafe admission.

The preceding57 host characterization controls, native source captures, original packets, cleanup receipts and historical custody UNKNOWNs remain immutable. Endpoint unbound; all execution and other holds stay.
