# T05 framing: standard reconciliation and next design boundary

Dex, November 11, 2026. Documentation-only investigation. No application, checker, fixture, parser, import, compilation or test execution; no source change. Jim retains the sole active T07 implementation/check-authoring assignment. D2 v2 has passed; T07 execution remains held.

## Primary-source requirements

- A response shorter than its valid Content-Length is incomplete. Chunk framing requires the data separators, terminal zero chunk, trailer section and final CRLF. Receiving valid JSON does not establish either boundary. [RFC 9112 sections 6.3, 7.1 and 8](https://www.rfc-editor.org/rfc/rfc9112.html#section-6.3).
- Close-delimited responses remain supported by HTTP. For TLS, a response without length/chunk framing is complete only after a valid closure alert. Complete length/chunk framing can establish completion despite incomplete TLS closure. [RFC 9112 sections 8 and 9.8](https://www.rfc-editor.org/rfc/rfc9112.html#section-9.8).
- Transfer-Encoding takes precedence over Content-Length, but their coexistence ought to be handled as an error. Conflicting or otherwise invalid lengths are unrecoverable framing errors. [RFC 9112 section 6.3](https://www.rfc-editor.org/rfc/rfc9112.html#section-6.3).
- For identical repeated decimal Content-Length values, the recipient may reject the message or replace the list with one value. Therefore blanket rejection is a permitted recipient choice, not a uniquely mandated interpretation. [RFC 9110 section 8.6](https://www.rfc-editor.org/rfc/rfc9110.html#section-8.6).

## Reconciliation with inspected local source

The retained [host-source review](../scheduler-d2-fake-v1/T05-Chunk-Termination-and-TLS-EOF-Review.md) distinguishes bounded fixed-length EOF, wrong chunk separators, missing trailer terminators and suppressed TLS EOF errors. Those observations remain source-derived hypotheses about application behavior. The standards above establish the required distinctions; they do not demonstrate that a pinned native invocation accepted malformed bytes.

The current proof design must preserve positive controls for complete fixed-length responses, complete chunked responses (including extensions/trailers where supported), and orderly TLS close-delimited responses. Pair each negative with the same valid bounded object and the same caller purpose. Include both token-success-shaped and invalid_grant-shaped bodies: a syntactically valid prefix must not stand in for a complete remote acknowledgment.

Later authorized original witnesses must exercise actual application/parser methods, retain raw-byte provenance and independently observe the caller outcome, sent state, transaction outcome and retirement. Parser closed flags, successful local close and JSON decoding alone are insufficient completion oracles. Native parser/SSL provenance and actual TLS closure behavior remain to be established.

## Narrowest next preparation step

After T07 is frozen and verified, assign Jim the bounded T05 original-behavior witness design against the accepted transport matrix. Require exact header/body variants and positive compatibility controls before proposing a completeness correction. Compare candidate fixes against the existing deadlines, cumulative response-byte ceiling and retirement contracts; do not replace bounded reads with unbounded reads.

No compatibility restriction is adopted here. If a proposed fix rejects a previously supported valid response form, bring the concrete impact and alternatives to Trish before implementation. Any parser/TLS option change requires its own reviewed fresh-copy scope. No T05 implementation or execution authority is added by this note. Full T01–T08 proof remains open; endpoint unbound and all holds stay.
