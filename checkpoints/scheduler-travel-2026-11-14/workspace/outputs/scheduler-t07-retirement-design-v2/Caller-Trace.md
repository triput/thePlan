# Caller trace v2 — event, identity, OAuth

Supersedes v1 tip `ABA0923505155EC0D7555B13A61CB6F7CFFE662051F0E2B5C439BEAC48800F2A`. Sources re-pinned; not executed.

## Shared spine

Unchanged from v1: domain adapters bind `covering_provider_transport` ->
`calendar_client` -> `CoveringHTTP.request` -> `JoinedTLS`.

### Cleanup replacement sites (current)

- CoveringHTTP.finally response then transport; first raise skips second
  (`covering_http_transport.py:125-128`).
- JoinedTLS.open except close can replace primary
  (`covering_joined_https.py:72-74`); closed=True before sock.close
  (`:107-111`) makes later outer close a no-op.

### Candidate classification (unapplied)

- CoveringHTTP.finally attempts both closes; stores
  `response_close_exc` / `transport_close_exc`; raises/enriches UNKNOWN with
  explicit `.primary` / `.response_close` / `.transport_close` /
  `.retirement_provenance`.
- JoinedTLS.open on close failure raises UNKNOWN with open `.primary` and
  `.transport_close` (required for R08; HTTP-only insufficient).
- Importer pull `except Exception` re-raises CoveringRootOutcomeUnknown via
  deferred import (`covering_refresh_import.py` proposed).

DB rollback acknowledgment remains distinct from provider retirement.

## OAuth / token

Chain unchanged. Candidate: cleanup after invalid_grant or lost response
yields UNKNOWN with provenance attrs; TokenRejected only when
CoveringReauthorizationRequired survives without cleanup uncertainty.
Public mapping still `CALENDAR_REFRESH_OUTCOME_UNKNOWN` via
`covering_http_dispatch.py:71-73`.

## Identity

Current hazard: prepare maps OSError to PREFLIGHT_EVIDENCE_UNAVAILABLE
(`covering_refresh_import.py:442-458`), including finally-replaced cleanup
OSError. Candidate classified UNKNOWN (from HTTP or JoinedTLS) is not an
OSError and is not mapped to that preflight; it stops later admission.

## Event

Current hazard: `_pull_provider` except Exception -> OUTCOME_FAILED
(`covering_refresh_import.py:976-994`) swallows UNKNOWN and allows later
targets/assessment (`covering_domain_dispatch.py:233-257`). Candidate
deferred re-raise restores stop semantics.

## R08 caller note

If only HTTP finally were changed, R08 still emits raw cleanup from open
(today) or would need open to swallow close failures silently — either way
outer finally cannot resurrect a sock.close failure after closed=True.
Therefore event/identity truthful UNKNOWN on R08 depends on the JoinedTLS.open
change plus importer re-raise.
