# Remaining gaps — native-provider prep-v4 (first vertical increment)

Flags: `executed=false`; `launch_authorized=false`; `launch_ready=false`; `prep_is_not_pass=true`; `first_vertical_increment=true`; endpoint unbound.

Immutable tipped predecessors preserved:
- prep-v1 TIP on-disk `0AA4C08197E897F8A91A23945D882854FED44528E476AF04506D245B2EDB211D`
- prep-v2 TIP on-disk `9C49E0B84B36F7B53FADC79490FCEF3AB2CE093FA6F6B6A8E16F40243BEDD38D`
- prep-v3 TIP on-disk `06C46CB3547C70247021885D463D9F642FE580534577919B964A56F745DC11A4`

## Port dependency (unchanged)

| Field | Value |
| --- | --- |
| Status | **VERIFIED finite host PASS 9/9** (extracted-class) |
| RESULT | `B8C6353A712382E16B601036034B32293EDEDF345388990D489B0E9AB9A12548` |
| Receipt | `61F266A34BF7E4BD8BD5193D3DB6A315F02C9C9AC13D4AC51F80C73C62720961` |
| Reconciliation | `E922DA6183B70D5DA9B1CBE19768F95E6B31578DA6B5594C2BD0CB5129861D7D` |
| Policy in assembly | `5F48FD7ED50C57A6A47ADA20138678BB3C112A2A69D1C234A47580E6CD068B88` |

Consumed verified PASS status for assembly. **Still not** native dial/TLS or full T01 closure.

## Explicit retained gaps

| ID | Disposition | Note |
| --- | --- | --- |
| T02-ITEMS-OVERFLOW | GAP + focused control authored | Host-fake EXCESS-ITEM-BYTE retained; focused approved-ceiling crossing control authored in checker (injected 9999+batch2) — not native 10k overrun. |
| T02-BYTES-OVERFLOW | GAP + focused control authored | Same; injected 16777215+body2 / reader left+1 — not native 16MiB run. |
| T08-NESTED | GAP_OR_FOCUSED_FAKE | ContextVar nesting; focused behavioral control now AST-extracts selected `covering_provider_transport`. |
| T08-RESET | GAP_OR_FOCUSED_FAKE | ContextVar reset normal/exceptional; same extracted checker. |
| T01-ORIGIN-FOREIGN-PORT | PORT_HOST_FAKE_PASS_NOT_NATIVE | Port PASS reconciled; not native dial/TLS / full T01. |
| T07-BOTH-CLOSE-AFTER-PRIMARY-FAILURE | NATIVE case authored / body HOLD | `NP-T07-BOTH-AFTER-FAILURE` — host-fake PRIMARY-BOTH-CLOSES does not close. |

## Future-only HOLD observations (excluded from first vertical)

- Close-delimited positive script still carries Content-Length when builder inserts CL — not proof of close-delimited response (HOLD until explicit no-CL/no-TE wire mode).
- Wrong-name leaf path authored (`serve_wrong_name_leaf`) but not first-vertical runnable proof.
- Microsoft OAuth tenant-prefix path completeness remains for expired/refresh HOLD cases.
- Actual receipt sanitizer end-to-end under live redact_mapping not exercised by report-boundary fake (explicitly disclosed `actual_sanitizer_verified=false`).

## Implementation HOLDs (prep-v4 first vertical)

First reviewable increment implements source for **NP-V-MS-NONEXPIRED** only (`np_runner_entry.IMPLEMENTED_CASE_IDS`). All other registry cases remain **explicit HOLD** (never fabricated PASS). Full 27+4 inventory + 76 planning IDs retained.

## Honest residual gaps in this increment

- Suite/runner/command/PKI/output/retirement **numeric bounds still unfrozen** — compute from actual ops before launch card.
- OUTER/VERIFICATION now carry **concrete pins** but `launch_authorized=false` / `launch_ready=false` remain.
- Token-terminal observer wraps `CoveringORMConnection.token_terminal`; live native confirmation still requires launch.
- AssessmentFactory setup path uses empty password_supplier (trust-auth fixture channel) — launch card must confirm reviewed fixture password channel.
- Generation of `/tmp/np-provider-tls` material not executed (recipe + caller contract only).
- Subsequent increments still required (expired refresh branches, remaining trust/framing/retirement, phase-specific deadline contracts).

## Assembly / launch holds

- 234-file assembly retained; sole override policy pin unchanged.
- Invocation and fault-retirement authority = later launch card only.
- Failed-container shutdown/removal separately gated.
- Unjoined/unconfirmed retirement → UNKNOWN.
- No failed-attempt reseed/retry.
- Endpoint unbound; no product binding.
- Fake Commands-Held not invoked.
- No Slack tip from this seat.
