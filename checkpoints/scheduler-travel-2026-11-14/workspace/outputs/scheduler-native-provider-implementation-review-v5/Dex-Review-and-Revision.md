# Frozen prep v5: independent source and fake-packet review

Disposition: source improvements accepted at the limits below; REVISE the fake packet before launch review. Native launch remains HOLD. No tests, imports, compilation, PKI or other execution performed. Corrections remain inside the existing approved 16-role preparation lane; no new Trish source-preparation card is needed.

## Integrity and accepted improvements

285 workspace/drop files match raw hashes; all 234 selected application files match the assembly map. TIP raw SHA256 49F16773BE3730B55F161EC65E422098BEE60F3752A93B917B5F8301D84B2EA1; exact zero-field preimage D1C7F790AEE043C745170E807B702999C089828DDE084B702017780F04B224FB matches; CR=0. Preserve v5 unchanged.

All sixteen declared fake packet pins and the one explicitly partial interpreter-runtime pin match their referenced bytes. Declaration fields now match the unchanged wrapper's relative_path/absolute_path schema. This is positive integrity evidence for those inputs, not complete input coverage or full runtime attestation. See Integrity-Reconciliation.json and Admission-Pin-Reconciliation.json.

The source now installs the actual release plan, uses a real monotonic clock and captures ingress context; adds explicit schema creation and the missing unchanged auth helper; uses mapped coverage fields; plants a real primary alias; repairs transcript tuple syntax text; and exact-matches path components while recording observed paths. These are source improvements, not native PASS observations.

## Fake launch blockers and required scope honesty

### F1. Documentation triggers the forbidden-alias detector

check_vertical_contract_shape refuses any runner text containing FixtureByteTransport. The runner intentionally contains that name in its module/function documentation explaining that the byte alias must not be used (lines13 and298). The current check therefore deterministically raises WitnessFailure even though those mentions are documentation. This was identified by reading the predicate and matching raw text; no checker was run.

Replace the blanket text membership check with an executable AST import/call/reference check appropriate to the claimed no-byte-alias property, ignoring comments/docstrings while rejecting real forbidden construction/installation. Include a harmless-documentation positive and an actual forbidden-use negative/mutant under the same oracle. Do not simply remove truthful documentation to satisfy the checker or replace the guard with another declaration-only string assertion.

### F2. Complete the actual read footprint under an acyclic root

The sixteen declaration hashes match, but the checker reads more inputs: its fixture glob, other fixture roles and helper/document files, plus the assembled tree it describes as ASSEMBLY-PINS. That check presently verifies only the policy hash and file count, then echoes ASSEMBLY_SELECTION_PIN; it does not verify the other selected application bytes. The outer-admission file used by the Python admission chain is also absent from this wrapper-rooted pin list.

Complete a concrete root-pinned input inventory for everything the check reads/extracts. Either pin the 234 selected files directly in admission or root-pin their exact manifest and actually check every selected file against it at admission/check time. Count234 is not equivalent to those234 hashes. Pin the actual outer-admission bytes through the wrapper's reviewed root. Avoid a hash cycle: OUTER currently contains verification_admission_sha256; do not also pin OUTER back from VERIFICATION while retaining that raw-hash back-reference. The outer code does not currently consume that extra back-reference, so use an explicit acyclic chain rather than a self-waiver or an impossible fixed point.

Retain a truthful partial runtime statement. For consistency with prior packets, reuse/recheck the relevant reviewed interpreter/core/stdlib provenance inputs that the new checker actually uses; do not describe an executable-only pin as the previous19/21-input provenance scope. Return the exact final set and limitations. No invocation is authorized now.

### F3. Behavioral versus shape controls

The mapped-state, extracted counter/context and report-boundary controls can provide useful finite fake evidence once their exact source/oracles are reconciled. The first-vertical shape control currently passes PKI because a helper name appears; that is not a bounded caller witness. Likewise keyword checks do not establish the actual shared-budget or subset-safe alias behavior. Label these as shape/source checks unless replaced by actual selected-definition controls. Verify the selected sanitizer on actual fake evidence and actual host consumer, keeping authority in the host ledger.

A narrowly described fake verification packet may advance before all native wiring is complete. It must not claim a runnable native vertical or that the native blockers below are fixed. Do not wait to implement all26 later native cases merely to run useful prerequisite controls. Keep the next card truthful about its exact14 groups and nested control inventories, timing/capture/retirement bounds and remaining gaps.

## Native first-vertical blockers still present

### N1. Correct construction still fails the budget observation

The runner checks transport.budget/counter.budget, but selected CoveringHTTP stores counter and selected ProviderCounter stores budget.work_remaining as remaining. Neither selected class defines budget. Therefore the current check rejects the correct production worker construction after POST. Observe counter.remaining.__self__ identity against captured ingress_context.budget and the selected bound work_remaining function; do not add fixture-only budget attributes as proof. The earlier working-copy clarification remains applicable.

### N2. Alias is on the later target and trips the preserved sibling guard

np_auth_seed currently assigns primary at index0. inverted_subscription_ids puts that row on the higher UUID. Production processes the lower stable target first; account-wide canonicalization then rewrites its primary sibling, which classify_covering_prepare_mutation correctly refuses. The successful vertical must plant primary on the lower str-sorted target, keep its canonical default unoccupied and preserve the higher unrelated stable target. Keep request IDs inverted and derive the actual identity/event sequence from these rows. Supply canonical IDs in the identity list, rather than treating primary as a provider-returned stable ID. Reference: review-v4/Alias-Subset-Safe-Seed-Reference.md. Do not relax the production mutation guard or result assertions.

### N3. PKI caller is still metadata-only

prepare_provider_pki_private_dir(generate=False) verifies the recipe path and returns PREPARED_NOT_GENERATED. It does not create/admit the private directory, generate certificates, capture a child, or retire its group/readers. Main calls that path before a peer requiring real certificate files. Author the actual bounded future caller in the named role; invoking it remains separately held. Declaring C06_PATTERN_SOURCE_ONLY does not implement that caller. Source-authoring authority already permits writing an invocation without executing it.

### N4. Retirement attempt flag is set after the call

The runner sets retirement_done only after retire_owned returns. If that call fails before clearing the worker handle, finally may invoke retirement again. Mark a sole attempt before calling it, track confirmed outcome separately, and never retry after any failed/unconfirmed attempt. A failure before any attempt may perform the one authorized local retirement path. Preserve the primary failure and explicit UNKNOWN if retirement cannot be confirmed; do not equate a discarded handle with a joined worker. Include selected-definition failure-path fake controls rather than only checking that the literal join_seconds=2.0 disappeared.

## Requested handback

One fresh successor under the same approved lane. First fix genuine fake blockers and freeze complete commands/pins/oracles/bounds; clearly distinguish fake behavioral controls from shape checks and native readiness. Continue correcting N1–N4 without another preparation card. All frozen predecessors/evidence remain preserved. Other26 native cases and four pure witnesses remain HOLD, all76 requirements retained. Endpoint unbound; no execution, new permissions, credentials, deployment or automatic retry authority added.
