from pathlib import Path
import hashlib
src=Path('F:/Code Repo/Cabinet/outputs/scheduler-investigation/Repair-Spec-2026-10-19.md')
b=src.read_bytes()
assert hashlib.sha256(b).hexdigest()=='71710e9b35c06462abf2e8119e7ae1eb7bc4c96cbd7a37070927c98450fa0155'
Path('outputs/scheduler-investigation/Repair-Spec-v0.2-reviewed.md').write_bytes(b)
s=b.decode('utf-8-sig')
s=s.replace('Draft 0.2 (consolidated full review edition)', 'Draft 0.3 (revised after full review)')
s=s.replace('Exact responses are in Session-Decisions-2026-10-19.md.', 'Exact responses and subsequent clarifications are included in the decision record below.')
s=s.replace('No subsequent run/write explained the apparent recurrence of clutter; Google was manually cleaned while thePlan retained its blocks.', 'Julie reports no later run or write as of her October 19 approximately 10:30 Pacific read-only check. The apparent repeats were distinct stand-ins placed early; this is not evidence of repopulation after cleanup. Google was manually cleaned while thePlan retained its blocks.')
s=s.replace('free all-day reminders became busy', 'free timed and all-day reminders became busy')
s=s.replace('Preserve these qualifications in implementation documentation.', '''Preserve these qualifications in implementation documentation. The reported eight versus stored nine admin blocks and Monday 16 versus 17 counts remain unresolved.

Breaks/lunch were not configured and Time Maps were unassigned, according to Julie. These are configuration gaps outside this repair; Tracks 0–3 alone do not restore lunch. Julie also reports Trish's standing intent that Coursera learning-time events never block. Flag a contradictory opaque copy for resolution rather than silently treating that known exception as busy; do not generalize it to unrelated events.''')
s=s.replace('Normalize date-only boundaries using a documented owning timezone, with exclusive end dates and DST-aware conversion.', "For date-only events, preserve the source calendar's timezone when known, with exclusive end dates and DST-aware conversion. Do not reinterpret a known source-local day in the owner's timezone. If the source zone is unavailable, flag unresolved timezone provenance; a fallback must be specified and reviewed before treating the interval as trustworthy.")
s=s.replace('Technical review required: owning timezone/fallback,', 'Technical review required: missing-source-zone fallback,')
s=s.replace("Owner-settings timezone is Jim's candidate for date-only interpretation; resolve different-source-zone semantics explicitly before adopting it.", "Trish accepted preserving the source calendar's known timezone; the earlier owner-settings default proposal is superseded. Preserve the source zone independently of the display/schedule zone.")
s=s.replace('Define the threshold and partial-refresh policy before implementation.', '''Define the freshness age threshold and coverage policy before implementation. Successful sync must cover the entire requested horizon and any explicitly required boundary padding; incomplete coverage fails the gate. Canonicalize aliases by verified provider/account/calendar identity so two enabled aliases of the same calendar cannot double-ingest. Do not collapse unrelated calendars merely named primary. Microsoft busy/free mapping is a Track 1 completion gate, not an optional footnote.''')
s=s.replace('Routine admin: intended-day earliest start and finish boundary, desired afternoon preference, 30 minutes in one block. Exact template hours remain to be configured.', 'Routine admin: intended-day earliest start and finish boundary, a soft early-afternoon preference inside those hard bounds, and 30 minutes in one block. Exact hours remain to be configured per occurrence.')
s=s.replace('Blanket silent skipping of all overdue tasks is not authorized.', 'Default missed routines to visible and held unless explicitly designated skippable. Preserve skipped disposition history; no blanket silent skipping. A skippable designation does not erase evidence of the miss or authorize catch-up stacking.')
s=s.replace('Specify a reviewed migration for existing generated occurrences, preserving identity/history. Template changes alone do not constrain existing admin stand-ins.', '''The eleven existing admin stand-ins are manually created one-off tasks with no template, recurrence or parent. Specify a reviewed migration preserving their identities/history. Past-due stand-ins follow the missed-work policy rather than becoming automatic catch-up backlog on the first post-repair run.

Recurrence-engine and recurrence-CLI support are outside this repair. Once fields exist and Trish authorizes live entry, Julie can set bounds on individual admin occurrences through the CLI. Until then no new stand-ins or live edits are authorized by this specification. Existing tasks need their own explicit bounds; there is no template to regenerate these stand-ins from.''')
s=s.replace('Test these states and repeated reconciliation without losing progress or duplicating work.', 'Assess existing time_worked_minutes and remaining-estimate fields for these semantics; identify any missing actual-start signal explicitly. Test these states and repeated reconciliation without losing progress or duplicating work.')
s=s.replace('- Bounds round-trip across supported authoring surfaces and appear in snapshots/explanations.', '- Bounds round-trip across supported authoring surfaces and appear in snapshots/explanations. Changes to either bound must trigger appropriate fingerprint/stale detection with schema coverage for the selected category.\n- Held versus explicitly skippable routines retain visible disposition history and never auto-stack.\n- Migration preserves one-off IDs, handles past-due stand-ins as missed, and does not require recurrence support.')
s=s.replace('Test the manually extended survivor and deleted mappings on the first post-repair reconciliation.', "Test the manually extended survivor and deleted mappings on the first post-repair reconciliation. Julie reports ID-level pre-cleanup evidence for the 12 admin blocks only; the other 24 remain unresolved unless additional evidence is verified. The sufficiency of worker-log POST records is unchecked. Even the admin evidence must be validated before seeding; evidence availability is not automatic proof of a complete baseline.")
s=s.replace('This does not settle date-only source timezone ownership.', "Date-only imports instead retain the source calendar's known timezone, as accepted by Trish.")
s=s.replace('Exact source links are pending inclusion. Microsoft equivalents remain unchecked.', '''Jim supplied [Google insert documentation](https://developers.google.com/calendar/api/v3/reference/events/insert), [versioned resources and conditional requests](https://developers.google.com/workspace/calendar/api/guides/version-resources), and [update documentation](https://developers.google.com/calendar/api/v3/reference/events/update), also saved at F:\\thePlan-imports\\investigation-2026-10-19\\google-provider-contracts-1130.md. These references are attributed to Jim's review, not independently verified by Dex. Microsoft equivalents remain unchecked and are a Track 3 completion gate; Google-only protection cannot establish safety while another supported mirror path remains destructive.''')
s=s.replace('Deployment and release decisions remain hers.', 'Deployment and release decisions remain hers. Before any authorized deployment, isolated startup/restart checks must demonstrate that API/worker startup does not enqueue held sync, calculation or export. Leave the scheduler worker unchanged under the current hold; absence of recent runs does not prove startup safety.')
s=s.replace('timezone ownership, freshness policy,', 'missing-source-zone fallback, freshness policy,')
s=s.replace('Julie and Jim reviewed condensed 0.1 in Slack, not the full local draft. This version integrates their comments; full-document review remains pending.', 'Julie and Jim both reported reading full draft 0.2 with SHA256 71710E9B35C06462ABF2E8119E7AE1EB7BC4C96CBD7A37070927C98450FA0155. Their full reviews are at 1792434985.791419/1792434985.837849 and 1792435676.832389. Neither found a blocker to writing 0.3. This revision integrates their corrections and four follow-up decisions accepted directly by Trish in Dex Cabinet on October 19. The 0.3 change review remains pending; no implementation approval is implied.')
s=s.replace('support recovery without duplicate creates.', 'support recovery without duplicate events.')
s=s.replace('# Scheduler session decisions — October 19, 2026', '### Original session decisions')
s=s.replace('## Item ', '### Item ')
s+='''
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
'''
Path('outputs/scheduler-investigation/Repair-Spec-2026-10-19.md').write_text(s,encoding='utf-8')
assert 'Draft 0.3' in s and 'Exact source links are pending' not in s
print('Prepared 0.3:',len(s),'characters')
