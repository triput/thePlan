# Google provisional review — final revision coherence (same CEBD83C3 assignment)

Matt — one additional functional acceptance point from the same provisional runner snapshot99815bytes/mtime2026-11-14T04:02:50.9034225Z. No frozen acceptance, code edits, execution, new task or scope expansion by Dex. Keep working on primary feedback55B75EA0 within current assignment.

The snapshot's final assessment guard only requires scheduling_revision to be int>=1. measure_all has persisted credentials/coverage/events but no independent persisted owner scheduling revision or busy-signature observation. This can verify imported rows and a ready boolean without proving the new busy data is reflected in the returned final revision.

As part of existing CEBD83C3 requirements (native final assessment at actual final revision, observable before/after busy change), please measure the actual owner scheduling revision and immovable_busy_signature in your existing separate native before/after read sessions. Require the declared nonempty busy data to change the signature, after revision to exceed the planted before revision, and public final scheduling_readiness.scheduling_revision/end revision (where exposed) to equal the independently persisted after revision. Use actual payload schema, not a new field. Retain bounded counts/hash/typed revisions, no event title/body or credentials. This is a small functional check, not another generic owner-lock/SQL suite.

Source basis in unchanged API: covering_refresh_import.py1110 commit_covering_revision_if_required after apply compares busy/trust; covering_domain_dispatch.py251 runs actual ASSESSMENT; covering_refresh.py379 locks owner, reads revision, expires identity map and assembles freshness/readiness in that role. Existing13 shared contract hashes remain I01/I02-identical, so do not repeat their full generic SQL/owner-contention matrix. Source/reuse map outputs/scheduler-investigation/Google-Functional-Review-Reuse-Map-2026-11-13.json5C517B3C is context, not substituted for the new Google witness.

Also verified: your explicit opaque/provider_explicit expected event fields match current resolve_google_transparency. Your token_terminal retained key correctly respects this baseline's sanitizer; keep it unchanged if its actual retention controls pass. No need to switch to a token_terminal_sequence key merely because a later Microsoft lineage used it.

If you already added stronger revision/busy checks after the observed snapshot, just retain them in handback; no new revision is requested solely for this note. No production source changes, parsing/imports/tests/helpers/DB/Docker/execution. Endpoint unbound; all holds stay.

Signed: Dex