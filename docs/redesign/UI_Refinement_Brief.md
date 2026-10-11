<!--
==============================================================================
  File: docs/redesign/UI_Refinement_Brief.md
  Description: Dex review synthesis and bounded next-pass UI design brief.
  Component: Design
  Version: 1.0 (Review Brief)
  Created: 2026-10-10
  Last Update: 2026-10-10
==============================================================================
-->

# thePlan UI refinement brief

Produce one refined design for thePlan using Opus's Midnight Workbench as the visual foundation and Sonnet's Ledger support-panel behavior as a layout improvement. Demonstrate that it remains readable and efficient during a busy week.

This is Dex's recommended direction for the next review, not final approval of a design or authorization to implement it. Trish will judge the resulting screens before production work begins. Do not generate another set of competing concepts.

## Review materials

All paths below are relative to this brief.

- [Opus design directions](<thePlan Design Directions - Opus55.pdf>): especially Midnight Workbench, the busy calendar, board, and placement panel on pages 16 and 18–20. Night Shift's list on page 8 is a useful readability reference.
- [Opus rationale and decisions](thePlan-design-review-Opus55.zip).
- [Sonnet independent review](<UI mockups for review package - Sonnet55.pdf>): Ledger's collapsible dock, list, and task state grouping; Studio's smaller-layout examples illustrate problems to avoid. The PDF is a large review canvas, so use its concept labels rather than page numbers.
- [Original screenshots](screenshots/theplan-design-review-2026-10-10.zip): existing content and functionality, not a styling prescription.
- [Sonnet playbook](Sonnet_Design_Playbook.md): functional constraints and independent-round scope.

The models received different briefs. Sonnet benefited from clarifications prompted by the Opus review. This synthesis evaluates the proposals, not general model capability.

## Assessment behind the direction

Midnight Workbench offers the strongest overall combination of visual hierarchy, accessible project navigation, and a calm dark palette. Its task placement panel groups related information well. Its busy calendar still gives too much space to supporting information.

Ledger's strongest contribution is a shared support dock: preview, unscheduled work, and the legend occupy one area; task details replace that area rather than opening another panel. Collapsing it returns space to the calendar. Its calendar patterns and very small metadata undermine the benefit of that extra room.

Studio's persistent navigation is useful, but its calendar remains crowded. Its narrow-layout rail has overflowing labels and its toolbar wraps awkwardly. Epic swimlanes consume substantial vertical space and should not become the default board structure in this pass.

## Retain and refine

| Element | Next-pass direction |
| --- | --- |
| Visual foundation | Use Midnight Workbench's cool dark surfaces and restrained hierarchy. Keep the palette coherent across screens. |
| Navigation | Retain a visible scope tree for Work, Inbox, projects, epics, and saved views. Make it collapsible with a discoverable restore control. Labels belong primarily in filters. |
| Calendar workspace | Give the grid priority. Show navigation and support-panel collapse states without squeezing essential controls or text. |
| Support area | Use one area for Unscheduled, Preview, and supporting information. Task details replace it. Preserve enough context to return to the previous panel without losing work. |
| Task detail | Retain Workbench's placement grouping. Clearly distinguish workflow, completion, and scheduling. Place scheduling explanations near placement controls. |
| Hierarchical list | Combine readable title spacing with Ledger's aligned metadata and restrained hierarchy guides. Preserve long titles and parent-child relationships. |
| Board | Keep ordinary workflow columns as the default. Make title, selection, completion, and relevant scheduling state easy to distinguish. |

Do not combine every attractive element from the concepts. Each addition must earn the space and attention it consumes.

## Specific corrections

### Reduce calendar pattern noise

Sonnet's external-busy hatching, exclusion hatching, acceptable-time stripes, colored fills, borders, and glyphs compete with the scheduled content. Use a quieter visual treatment while retaining non-color cues.

Show a coherent distinction between external events, pinned placements, movable placements, and unapplied proposals. Make availability and exclusions legible without making the entire week look hazardous. Acceptable availability should not resemble a warning.

Keep the legend accessible on demand. Demonstrate how a selected item reveals additional detail without requiring all metadata to remain visible in every block.

### Make text comfortably readable

Do not rely on 10–11 px metadata to fit the design. Establish a readable type scale, then adapt the layout around it. Demonstrate actual-size screens and browser zoom behavior; do not make the review depend on zooming an oversized PDF canvas.

Prevent metadata from clipping vertically inside calendar blocks. Short events may use a concise title and reveal full details on focus or selection. Long task titles in boards and lists need a deliberate wrapping strategy. Completed tasks must remain readable when shown.

### Resolve navigation and panel behavior

Show expanded and collapsed navigation. A collapsed rail must not leave half-visible labels or make destinations depend on color alone. Show how projects and saved views are reached from that state.

Show the transition from preview to task details and back, including preservation of preview context and unsaved edits. Explain what happens when the user closes or switches away from an edited task. Avoid stacking another inspector beside the support dock.

### Keep product copy honest

- Replace deadline guarantees such as “scheduler must not miss” with accurate constraint language. A schedule can be infeasible; the UI must be able to explain that outcome.
- Keep “not scheduled” neutral when the task is intentionally manual or in the backlog.
- Move design annotations such as “per-change undo is not assumed to exist” out of the application mockup and into review notes.
- Put raw identifiers such as `outline_id` in secondary technical details rather than directly beneath the task title.
- Use explicit action wording where “Remove” could mean either removing a placement or deleting a task.

## Functional guardrails

Preserve existing product semantics. Resolve uncertain behavior against current documentation before turning it into an interaction requirement; flag anything still unresolved.

- Due dates, soft targets, and hard deadlines remain distinct.
- Workflow, completion, and scheduling are distinct facts. A Ready task is not necessarily eligible for placement.
- “Coursera learning time” in the supplied screenshots is an external busy event, not a Time Map window. The scheduler does not move external events.
- Time Map preferences and exclusions are scoped to the applicable map. Do not turn one map's exclusion into a global exclusion for unrelated maps.
- Pinned placements are not moved by the scheduler. Movable does not mean an AI has blanket authority to change the user's plan.
- A preview is unapplied until explicitly applied. Resolve the relationship between “Update schedule” and “Preview changes”; do not silently make them equivalent.
- Show current, stale, and never-evaluated explanation states accurately. Use illustrative reasons only when clearly identified as such in review annotations.
- Do not assume selective apply, per-move undo, activity history, live match counts, or new summary metrics already exist.
- Preserve owner-wide Work, narrower scopes, and standalone tasks. Epic membership must not be required to use the design.

## Required screens and states

Use the same representative content across screens. Label invented tasks, placements, and counts in review annotations. Do not imply that illustrative data reflects Trish's actual schedule.

1. **Busy weekly calendar at 1440 × 900.** Include overlapping external events, short and long tasks, pinned and movable placements, Time Map bands, and an unapplied preview. Show the support panel open and collapsed.
2. **Calendar at 1366 × 768.** Show collapsed navigation and task details replacing the support dock. Toolbar controls, navigation, and event content must remain usable. These are comparison viewports, not a claim about Trish's exact hardware.
3. **Populated workflow board.** Use several occupied columns, long coursework titles, mixed dates and scheduling states, and completed tasks. Show selection separately from completion and provide a discoverable non-drag move action.
4. **Task detail.** Show dates, placement, pinning, explanation, and editing controls. Include a compact state sheet for stale and never-evaluated explanations and for deliberately unscheduled work.
5. **Hierarchical coursework list.** Show long titles, nesting, aligned metadata, selection, and completion. Make deliberate choices about which metadata is always visible and what appears on demand.

A compact state sheet may supplement these screens. Do not expand the round into redesigning every form or adding new features.

## Review criteria

| Question | Evidence expected |
| --- | --- |
| Can Trish read the busy week without consulting a legend repeatedly? | Actual-size calendar; quiet availability treatment; identifiable event and placement states. |
| Does collapsing supporting UI materially help? | Comparable open/closed views with the same content; no hidden essential action. |
| Is the smaller layout resolved? | No overflowing rail labels, clipped controls, accidental toolbar wrapping, or overlapping text. |
| Are long titles and metadata usable? | Representative board and list examples; readable text without depending on tiny labels. |
| Are actions and state meanings clear? | Selection versus completion, unschedule versus delete, preview versus apply, and accurate scheduling copy. |
| Can keyboard users operate the proposed interactions? | Focus order and visible focus annotations; non-drag alternatives; shortcuts scoped away from text entry. |
| Is the scope reviewable? | A short list distinguishing visual changes, interaction changes, and proposed new capabilities. |

Check contrast for the actual foreground/background combinations, including muted and completed states. Report what was measured. Static mockups do not establish keyboard, screen-reader, or full accessibility compliance.

## Deliverables and stopping point

Deliver one refined direction with a short rationale, the required screens, a compact typography/color/spacing specification, and the interaction notes needed to evaluate panel and navigation behavior. Include readable individual screen exports and a review document; provide editable source if available.

List unresolved functional questions and any proposed new capability separately. Do not hide assumptions in polished screens.

Stop after delivering the refinement package. No production edits, commits, deployment, additional design directions, or automatic follow-on rounds. Trish's next review decides whether this direction is ready for an implementation specification.
