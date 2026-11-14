# thePlan scheduler investigation: October 19, 2026

Session: 10:30 a.m.–12:30 p.m. America/Los_Angeles.
Existing investigation task: `5b4607f6-2a73-4278-a758-0757bff48b53`.
Prepared by Dex from five Slack evidence threads, reread October 19. This packet verifies what was reported in Slack, not the current production state. No live system inspection or mutation was performed to prepare it.

## Decision and boundaries

Trish selected investigation for this session. No preview, Update Schedule, replan, calendar cleanup, worker stop, deployment or code fix is authorized by this preparation. Preserve the hand-cleaned Google Calendar, appointments and breaks. The no-replan hold remains until the behavior is understood and Trish decides the next step.

## Start here: the working explanation changed

Trish saw eight apparent repeated email/admin blocks and explicitly pressed NEITHER Update Schedule NOR Preview Changes. Julie's subsequent October 16 read-only investigation found no new run or write. Her previous cleanup had changed Google Calendar only; thePlan still retained the original schedule. A fresh automatic trigger was not identified, and nothing was paused. Do not present containment as completed or an automatic rerun as established.

Julie reported that thePlan held nine distinct admin instances due October 16–29, all placed Friday October 16, and still mapped them to Google events she had deleted. This focuses the investigation on original placement logic and reconciliation of external edits. The explanation that Trish was looking at the unchanged internal agenda remains an inference, not a proven reconstruction.

## Evidence timeline

| When (Pacific) | Source and reported evidence | Limits |
|---|---|---|
| Oct 15, 6:06 p.m. | Original schedule push; later identified by Julie as run `6fab234c`. | Short run ID only; obtain full ID and snapshots at session. |
| Oct 15, 6:53 p.m. | Julie: Friday had 16 fragmented blocks, nine 30-minute admin blocks and four 15-minute job checks, 5-minute spacing, fixed-review overlaps, no lunch/rest. She manually thinned Google events. | Initial cleanup account differs from later remaining-event count; use event IDs/history to reconcile. |
| Oct 15, 7:00 p.m. | Julie: Monday had 17 blocks, six 15-minute job checks, two weekly reviews, two money checks; overlaps with 10:30–12:30 Cabinet and 2 p.m. Microsoft call; no lunch. Reduced to nine events. | Historical calendar report, not today's verified appointments. |
| Oct 15, 7:03 p.m. | Julie created investigation task, P2/manual/unscheduled/no due date, including evidence and hold. | Current task contents not independently fetched. |
| Oct 16, 9:55 a.m. | Dex relayed Trish's decision: Monday session is scheduler investigation, hold retained. | Thread contains decision relay, no Julie confirmation reply. Trish later said she had seen the schedule. |
| Oct 16, 10:05 a.m. | Trish's report relayed: eight admin copies, neither UI button touched. Initially requested narrow containment. | Does not prove a new run. |
| Oct 16, 10:09–10:10 a.m. | Julie: Google had one admin event Friday 9:10–10:10 and one Monday 8:50–9:20; all scheduler-created events from original push. No queued/running runs; newest preview Oct 11. Worker silent since 6:06:24 p.m.; one web replan request in ~20h; no blocks updated since 6:06:01 p.m. | Julie's historical read-only findings; snapshots reportedly on supernova, exact paths not supplied. |
| Oct 16, 10:10 a.m. | Julie: internal Friday retained 16 blocks including nine admin instances due Oct 16–29, stale Google mappings, stale-summary endpoint returned 500. Nothing paused, no further cleanup. | Root causes unverified. Dex instructed no further cleanup/worker stop. Trish subsequently chose to leave Google alone. |

## Questions to answer, in order

1. **Establish the current baseline without invoking scheduling.** Retrieve the existing task and Julie's saved snapshots; locate the full original run record, inputs, generated blocks, export mappings and relevant logs. Compare historical and current state explicitly.
2. **Why were future instances pulled into Friday?** Follow instance generation and candidate selection through placement. Inspect actual recurrence period, due date, earliest eligible date, duration and split settings. Determine whether multiple legitimate instances were scheduled too early, duplicated, fragmented, or a combination. Do not assume every repeated title is a duplicate.
3. **Why did fixed commitments overlap?** Inspect the run's imported busy intervals, calendar selection, fixed/pinned rules, timezone conversion and conflict checks. Compare the exact intervals used against source events.
4. **Were lunch/rest constraints represented?** Separate missing configuration from a constraint the scheduler ignored. Determine intended task duration/splitting before prescribing a rule.
5. **How should external cleanup reconcile?** Trace stale event mappings and what preview/replan/export would do after an event is deleted or edited in Google. Inspect code or an isolated fixture; do not invoke production preview to find out.
6. **What failed in stale-summary?** Obtain the original 500 response/trace and correlate with run data and deleted mappings. Treat linkage as a hypothesis until evidenced.
7. **Explain the timezone representation.** UTC labels paired with -07:00 offsets are evidence to inspect, not proof of a bug. Identify parser/normalization behavior and actual instants before attributing causation.

## Suggested two-hour session shape

- 10:30–10:45: confirm boundaries and read-only baseline; obtain snapshots and exact records.
- 10:45–11:20: trace recurrence-instance eligibility and placement from original inputs.
- 11:20–11:45: inspect conflicts, breaks, fragmentation and timezone handling.
- 11:45–12:10: inspect Google reconciliation, stale mappings and stale-summary failure.
- 12:10–12:30: summarize verified causes versus remaining hypotheses, propose smallest fix and isolated acceptance checks for Trish's decision.

This is a proposed agenda, not a calendar change. Narrow the investigation if the evidence warrants it.

## Evidence and acceptance outputs to bring back

- A traceable symptom → input → code/data path → observed result for each confirmed cause.
- A reconciliation of the eight reported versus nine stored admin blocks, and differing cleanup counts, using IDs rather than titles alone.
- Proposed isolated checks for recurrence-period eligibility, fixed-event non-overlap, configured break protection, appropriate splitting, timezone-equivalent inputs, and external deletion/edit handling.
- A safe plan for preserving manual edits before any future live run. Do not claim preview is harmless without establishing its side effects.
- An explicit list of unresolved questions and a separate approval decision for fixes/deployment/replanning. Finding a cause does not lift the hold.

## Source threads

- [Friday original report](https://app.slack.com/archives/C0C6ZFQ3K6C/p1792115628984589)
- [Monday original report](https://app.slack.com/archives/C0C6ZFQ3K6C/p1792116026007099)
- [Capture request and Julie's task confirmation](https://app.slack.com/archives/C0C6ZFQ3K6C/p1792116104050169)
- [Monday scope decision](https://app.slack.com/archives/C0C6ZFQ3K6C/p1792169720336429)
- [Containment investigation and revised explanation](https://app.slack.com/archives/C0C6ZFQ3K6C/p1792170354598549)
- [Julie's detailed read-only findings](https://app.slack.com/archives/C0C6ZFQ3K6C/p1792170623045879)

## Missing evidence to retrieve during the session

Exact snapshot paths on supernova; full run ID and input/output payloads; actual task/instance/event IDs; relevant worker/API logs; stale-summary trace; current code revision and deployed image versions. Prior rebuild claims are not proof of current parity. No need to interrupt Julie's morning routine to prepare this packet.

## Morning brief addendum, October 19 at 08:18 PDT

Julie confirms the 10:30–12:30 investigation session (session task `3288ca3a`), with Jim on call. Acceptance checks are to be settled at the start; the checks proposed above are not yet approved.

Additional specifics from Julie: stale mappings are in `external_calendar_events`; the stale-summary 500 concerns `priority_ups`. She reports fresh observation that today's thePlan-created TP@Gmail events carry `scheduledTimeZone: UTC` with -07:00 offsets. This is her report, not an independent fetch or proof of new writes or timezone causation.

Nothing has been paused. Stopping `compose-scheduler-1` remains Trish's decision. Investigation only: no fixes, deployment or live scheduler run.

Other coordination: design-refresh review is 15:45–16:00 today (`356d5039`). Watched Slack threads/Jim mention-driven wake is next after scheduler work (`22a6c95c`, P1), not authorized to start before it is done.

Source: https://app.slack.com/archives/C0C6ZFQ3K6C/p1792423138751709

## In-session product intent, 10:35 Pacific
Trish states routine admin should typically be completed day-of, with exceptions where the exact day is not required. She proposes considering a start date/time option. Source: https://app.slack.com/archives/C0C6ZFQ3K6C/p1792431351783049 . Day-of is stated typical intent; earliest-start/window design remains a proposal, not implementation approval. Dex requested read-only assessment of existing hard earliest-start support versus soft targets, across model/API/UI/CLI, and recurrence occurrence windows. No-replan hold unchanged.

## Separate afternoon coordination, reported by Julie at 10:48
Julie reports Trish moved the five-minute Slack files:read discussion to October 19, 13:30–13:35 Pacific on TP@Gmail, replacing an already-completed money check. Participants: Trish, Julie, Dex; discussion via Slack. This is meeting context only, not authorization to add scope or reinstall. Source: https://app.slack.com/archives/C0C6ZFQ3K6C/p1792432099914119 . Calendar not independently verified by Dex. Scheduler session remains unchanged.
