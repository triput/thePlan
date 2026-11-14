# Actual decisions vs routine preparation

## ACTUAL DECISIONS (need Trish / Dex)

These are not routine prep. Do not treat this handback as approval.

1. **Authorize (or refuse) the unapplied three-file source change** in
   `Proposed-Changes.diff` (`CoveringHTTP.request` finally,
   `JoinedTLS.open` close-failure classification,
   importer deferred `CoveringRootOutcomeUnknown` re-raise).
2. **Exception dependency placement:** accept deferred local import in
   `covering_refresh_import` (chosen), **or** require Alternative B
   (dependency-neutral base type in `covering_transport_policy`) so
   `covering_joined_https` does not import `covering_target_transaction`.
3. **R11 public semantics:** when complete `invalid_grant` is followed by
   cleanup failure, confirm UNKNOWN-stop (proposed) rather than preserving
   `TokenRejected` / ordinary disconnected preflight despite uncertain
   retirement.
4. **Primary provenance shape:** accept `__cause__`/`__context__` chaining
   on `CoveringRootOutcomeUnknown` for witnesses, or require explicit
   sanitized structured attributes (would widen the diff).
5. **Whether JoinedTLS.open change is in-scope for the first source card**
   or staged after HTTP+importer-only (HTTP+importer alone leave R08
   silent-idempotent outer close gap).
6. **Separate execution authority** for Class A/B original witnesses before
   any “corrected” run; preserve originals; no silent repair mid-card.
7. **D2 one-shot fake-verification card** remains untouched and grants no
   T07 authority until Trish answers it (assignment text).

## Routine preparation (not decisions)

- Re-pin / re-hash immutable API sources.
- Read prior Transport-Proof-Matrix, T07/T05 reviews, transport addendum.
- Trace callers and document R01–R12 oracles.
- Draft unapplied diff and proof inventory.
- Freeze this documents-only tip.
- Later (when authorized): extract frozen definitions, fake owned
  sockets/responses, register globals, pin parser/runtime — still not
  implementation approval by itself.

## Non-decisions explicitly held

- No apply of `Proposed-Changes.diff`.
- No check authoring, imports, compile, execution, sockets, PKI, Docker,
  install, binding.
- No D2 packet mutation.
- No change to public UNKNOWN HTTP code string.
- No sock.close retry contract.
- No broadening of T01–T08 inventory ceiling to “T07-only done.”
\n
