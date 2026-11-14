# Scheduler repair specification and acceptance checklist

Draft 0.3 (revised after full review), October 19, 2026. Prepared by Dex for Julie and Jim review.

## Authority and sources

Trish accepted the six product/scoping decisions in Cabinet thread 1792430862.330659, replying to Dex's list 1792433328.635569. Exact responses and subsequent clarifications are included in the decision record below. Her “Engage!” at 1792434203.808079 follows the proposal to write this repair spec. This draft does not authorize implementation, deployment, Preview Changes, Update Schedule, live calculation/replanning, or calendar/task changes. Preserve the manually cleaned calendar.

Investigation task: 5b4607f6-2a73-4278-a758-0757bff48b53. Evidence claims below are attributed to Julie's saved data and Jim's code review, not independent execution by Dex. Jim reviewed revision 8b5909d; parity with the original deployed image remains unverified.

## Problem and evidence boundary

Julie reports original run 6fab234c-82e7-43b5-94f8-b719a64fa977 produced 36 blocks on October 15. Julie reports no later run or write as of her October 19 approximately 10:30 Pacific read-only check. The apparent repeats were distinct stand-ins placed early; this is not evidence of repopulation after cleanup. Google was manually cleaned while thePlan retained its blocks. Trish pressed neither scheduling button.

Distinct future admin stand-ins were eligible too early; description text supplied no hard day-of constraint. A legal split under task defaults added fragmentation. Current due_at ranking is not a hard eligibility or completion bound. Cached calendar inputs omitted newer appointments and retained stale show times. Google transparency was not persisted, so free timed and all-day reminders became busy. Weekend shows were present, merged under all-day intervals, not missing from ingestion. A priority_ups schema mismatch breaks explanations. Current Apply's delete/recreate path threatens remote manual edits and deletions.

Original snapshots and provider evidence support these findings with limits: present provider timestamps are not an archived original provider payload. Informational-calendar role filtering is a separate gap, not the demonstrated cause of this run. Preserve these qualifications in implementation documentation. The reported eight versus stored nine admin blocks and Monday 16 versus 17 counts remain unresolved.

Breaks/lunch were not configured and Time Maps were unassigned, according to Julie. These are configuration gaps outside this repair; Tracks 0–3 alone do not restore lunch. Julie also reports Trish's standing intent that Coursera learning-time events never block. Flag a contradictory opaque copy for resolution rather than silently treating that known exception as busy; do not generalize it to unrelated events.

## Track 0: restore explanations

Add the already-compared priority_ups category to the response schema and correct stale documentation. Preserve existing categories and explanation semantics.

Acceptance:
- A fixture with priority_ups drift returns valid stale-summary and task explanation responses, rather than validation errors.
- Existing categories remain valid; unchanged inputs do not acquire false drift.
- Passing this track does not clear the scheduling hold.

## Track 1: calendar fidelity

Persist and use provider busy/free meaning; keep unknown distinct from explicitly free. Resolve unknown legacy rows by refresh or an explicit policy before trusting calculations. For date-only events, preserve the source calendar's timezone when known, with exclusive end dates and DST-aware conversion. Do not reinterpret a known source-local day in the owner's timezone. If the source zone is unavailable, flag unresolved timezone provenance; a fallback must be specified and reviewed before treating the interval as trustworthy. Refresh/verify every relevant calendar's usable inputs before calculation; incomplete or failed refresh must be visible and prevent a trustworthy proposal under the proposed fail-closed contract.

Exclude free events before busy-interval merging. Preserve raw event identity/provenance for explanation. A refresh must retain the baseline needed to detect manual edits/deletions for Track 3.

Acceptance:
- Transparent all-day reminders do not block work; opaque all-day events do.
- Opaque timed shows overlapping a removed transparent all-day span remain busy.
- Local date-only boundaries work across DST transitions and differing calendar/user zones under the specified ownership rule.
- Newly added appointments and changed show times appear in refreshed fixture inputs.
- Unknown status, partial refresh, stale inputs and refresh failure yield explicit diagnostics without presenting an unsafe proposal as ready.
- Provider equivalents are mapped explicitly for supported integrations; do not assume Google fields exist on Microsoft events.

Technical review required: missing-source-zone fallback, freshness contract and threshold, provider field mapping, legacy-data migration, and baseline retention. No live sync is requested by this specification.

### Calendar migration and synchronization contract

Freshness means successful complete event synchronization for each relevant enabled subscription, checked before cache-only collect. Account updated_at or token refresh is not evidence of event freshness. Failed/dead subscriptions must surface actionable diagnostics for Trish to fix or disable; never ignore them silently. Define the freshness age threshold and coverage policy before implementation. Successful sync must cover the entire requested horizon and any explicitly required boundary padding; incomplete coverage fails the gate. Canonicalize aliases by verified provider/account/calendar identity so two enabled aliases of the same calendar cannot double-ingest. Do not collapse unrelated calendars merely named primary. Microsoft busy/free mapping is a Track 1 completion gate, not an optional footnote.

Populate unknown legacy free/busy even for unchanged events. Jim reports no transparency or backfill path in current Google upsert. An existing hash-based update skip was not established; unchanged-hash coverage is a migration safeguard. Preserve event identities, provider dates and timezone provenance. Trish accepted preserving the source calendar's known timezone; the earlier owner-settings default proposal is superseded. Preserve the source zone independently of the display/schedule zone.

Additional acceptance: unchanged legacy events populate correctly; token refresh without event sync fails freshness; one failed subscription is visible; refresh preserves the export comparison baseline. No live sync is authorized.

## Track 2: occurrence eligibility and start windows

Expose two independently optional hard bounds: start no earlier than and start no later than. Finish by remains separate. Do not globally reinterpret due_at. Carry bounds through persistence, API, CLI, UI, task/occurrence inputs, fingerprints, explanations, placement and chunked paths. Auto-defer and soft preferences cannot relax them.

An equal earliest/latest start is valid. Contradictory bounds are validation errors; a valid window lacking an available slot is an unplaced result with a reason. For a single block the latest feasible start is the lesser of explicit latest-start and finish-by minus duration, where those constraints exist.

For split work, latest-start constrains the first piece only. Pieces remain sequential and non-overlapping; finish-by constrains completion of all pieces. Enforce minimum chunk rules. Specify handling of already-started tasks and completed pieces before coding so replanning does not reset the original start requirement.

Routine admin: intended-day earliest start and finish boundary, a soft early-afternoon preference inside those hard bounds, and 30 minutes in one block. Exact hours remain to be configured per occurrence. Flexible exceptions explicitly widen/remove relevant bounds. No global split-default change.

Missed hard bounds produce an unplaced reason, never quiet late scheduling. Do not auto-stack missed routines. Preserve missed-occurrence identity/history and distinguish skipped from completed. Many routines may resume at their next occurrence; Trish can request a recovery one-off. Default missed routines to visible and held unless explicitly designated skippable. Preserve skipped disposition history; no blanket silent skipping. A skippable designation does not erase evidence of the miss or authorize catch-up stacking.

Acceptance:
- Unset, lower-only, upper-only and two-sided bounds behave independently.
- Exact-start is valid; inverted constraints are rejected; busy-slot failure remains distinguishable from invalid input.
- Auto-defer cannot cross either hard bound.
- Future admin instances cannot migrate into an earlier day; single-block intent is enforced.
- First piece meets latest-start; later sequential pieces may start later, but all finish by the completion boundary.
- Existing minimum chunks and already-started work behave according to the documented contract.
- Missed routine does not generate automatic catch-up stacking; the next occurrence remains distinct.
- Bounds round-trip across supported authoring surfaces and appear in snapshots/explanations. Changes to either bound must trigger appropriate fingerprint/stale detection with schema coverage for the selected category.
- Held versus explicitly skippable routines retain visible disposition history and never auto-stack.
- Migration preserves one-off IDs, handles past-due stand-ins as missed, and does not require recurrence support.

### Existing occurrences and actual progress

The eleven existing admin stand-ins are manually created one-off tasks with no template, recurrence or parent. Specify a reviewed migration preserving their identities/history. Past-due stand-ins follow the missed-work policy rather than becoming automatic catch-up backlog on the first post-repair run.

Recurrence-engine and recurrence-CLI support are outside this repair. Once fields exist and Trish authorizes live entry, Julie can set bounds on individual admin occurrences through the CLI. Until then no new stand-ins or live edits are authorized by this specification. Existing tasks need their own explicit bounds; there is no template to regenerate these stand-ins from. Do not silently regenerate, duplicate, or let legacy day-of instances run unbounded. Backfill is a proposed migration approach, not authorization for live edits.

Recorded actual progress, not elapsed scheduled time or placement alone, determines whether work has begun. Planned slices and remaining estimates are bookkeeping, not proof of completion. Specify partially completed, pinned and horizon-straddling behavior, including whether the first-piece latest-start has already been satisfied. Assess existing time_worked_minutes and remaining-estimate fields for these semantics; identify any missing actual-start signal explicitly. Test these states and repeated reconciliation without losing progress or duplicating work.

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

### Legacy baseline and resolution matrix

Existing mirrors without a trustworthy last-exported baseline remain unresolved until reviewed or seeded from attributable captured evidence. Do not copy today's remote state into an alleged original baseline and erase evidence of manual changes. Test the manually extended survivor and deleted mappings on the first post-repair reconciliation. Julie reports ID-level pre-cleanup evidence for the 12 admin blocks only; the other 24 remain unresolved unless additional evidence is verified. The sufficiency of worker-log POST records is unchecked. Even the admin evidence must be validated before seeding; evidence availability is not automatic proof of a complete baseline.

| State | Required treatment before destructive reconciliation |
| --- | --- |
| User-deleted, still mapped | Preserve evidence; explicit resolution before recreating or retiring the mapping. |
| Failed-delete tombstone | Preserve failed-operation identity/outcome; reconcile under the reviewed recovery policy, not as a new user deletion. |
| Hand-edited survivor | Compare against a trustworthy baseline; preserve edits pending resolution. |

Jim reports that current delete treats 404/410 as success and removes mappings; pending_deletion marks failed deletion. Detection must therefore be non-destructive and preserve evidence before cleanup. Capture last-exported values and provider revision metadata durably; a pre-refresh snapshot of current cache alone is not necessarily the original export baseline.

### Export and concurrency contracts

New timed exports use the schedule's intended named local timezone consistently with their instants. Compare equivalent timed instants independently of label-only differences; preserve recurrence/date-only zone meaning. Date-only imports instead retain the source calendar's known timezone, as accepted by Trish.

Use stable operation identity across retries and local block regeneration. Current Google create supplies no client ID and receives an ID only on success, according to Jim's code review. An uncertain create therefore needs new reconciliation support; do not assume the current implementation can look up an unknown ID. A conflict requires read-and-match against expected ownership/content, not assumed success.

Jim reports Google documentation supports client-supplied event IDs and conditional update/delete using etags; these are provider-feasible candidates, not implemented or tested contracts. Jim supplied [Google insert documentation](https://developers.google.com/calendar/api/v3/reference/events/insert), [versioned resources and conditional requests](https://developers.google.com/workspace/calendar/api/guides/version-resources), and [update documentation](https://developers.google.com/calendar/api/v3/reference/events/update), also saved at F:\thePlan-imports\investigation-2026-10-19\google-provider-contracts-1130.md. These references are attributed to Jim's review, not independently verified by Dex. Microsoft equivalents remain unchecked and are a Track 3 completion gate; Google-only protection cannot establish safety while another supported mirror path remains destructive. Specify provider formats, collision behavior, uncertain outcomes and partial export recovery before implementation. No cross-system atomic transaction is assumed.

Additional acceptance: preserve remote-deletion evidence on 404/410; equivalent zone representation versus real duration edit; conditional-write conflict; uncertain create with matching/mismatching event; retry after local ID regeneration; partial success with visible per-operation outcomes and duplicate-free recovery.

## Verification and release boundary

Build isolated fixtures from the reported failure patterns with personal data minimized. Test pure scheduling and provider mocks first, then integration contracts in an isolated environment. No production calendar writes or live replan are needed to prove these checks.

The hold includes real-data proposal-only calculations, Preview Changes, Update Schedule, live replanning and Apply. Passing Tracks 0–2 does not lift it. Only Trish may authorize lifting the hold.

Review order: Track 0, Track 1, Track 2, Track 3. Before any live Apply, require all applicable checks, an integrated preservation review and Trish's explicit authorization. Deployment and release decisions remain hers. Before any authorized deployment, isolated startup/restart checks must demonstrate that API/worker startup does not enqueue held sync, calculation or export. Leave the scheduler worker unchanged under the current hold; absence of recent runs does not prove startup safety. A passing explanation endpoint is not sufficient evidence of scheduling safety.

## Next review

Julie: verify that this specification preserves the accepted workflow and evidence qualifications.
Jim: review implementation seams, missing contracts and the feasibility of the isolated acceptance tests. Return material gaps or concrete alternatives, not another full duplicate decision list.

Open details are technical proposals to resolve in review, not implicit permission to change live settings: missing-source-zone fallback, freshness policy, legacy unknown status, already-started split tasks, baseline/version handling and export recovery. Bring consequential tradeoffs to Trish with a recommendation.


## Review provenance and status

Julie and Jim both reported reading full draft 0.2 with SHA256 71710E9B35C06462ABF2E8119E7AE1EB7BC4C96CBD7A37070927C98450FA0155. Their full reviews are at 1792434985.791419/1792434985.837849 and 1792435676.832389. Neither found a blocker to writing 0.3. This revision integrates their corrections and four follow-up decisions accepted directly by Trish in Dex Cabinet on October 19. The 0.3 change review remains pending; no implementation approval is implied. Julie reported the six decisions captured in task 5b4607f6 with exact replies and before/after snapshots, not independently verified by Dex.

Source thread: https://app.slack.com/archives/C0C6ZFQ3K6C/p1792430862330659
Review messages: Julie 1792434333.462909, 1792434509.511429; Jim 1792434355.770199, 1792434462.317949, 1792434558.358749. Provider feasibility is attributed to Jim's documentation review; original deployment parity remains unknown.

## Accepted decisions (complete record)

### Original session decisions

Source: Cabinet thread 1792430862.330659. Decisions refer to Dex's numbered list at 1792433328.635569.

### Item 1 — accepted
Trish: “1. Accepted as written” at 1792433735.322119 (11:15:35 Pacific).

Accepted repair order for scoping:
0. Restore explanations (priority_ups schema mismatch).
1. Calendar fidelity: free/busy, all-day timezone handling and freshness together.
2. Task start-window and occurrence rules.
3. Safe Apply: detect and preserve or explicitly resolve manual calendar changes; visible export failures.

Track 0 alone does not make scheduling safe. All scheduling prerequisites must pass before a live replan. This is a product/scoping decision, not implementation, deployment or live-replan authorization. Investigation hold remains.

All six product/scoping items accepted, with clarifications recorded below. The investigation hold remains in place.

### Item 2 — accepted
Trish: “2. Accepted as written” at 1792433772.382279 (11:16:12 Pacific).

Add optional hard start no earlier than and start no later than, independently settable. Keep finish by separate. Unset bounds allow flexibility; set bounds remain hard even under auto-defer. Equal start bounds mean an exact start, not an invalid window. Both fields are included in the scoped work. Avoid “start-by” as the earliest-start label.

This accepts product/scoping semantics only. Implementation, deployment and live replanning remain unauthorized under the existing hold.

### Item 3 — accepted
Trish: “3. Dex's wording represents my intent. Accepted.” at 1792433819.555739 (11:16:59 Pacific).

Each routine admin occurrence gets its intended day's earliest start and finish boundary, plus the desired afternoon preference; its 30 minutes are a single block. A latest-start bound is optional when beginning by a particular time matters independently. Flexible exceptions explicitly widen/remove the relevant bounds rather than changing all tasks' behavior. Exact hours remain to be set when configuring the template.

Product/scoping acceptance only; no task/template edits, implementation, deployment or replan performed or authorized by this acceptance.

### Item 4 — accepted with sequential-piece clarification
Trish at 1792433930.328999 (11:18:50 Pacific): “First piece only. Finish-by does indeed apply to all pieces. To maintain flexibility in start for the various pieces, they are dependent on each other. If they could run concurrently, it may be that I messed up and it should be two separate tasks”.

Start no later than governs only the first piece. Finish-by applies to completion of all pieces. Pieces of one task are sequential/dependent, not concurrent; later pieces retain scheduling flexibility after preceding pieces. Work that can run concurrently may belong in separate tasks. Retain minimum-chunk rules from the accepted proposal.

Product/scoping decision only; hold unchanged.

### Item 5 — accepted with no-stacking clarification
Trish at 1792434050.135799 (11:20:50 Pacific): “Absolutely aligns with my intent. Many times, items could safely be skipped and picked up on the next run; I am not a fan of stacking those sorts of tasks. Case by case basis, I can ask for it to be run as a one-off.”

When a hard window cannot be met, report the unplaced task and reason; do not silently schedule outside its bounds. Do not automatically stack missed routine occurrences onto later ones. Trish notes that many routines can safely skip a missed occurrence and resume with the next occurrence; she may request a one-off case by case. This does not establish blanket automatic skipping for all task types or authorize live task changes. Preserve the distinction between a missed occurrence and its next regular occurrence.

Product/scoping decision only; hold unchanged.

### Item 6 — accepted
Trish: “6. YES! accepted as is.” at 1792434086.669309 (11:21:26 Pacific).

Require current, usable calendar inputs before proposing a trustworthy schedule. Unknown free/busy remains unresolved until refreshed or explicitly resolved. Before Apply, show a reviewable comparison covering manual edits/deletions and require conflict resolution; preserve the comparison baseline through refresh. Test that removing transparent all-day events retains overlapping opaque shows. Surface partial export failures and support recovery without duplicate events.

All six product/scoping decisions are now accepted. No implementation, deployment, task/calendar changes or live replan authorized by these decisions. Exact template hours and detailed technical contracts remain to be specified within this direction.

## Follow-up decisions accepted for draft 0.3

Trish in Dex Cabinet, October 19, 2026: “Those recommendations make sense. Accept all four, including preserving the source calendar's timezone. Let's fold them into 0.3 and have Julie and Jim check the changes. Still no implementation or replanning.”

1. Early afternoon is a soft preference inside the hard day-of window.
2. Missed routines remain visible and held unless explicitly designated skippable; preserve history, no automatic stacking, recovery one-off at Trish's direction.
3. Recurrence support stays outside this repair. Existing manually created one-offs receive explicit bounds through authorized entry once supported.
4. Preserve the source calendar's timezone for all-day/date-only events when known. The missing-zone fallback remains a technical contract to specify and review; no silent owner-zone substitution.

These clarify the original six decisions; historic template wording above records the earlier discussion and does not expand recurrence scope.

## Changes to check against draft 0.2

- The four accepted follow-up decisions above and their Track 1/2 acceptance implications.
- Manual stand-in migration, missed defaults, actual-progress mapping and fingerprint coverage.
- Canonical subscription identity, sync horizon coverage, and Microsoft completion gates.
- Baseline evidence limits, timed plus all-day transparency, unresolved counts and breaks/lunch exclusion.
- Deployment/startup checks under the hold, provider reference links, and restoration of “without duplicate events” in item 6.

Julie: check workflow fidelity and migration/disposition wording. Jim: check technical consistency and acceptance changes, particularly source-zone preservation rather than the superseded owner-zone default. Report specific corrections or remaining consequential choices; do not implement or run live scheduling.
