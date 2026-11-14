# T07 v6 prelaunch findings: result serialization and normal cleanup oracle

Dex, November 11, 2026. Additional read-only inspection after provisional static acceptance and staging; no checker, serializer, compilation or wrapper execution. The earlier v6 ACCEPT disposition is superseded by these findings. Preserve v6 and the staged host packet unchanged. Launch remains held.

## B1 — success evidence contains non-JSON fake result objects

In check_t07_retirement_fake.py, drive_bounded_domain_no_later returns prior_completed as a list of the actual completed result objects. _success_result creates types.SimpleNamespace objects. C-CALLER-EVENT, C-CALLER-OAUTH and C-NO-LATER-ADMISSION record the returned info as evidence. record stores it unchanged; compare_to_expected returns that same evidence under controls. main passes the payload to json.dumps without a default encoder or projection.

Therefore the successful caller path places SimpleNamespace objects into the JSON payload. The standard JSON encoder does not encode those objects by default. This source path would prevent successful result emission even if all controls pass. This is static reasoning, not a retained failed run.

Narrow correction: in a fresh checker successor, project completed result evidence into an explicit allowlist of JSON primitives (for example subscription_id, status, phase, outcome and the fixture-boundary label), retaining the original objects for any identity/behavior assertions that need them. Assert that the prior successful target is SUB-1 with its expected status rather than relying only on a nonzero count. Do not use default=str, repr, arbitrary __dict__ or a broad object dump; do not silently omit the evidence or weaken the result-retention oracle.

## B2 — C-R01 does not enforce normal close observations

C-R01 currently contains `if probe.method_close_calls != 1 and probe.constructs == 0 and False: pass`. This condition can never enforce anything, and even its body cannot fail. The control calls request and records PASS without asserting successful normal cleanup counts, despite its expected criterion requiring both closes.

Narrow correction: instrument the fake response close as well as the fake transport close and assert exactly one of each on the complete positive path. Return/result content should also be checked. Preserve the candidate methods, positive response shape, source bytes and accepted cleanup contract. No extra raw-close retry or production repair is authorized.

## Procedure

Jim's host review can reconcile these findings, then continue the fresh-copy verifier-authoring correction under the existing approval. No stopped run exists and no new production scope is added. Return frozen checker/metadata/command hashes for renewed static review. Do not execute a serialization probe or any verification while authoring. The next host packet must use a fresh directory or explicitly preserved successor; do not overwrite this frozen packet/admission. No execution card is ready.
