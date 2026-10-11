<!--
==============================================================================
  File: docs/redesign/Sonnet_Design_Playbook.md
  Description: Independent Sonnet UI design exploration brief for thePlan.
  Component: Design
  Version: 1.0 (Review Brief)
  Created: 2026-10-10
  Last Update: 2026-10-10
==============================================================================
-->

# thePlan independent UI design exploration for Sonnet

Create two distinct, well-developed design directions for thePlan, a personal planning and scheduling application. Produce concrete visual concepts that let its owner judge everyday usability and visual character. This is a bounded design exploration, with no production implementation.

## Input packet and independence

Use this brief and the original screenshot packet:

`screenshots/theplan-design-review-2026-10-10.zip`

The screenshots show existing functionality and real content. Their styling and layout are open to reconsideration. Some states are sparse; construct clearly labelled illustrative data to demonstrate busy states.

Work independently from any other design review. Do not open other designers' concepts, recommendations, PDFs, or review archives in this directory. If repository access is available, consult relevant product documentation to resolve functional questions, but avoid previous design proposals. If a behavior remains uncertain, state the uncertainty rather than inventing a product rule.

## Product and owner

Trish is an experienced technical user managing coursework, software projects, household responsibilities, theater, music, and other personal work. Her weeks can be busy and uneven, with substantial daytime work and evening commitments.

She wants scheduling capabilities beyond a basic to-do list, without a project management tool's configuration burden. Kanban is a particularly important way she visualizes work in progress. Calendar and hierarchical lists are equally real working surfaces, not secondary reporting screens.

The CLI and AI-assisted workflows reduce repetitive administration. The UI must make the resulting work understandable and editable. Do not add a chat panel or AI mascot merely because the product supports AI access.

## Preferences and creative freedom

Dark mode is required for both concepts. Choose the palette, typography, navigation, composition, and visual character freely. No specific dark palette or reference application is prescribed.

Aim for clear hierarchy, readable text, manageable density, and a distinctive but coherent appearance. Avoid generic dashboard composition. A technically sophisticated user still benefits from progressive disclosure and discoverable controls.

Labels should work primarily as filters, rather than consuming permanent navigation space. Keep epics, projects, saved views, and standalone work accessible. Do not require every task to belong to an epic to make the interface usable.

Allow room for long course titles and useful context. Do not achieve apparent simplicity by hiding essential information, shrinking metadata, removing capabilities, or showing only empty states.

## Functional meaning to preserve

| Concept | Constraint |
| --- | --- |
| Dates | Due dates, soft targets, and hard deadlines have different meanings. Preserve those distinctions and show unset values honestly. |
| Task state | Workflow, completion, and scheduling are distinct. Ready does not by itself guarantee that a task can be scheduled. |
| Unscheduled work | Manual or backlog work may deliberately remain unscheduled. Do not label every unscheduled task as needing attention. |
| External events | Provider calendar events represent busy time; the scheduler does not move them. In the supplied screenshots, “Coursera learning time” is an external busy event, not a Time Map window. |
| Time Maps | Availability preferences and exclusions are distinct from booked events. Preserve green, yellow, and red semantics with additional non-color cues. Red exclusions belong to their applicable map; do not turn them into global exclusions across unrelated maps. |
| Placements | Distinguish pinned placements, movable placements, and unapplied proposals. A movable placement does not imply unrestricted permission for an AI to act. |
| Preview and apply | Show proposed changes separately from the committed schedule. Applying a preview is consequential. Do not imply per-change apply or undo is already supported. |
| Explanations | Use only explanations supported by actual evaluation state. Preserve stale and never-evaluated states; do not invent a reassuring reason for a placement. |
| Scope | Preserve the distinction between owner-wide Work and narrower scopes such as Inbox, projects, and saved views. |

These are design constraints, not a complete scheduling specification. Ask or flag an assumption where more detail is needed.

## First assess the existing interface

Give a concise assessment of the five most consequential opportunities. Consider attention, navigation, density, task metadata, scheduling, and editing. Separate screenshot observations from behaviors that require interaction to verify.

Use that assessment to explain your choices. Avoid a long generic UX audit.

## Develop two credible directions

Make the directions differ meaningfully in composition, navigation, typography, density, or control treatment. Two color variations are insufficient. Give both a fair, usable treatment.

For each direction provide:

1. A short name and description of the intended experience.
2. A busy weekly calendar.
3. A populated Kanban board with tasks across several workflow columns.
4. A task detail or edit panel showing dates and placement information.
5. The strongest benefits, compromises, and interaction changes.

Use the same tasks, events, dates, and viewport sizes across directions. Show the main concepts at 1440 × 900 and demonstrate how the calendar and task detail adapt to 1366 × 768. These are comparison targets, not claims about the owner's exact hardware. Present the screens at legible resolution, without oversized export margins.

Use realistic stress cases: long titles, nested coursework, multiple labels, mixed workflow states, overlapping external events, pinned tasks, Time Map bands, and a schedule preview. Identify illustrative content. Do not fabricate a real conflict or a successful operation.

Show how the calendar can reclaim space from supporting panels. Make daily work possible without leaving every legend, explanation, activity feed, and attention panel permanently open.

After comparing the two directions, choose your recommendation and extend it with:

- A hierarchical coursework list that preserves long titles and clear parent-child relationships.
- A supporting sketch of one dense form: Import or the saved-view filter builder.
- A compact visual specification for typography, spacing, surfaces, primary actions, selection, focus, and semantic states.

## Interaction and accessibility

Keep primary actions discoverable without relying exclusively on hover. Distinguish selecting a task from completing it. Include visible keyboard focus, readable secondary text, and cues beyond color for state and scheduling meaning.

Target readable contrast and document the intended foreground/background pairs. Only claim measured contrast compliance if you actually measure it. Static mockups do not establish keyboard or screen-reader accessibility.

Design keyboard interactions for Windows first. Scope shortcuts so typing in fields remains safe and ordinary navigation does not unexpectedly move, complete, delete, or unschedule work. A full shortcut redesign is optional, not a required deliverable.

## Mark the scope of each proposal

Distinguish three categories in annotations or a short table:

- **Visual change:** typography, color, spacing, grouping, or existing-state presentation.
- **Interaction change:** a different way to navigate or use an existing capability.
- **New capability:** behavior or data the product would need to add.

New ideas are welcome when they solve a specific problem. Keep the concepts useful without requiring an expanded feature set. In particular, treat selective schedule apply, individual move undo, new history feeds, and new summary metrics as proposals unless existing support is verified.

## Deliverables and stopping point

Deliver a concise assessment, two comparable visual directions, a comparison and recommendation, the recommended direction's list and form extension, and up to five unresolved questions.

Supply viewable mockups plus a portable review document. Include editable source if your environment supports it. Clearly label sketches and illustrative behavior. Keep all artifacts separate from production code. Do not modify the application, commit, push, or deploy.

Stop after this package. Do not begin implementation, generate further alternatives, or initiate another refinement round without Trish's direction.

## Later comparison round

Only after Trish has reviewed this independent pass may she supply other design work. At that point, compare both sets candidly against the same criteria: busy-week readability, navigation, Kanban usefulness, long-title handling, scheduling clarity, accessibility, visual character, and implementation scope.

Identify what to retain, what to reject, and any specific idea worth borrowing. Be willing to prefer the other design or revise your own. Recommend one bounded refinement pass rather than automatically combining every attractive feature.
