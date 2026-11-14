# Actual decisions vs routine preparation (v2)

Supersedes v1 tip `ABA0923505155EC0D7555B13A61CB6F7CFFE662051F0E2B5C439BEAC48800F2A`.

## ACTUAL DECISIONS (need Trish / Dex)

1. Authorize or refuse the unapplied three-file v2 diff (HTTP + JoinedTLS.open
   + importer), including explicit provenance attributes on UNKNOWN.
2. Confirm R08 retains JoinedTLS.open change (no two-file ceiling).
3. Accept explicit `.primary` / `.response_close` / `.transport_close` /
   `.retirement_provenance` as the witness oracle (not `__context__`).
4. R11: UNKNOWN-stop when invalid_grant is followed by cleanup failure.
5. Optional later Alternative B (neutral exception base) if JoinedTLS must
   not import covering_target_transaction.
6. Separate execution authority for original vs candidate witnesses.
7. D2 one-shot card still grants no T07 authority until Trish answers it.

## Routine preparation

Re-pin sources; revise docs from v1; freeze v2 tip; later authorized
fixture prep still separate.

## Non-decisions held

No apply; no execution; no D2 mutation; no sock.close retry; v1 tip
immutable.
