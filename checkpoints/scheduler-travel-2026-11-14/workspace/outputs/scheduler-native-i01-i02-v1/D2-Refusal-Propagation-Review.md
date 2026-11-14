# D2 path refusal — actual caller propagation boundary

Dex static review, November 11, 2026. No imports, application/check execution, live provider, sockets or database operations. Jim remains on the sole approved D2 source/fake-packet authoring assignment. This note adds no assignment or implementation authority.

The approved proposed helper is called in context after a unique route purpose is found, and in HTTP after route selection but before page/OAuth counter admission and transport creation/open/send. A fake check can establish that the refused target caused zero provider opens/sends. It cannot infer the final API outcome solely from that low-level exception.

## Inspected unchanged callers

Source root: `outputs/scheduler-t02-fake-v1/packet/payload/workspace/apps/api/app/services`.

| Source | SHA256 |
|---|---|
| covering_refresh_import.py | C57A5F956BEA5A364B781C586B595C984013F357F337355B30C4182230BFE1F0 |
| covering_role_connector.py | C5BA15CDE276586CFFA2DE24A51E79F40CC6479D3A5A1D6663D23A20D930B288 |
| covering_domain_dispatch.py | E73EFF6812A191F3F03431B98990BBF3C61D09D8398101AC804DBD2B2E7F6566 |
| covering_domain_adapters.py | BA82577E8CF4B27D4EDD5A1B9D31B35E87990A381B83E22D4DB2A4D89352A53C |
| covering_target_transaction.py | 8ADC67737002512BD66D87A6A874E6970250094BA1CF7FCE69E7A66B966A235A |

- **Token role:** token adapter catches CoveringReauthorizationRequired as a classified rejection. A different path-refusal exception escapes the body. The connector's `_session_scope` stops admission, attempts quarantine and raises CoveringRootOutcomeUnknown. Existing dispatch preserves UNKNOWN; zero send does not itself make an arbitrary token exception a typed preflight result. Preserve this conservative contract rather than silently adding a new public path code.
- **Identity preparation:** the explicit evidence-fetch catch covers httpx.TransportError, JSONDecodeError and OSError, not CoveringTransportRefused. An uncaught path refusal therefore propagates through the parent error/abort path rather than automatically becoming EVIDENCE_UNAVAILABLE. The parent connector stops admission and preserves/raises UNKNOWN on unclassified failures. Actual cleanup/terminal evidence remains required in a later integrated proof.
- **Event enumeration:** `_pull_provider` is inside a broad Exception catch at lines 968–992. A path refusal there returns OUTCOME_FAILED with rollback_required and needs_failure_unit. That result becomes a known public failure only through the acknowledged parent rollback/lock-exit/retirement and failure-recorder protocol. The exception alone does not prove those transitions or safe later-target admission.

## Attempt metadata versus observed effects

The event exception result sets `provider_event_read_attempted=True`, even if the provider path was refused before an open/send. That field records the attempted import/provider-read branch; it is not wire-effect evidence. A later fixture must keep it separate from observed transport open/send counts, sent-state, counters, terminal acknowledgments and next-target admission. Do not relabel that API metadata as a proven exchange or change it merely to match a low-level test.

## Use in later evidence review

The current fake-only D2 packet may prove extraction/caller wiring, admission and wire-target behavior with its stated fakes. It cannot prove native rollback acknowledgment or an integrated sanitized 503 without the separately authorized real caller/transaction composition evidence. Later transport fixtures must inject refusal separately in token, identity and event phases, observe actual public result/classification and all resource retirement, and retain the correct ordered target results. UNKNOWN prevents continuation. Do not weaken conservative uncertainty to make a path-refusal case appear uniformly known.

This extends the earlier Transport-Outcome-Trace.md to the new pre-send helper and preserves the full T01–T08 goal. Endpoint/profile remains unbound. No code change is proposed here.
