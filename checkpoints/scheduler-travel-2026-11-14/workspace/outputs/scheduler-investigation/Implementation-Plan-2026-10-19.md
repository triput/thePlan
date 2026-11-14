# Scheduler repair implementation plan (draft)

October 19, 2026. Dex consolidation. Planning only; no implementation, deployment, live sync, task/calendar migration, Preview Changes, Update Schedule, calculation/replanning or Apply authorized. Trish retains all release and live-operation decisions.

Sources: reviewed Repair-Spec-2026-10-19.md draft 0.3 and Draft-0.3-Review-Closure.md. Jim planning proposal: Slack 1792436824.604999. Julie workflow/migration proposal: 1792436890.802669, Cabinet thread 1792430862.330659. Proposals below are not implemented or independently verified against current UI.

## Sequence and deliverables

1. Track 0: bounded explanation-schema repair (priority_ups), documentation and isolated regressions. Preserve existing explanation semantics. Suggested first coding slice once Trish authorizes implementation. Held-miss counting is a later Track 2 extension, not extra scope for this initial repair.
2. Track 1: busy/free persistence and legacy unknowns, source-zone preservation, missing-zone fail-closed handling, complete/fresh calendar coverage, canonical identities and Microsoft mapping gate. Jim is preparing the acceptance table and concrete freshness recommendations. Close this track's technical contracts before its coding starts.
3. Track 2: hard start bounds, soft afternoon preference, actual progress semantics, stale-category/schema coverage, held/skippable misses and one-off authoring. Close progress/fingerprint choices before Track 2 coding; they need not delay unrelated Track 1 work.
4. Track 3: baseline-preserving reconciliation, explicit remote conflicts, durable operation identity and provider-safe recovery, including Microsoft concurrency/export contracts. All applicable tracks and integrated preservation checks plus Trish's explicit go precede live scheduling.

## Proposed held-miss presentation

Julie's proposal: use the existing unplaced-work list, with a distinct "Missed, held" state and original intended window. Confirm the actual UI surface during design rather than assuming its current capabilities. Add a held-miss count to the explanation summary in Track 2. Held misses remain visible across subsequent runs; they never block, delay or merge with the next occurrence. Skip/recovery requires Trish's direction. These are proposed UI details, not a claim of current behavior.

Each one-off carries a skippable setting, off by default. Only Trish or someone acting at her direction sets it alongside day-of bounds. The scheduler never infers it. Unmarked missed one-offs remain held.

## Separate migration checkpoints

Task migration follows supported Track 2 fields. Update the eleven existing admin stand-ins in place, preserving IDs, history and recorded time. Verify one-to-one IDs before/after. No delete/recreate or recurrence regeneration. Past-due tasks remain held unless Trish directs a disposition; no automatic recovery backlog.

Calendar reconciliation belongs to Track 3. Preserve manual edits and unresolved mirrors; seed baselines only from validated attributable evidence. Task migration must not write remote calendars. Neither checkpoint is authorized by passing tests or completing this plan.

Before an authorized migration: fresh read-only snapshots of task IDs/status/bounds/progress, mappings and relevant remote events; comparison with captured evidence; isolated-copy dry run producing per-task/per-event diffs; explicit unresolved-count labels if 8-vs-9 or 16-vs-17 remain open; Trish's disposition choices where required; isolated startup/restart proof that held sync/calculation/export is not triggered. Evidence coverage remains limited to what has actually been captured and validated, not all 36 original blocks by assumption.

## Pending planning inputs

- Jim's Track 1 acceptance table, provider evidence and recommended freshness coverage/padding/age.
- Explicit progress signal and fingerprint category before Track 2 implementation.
- UI confirmation for held-miss presentation.
- Microsoft and export recovery contracts before the applicable tracks are implemented/completed.
- Consolidation of the review-closure corrections into a subsequent spec revision, preserving reviewed-version provenance.

No new product choice identified by Julie or Jim at this stage. Consequential tradeoffs return to Trish. No dates or staffing commitments assigned by this draft.

## Additional migration dependencies and decisions (Julie, 12:09)

Source: Slack 1792436940.293869 and 1792436940.391469. These extend her earlier pass; do not treat earlier "no new choice" as closing the later cleanup-disposition question.

- Before any cache-changing Track 1 deployment/migration or authorized refresh, preserve fresh hashed task, mapping, subscription, cache and remote-range evidence. This preserves current comparison evidence, not proof of the original export baseline. Validate the attributable historical evidence separately.
- Track 1 isolated tests can pass without live sync. Resolving production legacy rows requires a separately authorized refresh, even when it writes only local cache. Do not equate fixture completion with production migration completion.
- Bounds/held-default migration for the eleven one-offs is a prerequisite to any eventually authorized real-data calculation, including proposal-only work.
- Plan a tested backup/restore on an isolated copy and before/after diffs. Verify all task IDs, counts, created dates, recorded time, notes and history; only intended fields change. No unintended block creation/deletion or remote writes. Julie offers the read-only before/after evidence capture when authorized.
- Proposed presentation: a named "Missed and unplaced" list in schedule review, plus explanation and CLI/API access. Include intended day/window, missed bound and reason. Skip/recovery actions remain at Trish's direction. Sketch and review before final UI choice. Do not confuse a held/skippable policy with actual missed/held/skipped/completed disposition; exact schema remains design work. Record who explicitly designates skippable and when.
- Track 3 must restrict mutations to verified thePlan-owned exports. Ordinary appointments, shows and reminders are never mutation candidates. Stored mappings are evidence to validate, not sufficient authority if remote ownership/content conflicts; retain stable-operation recovery for uncertain creates without a returned mapping.

Decisions to present at the appropriate checkpoint:
1. Does Trish intend the manually cleaned Google calendar as the retained state for the identified deleted exports? Julie recommends explicitly retiring validated remote-absent mappings instead of recreating those events. This is a proposal, not an accepted global default. Unknown baseline, failed-delete tombstones and unrelated mappings remain unresolved; do not infer all 36 outcomes from the 12 admin evidence set.
2. Authorize any production refresh/migration only once its concrete scope, evidence preservation and safeguards are reviewable.
3. Review the held-miss UI proposal before finalizing its location/actions.

No current live operation is authorized by these planning notes.

## Track 1 table received and reviewed by Dex

Jim's Track-1-Acceptance-Table.md, announced at Slack 1792436972.303589, contains 14 proposed gates with isolated fixtures and explicit unverified Microsoft contracts. Dex read the complete table. It is a planning companion, not test results.

Freshness candidates: covering sync with padding max(inter_block_buffer, 24h), age no more than 15 minutes. These remain engineering recommendations, not validated sufficiency or live configuration. Specify elapsed-time padding separately from source-local calendar-day conversion; DST days need not be 24 hours. Provider retrieval must include overlapping events crossing query boundaries and complete pagination; padding cannot substitute for overlap correctness.

Corrections requested before treating the table as ready: T1-1 must retain the opaque timed show within the removed transparent all-day span, not on an adjacent day; T1-4 must use verified calendar/event/series identity and explicit policy rather than title matching; unresolved timezone/free-busy provenance must prevent marking the affected proposal trustworthy, since its extent may itself be unknown. A guessed local interval cannot safely bound that uncertainty. T1-4 provisional busy handling must not silently resolve the policy conflict or mark the proposal ready.

Microsoft mapping and sync completeness remain unverified. No implementation or live refresh authorized.

### T1-4 review correction (Julie, 1792437064.323439)

Julie's more precise recommendation supersedes the provisional-busy phrasing above: an opaque copy of a verified known non-blocking exception stays unresolved, trusted as neither busy nor free, with a visible diagnostic and proposal not ready until resolved under the explicit policy. Resolution under Trish's established non-blocking policy makes it free. This avoids representing the unresolved contradiction as an accepted busy constraint. Scope by verified identity and policy, never title alone.

Julie also reports corrupted comparison symbols in her reading of table hash prefix 81DB73E6. Dex's earlier read rendered the symbols correctly; cross-reader encoding is therefore not yet diagnosed. Request UTF-8 plus plain-word comparisons in the shared table for unambiguous access.

## Trish decision: deliberate remote deletions

October 19, 2026, direct instruction in Dex Cabinet: "Yes, the blocks I deliberately deleted should stay deleted. Let's retire those links once verified, then show me the consolidated plan and what you'd recommend as our first coding slice. No replanning yet. :D"

Accepted: preserve deliberately deleted blocks as deleted and retire their links once verified. Verification must identify the specific thePlan-owned export and establish intentional deletion; a missing remote event alone is insufficient. Preserve an audit trail. Do not apply this decision to failed-delete tombstones, uncertain provider outcomes or unverified mappings. No links have been retired by Dex. This does not authorize replanning or starting the recommended coding slice.

Track 1 table corrections closed: Dex inspected the updated relevant gates at SHA256 832FE7022CF5B90CA4C49277621581ED572A8D2304EAF2E15A3CD5377C5C2200; Julie confirmed the same version and closed her corrections at Slack 1792437243.487039. This is document review, not executed acceptance tests. Microsoft contracts and engineering candidates remain open as stated.

## Backlog reconciliation gate before coding recommendation

Trish raised unfinished planned thePlan work at Slack 1792437698.912189. Dex acknowledged at 1792437727.612029 that this plan has not been reconciled against that work. Jim independently confirmed the same gap at 1792437787.215989 and requested Julie's open-item inventory, offering technical conflict review.

Track 0 remains a bounded technical candidate, not a backlog-validated first-slice recommendation. Before coding authorization, compare existing unfinished tasks/specs with Tracks 0-3 for overlap, dependencies and conflicts; identify whether the repair fits existing slices rather than creating duplicate work. Julie supplies captured work/priorities, Jim reviews technical fit, Dex consolidates. No changes to priority, schedule or records are implied; consequential sequencing choices return to Trish. Implementation and replanning remain on hold.

## Backlog inventory limitations and sequencing choices

Julie reports read-only review of 157 tasks (110 open) and TP@Gmail at Slack 1792437874.417069. Dex has not independently verified these records. The open task list does not describe the remaining product slices, so it is not a complete product-backlog inventory; Jim's comparison must use the existing product specs as well.

Reported captured work: watched threads/Jim wake 22a6c95c P1, explicitly next after scheduler fix; chatter c6e7cc69 P4 unscheduled fallback; investigation 5b4607f6 P2 with non-expiring hold; agent accounts/CLI 11ef5eab, observation format ac9c1aae, Assist ZenBook b715292d and commercialization fad33bb4 P3/P4 unscheduled. No further Cabinet coding session booked. Julie reports agent-access scoping Oct 20 10:00-10:45 Pacific with an earlier proposed development window before Oct 23, potentially conflicting with the subsequently chosen watched-thread priority. Do not reschedule or infer which wins.

Bring Trish the meaning of "after the scheduler fix" with the technical fit: explanation repair alone does not restore scheduling safety. Recommend evaluating a usable/safe-scheduling milestone rather than treating Track 0 as that milestone; no new priority decision made here.

Check remaining product specs for Time Maps, preferred_time_window_id and recurrence/Routines overlap before committing Track 2 schema/migration. Julie reports Time Maps configuration is intended after the update, including meals, walks, drive time, focus/light periods and wiggle room; these remain outside this repair, not newly adopted requirements for it. Check future routine migration to avoid migrating the eleven stand-ins twice. Julie reports manual scheduling currently protects near-term deadlines. Existing product plans, source references and technical overlap remain outstanding.

## Existing product-source pointers (Julie 1792437978.107039)

Julie identifies F:\Code Repo\ThePlan\docs\DEFECTS.md (open DEF-031 through 041 with differing approved contracts; DEF-043 triage; DEF-045 household check; retested DEF-042/044/046/047), NEXT-FEATURES-SPEC.md section 2 closeout (prerequisite candidate exclusion, parent-link flush, deferred failed-mirror deletion/durable retry), 07-wave-roadmap.md (Wave 2c), and delivery\0.7-S2-CUTOVER.md. Completeness/current implementation status not established by this inventory.

Dex read the cutover packet header: current documented Prefer-path retest PASS at 6b3f581; DEF-045 household re-verification and full DEF-040 remain open; earlier recurrence retest/deployment history exists. This is document evidence, not current runtime verification. Jim must separate planned/implemented/deployed/household-verified states. Recurrence outside the repair does NOT mean recurrence support absent from the product. Existing stand-ins have no recurrence links; review existing recurrence and Prefer/day-scoped contracts before choosing new fields or migration to avoid duplicate mechanisms.

## Jim backlog-fit review received

Dex read Backlog-Fit-2026-10-19.md (Jim, Slack 1792437985.113249). Recommendation: keep Tracks 0-3 under existing investigation/repair task 5b4607f6; no duplicate epic. Track 0 remains the bounded schema/docs/tests candidate. Coordinate Track 2 with existing Prefer/availability machinery before coding. Watched-thread work should follow a Trish-defined safe-scheduling milestone, not merely explanation repair. Agent-access work has a possible attention conflict, not a demonstrated code dependency.

Limit: Jim's note principally cites the open task dump and DEF-040/045. It has not yet explicitly reconciled the remaining ordered S2 cutover slices or NEXT-FEATURES closeout items identified by Julie. Treat the fit as partial, especially for Tracks 2-3; existing recurrence implementation/deployment history must be distinguished from future work. Do not silently accept a competing temporary soft-window field. Requested a narrow addendum covering those named sources and slice statuses before presenting the broad plan as reconciled. No implementation authorized.

## Standing planning-process lesson

Trish approved on October 19: check existing work before recommending a new slice. Recorded in outputs/cabinet-listener/Cabinet-Agreement.md. Review tasks plus product specs/roadmap and unfinished delivery/verification; identify overlap/dependencies, distinguish implementation from deployment/verification, and present the fit before recommending the next slice. Current recommendation remains provisional pending Jim's final source comparison. No coding or replanning.

## Final named-source comparison received (Jim Addendum A)

Dex read Addendum A of Backlog-Fit-2026-10-19.md, announced at 1792438205.410649. This closes the requested comparison against named CUTOVER section 3 and NEXT-FEATURES section 2 sources; statuses remain document-attributed, not freshly tested runtime facts. No comprehensive unpublished-roadmap claim.

Consolidated fit: Track 0 is a narrow schema repair inside 5b4607f6, coordinated with remaining S2-V5 fingerprint/stale work, not a parallel redesign. Track 1 adds calendar fidelity/freshness/provider gates. Track 2 must reuse existing Prefer and coordinate new bounds/fingerprints with V5; DEF-045 household re-verification remains open. Track 3 explicitly owns the previously deferred failed remote-delete/durable-retry limitation for owned exports. Remaining V6 SS-30 evidence and V7 context/travel stay visible in the existing roadmap, not silently absorbed or cancelled. Prerequisite-enforcement and parent-link-flush closeouts require verification; no closure claimed. CLI recurrence exists in code with retest/deployment history but household verification remains open; do not build a duplicate recurrence system.

Recommendation for Trish: keep the repair under the existing task; nominate Track 0 first once authorized; settle Track 2/V5/Prefer design dependencies before that coding; retain original V6/V7 scope for later sequencing. Define watched-thread work's "after scheduler fix" milestone as safe usable scheduling with the applicable repair gates met and explicit hold lift, if Trish agrees. No automatic postponement of tomorrow's agent-access scoping; raise any execution-time conflict to her.

Decisions presented: accept integrated repair fit/reuse of Prefer; choose safe-scheduling milestone for watched-thread priority; choose whether/when to authorize the bounded Track 0 slice. No code, deployment, calendar mutation or replanning performed.

## Trish approval: integrated fit, milestone and Track 0

October 19, 2026, direct instruction in Dex Cabinet: "That fit makes sense. Let's use safe, usable scheduling as the milestone, and go ahead with the bounded Track 0 slice. No deployment or replanning yet. Let Julie and Jim know."

The integrated fit is accepted. Watched-thread/Jim wake work follows safe, usable scheduling, not Track 0 completion alone. Applicable calendar/task/Apply safeguards and Trish's explicit live-path authorization remain necessary.

Track 0 coding is authorized under existing task 5b4607f6: priority_ups response-schema correction, relevant documentation and isolated regression tests; preserve explanation semantics. Coordinate with V5 without redesigning fingerprints. Held-miss counts remain Track 2. No production data mutations, deployment, rebuild, live sync, Preview Changes, Update Schedule, calculation/replanning or Apply authorized. Tracks 1-3 implementation remains outside this bounded go-ahead. Jim executes the bounded slice; Dex reviews the diff and validation evidence before reporting completion.

## Project coordination roles assigned by Trish

October 19, 2026, Slack 1792438668.992559 in thread 1792437787.215989: Trish places Dex in charge of monitoring this project and Jim at the helm driving work under Dex's direction; Trish remains available for human decisions.

Dex tracks approved scope, dependencies, review evidence, blockers and readiness; coordinates Jim's next steps within existing authorization and brings consequential choices to Trish. Jim drives delivery and returns exact revisions and test evidence. Use existing Cabinet handoffs for monitoring; no additional polling schedule created. Role assignment does not expand implementation scope: only bounded Track 0 currently approved. Deployment, live changes and replanning remain held; subsequent tracks require approval. Completion claims require integrated review, not only a contributor's report.

## Track 0 integrated review complete

Dex reviewed code commit 9a8a2a9 and prose-only follow-up dcebf61 on October 19. Independently ran tests/test_track0_priority_ups_schema.py and tests/test_input_fingerprint.py using pytest --noconftest -p no:cacheprovider: 20 passed. Shared database fixtures disabled; no live scheduling invoked. Web tsc -p tsconfig.app.json --noEmit --incremental false passed. Reviewed all eight code-revision files and all three follow-up files. Remaining snapshot-version prose corrected. No re-run needed for prose-only follow-up. Composition is another already-emitted category missing from the same response contract; web unions/labels aligned without algorithm changes.

Bounded code review complete, not deployed or live-verified. No claim of clean working-tree status (git status returned a work-tree error); reviewed commit diffs were readable. All deployment/live scheduling holds remain. Tracks 1-3 await authorization; project not complete.

## Track 1 contract-closure direction

Trish directly authorized on October 19: close remaining Track 1 contracts for review of the next coding slice; keep deployment and replanning held. Dex directed Jim to produce Track-1-Contracts.md with official provider evidence, explicit provider mapping/policy distinctions, complete-sync freshness semantics and thresholds, unknown/conflict fail-closed behavior, migration/baseline preservation, and a bounded coding proposal. Julie reviews workflow fidelity. This authorizes design/research, not Track 1 implementation or live provider/data operations. Track 0 remains reviewed and undeployed. Exact outbound direction is saved locally as track1-contract-direction.txt.
