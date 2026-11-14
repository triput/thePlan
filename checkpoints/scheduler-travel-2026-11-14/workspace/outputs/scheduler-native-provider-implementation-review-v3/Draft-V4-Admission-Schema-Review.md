# Draft v4 admission schema observation

This is a working-copy observation, not acceptance of a frozen handback. No wrapper, Python, helper or check was invoked. Preserve any already frozen successor and apply changes in the next authorized copy.

The current v4 VERIFICATION-ADMISSION.json contains fourteen packet entries with `path` and three purported runtime entries also containing relative `path` values pointing to checker/launcher/expected files. All fourteen packet paths resolved and raw hashes matched when read as data relative to the packet root.

However, the unchanged Invoke-Fake.ps1 consumes `relative_path` for packet entries and `absolute_path` for runtime entries. It also requires the exact interpreter to appear in the runtime inventory. Therefore these concrete values do not yet form a consumable admission packet: the wrapper would stop on the first missing relative_path before launching a child. The three runtime entries are packet files, not runtime provenance, and none supplies the required absolute_path/interpreter membership.

Reconcile the JSON field schema with the actual unchanged wrapper; populate genuine exact runtime inputs from the reviewed pinned interpreter/provenance lineage, explicitly stating partial runtime scope as before. Do not loosen or bypass the wrapper guard to accept the invalid inventory. Complete pin coverage for everything the checker reads/extracts, including added coverage/receipt controls, and freeze final source/hash/expected-output/command files together.

Draft-V4-Admission-Observation.json records a hash-only snapshot. Its first exploratory runtime lookup used the generic relative path field and yielded three unresolved paths; this is an invalid-declaration observation, not evidence of changed interpreter/runtime bytes. Runtime drift is not established. Exact admission SHA and current files are recorded there; recheck the final frozen packet rather than trusting this mutable snapshot.

The separate current receipt-path review also finds that case_result_receipt uses build_receipt defaults executed=false and prep_is_not_pass=true even when returned by an actually executed passing case. Make preparation-versus-execution metadata truthful at the right layer in the successor; the runner cannot grant launch authority by writing launch_authorized=true. The host's approved command/receipt ledger establishes authority. Preserve actual bounded per-case observations through the selected sanitizer, and exercise the actual sanitizer and host consumer in the later fake packet rather than a model substitute.

These are same-lane packet corrections, not an extra decision or authorization request. Numeric limits, complete commands and all launches remain held.
