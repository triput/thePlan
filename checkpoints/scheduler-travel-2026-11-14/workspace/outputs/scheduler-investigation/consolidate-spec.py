from pathlib import Path
p=Path('outputs/scheduler-investigation/Repair-Spec-2026-10-19.md')
s=p.read_text(encoding='utf-8-sig').split('## Review additions: Julie')[0]
s=s.replace('Draft 0.1,','Draft 0.2 (consolidated full review edition),')
s=s.replace('## Track 2: occurrence eligibility and start windows', '''### Calendar migration and synchronization contract

Freshness means successful complete event synchronization for each relevant enabled subscription, checked before cache-only collect. Account updated_at or token refresh is not evidence of event freshness. Failed/dead subscriptions must surface actionable diagnostics for Trish to fix or disable; never ignore them silently. Define the threshold and partial-refresh policy before implementation.

Populate unknown legacy free/busy even for unchanged events. Jim reports no transparency or backfill path in current Google upsert. An existing hash-based update skip was not established; unchanged-hash coverage is a migration safeguard. Preserve event identities, provider dates and timezone provenance. Owner-settings timezone is Jim's candidate for date-only interpretation; resolve different-source-zone semantics explicitly before adopting it.

Additional acceptance: unchanged legacy events populate correctly; token refresh without event sync fails freshness; one failed subscription is visible; refresh preserves the export comparison baseline. No live sync is authorized.

## Track 2: occurrence eligibility and start windows''')
s=s.replace('## Track 3: safe Apply', '''### Existing occurrences and actual progress

Specify a reviewed migration for existing generated occurrences, preserving identity/history. Template changes alone do not constrain existing admin stand-ins. Do not silently regenerate, duplicate, or let legacy day-of instances run unbounded. Backfill is a proposed migration approach, not authorization for live edits.

Recorded actual progress, not elapsed scheduled time or placement alone, determines whether work has begun. Planned slices and remaining estimates are bookkeeping, not proof of completion. Specify partially completed, pinned and horizon-straddling behavior, including whether the first-piece latest-start has already been satisfied. Test these states and repeated reconciliation without losing progress or duplicating work.

## Track 3: safe Apply''')
s=s.replace('## Verification and release boundary', '''### Legacy baseline and resolution matrix

Existing mirrors without a trustworthy last-exported baseline remain unresolved until reviewed or seeded from attributable captured evidence. Do not copy today's remote state into an alleged original baseline and erase evidence of manual changes. Test the manually extended survivor and deleted mappings on the first post-repair reconciliation.

| State | Required treatment before destructive reconciliation |
| --- | --- |
| User-deleted, still mapped | Preserve evidence; explicit resolution before recreating or retiring the mapping. |
| Failed-delete tombstone | Preserve failed-operation identity/outcome; reconcile under the reviewed recovery policy, not as a new user deletion. |
| Hand-edited survivor | Compare against a trustworthy baseline; preserve edits pending resolution. |

Jim reports that current delete treats 404/410 as success and removes mappings; pending_deletion marks failed deletion. Detection must therefore be non-destructive and preserve evidence before cleanup. Capture last-exported values and provider revision metadata durably; a pre-refresh snapshot of current cache alone is not necessarily the original export baseline.

### Export and concurrency contracts

New timed exports use the schedule's intended named local timezone consistently with their instants. Compare equivalent timed instants independently of label-only differences; preserve recurrence/date-only zone meaning. This does not settle date-only source timezone ownership.

Use stable operation identity across retries and local block regeneration. Current Google create supplies no client ID and receives an ID only on success, according to Jim's code review. An uncertain create therefore needs new reconciliation support; do not assume the current implementation can look up an unknown ID. A conflict requires read-and-match against expected ownership/content, not assumed success.

Jim reports Google documentation supports client-supplied event IDs and conditional update/delete using etags; these are provider-feasible candidates, not implemented or tested contracts. Exact source links are pending inclusion. Microsoft equivalents remain unchecked. Specify provider formats, collision behavior, uncertain outcomes and partial export recovery before implementation. No cross-system atomic transaction is assumed.

Additional acceptance: preserve remote-deletion evidence on 404/410; equivalent zone representation versus real duration edit; conditional-write conflict; uncertain create with matching/mismatching event; retry after local ID regeneration; partial success with visible per-operation outcomes and duplicate-free recovery.

## Verification and release boundary''')
s=s.replace('Review order: Track 0, Track 1, Track 2, Track 3.', 'The hold includes real-data proposal-only calculations, Preview Changes, Update Schedule, live replanning and Apply. Passing Tracks 0–2 does not lift it. Only Trish may authorize lifting the hold.\n\nReview order: Track 0, Track 1, Track 2, Track 3.')
s+='''\n## Review provenance and status

Julie and Jim reviewed condensed 0.1 in Slack, not the full local draft. This version integrates their comments; full-document review remains pending. Julie reported the six decisions captured in task 5b4607f6 with exact replies and before/after snapshots, not independently verified by Dex.

Source thread: https://app.slack.com/archives/C0C6ZFQ3K6C/p1792430862330659
Review messages: Julie 1792434333.462909, 1792434509.511429; Jim 1792434355.770199, 1792434462.317949, 1792434558.358749. Provider feasibility is attributed to Jim's documentation review; original deployment parity remains unknown.

## Accepted decisions (complete record)

'''+Path('outputs/scheduler-investigation/Session-Decisions-2026-10-19.md').read_text(encoding='utf-8-sig')
p.write_text(s,encoding='utf-8')
print('Consolidated full draft:',len(s),'characters')
