# T07 retirement / caller-classification design — Jim handback v3

Status flags: documents_only=true; applied=false; executed=false; d2_one_shot_untouched=true.

Supersedes tipped v2 at `F:/DropFolder/pending/post-native-t07-retirement-design-jim-v2-2026-11-11/` (TIP-FREEZE SHA256 `9522BC2F8166F508606E6ACB1912511DDDB39D472CBA2FE400419A7AC30163BB`). v1 tip `ABA0923505155EC0D7555B13A61CB6F7CFFE662051F0E2B5C439BEAC48800F2A` and v2 remain immutable.

Assignment SHA256 `28232EFED72B8B60E89086866B1B9A1B7A36366123CE834E1F4AB1EA0D672719` (re-verified). Required API pins MATCH (`INPUT-PINS.json`).

## One-sentence recommendation

No on current source; unapplied three-file change captures this invocation's primary in except locals (never ambient sys.exc_info), raises a new UNKNOWN on cleanup with append-only prior_retirement_provenance, keeps required JoinedTLS.open R08 UNKNOWN, and deferred-importer re-raise — hunk-count-verified diff.

## Dex feedback closed in v3

1. Primary capture without sys.exc_info; outer-handler controls; no mutation of caller-owned UNKNOWN; append-only provenance.
2. Exact context/count-correct unapplied diff with programmatic hunk verification; prospective resulting hashes only.

## Contents

| File | Role |
| --- | --- |
| HANDBACK.txt | Operator freeze summary |
| Caller-Trace.md | Caller paths (carried/refined) |
| T07-R01-R12-Reconciliation.md | Twelve branches |
| Design-Recommendation.md | Alternatives + chosen design |
| Proposed-Changes.diff | UNAPPLIED exact diff |
| Proof-Inventory.md | Witnesses including outer-handler controls |
| Decisions-vs-Routine.md | Actual decisions |
| Scope-and-Limits.md | Limits |
| INPUT-PINS.json | Pins + prospective hashes |
| ARTIFACT-HASHES.txt | Artifact hashes |
| TIP-FREEZE.json | Tip freeze |

No apply, execution, or D2 mutation.
