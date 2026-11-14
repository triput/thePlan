# Framing increment: bounded implementation brief
Dex design recommendation, November 11, 2026. No source/checker implementation, imports, compilation or verification. Proposed increment lane is still pending Trish; existing source/execution holds apply.

## Increment outcome
A bounded covering exchange must not classify a syntactically valid JSON prefix as a complete acknowledgment when fixed-length/chunked framing is incomplete or a close-delimited TLS message is truncated. Preserve complete fixed-length, chunked-with-extension/trailers and orderly close-delimited positives. Preserve existing access, verify-full trust, conservative sent marker, counter/deadline, UNKNOWN/no-retry and independent retirement contracts.

Engineering choice: a covering-only guarded HTTPResponse subclass for the parser gaps, a before-decode completion/header gate, and the separately described explicit ragged-EOF option. Keep the8192-byte body loop. No global parser monkeypatch, unbounded body read, TLS unwrap/shutdown exchange or replacement HTTP stack.

The subclass's private helper and length-attribute coupling is an engineering tradeoff to review against pinned host and native runtimes, not seven separate product decisions. Future runtime upgrades must requalify these paths. Do not runtime-hash or import captured native source into the host process.

## Candidate application scope
Fresh successors of the route candidate:
- covering_http_transport.py: add local response subclass and use it at the existing constructor; gate before JSON/known OAuth classification. Retain the route predicate, page/byte/item accounting, return/exception mapping and finally block.
- covering_joined_https.py: one explicit suppress_ragged_eofs=False argument, original/prospective pins in Proposed-TLS-EOF-Option-Pins.json.
No other application changes. Preserve prior sources/evidence and the historical bases.

## Implementation responsibilities, without prescribing a full protocol rewrite
1. Fixed length: after bounded collection and before decode, a declared remaining length must be zero. Do not use JSON validity as the completeness check. This catches F02/F03/F05 while preserving F01/F04/F05b.
2. Chunk boundaries: validate chunk-data separator equality, last-chunk line termination and the final empty trailer line. Preserve valid extension/trailer positives. Keep line/header-count and cumulative byte/deadline guards; an override must not drop the captured native limits.
3. Header inventory: retain all Content-Length and Transfer-Encoding occurrences before dictionary collapse. Refuse parser-reported malformed-header defects before decoding. Additional grammar restrictions are a proposed compatibility policy, not already accepted behavior.
4. TLS EOF: use the narrow proposed option; later real local native TLS must distinguish orderly close_notify from abrupt EOF. Complete self-delimiting responses must not acquire an extra requirement to read EOF after their already complete message boundary.
5. Retirement: preserve independently attempted response and transport closes, primary/provenance attribution and UNKNOWN classification. A framing error must flow through the existing finally block.

## Actual header-source finding
The captured native HTTP client gathers header lines then parses them as a Message; it does not automatically turn every parser defect into an exception. Captured Message initializes defects and provides get_all, whereas get returns the first matching occurrence.

The read-only host Python3.11 email/feedparser.py inspection shows a colonless nonblank header line can create MissingHeaderBodySeparatorDefect and proceed, rather than necessarily throwing. This supports inspecting defects as a narrow candidate guard. It is a host source prediction, not an executed original or native behavior claim. The corresponding native feedparser implementation was not part of the three-file collection.

Proposed illustrative original/candidate stimulus (design only): a complete fixed-length object with one colonless header line. Source reasoning predicts the first valid Content-Length may still control reading while a defect is recorded. A future authorized check must establish the exact actual outcome and the candidate refusal; unexpected parser results stop. Do not label this as an observed fourth source defect or add an unbounded header-grammar campaign.

## Compatibility recommendation to freeze before launch
Use one coherent fail-closed policy proposal:
- One Content-Length field with an unsigned ASCII decimal value; leading-zero decimal forms remain accepted. Reject repeated/list, conflicting, signed, negative, empty or nondecimal lengths.
- Reject Transfer-Encoding together with Content-Length. If transfer coding is supported, accept the single chunked mechanism; reject unsupported/repeated/mixed coding declarations.
- Require complete chunk/trailer boundaries. Propose rejecting malformed trailer field lines without promoting trailer fields into framing metadata.
- Keep accepted complete close-delimited positives, subject to actual orderly-TLS proof.

This can reject otherwise equivalent duplicate/list length spellings accepted by some peers. That is the material compatibility decision to disclose to Trish as one recommendation. Do not silently convert it into an accepted oracle. Exact whitespace/extension/trailer token handling must be documented with the candidate diff; avoid adding unrelated restrictions.

## Focused verification, reusing evidence
Reuse immutable57-wire host-characterization inputs/results as original evidence. Where the candidate must change outcomes, freeze explicit original-versus-candidate expectations. Preserve the3 expected invalid-JSON/nonobject/encoding OAuth UNKNOWNs. Assert known complete invalid_grant and complete token positives through actual selected owning adapters; never treat low-level decode as proof of token persistence.

Add only actual missing proof:
- Explicit malformed-header defect stimulus described above.
- Active primary plus both distinct close failures, exercising the real candidate finally block and preserving all3 exception roles.
- Item/byte excess within an already-admitted response: equality/new-admission tests do not establish these data-overrun branches.
- Fake option forwarding/error propagation for the TLS change, clearly not native TLS proof.

These additions are already named transport obligations or consequences of the actual correction, not optional adversarial expansion. Reuse the byte-identical ProviderCounter evidence and recorded five cleanup combinations at their demonstrated scope, with final-source lineage. Avoid a Cartesian product of every malformed wire, provider role, cleanup fault and runtime merely to grow coverage.

Real socket/TLS/timing/ownership and final native assessment remain separate bounded execution layers; do not substitute fake owner IDs, empty fake recv or fake transaction acknowledgments for those claims. Their reviewed finite cases, exact commands, topology and limits still need explicit launch authority.

## Deliverable and sequencing
Jim remains primary implementer. His current active task is the narrow EOF-option static review. After a concrete source-authoring approval/approved increment lane and explicit assignment transition, prepare a fresh candidate plus four-role fake packet, exact diffs, original/candidate hashes, finite ordered controls, commands and supervision limits. Independent review precedes launch. No automatic execution.

Endpoint unbound. No installation/build, live providers, real credentials, production changes, deployment or activation.
Host feedparser source read pin: A3A309A212382FA3CA054DB3150C78B931D9E975FD55EDBC8D6230FDA91A5E6D; path: C:\Users\trish\AppData\Local\Programs\Python\Python311\Lib\email\feedparser.py.
