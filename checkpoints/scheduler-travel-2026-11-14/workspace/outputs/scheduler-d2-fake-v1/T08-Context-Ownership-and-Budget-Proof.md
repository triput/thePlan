# T08 context, ownership and budget proof design

Dex, November 11, 2026. Static source/hash review only. No application/check imports, compilation, tests, threads, sockets or Docker were executed. This is preparation for the remaining transport proof; it neither changes sources nor authorizes fixture implementation. Jim retains the sole T07 documents-only assignment. The pending D2 verification packet and card are unchanged.

## Inspected current source

The API root is the immutable packet/payload/workspace/apps/api beside this note. Hashes are current read-only observations:

| app/services source | SHA256 |
| --- | --- |
| covering_provider_context.py | 875FBF61A386D661A4DD70609162E41540500F10AD6AEDCACAF790701D693240 |
| covering_transport_policy.py | A265F81F72E719B23FE3DE9BF332E2DE01D8E90073F3AC04675EC6A4B2203598 |
| covering_joined_https.py | C58382900BE1C190ED39242B4992FE88E1155E55F7E8C33D32065DBFCC993468 |
| covering_release_plan.py | 0265969CD230D42747CDB722D73FF2C8748144324B5B930E5EB940E97DC2B826 |
| covering_domain_adapters.py | BA82577E8CF4B27D4EDD5A1B9D31B35E87990A381B83E22D4DB2A4D89352A53C |
| covering_http_dispatch.py | 5160780F4F13E450F19515560CF85EDCDCB5A7906FED99A7027AE8C93071D1FF |
| covering_request_budget.py | D5C465CC8BACB83C49FCD8586BB84D5B32C12C113CB81386C6D715EBF7088975 |

## Actual production composition

dispatch_covering_http enters a shielded AnyIO scope and calls run_sync with abandon_on_cancel=False. The production CoveringReleasePlan is converted to a request binding inside that worker. for_request constructs a fresh counter and CoveringHTTP bound to budget.work_remaining. Domain token and apply adapters enter covering_provider_transport around synchronous provider calls. The ContextVar token is reset in finally. JoinedTLS captures the thread identity at construction; check refuses a foreign owner or closed transport. It refuses open reuse when sock is already assigned and rejects foreign-thread close before mutation.

These are distinct boundaries. The request-level CoveringHTTP/counter is not the same object as each per-exchange JoinedTLS. A provider callback receives a covering client only while the ContextVar is installed; outside that scope calendar_client intentionally constructs an ordinary httpx.Client. A test must observe which factory is selected, without actually opening an ordinary connection. Do not infer ordinary-client fallback during production covering work merely from that intentional outside-context branch.

The frozen transport-policy tests exercise counters/origin/limits, not the complete context/ownership lifecycle. A limited search of the transport-policy, refresh-d2 and production-boundary test files found no direct nested-provider-context or foreign-thread/reuse controls. That search is not a claim about every historical fixture. The D2 fake packet covers route/context admission and is not a substitute for T08 lifecycle proof.

## Required witnesses through real extracted definitions

These candidate IDs expand, rather than cap, the accepted T08 family. Later preparation must reconcile them against the accepted addendum's actual IDs and preserve both inventories. Fake controls and eventual joined-thread/native controls must be labeled separately.

| Candidate | Stimulus and required observation |
| --- | --- |
| CTX-ENTRY | Within the real covering_provider_transport manager, call real calendar_client and a provider helper. Observe _CoveringClient, exact reviewed transport identity, zero ordinary-client factory calls and the expected one exchange. |
| CTX-NESTED | Attempt a nested non-null covering context. Observe refusal before nested transport use and preservation of the original outer transport. The outer scope must still reset normally. |
| CTX-EXCEPTION | Raise a controlled primary failure inside the covering scope. Observe original exception provenance and reset to the prior ContextVar state in finally, including after transport refusal. |
| CTX-SEQUENTIAL | Two sequential request scopes on the same owner use distinct counters/transports. Assert no routes, limits, count or context leak from the first to the second. |
| CTX-ORDINARY-AFTER | After a covering scope closes, use a fake ordinary-client factory sentinel to prove reset. No socket/client network behavior is permitted in this control. |
| CTX-PRODUCTION-WORKER | Observe that actual production plan construction, provider context installation and synchronous provider use occur on the joined request worker. Record actual thread IDs and entry/exit order; injected identical IDs are not real ownership evidence. |
| OWNER-CHECK | Construct real JoinedTLS on owner A, then invoke check/send/receive on foreign owner B using a separately reviewed joined-thread fixture. Refusal must precede socket operations; owner A remains responsible for any admitted retirement. |
| OWNER-CLOSE | Foreign close refuses before setting closed or closing the raw socket. Observe same-owner retirement separately. Do not grant a cross-thread fallback to make teardown pass. |
| OWNER-REUSE | After an opened transport, repeated open refuses before a new dial; after close, check refuses. Count new allocations and actual raw-close attempts independently of method calls. |
| OWNER-CLOSE-FAIL | First same-owner raw close throws. A later same-owner close call must be described truthfully: the current closed flag suppresses another raw close. This is shared with T07; do not label idempotence as proven retirement or add retries. |
| CTX-ESCAPE-CHARACTERIZE | Characterize an escaped cached _CoveringClient or an explicitly copied context separately from the actual synchronous provider path. The current wrapper has no independent thread/lifetime guard. Establish reachability and the intended contract before proposing any new restriction; do not claim a production escape or silently widen a repair. |

## Deadline and disconnect cross-checks

The current budget is 240 seconds total, 210 seconds work and 30 seconds cumulative cleanup. work_remaining checks cancellation, stopped state and cleanup scope before returning time. ProviderCounter receives this callback; JoinedTLS checks it during connect, readiness, handshake, send and receive, including after readiness/receive. Thus later deadline controls must exercise the live callback rather than freeze a timeout once at construction.

Required original/candidate observations include: deadline before allocation, during selector readiness, after readiness but before operation, during partial send, after receive before body exposure, and disconnect before a later exchange. Count selector/socket operations after the refusal boundary. Positive read/write readiness and partial-send progression must also be retained. A fake callback sequence proves control flow only; elapsed bounds and joined real peer/worker retirement require the separately authorized real synthetic transport layer.

Provider close is local and does not invoke TLS unwrap or a second exchange. It has no explicit budget callback of its own. A proof of prompt local retirement must therefore come from the owned operation/worker evidence, not from calling work_remaining after a close and treating that as proof of close's duration. T07's failure provenance and both-attempt requirements still apply.

The existing production-boundary test file contains cumulative-cleanup and disconnect-retirement tests, but their existence is not a current run receipt. Preserve already verified native I01/I02 v4 disconnect/join evidence at its actual synthetic-provider scope; it does not prove real provider TLS deadline/retirement behavior.

## Later gates and completion

No new product decision is requested from these static observations. The escaped-client characterization is an explicit question for proof/reachability, not an established defect. Any source change, executable witness authoring or real-thread/socket topology must return through its existing approval gate with exact hashes and limits. No extra assignment is given to Jim here. Full T01–T08, actual caller outcomes, cleanup and independent reconciliation remain required before goal completion.
