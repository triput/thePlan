# T07-R01–R12 reconciliation (current-source hypotheses)

Offline reconciliation against re-pinned D2 API sources. Prior T07 note
hypotheses retained; historical assignment statements superseded by
`Next-Transport-Design-Assignment.md`. **No branch is a demonstrated
runtime failure** — unexecuted witnesses remain design candidates.

Pins: `covering_http_transport.py`
`AECE10186CFFAE46D3EF2292D3772F1C287FD0A562AA9E764AAC4ABB10C861D8`;
`covering_joined_https.py`
`C58382900BE1C190ED39242B4992FE88E1155E55F7E8C33D32065DBFCC993468`;
importer/transaction/connector pins MATCH assignment.

Legend for close columns:

- **R-close / T-close:** `HTTPResponse.close` / `JoinedTLS.close` method
  calls on the CoveringHTTP ownership path.
- **Raw sock:** actual `sock.close()` attempt inside `JoinedTLS.close`
  when `closed` was previously false.
- **Confirmed retirement:** acknowledged successful provider resource
  retirement (not DB rollback; not `closed=True` alone).

---

## T07-R01 — Complete event response; both closes succeed

| Field | Content |
| --- | --- |
| Current-source observation to test | Happy path through open/send/begin/body/return then finally both closes (`covering_http_transport.py:88-128`). |
| Acceptance oracle | One response-close attempt, one transport-close attempt, valid returned `httpx.Response`, raw sock close attempted once, confirmed retirement true, caller returns success object (not UNKNOWN). |
| Primary / cleanup provenance | Primary = success return; cleanup = none. |
| Close-method vs raw-socket | R-close yes; T-close yes; raw sock once if first close. |
| Confirmed retirement | Required true for PASS. |
| Status | Candidate control. Not executed. |

## T07-R02 — Complete response; response.close throws

| Field | Content |
| --- | --- |
| Current-source observation to test | `finally`: `response.close()` then `transport.close()`; exception in first skips second (`covering_http_transport.py:126-128`). |
| Acceptance oracle (contract) | Both retirement attempts required where a response exists; fail both-attempts oracle on current sequencing. |
| Primary / cleanup provenance | Pending success cancelled by response-close exception; transport-close not attempted. |
| Close-method vs raw-socket | R-close attempted (raises); T-close **not** called; raw sock not reached via outer finally. |
| Confirmed retirement | Uncertain / false. |
| Status | Original failing **design** witness if later authorized. Not executed. |

## T07-R03 — Complete response; transport.close throws

| Field | Content |
| --- | --- |
| Current-source observation to test | Response close succeeds; `transport.close()` raises; pending return cancelled (`covering_http_transport.py:126-128`). |
| Acceptance oracle | No successful returned body exposure; retirement uncertain; **actual caller** classification recorded (event importer today maps escaped Exception → `OUTCOME_FAILED`, not UNKNOWN — `covering_refresh_import.py:976-994`). |
| Primary / cleanup provenance | Primary was success; cleanup exception becomes escaping exception unless reclassified in finally. |
| Close-method vs raw-socket | Both method attempts; raw sock attempted; sock failure possible. |
| Confirmed retirement | False / uncertain. |
| Status | Hypothesis: current caller yields ordinary failed import + later admission. Not executed. |

## T07-R04 — Parser/body primary failure; response.close throws

| Field | Content |
| --- | --- |
| Current-source observation to test | Failure inside try (read/json/classify); finally response.close raises and replaces primary (`covering_http_transport.py:97-128`). |
| Acceptance oracle | Original primary and cleanup cause separately observable; must not report cleanup as sole primary. |
| Primary / cleanup provenance | Current: cleanup replaces primary (no preservation in finally). |
| Close-method vs raw-socket | R-close raises; T-close skipped. |
| Confirmed retirement | Uncertain. |
| Status | Original masking witness candidate. Not executed. |

## T07-R05 — Parser/body primary failure; transport.close throws

| Field | Content |
| --- | --- |
| Current-source observation to test | Response close OK; transport.close raises replacing primary. |
| Acceptance oracle | Both attempts as applicable; observe masking vs preserved primary + unknown retirement. |
| Primary / cleanup provenance | Current: cleanup replaces primary. |
| Close-method vs raw-socket | Both methods; raw sock on transport.close. |
| Confirmed retirement | Uncertain. |
| Status | Candidate. Not executed. |

## T07-R06 — Both close operations configured to throw

| Field | Content |
| --- | --- |
| Current-source observation to test | Same sequencing: first throw skips second (`covering_http_transport.py:126-128`). |
| Acceptance oracle | Observe whether both are attempted; do not count uncalled configured throw as evidence. |
| Primary / cleanup provenance | First cleanup exception wins; second never runs. |
| Close-method vs raw-socket | R-close only on current source. |
| Confirmed retirement | Uncertain. |
| Status | Current source fails both-attempts oracle by construction. Not executed. |

## T07-R07 — Raw socket setblocking throws after allocation

| Field | Content |
| --- | --- |
| Current-source observation to test | `JoinedTLS.open` assigns sock and `setblocking(False)` **before** its try (`covering_joined_https.py:44-46`); setblocking failure bypasses local close handler. `CoveringHTTP` constructs transport before try, calls `open()` inside try (`covering_http_transport.py:86-89`); `response is None` → finally still `transport.close()` (`covering_http_transport.py:126-128`). |
| Acceptance oracle | Outer same-owner transport retirement reached; count raw socket attempt and outcome; caller classification. |
| Primary / cleanup provenance | Primary = setblocking error; cleanup = outer close. |
| Close-method vs raw-socket | One outer T-close; raw sock once if close entered. |
| Confirmed retirement | Depends on close result. |
| Status | Static reachability reconciled with matrix; not a demonstrated leak. Not executed. |

## T07-R08 — Connect/TLS primary failure and inner socket.close throws

| Field | Content |
| --- | --- |
| Current-source observation to test | `open` except calls `self.close()`; close exception replaces primary (`covering_joined_https.py:72-74`). Outer finally calls `transport.close()` again; `closed=True` skips raw sock (`covering_joined_https.py:107-111`). |
| Acceptance oracle | Retain primary and retirement failure independently; record outer close call vs suppressed raw close. |
| Primary / cleanup provenance | Current: inner cleanup can replace primary; outer close may be silent method success without raw retry. |
| Close-method vs raw-socket | Two T-close **method** calls possible; at most one raw sock attempt. |
| Confirmed retirement | Uncertain if first sock.close failed after flag set. |
| Status | Hypothesis only. Not executed. |

## T07-R09 — First socket.close throws; later same-owner close

| Field | Content |
| --- | --- |
| Current-source observation to test | Idempotent method after `closed=True`; no second `sock.close()` (`covering_joined_https.py:107-111`). |
| Acceptance oracle | Distinguish method idempotence from successful retirement; **no** automatic retry/repair contract. |
| Primary / cleanup provenance | First close’s sock failure is the retirement failure evidence. |
| Close-method vs raw-socket | Later close = method only. |
| Confirmed retirement | Must remain false after failed sock.close. |
| Status | Contract witness; do not “fix” with retries. Not executed. |

## T07-R10 — OAuth send attempted, lost/malformed response + cleanup failure

| Field | Content |
| --- | --- |
| Current-source observation to test | `transport.sent` true → except maps to `CoveringRootOutcomeUnknown` (`covering_http_transport.py:120-123`); finally cleanup may replace that UNKNOWN with raw close exception (`:125-128`). Token adapter does not catch UNKNOWN; connector may rewrap raw exceptions as UNKNOWN (`covering_role_connector.py:142-150`). |
| Acceptance oracle | Exercise actual OAuth caller; retain sent state, no replay, final UNKNOWN, uncertain retirement; DB rollback ≠ provider retirement. |
| Primary / cleanup provenance | Need both sent/UNKNOWN intent and cleanup failure observable. |
| Close-method vs raw-socket | Per finally sequencing (incl. R02 skip risk). |
| Confirmed retirement | Uncertain. |
| Status | Caller-level witness required; fake DB ack insufficient. Not executed. |

## T07-R11 — Complete OAuth invalid_grant + cleanup failure

| Field | Content |
| --- | --- |
| Current-source observation to test | Try raises `CoveringReauthorizationRequired` (`covering_http_transport.py:107-110`); finally cleanup can replace it. Adapter maps only surviving `CoveringReauthorizationRequired` to `TokenRejected` (`covering_domain_adapters.py:50-52`). |
| Acceptance oracle | Distinguish known complete remote invalid_grant from uncertain resource retirement; do not claim ordinary reauthorization/preflight success if cleanup unknown; record actual public mapping. |
| Primary / cleanup provenance | Known reauth vs cleanup uncertainty must both be observable. |
| Close-method vs raw-socket | As finally. |
| Confirmed retirement | Uncertain on cleanup failure. |
| Status | Hypothesis: cleanup failure → not TokenRejected; often connector UNKNOWN. Not executed. |

## T07-R12 — Foreign-thread retirement attempt

| Field | Content |
| --- | --- |
| Current-source observation to test | `JoinedTLS.close` refuses when `get_ident()!=owner` before state change (`covering_joined_https.py:105-106`). |
| Acceptance oracle | Refusal before socket mutation; owning thread’s separately admitted retirement; workers joined; no cross-thread fallback. |
| Primary / cleanup provenance | Foreign attempt is refusal, not cleanup of owner’s primary. |
| Close-method vs raw-socket | Foreign: method raises, no sock mutation. |
| Confirmed retirement | Owner path only. |
| Status | Overlaps T08 ownership; still required T07 observation. Not executed. |

---

## Cross-cutting caller note (all branches that escape CoveringHTTP)

Event pull: `except Exception` → `OUTCOME_FAILED` (`covering_refresh_import.py:976-994`) can convert transport UNKNOWN into ordinary failed import with later admission.

Identity prepare: `OSError` → `PREFLIGHT_EVIDENCE_UNAVAILABLE` (`covering_refresh_import.py:442-458`) can convert cleanup `OSError` into ordinary preflight.

Token role: raw cleanup often becomes connector UNKNOWN (stop), but loses typed primary unless finally classifies with provenance.

A low-level both-close-attempts check alone cannot close T07 without these caller oracles.
\n
