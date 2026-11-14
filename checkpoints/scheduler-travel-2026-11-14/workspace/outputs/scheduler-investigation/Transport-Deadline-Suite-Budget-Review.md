# Future transport launch budget must cover full real deadline cases

Dex, November 11, 2026. Offline source/requirements review only. No budget amendment, fixture implementation, shortened clock, concurrency change or execution is authorized. Jim continues the current T05 assignment without interruption.

Source: covering_request_budget.py in the accepted T07 fake-v2 API snapshot (SHA256D5C465CC8BACB83C49FCD8586BB84D5B32C12C113CB81386C6D715EBF7088975). Production constructs work deadline at start+210s, request deadline at start+240s and cumulative cleanup allowance30s. Native I01/I02's inherited600s runner/900s suite limits are historical limits for that reviewed run, not authority or a sufficient budget for the future full provider-transport suite.

## Concrete timing incompatibility

The accepted matrix contains distinct real handshake stall, header stall and body stall obligations. For fixtures intended to prove actual expiry at their respective phases using the unchanged request budget, three independent full-duration requests contain630s of configured work windows in aggregate, before collection, DB setup, fixture/worker retirement and teardown overhead. A serial600s runner would expire before those three requests could complete their intended proof. Additional send/cleanup/cancellation and other variants may extend the suite further.

This is a source-derived scheduling constraint, not a runtime measurement or a frozen count/duration for all cases. A case whose intended actual first stop is a parser cap, byte ceiling, disconnect or an injected fault can finish earlier; its receipt must identify that guard honestly and cannot be relabeled as deadline expiry. The three full-expiry windows above assume the fixture avoids earlier guards and observes the intended phase until the application budget expires.

## Later bounded proposal requirements

- Derive suite/runner/per-case/supervisor limits from the complete finite case inventory, actual production windows, allowed expected UNKNOWNs, native setup and bounded worker/resource retirement. Do not copy600/900s from the old native packet without this calculation.
- Keep deterministic fake-clock arithmetic tests separate from actual elapsed-time witnesses. A fixed remaining callback or an outer kill at a shortened deadline cannot establish production210/240/30 behavior.
- Serial case batches with adequate disclosed limits are the straightforward proposal. Any parallel case plan must separately justify isolation, owned peer/worker limits, deterministic phase evidence, per-request counters and joining; parallelism is not approved by this note.
- Preserve every accepted planning ID/variant. Batching is an execution organization choice, not permission to omit expensive stall cases. New requests for distinct reviewed cases are not retries, but any failed/mismatched/timed-out/unexpected UNKNOWN case still stops the authorized suite without repair or automatic retry.
- Explicitly distinguish command admission deadlines from after-fault CLI/worker/readers retirement and unbounded file/hash/OS latency. Trish must review exact amended limits with the final commands/hashes before execution.

No current decision card is ready: the actual full transport fixture/case inventory and parser correction evidence still need reconciliation. This note prevents an inherited supervisor timeout from becoming a false application-deadline PASS or an avoidable failed launch. Endpoint unbound; all other holds remain.