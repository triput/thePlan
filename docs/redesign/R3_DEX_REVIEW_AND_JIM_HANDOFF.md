<!--
==============================================================================
  File: docs/redesign/R3_DEX_REVIEW_AND_JIM_HANDOFF.md
  Description: R3 design assessment and implementation handoff for Jim and team.
  Component: Design/Delivery
  Version: 1.0 (Implementation Handoff)
  Created: 2026-10-11
  Last Update: 2026-10-11
==============================================================================
-->

# R3 review and implementation handoff

**Dex recommendation: move forward with R3 Midnight Workbench. No further broad design round is needed.** Trish's reaction: “It's a nice, clean look - not so dense that it's confusing to the eye, but with enough information to work in each screen.” Preserve that balance during implementation.

This handoff prepares the work for Jim and the team. It is not evidence of implementation, runtime testing, or release approval. No application changes, commits, pushes, or messages to other chats were made as part of this review.

## Inputs and precedence

- [R3 review package](thePlan-R3-review.zip): review notes, named PNG screens, editable HTML/CSS artboards, and PDF. Use the PNGs at actual size. The artboards are design references, not production components.
- [Refinement brief](UI_Refinement_Brief.md): intended scope and review criteria.
- This handoff: corrections and implementation boundaries. Where an illustrative R3 behavior conflicts with the current API contract, preserve the contract and adapt the presentation. Do not silently change scheduler behavior to match a drawing.

## Design assessment

R3 resolves the main design concerns sufficiently to proceed. The calendar is quieter, typography is more readable, the board separates selection from completion, and the coursework list gives hierarchy and metadata distinct places. The collapsible support area materially improves available calendar width. The narrow navigation rail avoids the clipped labels in the earlier concepts. Task details now group dates, effort, placement, and explanations coherently, with technical identifiers moved out of primary reading space.

Retain the cool dark tokens, type scale, spacing, ordinary workflow columns, visible-but-collapsible scope navigation, and one shared support area. Preserve non-drag actions and the neutral treatment of intentionally unscheduled work. Do not add swimlanes, daily workload charts, activity history, or per-change undo in this redesign.

The review inspected supplied PNGs for the open/collapsed calendar, 1366 detail layout, 125% zoom export, rail flyout, board, both coursework list sizes, full task panel, and state sheet. It also read the R3 rationale and selected source CSS. These are static artifacts. Scrolling, focus, screen readers, dirty-form transitions, and browser zoom behavior remain implementation acceptance work. The 125% export shows only the upper part of the day; that is not itself a failure if the remaining content is scroll-accessible. Do not claim the full day fits at every zoom.

## Corrections to incorporate during implementation

1. **Keep all three Time Map tiers.** R3's visual language reduces bands to Available and Excluded. Retain distinct green/preferred, yellow/acceptable, red/excluded, and neutral/no-band meanings, including non-color cues and map-scoped precedence. Keep the quiet appearance; do not restore the earlier dense hatching. Preserve overrides, settings-timezone rendering, day/week behavior, and out-of-window clipping.

2. **Preserve capability access beyond the pictured controls.** Inventory existing calendar, task, navigation, and saved-view actions before replacing components. Retain Clear unpinned with its existing scope and confirmation, override editing, release remainder, archive/trash access, filters, pagination, sort, saved-view presentation and reorder. An overflow menu is acceptable for secondary actions. Absence from a mockup is not removal authorization.

3. **Treat overlaps and tiny blocks as acceptance cases.** R3's indented overlap cascade works for the illustrated pair, but must keep all items reachable for three or more overlaps, identical starts, containment, and narrow columns. Preserve current overlap behavior for the initial slice if the cascade cannot meet this. Defer grouping adjacent short tasks; individual task identity and actual start/end times must survive. Minimum visual height must not create false duration or hide subsequent tasks.

4. **Use actual API states and reason text.** Map existing outcome facts to presentation. Do not manufacture the mockup's precise “no 60-minute opening” explanation from a generic unplaced result. Keep partial placement and remaining minutes visible. Distinguish a saved evaluation from an unsaved edit; do not imply a “Current” badge validates draft values.

5. **Handle the complete preview lifecycle.** R3 shows ready and stale, but implementation also needs queued/running, failure, expiry, past-block rejection, conflicting replan, successful apply, retry, and empty/no-change states. Keep whole-proposal apply. After a relevant edit, invalidate/recheck; do not silently regenerate or apply. UI disabling does not replace apply-time server validation.

6. **Use Windows-aware controls and honest action scope.** Replace Mac-only shortcut glyphs with platform-appropriate labels. Scope shortcuts away from text entry, expose equivalent buttons, and preserve focus. A unified search/add/command palette and new bulk operations are not automatically included simply because they appear in the artboards; retain existing commands unless an explicit scoped implementation is agreed.

7. **Preserve defaults and authoritative counts.** Do not introduce “Done, last 7 days” as a new default just because R3 illustrates it. Keep saved-view completion semantics, actual list/board counts, pagination, roots-only behavior, and WIP definitions. The screenshot counts are illustrative, not fixtures to hard-code.

8. **Make unsaved-edit prompts context-specific.** “Save and open” fits switching tasks. Closing, returning to preview, or changing tabs needs suitable wording and a defined destination. Save failure must keep the draft and current context. Preview inspection must never mutate a committed placement merely by opening it.

## Functional questions resolved from the repository

These findings come from current source inspection and delivery documentation, not a fresh execution of the test suites. Older delivery status headings are not current release certification.

| R3 question | Existing contract and handoff guidance |
| --- | --- |
| Does apply recompute? | `apply_schedule_preview` rehydrates the stored proposal using `calculation_result_from_proposal`, validates it, and passes that result to `apply_calculation`. It collects inputs but does not recalculate replacement placements. Preserve this behavior. |
| Can a preview become stale or expire? | Yes. Apply checks owner revision/fingerprint, expiry, running replan, and past blocks. There is an idempotent receipt for an applied retry. Ready previews have a documented 15-minute TTL. These are existing features to present, not new scheduler work. |
| Is direct Update different from Preview? | Yes. Direct replan collects, calculates, and applies; preview calculates and stores without applying. Preserve both paths. R3 proposes an additional confirmation for direct Update; retain the existing interaction for the first slice unless Trish chooses the extra prompt. |
| Are explanations and stale summaries available? | Yes. Task explanations provide recorded facts and stale/never-evaluated states; CalendarView already queries a run-level stale summary. Use the API's coverage and wording. A zero stale count is not proof of every conceivable input remaining unchanged; do not overstate what is checked. |
| Are deadline/eligibility reasons available? | Yes, including deadline limits, no slot, horizon exhaustion, manual/bundle exclusions, prerequisites, and other reason families. Use the returned facts and remaining minutes, rather than treating all unplaced work as a deadline failure. |
| Is Done a workflow enum? | The stored workflow enum has Ready, In progress, and Waiting. Done is a derived board column associated with completion. Preserve completion, open-child policy, recurrence, revisions, and existing workflow endpoint behavior. |
| What are schedule styles? | `standalone`, `time_block`, `bundle`, `manual`; inheritance resolves task, project, epic, then user default. Show the effective source instead of assuming “Project default” for every task. Waiting alone must not change schedule style. |
| Should coursework go inside the external Coursera event? | Do not reinterpret that event through this redesign. Preserve current external busy handling. Changing the meaning of that calendar data is a separate planning decision. |

Source anchors:

- [Preview apply service](../../apps/api/app/services/schedule_preview_apply.py)
- [F6 preview contract and delivery notes](../delivery/F6-REPLAN-PREVIEW.md)
- [F3 explanation contracts](../delivery/F3-SCHEDULER-EXPLANATIONS.md) and [reason formatter](../../apps/api/app/scheduler/reasons.py)
- [Workflow and scheduling enums](../../apps/api/app/models/enums.py), [style inheritance](../../apps/api/app/scheduler/style.py), and [F2 delivery notes](../delivery/F2-KANBAN.md)
- [Calendar integration](../../apps/web/src/components/CalendarView.tsx)

## Suggested implementation order

### Slice 1 Foundations and work surfaces

Inventory current capabilities and data contracts. Introduce reusable theme/type/spacing tokens and navigation layout, then restyle the list and board. Preserve existing query keys, server sorting, filtering, accumulators, pagination, and mutation semantics. Finish with a working integrated list/board/nav checkpoint rather than isolated component screenshots.

### Slice 2 Shared panel and task details

Implement the support-panel state model, task detail replacement, return context, scroll restoration, dirty-edit protection, and persistent save actions. Preserve actual task fields and inherited settings. Define collapse preferences with safe defaults and responsive overrides; local presentation persistence does not require scheduler changes.

### Slice 3 Calendar and preview integration

Apply the quieter visual system to real blocks and all Time Map tiers. Integrate the existing preview APIs and reason states into the shared panel. Keep the current scheduler, locks, invalidation, expiry, and apply protections intact. Validate short blocks and overlaps before adopting the cascade layout.

### Slice 4 Integrated verification and polish

Run relevant existing tests and build checks, then exercise the browser flows below against a disposable fixture. Add focused regression tests for new state transitions, not tests that merely duplicate CSS values. Record automatic and manual results separately. Keep unresolved checks open with notes.

## Acceptance evidence for Renee and Dex

- At 1440 × 900 and 1366 × 768, expanded/collapsed navigation and support panel remain usable with real long titles. At 125% and 200% zoom, every action and all content are reachable through an intentional responsive or scrolling layout.
- Keyboard focus remains visible and sensible through flyout, calendar item, details, dirty-edit prompt, return, and collapse. Non-drag move actions work; typing cannot trigger global mutations.
- Three-way overlaps, short adjacent blocks, multiple placements for one task, and mixed external/pinned/movable/proposed blocks remain distinguishable and selectable.
- Green/yellow/red bands, overrides, settings timezone, clipping, and selected-map scope retain their behavior.
- Preview create causes no live placement changes. Apply uses the displayed valid proposal. Stale/expired/running-conflict cases fail honestly; retry cannot duplicate work. Edits invalidate relevant explanations and previews.
- Board moves, within-column ordering, Waiting notes, completion/uncompletion, recurrence, child policy, and stale revision recovery retain existing behavior. Repeated moves cannot blank accumulated pages.
- Saved views preserve filters, sort, presentation, completion membership, pagination, and sidebar ordering. Counts do not claim completeness while pages remain.
- Task draft survives failed save and cancelled navigation. Unschedule preserves the task; delete is distinct. Collapsing or switching panels does not discard a draft or apply a preview.
- No pictured placeholder becomes a hard-coded production count, reason, grouping, seven-day limit, or unsupported command.

## Jim handoff summary

Proceed with R3 as the implementation direction, incorporating this document's corrections. Start with a capability inventory and slice plan, then build reviewable increments. Preserve existing backend behavior and keep optional new capabilities deferred. Return an integrated build with test evidence, screenshots, and open manual checks for Trish and Dex. Do not represent static design review as functional sign-off or release approval.
