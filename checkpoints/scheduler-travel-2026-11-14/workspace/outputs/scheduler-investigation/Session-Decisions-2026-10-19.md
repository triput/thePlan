# Scheduler session decisions — October 19, 2026

Source: Cabinet thread 1792430862.330659. Decisions refer to Dex's numbered list at 1792433328.635569.

## Item 1 — accepted
Trish: “1. Accepted as written” at 1792433735.322119 (11:15:35 Pacific).

Accepted repair order for scoping:
0. Restore explanations (priority_ups schema mismatch).
1. Calendar fidelity: free/busy, all-day timezone handling and freshness together.
2. Task start-window and occurrence rules.
3. Safe Apply: detect and preserve or explicitly resolve manual calendar changes; visible export failures.

Track 0 alone does not make scheduling safe. All scheduling prerequisites must pass before a live replan. This is a product/scoping decision, not implementation, deployment or live-replan authorization. Investigation hold remains.

All six product/scoping items accepted, with clarifications recorded below. The investigation hold remains in place.

## Item 2 — accepted
Trish: “2. Accepted as written” at 1792433772.382279 (11:16:12 Pacific).

Add optional hard start no earlier than and start no later than, independently settable. Keep finish by separate. Unset bounds allow flexibility; set bounds remain hard even under auto-defer. Equal start bounds mean an exact start, not an invalid window. Both fields are included in the scoped work. Avoid “start-by” as the earliest-start label.

This accepts product/scoping semantics only. Implementation, deployment and live replanning remain unauthorized under the existing hold.

## Item 3 — accepted
Trish: “3. Dex's wording represents my intent. Accepted.” at 1792433819.555739 (11:16:59 Pacific).

Each routine admin occurrence gets its intended day's earliest start and finish boundary, plus the desired afternoon preference; its 30 minutes are a single block. A latest-start bound is optional when beginning by a particular time matters independently. Flexible exceptions explicitly widen/remove the relevant bounds rather than changing all tasks' behavior. Exact hours remain to be set when configuring the template.

Product/scoping acceptance only; no task/template edits, implementation, deployment or replan performed or authorized by this acceptance.

## Item 4 — accepted with sequential-piece clarification
Trish at 1792433930.328999 (11:18:50 Pacific): “First piece only. Finish-by does indeed apply to all pieces. To maintain flexibility in start for the various pieces, they are dependent on each other. If they could run concurrently, it may be that I messed up and it should be two separate tasks”.

Start no later than governs only the first piece. Finish-by applies to completion of all pieces. Pieces of one task are sequential/dependent, not concurrent; later pieces retain scheduling flexibility after preceding pieces. Work that can run concurrently may belong in separate tasks. Retain minimum-chunk rules from the accepted proposal.

Product/scoping decision only; hold unchanged.

## Item 5 — accepted with no-stacking clarification
Trish at 1792434050.135799 (11:20:50 Pacific): “Absolutely aligns with my intent. Many times, items could safely be skipped and picked up on the next run; I am not a fan of stacking those sorts of tasks. Case by case basis, I can ask for it to be run as a one-off.”

When a hard window cannot be met, report the unplaced task and reason; do not silently schedule outside its bounds. Do not automatically stack missed routine occurrences onto later ones. Trish notes that many routines can safely skip a missed occurrence and resume with the next occurrence; she may request a one-off case by case. This does not establish blanket automatic skipping for all task types or authorize live task changes. Preserve the distinction between a missed occurrence and its next regular occurrence.

Product/scoping decision only; hold unchanged.

## Item 6 — accepted
Trish: “6. YES! accepted as is.” at 1792434086.669309 (11:21:26 Pacific).

Require current, usable calendar inputs before proposing a trustworthy schedule. Unknown free/busy remains unresolved until refreshed or explicitly resolved. Before Apply, show a reviewable comparison covering manual edits/deletions and require conflict resolution; preserve the comparison baseline through refresh. Test that removing transparent all-day events retains overlapping opaque shows. Surface partial export failures and support recovery without duplicate creates.

All six product/scoping decisions are now accepted. No implementation, deployment, task/calendar changes or live replan authorized by these decisions. Exact template hours and detailed technical contracts remain to be specified within this direction.
