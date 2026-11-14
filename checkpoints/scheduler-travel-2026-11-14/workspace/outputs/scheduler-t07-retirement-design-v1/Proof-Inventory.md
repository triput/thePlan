# Proof inventory — original vs candidate witnesses

Documents-only. No fixtures authored or executed under this assignment.
Distinguishes **fake acknowledgments** from **future real local TLS/socket
retirement evidence**.

## Evidence classes

| Class | Meaning | May close T07 alone? |
| --- | --- | --- |
| A. Control-flow / fake owned socket+response | Deterministic injection into extracted `CoveringHTTP` / `JoinedTLS` with registered globals | Necessary, not sufficient |
| B. Caller-level classification | Actual token/identity/event path through importer → transaction → connector → domain → HTTP dispatch | Required for UNKNOWN / no-later-admission |
| C. Fake DB rollback / recorder ack | `RootOutcome.ROLLBACK_ACKNOWLEDGED`, failure unit persist | Proves DB path only |
| D. Real isolated local TLS peer | Real `JoinedTLS`, joined workers, real sock close under synthetic peer | Required later for native retirement; not this handback |

Do not change transaction guards, retry policy, public contracts, deadlines,
or resource authority as fixture convenience.

---

## Original witnesses (current source; expect contract miss)

These are **designated original failing / masking witnesses** if later
authorized — not demonstrated runs.

| ID | Layer | Stimulus | Expected current observation (hypothesis) | Oracle miss |
| --- | --- | --- | --- | --- |
| O-R02 | A | Complete response; response.close raises | transport.close not called | Both-attempts |
| O-R06 | A | Both closes raise | Second never attempted | Both-attempts |
| O-R03-ev | A+B | Success body; transport.close raises on event apply path | Escaping cleanup → importer `OUTCOME_FAILED`; later target/assessment still eligible | UNKNOWN stop; no later admission |
| O-R04 | A | Body primary + response.close raise | Cleanup replaces primary | Primary preservation |
| O-UNK-pull | B | Raise `CoveringRootOutcomeUnknown` from pull (e.g. via HTTP oauth-style mapping on a path that reaches `_pull_provider`) | Importer returns `OUTCOME_FAILED` (`covering_refresh_import.py:976-994`) | UNKNOWN escape |
| O-ID-OS | B | Identity list; finally raises `OSError` | Prepare → `PREFLIGHT_EVIDENCE_UNAVAILABLE` | UNKNOWN stop |
| O-R08 | A | open primary + inner close raise | Primary replaced; outer close may skip raw sock | Primary+cleanup provenance; confirmed retirement false |
| O-R11 | B | invalid_grant then cleanup raise | Reauth replaced; not TokenRejected if raw cleanup escapes | Known reauth vs uncertain retirement distinction |

Fake DB ack must **not** be asserted as provider retirement in any O-* row.

---

## Candidate / corrected witnesses (after proposed unapplied change)

| ID | Layer | Stimulus | Candidate observation | Still requires |
| --- | --- | --- | --- | --- |
| C-R01 | A | Both closes succeed | Result returned; both attempts; confirmed retirement | Class A harness |
| C-R02 | A | response.close raises | transport.close still attempted; UNKNOWN if cleanup failed | Class A |
| C-R03-ev | A+B | transport.close raises after success | `CoveringRootOutcomeUnknown`; domain stops; no later admission | Class B caller harness |
| C-R04/R05 | A | Primary + cleanup fail | UNKNOWN with primary in `__context__`/`__cause__` chain; both attempts | Class A |
| C-R06 | A | Both closes raise | Both attempted; UNKNOWN | Class A |
| C-R07 | A | setblocking fail | Outer finally close attempted; classification recorded | Class A through CoveringHTTP |
| C-R08 | A | open primary + close fail | UNKNOWN; primary `__cause__`; cleanup `__context__`; outer close method may be idempotent | Class A; no sock retry |
| C-R09 | A | close fail then second close | Method idempotent; confirmed retirement remains false | Class A |
| C-R10 | B | OAuth sent + lost/malformed + cleanup fail | UNKNOWN; sent retained; no replay; no later admission | Class B token path |
| C-R11 | B | invalid_grant + cleanup fail | UNKNOWN (not TokenRejected success path); prior reauth visible in context | Class B |
| C-R12 | A+T08 | Foreign close | Refusal before mutation; owner retires separately | Ownership harness |

---

## Caller-level UNKNOWN / no-later-admission checklist (required)

For each of event, identity, and OAuth candidate rows that claim stop:

1. Public outcome is `CALENDAR_REFRESH_OUTCOME_UNKNOWN` (or raised
   `CoveringRootOutcomeUnknown` before HTTP mapping).
2. `completed_results` contains only prior finished targets.
3. No subsequent `CoveringRole.PARENT` / apply admission for later
   subscriptions in the same request.
4. No `CoveringRole.ASSESSMENT` admission after the uncertainty.
5. Failure-recorder / DB rollback acknowledgments recorded separately and
   **not** labeled as provider socket retirement.
6. Response-close attempt count, transport-close attempt count, raw
   `sock.close` attempt count, and confirmed-retirement boolean are
   distinct fields.

---

## Explicit non-substitutions

- Class C fake rollback ≠ Class D socket retirement.
- Byte-fake HTTP framing success ≠ T03 TLS.
- Method-call count ≠ raw-socket attempt count ≠ confirmed retirement.
- Unexecuted O-* / C-* rows ≠ demonstrated PASS/FAIL.
\n
