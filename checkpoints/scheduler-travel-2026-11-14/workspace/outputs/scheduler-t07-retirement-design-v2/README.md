# T07 retirement / caller-classification design — Jim handback v2

Status flags: documents_only=true; applied=false; executed=false; d2_one_shot_untouched=true.

Supersedes tipped v1 at `F:/DropFolder/pending/post-native-t07-retirement-design-jim-v1-2026-11-11/` (TIP-FREEZE SHA256 `ABA0923505155EC0D7555B13A61CB6F7CFFE662051F0E2B5C439BEAC48800F2A`). v1 remains immutable.

Assignment: `.../scheduler-d2-fake-v1/Next-Transport-Design-Assignment.md`
SHA256 `28232EFED72B8B60E89086866B1B9A1B7A36366123CE834E1F4AB1EA0D672719` (re-verified on read).

Immutable API root: `.../scheduler-d2-fake-v1/packet/payload/workspace/apps/api`
Required pins all MATCH (see `INPUT-PINS.json`).

## One-sentence recommendation

No: uncertain retirement cannot truthfully stop at UNKNOWN today; the justified unapplied change keeps the three-file set (CoveringHTTP dual-attempt finally with explicit dual cleanup provenance, required JoinedTLS.open UNKNOWN for R08 because outer finally is a no-op after closed=True, and deferred importer re-raise of CoveringRootOutcomeUnknown).

## Dex provisional feedback closed in v2

1. R08 / two-file ceiling: JoinedTLS.open change is required and justified; HTTP-only is insufficient (see Design-Recommendation.md).
2. Dual cleanup provenance: explicit `.primary` / `.response_close` / `.transport_close` / `.retirement_provenance` on UNKNOWN; witnesses must not rely on `__context__` for caught cleanup (see Proof-Inventory.md, T07-R01-R12-Reconciliation.md).
3. Doc hygiene: control-byte and trailing-escape artifacts removed; INPUT-PINS.json must parse.

## Contents

| File | Role |
| --- | --- |
| HANDBACK.txt | Operator-facing freeze summary |
| Caller-Trace.md | Event / identity / OAuth to public outcome and later admission |
| T07-R01-R12-Reconciliation.md | All twelve branches |
| Design-Recommendation.md | Alternatives + chosen narrowest |
| Proposed-Changes.diff | UNAPPLIED proposed source diff |
| Proof-Inventory.md | Original vs candidate witnesses |
| Decisions-vs-Routine.md | Actual decisions vs routine prep |
| Scope-and-Limits.md | Later prep/run limits; open questions |
| INPUT-PINS.json | Re-pinned consumed sources |
| ARTIFACT-HASHES.txt | This handback's artifact hashes |
| TIP-FREEZE.json | Frozen tip record |

No packet/, application source, check, import, compile, execution, socket, PKI, Docker, install, or binding work was performed. D2 fake-verification card untouched.
