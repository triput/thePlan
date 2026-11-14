# T07-R01–R12 reconciliation v2

Supersedes v1 tip `ABA0923505155EC0D7555B13A61CB6F7CFFE662051F0E2B5C439BEAC48800F2A`. Offline hypotheses only — not executed failures.

Pins MATCH assignment for the five required covering sources.

Provenance inventory (candidate): on `CoveringRootOutcomeUnknown` instances
raised from retirement paths, witnesses read:

- `.primary`
- `.response_close`
- `.transport_close`
- `.retirement_provenance` == `(primary, response_close, transport_close)`

Do **not** use `__context__` as the oracle for caught cleanup exceptions.

## T07-R01 — Complete event; both closes succeed

Observation: happy path open/send/body/return; finally both closes OK.
Oracle: valid result; both method attempts; raw sock once; confirmed
retirement true; no UNKNOWN.
Primary/cleanup: primary=success; both cleanup None.
Status: candidate control. Not executed.

## T07-R02 — Complete response; response.close throws

Current: transport.close skipped after response.close raise
(`covering_http_transport.py:126-128`).
Candidate: both attempts; `.response_close` set; `.transport_close` may be
None if transport succeeds; UNKNOWN with `.primary` None (cancelled
success).
Oracle: both-attempts pass; provenance shows response_close identity/type.
Status: original fail / candidate corrected design. Not executed.

## T07-R03 — Complete response; transport.close throws

Current: escaping cleanup; event importer may map to OUTCOME_FAILED.
Candidate: UNKNOWN; `.transport_close` set; `.primary` None; importer
re-raises; no later admission.
Status: hypothesis. Not executed.

## T07-R04 — Parser/body primary; response.close throws

Current: cleanup replaces primary; transport.close skipped; no separate
retained cleanup object after bare except.
Candidate: dual attempt; UNKNOWN with `.primary` = body/parser exception
and `.response_close` = close exception (explicit attrs); `.transport_close`
may be set if second attempt also fails, else None or success None.
Witnesses must observe primary AND response_close independently.
Status: original masking / candidate provenance. Not executed.

## T07-R05 — Parser/body primary; transport.close throws

Current: transport.close replaces primary.
Candidate: UNKNOWN with `.primary` and `.transport_close` both set;
`.response_close` None if response close succeeded.
Witnesses assert both primary and transport_close.
Status: candidate provenance. Not executed.

## T07-R06 — Both closes configured to throw

Current: first throw skips second; second configured throw never evidence.
Candidate: both attempted; UNKNOWN with **both** `.response_close` and
`.transport_close` non-None and distinct objects; witnesses assert each
independently (type/identity/sanitized message class). `.primary` is prior
exchange primary or None on success-cancel path.
Status: current fails both-attempts+dual-cleanup; candidate closes.
Not executed.

## T07-R07 — setblocking throws after allocation

Current: bypasses open local close; CoveringHTTP finally still
transport.close.
Candidate: outer close classification + provenance if outer close raises;
if outer close succeeds, confirmed retirement may be true.
Status: static reachability. Not executed.

## T07-R08 — Connect/TLS primary + inner sock.close throws

Current: open except close replaces primary; outer finally transport.close
is no-op after closed=True; raw OSError may reach callers.
**HTTP-only insufficient** (Design-Recommendation.md).
Candidate JoinedTLS.open: raise UNKNOWN with `.primary` = open primary,
`.response_close` None, `.transport_close` = sock/close failure; no retry.
Outer finally no-op does not erase that UNKNOWN.
Importer re-raise stops later admission.
Status: requires JoinedTLS.open change. Not executed.

## T07-R09 — First sock.close throws; later same-owner close

Oracle: method idempotence vs confirmed retirement false; no automatic
retry. Unchanged close flag contract.
Status: contract witness. Not executed.

## T07-R10 — OAuth sent + lost/malformed + cleanup failure

Candidate: UNKNOWN (oauth mapping and/or cleanup enrichment); provenance
attrs carry cleanup; sent retained; no replay; no later admission.
If oauth already raised UNKNOWN, finally enriches same instance with
cleanup attrs rather than nesting.
Status: caller-level. Not executed.

## T07-R11 — invalid_grant + cleanup failure

Candidate: cleanup forces UNKNOWN with `.primary` capturing prior
CoveringReauthorizationRequired when still active via sys.exc_info, plus
cleanup attrs; not TokenRejected success path.
Status: decision item retained. Not executed.

## T07-R12 — Foreign-thread retirement

Unchanged: refuse before mutation; owner path separate.
Status: overlaps T08. Not executed.

## Cross-cutting

Event pull swallow and identity OSError preflight remain current-source
hazards addressed by UNKNOWN raise + deferred re-raise (and by not letting
raw cleanup OSError escape on classified paths).
