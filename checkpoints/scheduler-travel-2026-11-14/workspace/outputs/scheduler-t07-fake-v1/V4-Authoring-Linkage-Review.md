# T07 v4 authoring review: remaining linked-caller oracle

Dex, November 11, 2026. Provisional static reading of Jim's mutable working copy, not acceptance or a freeze receipt. No checker/application execution. The directory's TIP still described its v3 predecessor when inspected; a final successor manifest must be independently reconciled after handback.

Observed working file: F:/DropFolder/pending/post-native-t07-source-fake-prep-jim-v4-2026-11-11/fake-only-t07-retirement-verification/check_t07_retirement_fake.py.

The new drive_bounded_domain_no_later invokes extracted run_bounded_domain and the connector, improving on the prior handwritten connector handler. However, the inspected version constructs cleanup_unknown locally; its token port returns ready for both event/oauth labels, while apply raises that constructed exception. It therefore proves neither the actual OAuth token-port failure location nor identity-preserving propagation of the HTTP retirement fault through the event importer and domain. Separate passing low-level HTTP controls would not close this gap.

The inspected domain body also has only two targets: one successful, then one faulted. A third target is needed to observe whether domain iteration admits another target after the fault. A later manual assessment attempt alone is a different continuation witness.

Required correction within the existing authoring scope: link the fake-backed actual extracted HTTP exchange and owning event/OAuth callers into their respective real domain ports; capture the actual cleanup UNKNOWN from the exchange and compare identity at terminal catch. Preserve prior successful target output. Observe later role, target, provider and assessment counters without rewriting them. Use the same oracle against the actual continuation mutation, with a positive control showing that counters can detect admitted continuation. No production behavior change is requested.

Feedback delivered as Dex in the existing assignment thread at Slack 1794429171.629589, sender U0CAEKN2ZL0. Text retained in Jim-v4-In-Progress-Linkage-Feedback.txt. This is one existing assignment with clarified acceptance evidence; no new scope, source-change or execution authority. Wait for a genuinely frozen successor before final pin review or a verification card.
