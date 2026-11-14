# T03/T04 shared deadline and stall proof

Dex, November 11, 2026. Offline source/design review only; no fixture/check implementation, imports, compilation, sockets or execution. Jim's one active assignment remains T07. This note refines the accepted transport matrix without closing any family or adding execution authority.

## Inspected provenance and contract

- covering_request_budget.py from scheduler-d2-fake-v2/payload: D5C465CC8BACB83C49FCD8586BB84D5B32C12C113CB81386C6D715EBF7088975.
- covering_transport_policy.py from the same payload: A265F81F72E719B23FE3DE9BF332E2DE01D8E90073F3AC04675EC6A4B2203598.
- covering_joined_https.py from frozen T07 source/fake v4: 2E6A4ABB0E9658747C07A06F17D4359987C926DDD3CFDC0FE098984922A6A29B.

The actual request budget fixes its work deadline at start+210 seconds and request deadline at start+240, reserving 30 cumulative cleanup seconds. Each cleanup scope uses the lesser of the request deadline and its start plus remaining cleanup; elapsed time is deducted when the scope exits. An escaping cleanup exception latches stop. These are source-observed rules, not measured timing results.

JoinedTLS.ready polls for at most min(remaining,0.05) per selector call and rechecks the live remainder after readiness. Its send loop marks sent before calling the socket and retries only readiness/would-block conditions within that invocation. Receive checks before and after socket recv. HTTP header parsing reads through the same bounded reader/counter, so header waits must be tested as well as body waits. Repeated readiness or partial progress must not create a new request budget.

## Required distinct witnesses

| Phase | Positive/control | Stall or interruption | Required observations |
| --- | --- | --- | --- |
| Numeric connect | Writable connection and successful SO_ERROR | No readiness; readiness with connect error; expiry before connect | Exact admitted numeric peer, no DNS/fallback, no send before connection; shared deadline and terminal cleanup. |
| TLS handshake | Valid CA and hostname | WantRead/WantWrite alternating without completion; wrong CA/hostname | Verification outcome separate from deadline; readiness loop consumes original remainder, peer/worker joined. |
| Request send | Full send and bounded partial progress | Partial bytes accepted then stall; would-block/read-required; disconnect | sent set before first call, retained partial-send count, no replay or second exchange, purpose-specific uncertainty. |
| Headers | Complete final headers, including bounded informational responses | No first byte; partial status/header; endless bounded progress until deadline | Actual parser path, cumulative bytes including headers, no reset after each read or 1xx response, no body exposure. |
| Body | Complete valid framed object | Partial body then stall; peer dribbles data while time expires | Original request deadline, byte ceiling and framing completeness independently enforced; no valid-prefix success. |
| Cleanup | Multiple known serialized scopes | Later scope consumes remaining allowance; expiry; cleanup throws | 30 seconds cumulative, never beyond request deadline; no fresh 30 seconds per scope, no ordinary readmission after stop. |
| Cancellation | Completed operation before cancellation | Disconnect before send, after partial send and during wait | Actual request cancellation observed by owned worker, no detached continuation or later provider/target admission; classify at the actual phase. |

Use deterministic fake-clock controls on the actual extracted budget for arithmetic/boundaries, including exact deadline equality, cleanup after work expiry, cumulative two-scope charging and an exception escaping cleanup. A fixed fake budget returning 30 for every call cannot establish these rules. No clock control is a real elapsed-time proof.

Separately authorize bounded local synthetic TLS/socket witnesses using the actual budget/transport methods and pinned runtime. Retain start/deadline/phase timestamps, actual wait transitions, admitted exchange counts, sent state, peer observations and worker/resource retirement. Record nominal application deadline separately from fixture supervisor limits and process/OS retirement latency. Outer timeout is a safety bound, not evidence that the application honored its own deadline. Do not terminate a test early and call a still-live worker joined.

## Classification and authority boundaries

Event/identity failure classification still depends on actual caller transaction and retirement evidence; OAuth after possible send must retain uncertainty rather than replay. A provider stall and uncertain local retirement are separate causes. The T07 correction is a prerequisite for preserving cleanup uncertainty, not proof of timing. Existing native lost-DB-ack evidence concerns a different transport path.

No shortened production budget, accelerated native clock, socket topology, supervisor termination or additional cleanup is approved by this document. Freeze exact durations, cases, pins and owned-resource retirement scope in the later packet, with Trish's launch approval. Preserve all accepted 76 planning IDs and framing/ownership variants; this table does not replace them.
