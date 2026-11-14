# T07 check-authoring provisional review

Dex, November 11, 2026. Current Jim handback is not frozen. These findings concern the in-progress check file, not immutable final bytes or an executed run. No check, import, compilation, real thread/socket or application execution occurred in this review.

## Caller/no-continuation oracle

The inspected C-CALLER-EVENT/OAUTH/IDENTITY controls call CoveringHTTP directly, then record caller_kind and later_admission=False. The identity row uses event purpose. No actual identity/token/importer/transaction/domain caller is driven by those rows. The inspected C-NO-LATER-ADMISSION control creates false target/assessment flags and checks that they remain false without invoking orchestration. These are not observable caller-stop oracles.

Required correction within the approved scope: exercise actual extracted pinned callers/domain orchestration with fake dependencies and role/callback counters. Preserve prior completed rows and observe zero later PARENT/apply/ASSESSMENT callbacks after the cleanup UNKNOWN. Require a continuation-enabling mutation to fail the same oracle. Label fake database acknowledgments and synthetic ownership separately from real native/transport proof.

## Importer exception context and source fidelity

The inspected importer_unknown_escape locates a handler using both CoveringRootOutcomeUnknown and the comment phrase Deferred import in ast.dump. Comments are not AST nodes, so that selector cannot reliably identify the actual handler. It then extracts only the handler body into a new function and invokes it without an active owning except context; the bare raise cannot establish rethrow of the original marker. Its original_handler is a hand-written swallow imitation, not the original source path.

Required correction: drive the full pinned importer function or the complete actual owning try/except AST with dependencies faked. Retain the active exception context and assert both original and candidate observations. Independent full caller/domain controls must still establish no continuation; an isolated handler witness cannot close that obligation alone.

## JoinedTLS outer retirement observations

The inspected R08 control contains an imitation of the proposed open/close handler, then invokes actual extracted JoinedTLS.open separately. The outer HTTP close/no-op is described rather than observed through that caller. Fake raw close sets a Boolean without establishing separate method/raw-close attempt counts.

Required correction: drive the actual CoveringHTTP→JoinedTLS path with fake owned socket state for R07/R08/R09. Count transport-close method calls, raw socket-close attempts and retirement outcomes separately. Observe the outer close and absence of a second raw-close retry; do not infer them from a comment or closed=True. Discard the imitation block as proof. Preserve all original/candidate distinctions and the unchanged production diff.

Feedback sent at Slack1794427286.171889 under the same approved T07 preparation assignment. Routine check-authoring corrections before freeze are already authorized. No extra source change, implementation scope, execution card or second Jim assignment is created. A final frozen handback and independent static review remain prerequisites to any launch card.

## Remaining batch: mutations, enforcement and bounded provenance

The inspected mutation controls use a Mini imitation or direct object assignments rather than mutate and drive the actual extracted candidate. Require in-memory AST/definition mutation with coherent rebinding, the same functional oracle on original candidate and mutant, observed candidate acceptance/mutant refusal and restored globals. A demonstration that assigning an attribute changes it is not mutation sensitivity of the implementation.

The inspected inventory self-checks compare constructed lists with expected lists, without invoking compare_to_expected or the actual enforcement function. Drive that real gate with a complete valid result plus missing, duplicate, reordered and altered variants. Assert real acceptance/refusal, not just that the bad input differs from the good input.

The inspected provenance-boundary loop performs no field enforcement and only tests tuple dimensions; it has no finite occurrence-count limit or member-type validation. Specify the actual finite production topology and separately label any synthetic extra boundary. Reject over-count, malformed history and non-exception/non-None members before sanitization/emission. Do not silently truncate, normalize or overwrite unexpected provenance. Keep the later real provider/native proof obligation separate.

Original R04/R05 witnesses must observe actual primary/context/cleanup classes, not infer that the primary disappeared solely because the original exception lacks new attributes. Implicit Python exception context may retain that primary. Record that observed representation limit honestly; do not manufacture an original failure from a new metadata convention. The O-ID-OS constant witness must also become an actual source-path observation.

This remainder batch was delivered at Slack1794427379.735709. Jim was asked to reconcile the whole batch before one final handback, without per-item approvals or replies. No production diff or execution authority changed.
