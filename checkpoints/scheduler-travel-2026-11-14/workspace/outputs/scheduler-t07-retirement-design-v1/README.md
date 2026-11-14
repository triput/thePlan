# T07 retirement / caller-classification design — Jim handback

Status flags: documents_only=true; pplied=false; xecuted=false; d2_one_shot_untouched=true.

Assignment: .../scheduler-d2-fake-v1/Next-Transport-Design-Assignment.md  
SHA256 28232EFED72B8B60E89086866B1B9A1B7A36366123CE834E1F4AB1EA0D672719 (re-verified on read).

Immutable API root: .../scheduler-d2-fake-v1/packet/payload/workspace/apps/api  
Required pins all MATCH (see INPUT-PINS.json).

## One-sentence recommendation

No: the covering provider path cannot truthfully stop at UNKNOWN on uncertain retirement today — CoveringHTTP.finally can replace the primary with a raw cleanup exception and skip transport-close after response-close failure, and import_covering_subscription_cache's broad xcept Exception around _pull_provider turns surviving CoveringRootOutcomeUnknown into an ordinary failed import that still allows later target/assessment admission; the narrowest justified unapplied change is dual-attempt cleanup classification to CoveringRootOutcomeUnknown in CoveringHTTP.request plus a deferred re-raise of that type in the importer pull catch (no top-level reverse import).

## Contents

| File | Role |
| --- | --- |
| HANDBACK.txt | Operator-facing freeze summary |
| Caller-Trace.md | Event / identity / OAuth → public outcome → later admission |
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
\n
