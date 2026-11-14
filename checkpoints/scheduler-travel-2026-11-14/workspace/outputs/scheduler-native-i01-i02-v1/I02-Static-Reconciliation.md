# I02 current-source reconciliation

Disposition: no additional blocker found in the reviewed contention/assessment oracle. This is static review, not runtime acceptance. The C06 correction remains Jim's one active assignment. No source edits, imports, tests, database calls, sockets or Docker checks were performed.

Reviewed the current blocked native draft's i02_owner_lock_contention.py and the i02_c01 wrapper in i01_i02_suite.py. These are the source identities in I02-Static-Reconciliation-Pins.json; any future copied payload must reconcile them before carrying this finding forward.

Observed chain:

1. Seed revision1 and active=success generation1. Mutator obtains the production owner scheduling lock. The observer must find exactly one granted holder row for the exact database OID, namespace1886415951, owner key, objsubid2 and holder PID before starting assessment.
2. Assessment records its own backend PID before entering the production _assemble_final_assessment path. Observer then requires a granted holder and ungranted waiter on the same exact advisory-lock identity, distinct PIDs, and holder membership in pg_blocking_pids(waiter). An elapsed wait or thread Event alone cannot produce this observation.
3. Only after that observation does the owner set admit_mutation. Failure teardown sets retire_mutator without granting mutation admission. Bare release_hold is insufficient. A successful mutation increments the scheduling revision, leaves active_generation1, changes success_generation2 and requires commit evidence.
4. Both workers are joined, and any alive-at-limit or cleanup failure rejects PASS. Worker operational exceptions and owner/cleanup secondaries retain separate precedence; no new acceptance of cleanup failure was found.
5. The final assessment must exist. A separate verification query records persisted subscription generations. Acceptance additionally requires the actual final requested diagnostic to name the intended subscription and calendar_coverage_generation_mismatch; the DB predicate is explicitly not a substitute.
6. Coherence compares the final readiness revision with the committed mutator revision and DB generations with mutator generations; requested.ok and scheduling_ready must both be false. The wrapper independently rejects mixed_revision_detected, missing commit/result, missing joined workers and cleanup failures.

Future-run evidence review must inspect the actual lock rows/PIDs, final assessment and committed revision/generation values, not merely trust passed=true, the receipt's fixed description strings, or a synthetic fixture label. This demonstrates the bounded mutation scenario only; it is not a general proof of serializability under all workloads or of real HTTP contention. HTTP composition has its separate I01 obligation.

No native run occurred. I02, all I01 runtime cases and T01–T08 remain open until separately authorized evidence and cleanup satisfy the full goal.