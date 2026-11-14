# Scheduler repair specification and acceptance checklist

Draft 0.1, October 19, 2026. Prepared by Dex for Julie and Jim review.

## Authority and sources

Trish accepted the six product/scoping decisions in Cabinet thread 1792430862.330659, replying to Dex's list 1792433328.635569. Exact responses are in Session-Decisions-2026-10-19.md. Her “Engage!” at 1792434203.808079 follows the proposal to write this repair spec. This draft does not authorize implementation, deployment, Preview Changes, Update Schedule, live calculation/replanning, or calendar/task changes. Preserve the manually cleaned calendar.

Investigation task: 5b4607f6-2a73-4278-a758-0757bff48b53. Evidence claims below are attributed to Julie's saved data and Jim's code review, not independent execution by Dex. Jim reviewed revision 8b5909d; parity with the original deployed image remains unverified.

## Problem and evidence boundary

Julie reports original run 6fab234c-82e7-43b5-94f8-b719a64fa977 produced 36 blocks on October 15. No subsequent run/write explained the apparent recurrence of clutter; Google was manually cleaned while thePlan retained its blocks. Trish pressed neither scheduling button.

Distinct future admin stand-ins were eligible too early; description text supplied no hard day-of constraint. A legal split under task defaults added fragmentation. Current due_at ranking is not a hard eligibility or completion bound. Cached calendar inputs omitted newer appointments and retained stale show times. Google transparency was not persisted, so free all-day reminders became busy. Weekend shows were present, merged under all-day intervals, not missing from ingestion. A priority_ups schema mismatch breaks explanations. Current Apply's delete/recreate path threatens remote manual edits and deletions.

Original snapshots and provider evidence support these findings with limits: present provider timestamps are not an archived original provider payload. Informational-calendar role filtering is a separate gap, not the demonstrated cause of this run. Preserve these qualifications in implementation documentation.

## Track 0: restore explanations

Add the already-compared priority_ups category to the response schema and correct stale documentation. Preserve existing categories and explanation semantics.

Acceptance:
- A fixture with priority_ups drift returns valid stale-summary and task explanation responses, rather than validation errors.
- Existing categories remain valid; unchanged inputs do not acquire false drift.
- Passing this track does not clear the scheduling hold.

## Track 1: calendar fidelity

Persist and use provider busy/free meaning; keep unknown distinct from explicitly free. Resolve unknown legacy rows by refresh or an explicit policy before trusting calculations. Normalize date-only boundaries using a documented owning timezone, with exclusive end dates and DST-aware conversion. Refresh/verify every relevant calendar's usable inputs before calculation; incomplete or failed refresh must be visible and prevent a trustworthy proposal under the proposed fail-closed contract.

Exclude free events before busy-interval merging. Preserve raw event identity/provenance for explanation. A refresh must retain the baseline needed to detect manual edits/deletions for Track 3.

Acceptance:
- Transparent all-day reminders do not block work; opaque all-day events do.
- Opaque timed shows overlapping a removed transparent all-day span remain busy.
- Local date-only boundaries work across DST transitions and differing calendar/user zones under the specified ownership rule.
- Newly added appointments and changed show times appear in refreshed fixture inputs.
- Unknown status, partial refresh, stale inputs and refresh failure yield explicit diagnostics without presenting an unsafe proposal as ready.
- Provider equivalents are mapped explicitly for supported integrations; do not assume Google fields exist on Microsoft events.

Technical review required: owning timezone/fallback, freshness contract and threshold, provider field mapping, legacy-data migration, and baseline retention. No live sync is requested by this specification.

## Track 2: occurrence eligibility and start windows

Expose two independently optional hard bounds: start no earlier than and start no later than. Finish by remains separate. Do not globally reinterpret due_at. Carry bounds through persistence, API, CLI, UI, task/occurrence inputs, fingerprints, explanations, placement and chunked paths. Auto-defer and soft preferences cannot relax them.

An equal earliest/latest start is valid. Contradictory bounds are validation errors; a valid window lacking an available slot is an unplaced result with a reason. For a single block the latest feasible start is the lesser of explicit latest-start and finish-by minus duration, where those constraints exist.

For split work, latest-start constrains the first piece only. Pieces remain sequential and non-overlapping; finish-by constrains completion of all pieces. Enforce minimum chunk rules. Specify handling of already-started tasks and completed pieces before coding so replanning does not reset the original start requirement.

Routine admin: intended-day earliest start and finish boundary, desired afternoon preference, 30 minutes in one block. Exact template hours remain to be configured. Flexible exceptions explicitly widen/remove relevant bounds. No global split-default change.

Missed hard bounds produce an unplaced reason, never quiet late scheduling. Do not auto-stack missed routines. Preserve missed-occurrence identity/history and distinguish skipped from completed. Many routines may resume at their next occurrence; Trish can request a recovery one-off. Blanket silent skipping of all overdue tasks is not authorized.

Acceptance:
- Unset, lower-only, upper-only and two-sided bounds behave independently.
- Exact-start is valid; inverted constraints are rejected; busy-slot failure remains distinguishable from invalid input.
- Auto-defer cannot cross either hard bound.
- Future admin instances cannot migrate into an earlier day; single-block intent is enforced.
- First piece meets latest-start; later sequential pieces may start later, but all finish by the completion boundary.
- Existing minimum chunks and already-started work behave according to the documented contract.
- Missed routine does not generate automatic catch-up stacking; the next occurrence remains distinct.
- Bounds round-trip across supported authoring surfaces and appear in snapshots/explanations.

## Track 3: safe Apply

Provide a reviewable comparison between thePlan's proposal, its previous exported baseline and current remote state. Detect remote edits/deletions before replacing blocks. Require explicit conflict resolution, preserve manual changes by default pending resolution, and invalidate or recheck a reviewed proposal if relevant inputs change before Apply. A refresh must not overwrite the evidence of divergence.

Represent partial export failures explicitly and support retry/reconciliation without duplicate creates or false success. Specify durable operation identity, provider-result recording and ambiguous-outcome recovery. Do not assume cross-system atomic transactions.

Acceptance:
- A manually extended block is shown as changed and is not silently replaced.
- A remotely deleted block is not silently recreated.
- Newly added appointments are preserved and constrain placement.
- A remote edit between review and Apply prevents stale destructive execution.
- Partial export success/failure is visible; recovery does not duplicate successful creates.
- An uncertain provider outcome is reconciled before retrying a create.
- Removing old blocks, creating replacements and recovering failures preserve a traceable association with tasks/occurrences.

## Verification and release boundary

Build isolated fixtures from the reported failure patterns with personal data minimized. Test pure scheduling and provider mocks first, then integration contracts in an isolated environment. No production calendar writes or live replan are needed to prove these checks.

Review order: Track 0, Track 1, Track 2, Track 3. Before any live Apply, require all applicable checks, an integrated preservation review and Trish's explicit authorization. Deployment and release decisions remain hers. A passing explanation endpoint is not sufficient evidence of scheduling safety.

## Next review

Julie: verify that this specification preserves the accepted workflow and evidence qualifications.
Jim: review implementation seams, missing contracts and the feasibility of the isolated acceptance tests. Return material gaps or concrete alternatives, not another full duplicate decision list.

Open details are technical proposals to resolve in review, not implicit permission to change live settings: timezone ownership, freshness policy, legacy unknown status, already-started split tasks, baseline/version handling and export recovery. Bring consequential tradeoffs to Trish with a recommendation.

## Review additions: Julie, 11:25 Pacific

Source message 1792434333.462909. These are review requirements and implementation candidates, not verified provider contracts or additional product approvals.

- Legacy backfill must populate unknown free/busy even when the old change hash is unchanged. Julie's suspicion that sync_hash omits transparency is unverified; Jim should check the actual upsert/hash path and test unchanged-event migration.
- Freshness must use successful, complete event synchronization for each relevant enabled subscription, not account updated_at or token refresh. The account timestamp/token-refresh explanation remains a hypothesis unless separately traced. Surface failed/dead sources with an actionable fix/disable choice for Trish; never silently ignore them or silently block forever.
- Compare event instants/duration separately from timezone representation. An equivalent label-only normalization must not masquerade as a duration edit; retain timezone semantics for recurring/date-only events, where zone changes can matter. Specify the export zone contract rather than blindly rewriting all zones.
- Capture a durable last-exported baseline and provider revision metadata before refreshing caches. Preserve remote-deletion evidence before any cleanup; a 404/410 during deletion must not erase an unresolved review conflict.
- Candidate concurrency mechanism: provider revision/conditional writes plus proposal input revalidation. Julie proposes Google etag/If-Match and 412 handling. Verify endpoint support and behavior before adopting; test edits after review for both patch and delete.
- Candidate create recovery: deterministic provider-compatible event IDs and private ownership metadata. Verify provider format/scope/conflict behavior. A conflict must be read and matched to the expected operation/content, not assumed successful. Operation identity must remain stable across retries and local block regeneration. Specify equivalent recovery for other supported providers.
- Represent partial export errors distinctly from successful completion, with per-operation outcomes and recoverable state.
- Already-started work needs explicit progress semantics: elapsed wall-clock time alone does not prove a piece was started or completed. Julie proposes preserving started pieces and scheduling remaining duration without reapplying latest-start after the first piece satisfies it. Specify evidence of actual start/completion, treatment of pinned pieces, and horizon-straddling blocks; keep this a design proposal pending review.

Additional acceptance cases: unchanged-hash legacy refresh; token refresh without event sync; one dead subscription; equivalent-zone representation versus actual duration change; deleted-event evidence retained; conditional-write conflict; uncertain create followed by matching or mismatching existing event; partly completed split task; and block crossing horizon start.

## Review additions: Jim, 11:25 Pacific

Source message 1792434355.770199. Require freshness verification before cache-only collect. Edited survivors and deleted-but-mapped events need distinct review/resolution actions. The other listed gaps are covered above. Jim proposes owner-settings timezone for date-only bounds; this remains a candidate contract to assess against source-calendar date semantics, not a settled rule for calendars in different zones. Preserve provider dates and timezone provenance so normalization does not change the intended occupied local days.

## Current-code clarification: Jim, 11:27 Pacific

Source 1792434462.317949; attributed code review, not independently verified by Dex. Current create_google_event supplies no client ID and receives the provider ID only on success; ambiguous creates cannot currently rely on a known event ID. Stable preallocated identity/recovery is proposed new behavior. Current delete treats 404/410 as success and removes the mapping; pending_deletion represents failed deletion, not a user's remote deletion. Pre-Apply detection must be non-destructive and retain evidence. Google upsert has no transparency/backfill path; the unchanged-hash test is a migration design safeguard, not a diagnosed existing shortcut bug. Public provider support for proposed conditional writes and insert recovery still requires verification; reading application code alone does not verify provider contracts. Placed slices are not evidence of actual work progress.

## Legacy migration and hold clarification (Julie review, 11:28 Pacific)

Sources 1792434499.008049 and 1792434509.511429. Current application behavior remains attributed to Jim's code review. Absence of transparency/backfill is established by that report; an existing hash-based skip of new transparency updates is not established. Migration must populate unknowns regardless of unchanged legacy hashes.

Existing export mappings without a reliable last-exported baseline remain unresolved. Do not seed the baseline from today's remote state and assume it is the original export. Use attributable captured evidence where sufficient, otherwise require review before destructive reconciliation. Test the manually extended survivor and deleted mappings through the first post-repair reconciliation.

Existing generated occurrences must receive explicit migration treatment before becoming eligible under the new scheduler. Propose reviewed backfill preserving identity/history; do not silently regenerate, duplicate or treat legacy day-of tasks as unbounded. Template changes alone are insufficient. Migration remains scoped work, not permission to alter live tasks now.

Keep failed-delete tombstones distinct from user remote deletions. Specify a correct named timezone for new timed exports, consistent with the schedule's intended zone, while preserving provider/date-only semantics and equivalent-instant comparisons; exact export contract remains for technical review.

The hold includes real-data proposal-only calculations, Preview Changes, Update Schedule and live replanning, not merely Apply. Passing Tracks 0–2 does not authorize those operations. Only Trish may lift the hold. Isolated fixtures/mocks are the proposed verification path; any later live-data validation needs explicit scope approval.

## Review disposition: Jim, 11:29 Pacific

Source 1792434558.358749. Jim reports checking Google documentation for client-supplied insert IDs and conditional update/delete; provider feasibility is attributed to his review, not an independent Dex verification. Request exact documentation links for the engineering evidence packet. Microsoft equivalent remains unchecked. Mechanisms are not implemented or tested.

Resolution matrix required:
| State | Required treatment before destructive reconciliation |
| --- | --- |
| User-deleted, still mapped | Preserve remote-deletion evidence; explicit resolution before recreating or retiring mapping. |
| Failed-delete tombstone | Preserve failed-operation identity and outcome; reconcile/retry under reviewed recovery policy, not as a new user deletion. |
| Hand-edited survivor | Compare with trustworthy export baseline; preserve edit pending explicit conflict resolution. |

New timed exports should use the schedule's intended named local timezone, consistently with their instants. Keep this separate from date-only source timezone interpretation. Progress must derive from recorded actual progress, not placement alone; remaining/planned slices support bookkeeping but do not prove an actual start.

Jim reports no other material holes in the condensed 0.1 acceptance shape. This is not review of the full local draft or authorization to implement.
