# Proof inventory v2 — original vs candidate witnesses

Supersedes v1 tip `ABA0923505155EC0D7555B13A61CB6F7CFFE662051F0E2B5C439BEAC48800F2A`. No fixtures executed.

## Provenance observation contract (candidate)

For every UNKNOWN raised from CoveringHTTP.finally cleanup or
JoinedTLS.open close failure, witnesses record sanitizable fields:

1. `type(exc.primary).__name__` if primary is not None else None
2. `type(exc.response_close).__name__` if response_close is not None
3. `type(exc.transport_close).__name__` if transport_close is not None
4. object identity inequality where both cleanups present (R06)
5. `exc.retirement_provenance` tuple length 3 matching the three attrs

Forbidden oracle: "exception `__context__` after caught cleanup" — caught
exceptions are stored in locals/attrs explicitly because except exit
clears the active exception before the UNKNOWN raise.

Logs/receipts may keep only type names and fixed labels — never credentials,
URLs, or raw provider bodies.

## Evidence classes

| Class | Meaning |
| --- | --- |
| A | Fake owned socket/response control-flow |
| B | Caller-level token/identity/event classification |
| C | Fake DB rollback ack (not provider retirement) |
| D | Future real local TLS/socket evidence |

## Original witnesses (current source)

| ID | Notes |
| --- | --- |
| O-R02 | transport.close skipped |
| O-R06 | second close not attempted; no dual cleanup objects |
| O-R03-ev | cleanup -> OUTCOME_FAILED + later admission |
| O-R04 / O-R05 | primary replaced; cleanup not separately retained |
| O-R08 | open cleanup replaces primary; outer close no-op; raw OSError risk |
| O-UNK-pull | importer swallows CoveringRootOutcomeUnknown |
| O-ID-OS | prepare maps OSError to preflight |
| O-R11 | cleanup may replace reauth without provenance attrs |

## Candidate witnesses (after unapplied v2 diff)

| ID | Required provenance assertions |
| --- | --- |
| C-R02 | response_close set; transport attempted |
| C-R03-ev | transport_close set; UNKNOWN; no later admission |
| C-R04 | primary and response_close both set and observable |
| C-R05 | primary and transport_close both set |
| C-R06 | response_close AND transport_close both set, distinct |
| C-R08 | JoinedTLS UNKNOWN: primary + transport_close; response_close None; HTTP-only insufficient |
| C-R10/R11 | cleanup attrs present; caller UNKNOWN stop |
| C-R01/R07/R09/R12 | as v1 oracles with provenance None where success |

## Caller-level UNKNOWN / no-later-admission checklist

Unchanged from intent of v1: public UNKNOWN; completed_results only prior
rows; no later PARENT/apply; no ASSESSMENT after uncertainty; DB ack !=
socket retirement; separate counts for response-close, transport-close,
raw sock.close, confirmed retirement.
