# Draft 0.3 review closure and pre-implementation notes

October 19, 2026. Recorded by Dex. Companion to Repair-Spec-2026-10-19.md; does not authorize implementation or replanning.

Both reviewers report reading the complete draft 0.3 matching SHA256 4B173231B50923F8090AD5E5B86C1F03D75409B6FD82B28B097BA78A2830862C. Jim: Slack 1792436365.593509. Julie: 1792436474.142289 and 1792436480.306779, in Cabinet thread 1792430862.330659. Julie reports a line-by-line comparison with 0.2 and no material omissions. These are their review reports, not independent verification of implementation.

Both report no blockers to draft 0.3 change-review completion. The following narrow corrections are retained for the next revision; the reviewed draft is preserved unchanged so its hash remains meaningful.

## Fidelity corrections for the next revision

- Skippable is set by Trish or at her direction, never inferred by the scheduler. With recurrence outside scope, the designation belongs on each individual one-off alongside its bounds; no routine record is assumed.
- Past-due admin stand-ins default to held until Trish chooses skipping or a recovery one-off. Held misses remain distinct and must not block, delay or merge with the next occurrence.
- Name the user-visible location for held/unplaced misses in the UI design and include an acceptance test that they are surfaced there. The location is not yet selected.
- Add explicit timed-transparent reminder acceptance alongside all-day transparency, plus a contradictory opaque copy of a known non-blocking event being flagged for resolution.
- Replace "under the specified ownership rule" with "under the source-zone rule".
- Label the older review-message list as condensed draft 0.1 reviews; preserve the separate full 0.2 and 0.3 review provenance.

## Technical contracts to lock before implementation

Jim proposes and Julie supports missing source-zone fail-closed handling: unresolved timezone provenance, visible diagnostic, no trustworthy placement until refreshed or explicitly resolved. No silent owner-zone or UTC-midnight guess. This is their recommendation consistent with the accepted unknown-input safeguards, not a newly verified provider behavior.

Freshness must include successful synchronization covering the horizon plus defined boundary padding and an explicit age ceiling. Jim proposes padding at least inter_block_buffer or a fixed day; exact padding and age remain engineering choices to document before coding. Incomplete coverage fails closed.

Actual progress requires a reliable start/progress signal. Assess existing fields; specify either an explicit actual-start field or an insufficient-signal/not-started rule before coding. Do not infer progress from a planned block.

Select and schema-test the fingerprint/stale category for start-window changes (Jim proposes extending due_at_soft_target or a dedicated start_window category).

Microsoft busy/free and export/concurrency contracts remain required gates. No claim that these contracts have been verified. Provider details, visibility location, progress semantics and freshness choices still need design closure; review completion is not implementation readiness or release approval.

No new product decision was requested by either reviewer. Any consequential tradeoff discovered while settling these contracts returns to Trish. No implementation, deployment, live sync, task/calendar edits, Preview Changes, Update Schedule, calculation/replanning or Apply is authorized. Preserve the cleaned calendar and current hold.
