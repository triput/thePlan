# T07 v4 extracted caller dependency boundary

Dex, November 11, 2026. Provisional read-only review of the mutable working checker, not final frozen acceptance. No application/check imports, compilation or execution.

## What is actually extracted

The working checker selects the real role-admission classes, connector bindings/_RoleParent/CoveringRoleConnector, and run_bounded_domain. The domain body's referenced names are supplied: role enum, exception classes, token result types, auth/guard/preflight/window/response/assessment helpers, datetime/timezone, and telemetry placeholders. Its credential_id=None path intentionally bypasses agent telemetry. This review found no additional obviously missing top-level dependency in the inspected domain body; execution remains unproven.

## Substitutions that limit the claim

| Boundary | Current fake or replacement | Permitted inference after later passing verification |
| --- | --- | --- |
| Authentication/ownership | Fixed identity and generated fake targets; guard no-op | Domain orchestration after simulated authorization, not actual authorization proof. |
| Native transaction | _StubCoveringTargetTransaction calls locks/apply and retires on success | Connector exception propagation/admission behavior; no real SQL, commit, rollback or lock proof. |
| Parent adapter | Stub acknowledged outcome and retirement state | Controlled connector lease completion, not observed native retirement. |
| Session close | Fake RoleCompletion with outcome_known/locks_exited/retired true | Known cleanup supplied by the fixture; no actual transport cleanup acknowledgment. |
| Budget | Simplified stopped Boolean and constant remaining times | Admission stop under the specified fault; no deadline, elapsed-time or cumulative cleanup proof. |
| _classified_role | Handwritten equivalent catches fake ApiError only | UNKNOWN passes unchanged in this model, but full production policy-refusal behavior is not covered. Actual helper also catches CoveringSubscriptionNotEligible. |
| Final assessment | Stub raises deadline if reached | Counter/trace may prove assessment was not admitted; no final native assessment result from this check. |
| HTTP | Extracted HTTP/JoinedTLS methods with fake socket/TLS/dependencies | Fake behavioral regression evidence; no live TLS/socket, provider or native runtime proof. |

The expected UNKNOWN stop path does not depend on classifying CoveringSubscriptionNotEligible, so the narrower _classified_role stub is not independently treated as a launch blocker for this one path. Prefer extracting that helper if policy-refusal paths are later added; do not use this check to claim those paths covered.

## Remaining acceptance conditions

The actual HTTP retirement fault still must traverse its owning event/OAuth caller into the appropriate real domain port, as already sent to Jim. A hand-manufactured UNKNOWN in apply cannot establish that linkage, especially for OAuth's token phase. Require original/candidate evidence and continuation mutation sensitivity without altering the selected production methods or hiding counters. R07's precise fault/cleanup oracle must also be reconciled.

The final launch review must explicitly disclose these fake boundaries and independently pin every extracted source, original reference, control inventory, launcher and runtime input. Existing native I01/I02 evidence establishes different integration obligations; it does not convert these fake transport controls into native transport proof. No expansion of source or execution authority is implied.
