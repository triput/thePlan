# T02 corrected1 — provisional reviewer notes

Working copy only, not a frozen handback. Directory: F:/DropFolder/pending/post-native-t02-admission-prep-jim-v1-corrected1-2026-11-10. Its inherited v1 TIP/handback is not corrected1 completion evidence. No execution or imports. Recheck every finding against the final frozen source; do not issue a run card from this note.

Observed progress: four mutation controls now compile selected AST definitions from actual candidate source, with exact changed-attribute counts; M-C invokes the mutated token callable; M-D routes a framed fake response through the modified HTTP method. New helpers extract CoveringReleasePlan.for_request and run_bounded_domain. The inventory enforcer now compares emitted IDs directly and serialization no longer repairs order. Final invocation/provenance/pins still need verification.

Sent to Jim during authoring:

- Slack1794383509.675089: the original-token terminal sentinel sits beyond locks/ORM setup unsupported by the minimal fakes. Suggested exact db.info.get lookup instrumentation or complete deliberate downstream setup.
- Slack1794383631.925099: replacing covering_unit_locks still requires a fake target exposing owner_id/account_id/subscription_id because argument evaluation happens first. Current bare object in W-TOKEN and M-C is insufficient; no exception other than the deliberate sentinel may count as admission evidence.
- Slack1794383742.792059: composed HTTP responses exceed the convenience 64-byte ceiling due to header/framing accounting; use an adequate disclosed byte bound without changing production accounting. Ordered fake budget must expose check_admission, not check_deadline. Compare exact cardinality/subscription-ID order and token/parent call counts.

Additional point to reconcile at freeze: item-equality and byte-equality ALL-PURPOSES controls currently construct one counter outside the event/identity/OAuth loop. The first refusal sets counter.stopped=True, so subsequent purposes test the stopped latch rather than independent equality admission. Use a fresh counter for each purpose, inject only the intended exact ceiling and assert stopped=False before the call. This is a unit-oracle correction within the accepted authoring scope; not a request to change production refuse/admit semantics. Recheck whether Jim fixes this before handback.

The request-identity control now invokes the extracted release-plan construction, but manually constructs its HTTP test client from the captured counter. At final review, inspect whether observations establish that the composed domain ports and HTTP path use the same object across purposes/targets, and whether a second independent request gets a fresh counter. Do not demand a production change for a fake seam; do not accept a local id(variable)==id(variable) comparison as wiring proof.

All T01–T08/native proof obligations, endpoint hold and execution/source-change gates remain. Jim remains on this sole assignment and normal turnaround applies.
